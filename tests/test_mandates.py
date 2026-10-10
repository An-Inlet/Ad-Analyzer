"""Offline mandate acceptance; no provider client is instantiated."""

import hashlib
import json
from datetime import timedelta

import pytest
from app.ads.models import AdvertisingAccount
from app.goals import service as goals
from app.goals.schemas import ConfirmInput
from app.mandates import service as s
from app.mandates.models import Mandate, MandateAction, MandateRevision
from app.mandates.schemas import (
    AccountScope,
    ActionDraft,
    ClaimInput,
    MandateDefinition,
    ReconcileInput,
    SyntheticEvidence,
)
from app.settings import Settings
from app.workspaces.models import WorkspaceIntegration
from fastapi import HTTPException
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from tests.test_commerce_measurement import NOW
from tests.test_customer_goals import seed as seed_goal
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_shopify_sales import configuration as configuration


def seed(
    db: Session,
    config: Settings,
    slug: str = "alpha",
    *,
    days: int = 1,
    goal_budget_micros: int = 50_000_000,
    approve: bool = True,
) -> Mandate:
    g = seed_goal(db, config, slug, goal_budget_micros=goal_budget_micros)
    p = goals.preview(db, g, NOW)
    goals.confirm(
        db,
        g,
        ConfirmInput(expected_revision=1, preview_id=p.id, idempotency_key="goal-confirm"),
        NOW,
        actor_id="owner",
    )
    integration = WorkspaceIntegration(
        workspace_id=g.workspace_id,
        integration_key="fixture-ads",
        provider="google_ads",
        display_name="Offline",
        status="active",
        configuration={},
    )
    db.add(integration)
    db.flush()
    account = db.scalar(
        select(AdvertisingAccount).where(AdvertisingAccount.workspace_id == g.workspace_id)
    )
    assert account is not None
    account.connection_id = integration.id
    db.flush()
    d = MandateDefinition(
        goal_id=g.id,
        goal_revision=1,
        currency="USD",
        time_zone="UTC",
        starts_at=NOW - timedelta(hours=1),
        ends_at=NOW + timedelta(days=days),
        accounts=[
            AccountScope(account_id=account.id, connection_id=integration.id, platform="google_ads")
        ],
        total_cap_micros=100,
        per_action_cap_micros=80,
        positive_change_cap_micros=50,
        action_limit=10,
        cooldown_seconds=0,
        freshness_seconds=300,
        allowed_actions=["budget_change", "pause", "resume", "new_campaign", "creative"],
    )
    m = s.create(db, g.workspace_id, d, "owner", NOW)
    db.flush()
    if approve:
        s.approve(db, m, 1, "owner", NOW)
    db.commit()
    return m


def draft(
    db: Session, m: Mandate, resource: str = "one", kind: str = "budget_change", exposure: int = 60
) -> MandateAction:
    payload = {"resource": resource, "kind": kind, "new_budget": 50}
    d = ActionDraft(
        account=s.policy(db, m).accounts[0],
        kind=kind,
        resource_key=resource,
        payload=payload,
        payload_digest=hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
        expected_state_digest="a" * 64,
        exposure_micros=exposure,
        positive_change_micros=20,
        mandate_revision=m.revision,
    )
    a = s.draft(db, m, d, "owner", NOW)
    db.commit()
    return a


def evidence(db: Session, m: Mandate, total: int = 10, bound: int = 60) -> SyntheticEvidence:
    return SyntheticEvidence(
        state_digest="a" * 64,
        observed_at=NOW,
        bound_micros=bound,
        entitlement_active=True,
        period_consumed_micros=total,
        covered_account_ids=[x.account_id for x in s.policy(db, m).accounts],
    )


@pytest.mark.retained_execution
@pytest.mark.usefixtures("retained_execution_engine")
def test_durable_claim_unknown_and_reconciled_budget(
    customer_engine: Engine, configuration: Settings
) -> None:
    with Session(customer_engine) as db:
        m = seed(db, configuration)
        a = draft(db, m)
        e = evidence(db, m)
        b = ClaimInput(request_key="claim-one", evidence=e)
        s.claim(db, m, a, b, "owner", NOW)
        with Session(customer_engine) as replica:
            saved = replica.get(MandateAction, a.id)
            assert saved is not None and saved.state == "claimed" and saved.fence == a.fence
        s.claim(db, m, a, b, "owner", NOW)
        assert m.reserved_micros == 60 and m.actions_used == 1
        assert a.fence is not None
        s.dispatch(db, m, a, a.fence, e, "owner", NOW)
        unknown = ReconcileInput(
            fence=a.fence, outcome="unknown", evidence_at=NOW, period_consumed_micros=10
        )
        s.reconcile(db, m, a, unknown, "owner", NOW)
        db.commit()
        assert m.reserved_micros == 60 and a.state == "outcome_unknown"
        s.cancel(db, m, a, "admin", NOW)
        db.commit()
        assert a.cancel_requested and m.reserved_micros == 60
        with pytest.raises(HTTPException):
            s.dispatch(db, m, a, a.fence, e, "owner", NOW)
        done = ReconcileInput(
            fence=a.fence,
            outcome="success",
            consumed_micros=40,
            evidence_at=NOW,
            period_consumed_micros=50,
        )
        s.reconcile(db, m, a, done, "owner", NOW)
        db.commit()
        s.reconcile(db, m, a, done, "owner", NOW)
        assert m.observed_micros == 50 and m.reserved_micros == 0
        assert not s.view(db, m)["live_execution_enabled"]
        second = draft(db, m, "two")
        with pytest.raises(HTTPException, match="cap exceeded"):
            s.claim(
                db,
                m,
                second,
                ClaimInput(request_key="claim-two", evidence=evidence(db, m, total=50)),
                "owner",
                NOW,
            )


@pytest.mark.retained_execution
@pytest.mark.usefixtures("retained_execution_engine")
def test_exact_review_stale_state_and_stop_semantics(
    customer_engine: Engine, configuration: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.settings import settings

    with Session(customer_engine) as db:
        m = seed(db, configuration)
        a = draft(db, m, kind="new_campaign")
        e = evidence(db, m)
        body = ClaimInput(request_key="claim-one", evidence=e)
        with pytest.raises(HTTPException):
            s.claim(db, m, a, body, "owner", NOW)
        with pytest.raises(HTTPException):
            s.review(db, m, a, "b" * 64, "owner", NOW)
        s.review(db, m, a, a.digest, "owner", NOW)
        db.commit()
        with pytest.raises(HTTPException, match="stale"):
            s.claim(
                db,
                m,
                a,
                body.model_copy(
                    update={
                        "evidence": e.model_copy(update={"observed_at": NOW - timedelta(minutes=6)})
                    }
                ),
                "owner",
                NOW,
            )
        s.claim(db, m, a, body, "owner", NOW)
        assert a.fence
        s.stop(db, m, "admin", NOW)
        db.commit()
        with pytest.raises(HTTPException):
            s.dispatch(db, m, a, a.fence, e, "owner", NOW)
        assert m.reserved_micros == 60
        s.approve(db, m, 1, "owner", NOW)
        db.commit()
        monkeypatch.setattr(settings, "mandate_simulation_enabled", False)
        with pytest.raises(HTTPException, match="kill switch"):
            s.dispatch(db, m, a, a.fence, e, "owner", NOW)
        monkeypatch.setattr(settings, "mandate_simulation_enabled", True)
        with pytest.raises(HTTPException, match="state"):
            s.dispatch(
                db, m, a, a.fence, e.model_copy(update={"state_digest": "b" * 64}), "owner", NOW
            )
        s.cancel(db, m, a, "admin", NOW)
        db.commit()
        assert a.state == "cancelled" and m.reserved_micros == 0 and m.changes_used == 20
        s.stop(db, m, "admin", NOW, revoke=True)
        db.commit()
        with pytest.raises(HTTPException, match="revoked"):
            s.approve(db, m, 1, "owner", NOW)


@pytest.mark.retained_execution
@pytest.mark.usefixtures("retained_execution_engine")
def test_revisions_never_reset_consumption_or_expand_by_aggressiveness(
    customer_engine: Engine, configuration: Settings
) -> None:
    with Session(customer_engine) as db:
        m = seed(db, configuration)
        a = draft(db, m)
        s.claim(
            db, m, a, ClaimInput(request_key="claim-one", evidence=evidence(db, m)), "owner", NOW
        )
        d = s.policy(db, m)
        s.edit(db, m, 1, d, "owner", NOW)
        db.commit()
        assert m.revision == 2 and m.reserved_micros == 60 and m.changes_used == 20 and m.paused
        s.approve(db, m, 2, "owner", NOW)
        db.commit()
        assert a.fence
        with pytest.raises(HTTPException, match="scope changed"):
            s.dispatch(db, m, a, a.fence, evidence(db, m), "owner", NOW)
        s.cancel(db, m, a, "owner", NOW)
        db.commit()
        other = draft(db, m, "two", exposure=30)
        s.claim(
            db,
            m,
            other,
            ClaimInput(request_key="claim-two", evidence=evidence(db, m, bound=30)),
            "owner",
            NOW,
        )
        s.cancel(db, m, other, "owner", NOW)
        db.commit()
        third = draft(db, m, "three", exposure=30)
        with pytest.raises(HTTPException, match="cap exceeded"):
            s.claim(
                db,
                m,
                third,
                ClaimInput(request_key="claim-three", evidence=evidence(db, m, bound=30)),
                "owner",
                NOW,
            )
        assert m.changes_used == 40


@pytest.mark.retained_execution
@pytest.mark.usefixtures("retained_execution_engine")
def test_account_and_goal_revalidation_and_overlap(
    customer_engine: Engine, configuration: Settings
) -> None:
    with Session(customer_engine) as db:
        m = seed(db, configuration)
        a = draft(db, m)
        other = seed(db, configuration, "beta")
        with pytest.raises(HTTPException):
            s.owned(db, other.workspace_id, m.id)
        with pytest.raises(HTTPException):
            s.action(db, other, a.id)
        with pytest.raises(HTTPException, match="existing governing"):
            s.create(db, m.workspace_id, s.policy(db, m), "owner", NOW)
        p = s.policy(db, m)
        connection = db.get(WorkspaceIntegration, p.accounts[0].connection_id)
        assert connection is not None
        connection.status = "revoked"
        db.flush()
        with pytest.raises(HTTPException, match="scope unavailable"):
            s.claim(
                db,
                m,
                a,
                ClaimInput(request_key="claim-one", evidence=evidence(db, m)),
                "owner",
                NOW,
            )
        connection.status = "active"
        db.flush()
        g = goals.owned(db, m.workspace_id, p.goal_id)
        goals.revise(db, g, None, "owner", NOW)
        db.flush()
        with pytest.raises(HTTPException, match="revision changed"):
            s.claim(
                db,
                m,
                a,
                ClaimInput(request_key="claim-one", evidence=evidence(db, m)),
                "owner",
                NOW,
            )


@pytest.mark.parametrize("same_action", [False, True])
@pytest.mark.retained_execution
@pytest.mark.usefixtures("retained_execution_engine")
def test_postgres_claim_race_cannot_overspend_or_duplicate(
    customer_engine: Engine, configuration: Settings, same_action: bool
) -> None:
    if customer_engine.dialect.name != "postgresql":
        return
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    with Session(customer_engine) as db:
        m = seed(db, configuration)
        one = draft(db, m)
        two = one if same_action else draft(db, m, "two")
        mid, wid, ids = m.id, m.workspace_id, [one.id, two.id]
    barrier = Barrier(2)

    def reserve(index: int) -> int:
        with Session(customer_engine) as db:
            barrier.wait(timeout=10)
            m = s.owned(db, wid, mid)
            a = s.action(db, m, ids[index])
            try:
                s.claim(
                    db,
                    m,
                    a,
                    ClaimInput(
                        request_key="same-key" if same_action else f"claim-key-{index}",
                        evidence=evidence(db, m),
                    ),
                    "owner",
                    NOW,
                )
                return 200
            except HTTPException as e:
                return e.status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(reserve, i) for i in range(2)]
        assert sorted(f.result(timeout=30) for f in futures) == (
            [200, 200] if same_action else [200, 409]
        )
    with Session(customer_engine) as db:
        saved_mandate = db.get(Mandate, mid)
        assert saved_mandate is not None
        assert saved_mandate.reserved_micros == 60 and saved_mandate.actions_used == 1
        assert (
            db.scalar(
                select(func.count())
                .select_from(MandateAction)
                .where(MandateAction.state == "claimed")
            )
            == 1
        )


@pytest.mark.retained_execution
@pytest.mark.usefixtures("retained_execution_engine")
def test_canonical_dedup_and_complete_monotonic_observation(
    customer_engine: Engine, configuration: Settings
) -> None:
    with Session(customer_engine) as db:
        m = seed(db, configuration)
        a = draft(db, m)
        body = ActionDraft.model_validate(a.draft)
        body.payload = dict(reversed(list(body.payload.items())))
        assert s.draft(db, m, body, "owner", NOW).id == a.id
        incomplete = evidence(db, m).model_copy(update={"covered_account_ids": []})
        with pytest.raises(HTTPException, match="incomplete scope"):
            s.claim(
                db, m, a, ClaimInput(request_key="incomplete", evidence=incomplete), "owner", NOW
            )
        with pytest.raises(HTTPException, match="cumulative policy"):
            s.claim(
                db,
                m,
                a,
                ClaimInput(request_key="manual-cost", evidence=evidence(db, m, 50)),
                "owner",
                NOW,
            )
        db.commit()  # Preserve the high-water observation, even if a later sample is lower.
        with pytest.raises(HTTPException, match="cumulative policy"):
            s.claim(
                db,
                m,
                a,
                ClaimInput(request_key="lower-cost", evidence=evidence(db, m, 0)),
                "owner",
                NOW,
            )
        assert m.observed_micros == 50 and m.reserved_micros == 0


def test_api_roles_csrf_and_workspace_isolation(
    customer_engine: Engine, configuration: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    from collections.abc import Generator
    from unittest.mock import Mock

    from app.api import customer_mandates as api
    from app.api.customer import router as auth_router
    from app.customers.access import CSRF_COOKIE
    from app.customers.identity import get_identity_provider
    from app.customers.models import CustomerMembership
    from app.database.session import get_db
    from app.settings import settings
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from tests.test_customer_identity import ORIGIN, FakeProvider, login

    clock = Mock()
    clock.now.return_value = NOW
    monkeypatch.setattr(api, "datetime", clock)
    monkeypatch.setattr(settings, "customer_app_origin", ORIGIN)
    app = FastAPI()
    app.include_router(auth_router)
    app.include_router(api.router)

    def database() -> Generator[Session, None, None]:
        with Session(customer_engine) as db:
            yield db

    app.dependency_overrides[get_db] = database
    app.dependency_overrides[get_identity_provider] = lambda: FakeProvider()
    owner, outsider = TestClient(app, base_url=ORIGIN), TestClient(app, base_url=ORIGIN)
    uid = login(owner, "owner:1")
    login(outsider, "outsider:1")
    with Session(customer_engine) as db:
        m = seed(db, configuration, approve=False)
        other = seed(db, configuration, "beta", approve=False)
        wid, mid, otherid = m.workspace_id, m.id, other.id
        member = CustomerMembership(user_id=uid, workspace_id=wid, role="owner", status="active")
        db.add(member)
        db.commit()
    path = f"/api/customer/v1/workspaces/{wid}/mandates/{mid}"
    headers = {"Origin": ORIGIN, "X-CSRF-Token": owner.cookies[CSRF_COOKIE]}
    assert outsider.get(path).status_code == 404
    assert owner.get(path.replace(mid, otherid)).status_code == 404
    assert owner.post(path + "/stop/pause").status_code == 403
    assert owner.post(path + "/stop/pause", headers=headers).status_code == 200
    response = owner.get(path)
    assert response.status_code == 200 and response.headers["cache-control"] == "no-store"
    assert response.json()["live_execution_enabled"] is False
    for role in ("admin", "analyst", "viewer"):
        with Session(customer_engine) as db:
            saved_member = db.scalar(
                select(CustomerMembership).where(CustomerMembership.user_id == uid)
            )
            assert saved_member is not None
            saved_member.role = role
            db.commit()
        assert (
            owner.post(path + "/resume", json={"expected_revision": 1}, headers=headers).status_code
            == 403
        )
        assert owner.post(path + "/stop/pause", headers=headers).status_code == (
            200 if role == "admin" else 403
        )

    with Session(customer_engine) as db:
        for mandate_id in (mid, otherid):
            saved = db.get(Mandate, mandate_id)
            revision = db.get(MandateRevision, (mandate_id, 1))
            assert saved is not None and saved.state == "draft" and saved.paused
            assert saved.revision == 1
            assert (saved.observed_micros, saved.reserved_micros) == (0, 0)
            assert (saved.changes_used, saved.actions_used) == (0, 0)
            assert revision is not None
            assert revision.approved_at is None and revision.approved_by is None
        assert db.scalar(select(func.count()).select_from(MandateAction)) == 0
    owner.close()
    outsider.close()


@pytest.mark.retained_execution
@pytest.mark.usefixtures("retained_execution_engine")
def test_postgres_stop_dispatch_race(customer_engine: Engine, configuration: Settings) -> None:
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    if customer_engine.dialect.name != "postgresql":
        return  # PostgreSQL row-lock acceptance; other tests also exercise SQLite.
    with Session(customer_engine) as db:
        m = seed(db, configuration)
        a = draft(db, m)
        s.claim(
            db, m, a, ClaimInput(request_key="race-claim", evidence=evidence(db, m)), "owner", NOW
        )
        mid, wid, aid, fence = m.id, m.workspace_id, a.id, a.fence
        assert fence is not None
    barrier = Barrier(2)

    def operate(stop: bool) -> int:
        with Session(customer_engine) as db:
            barrier.wait(timeout=10)
            m = s.owned(db, wid, mid)
            a = s.action(db, m, aid)
            if stop:
                s.stop(db, m, "owner", NOW)
                s.cancel(db, m, a, "owner", NOW)
                db.commit()
                return 200
            try:
                s.dispatch(db, m, a, str(fence), evidence(db, m), "owner", NOW)
                return 200
            except HTTPException as exc:
                return exc.status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        stopping, dispatching = pool.submit(operate, True), pool.submit(operate, False)
        assert stopping.result(timeout=30) == 200
        dispatched = dispatching.result(timeout=30)
    with Session(customer_engine) as db:
        saved = s.owned(db, wid, mid)
        attempt = s.action(db, saved, aid)
        assert saved.paused
        if dispatched == 200:
            assert attempt.state == "dispatching" and attempt.cancel_requested
            assert saved.reserved_micros == 60
        else:
            assert dispatched == 409 and attempt.state == "cancelled"
            assert saved.reserved_micros == 0 and attempt.dispatch_at is None
