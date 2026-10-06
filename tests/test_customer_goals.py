"""B06 offline acceptance with isolated SQLite and PostgreSQL schemas."""

from datetime import date, timedelta
from typing import Any
from uuid import uuid4

import pytest
from app.commerce.ledger import apply_order
from app.commerce.models import CommerceSnapshot
from app.goals import service
from app.goals.interpreter import GoalInterpreter, InterpretationLimits, reserve, run
from app.goals.models import Goal, GoalUsage, UsagePolicy
from app.goals.schemas import (
    ConfirmInput,
    GoalDefinition,
    InterpretationInput,
    InterpretationOutput,
)
from app.settings import Settings
from app.shopify.privacy import process_event
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from tests.migration_engine import migration_customer_engine as migration_customer_engine
from tests.test_commerce_measurement import NOW, agreement, setup, source, window
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_shopify_sales import configuration as configuration


def definition(store_id: str) -> GoalDefinition:
    return GoalDefinition(
        metric="shopify_merchandise_net_sales_v1",
        store_id=store_id,
        target_micros=100_000_000,
        target_window=window(date(2026, 11, 1), date(2026, 12, 1)),
        baseline_window=window(),
        deadline=date(2026, 11, 30),
        budget_micros=50_000_000,
        budget_start=date(2026, 11, 1),
        budget_end=date(2026, 12, 1),
        aggressiveness="balanced",
    )


def seed(db: Session, config: Settings, slug: str = "alpha") -> Goal:
    row, store = setup(db, config, slug)
    apply_order(db, store, row, source(), [agreement()], config, NOW)
    goal = Goal(id=uuid4().hex, workspace_id=row.workspace_id, revision=0)
    db.add(goal)
    db.flush()
    service.revise(db, goal, definition(store.id), "offline-user", NOW)
    if db.get(UsagePolicy, "global") is None:
        db.add(UsagePolicy(scope="global", call_limit=1000, cost_limit_micros=0, version=1))
    db.commit()
    return goal


def test_confirm_edit_and_privacy_invalidation(
    customer_engine: Engine, configuration: Settings
) -> None:
    from app.shopify.models import ShopifyConnection

    with Session(customer_engine) as db:
        g = seed(db, configuration)
        p = service.preview(db, g, NOW)
        body = ConfirmInput(expected_revision=1, preview_id=p.id, idempotency_key="confirm-1")
        service.confirm(db, g, body, NOW, actor_id="offline-user")
        db.commit()
        service.confirm(db, g, body, NOW, actor_id="offline-user")
        assert service.serialize(db, g, NOW)["assessment"] == "confirmed"
        assert service.serialize(db, g, NOW)["baseline_snapshot_id"] == p.snapshot_id
        assert service.serialize(db, g, NOW)["confirmed_by"] == "offline-user"
        assert service.serialize(db, g, NOW)["spending_authorized"] is False
        row = db.scalar(
            select(ShopifyConnection).where(ShopifyConnection.workspace_id == g.workspace_id)
        )
        assert row is not None
        process_event(
            db,
            configuration,
            "customers/redact",
            row.shop_domain,
            {"customer": {"id": 100}, "orders_to_redact": [1]},
            NOW,
        )
        db.expire_all()
        assert service.serialize(db, g, NOW)["assessment"] == "baseline_unavailable"
        assert service.serialize(db, g, NOW)["baseline_snapshot_id"] is None
        assert db.scalar(select(func.count()).select_from(CommerceSnapshot)) == 0
        service.revise(db, g, None, "offline-user", NOW)
        db.commit()
        assert service.serialize(db, g, NOW)["assessment"] == "draft"
        with pytest.raises(HTTPException):
            service.confirm(db, g, body, NOW, actor_id="offline-user")


def test_stale_partial_changed_and_future_baselines(
    customer_engine: Engine, configuration: Settings
) -> None:
    from app.commerce.models import CommerceStore

    with Session(customer_engine) as db:
        g = seed(db, configuration)
        d = GoalDefinition.model_validate(service.current(db, g).definition)
        store = db.get(CommerceStore, d.store_id)
        assert store is not None
        p = service.preview(db, g, NOW)
        store.revision += 1
        with pytest.raises(HTTPException, match="baseline changed"):
            service.confirm(
                db,
                g,
                ConfirmInput(expected_revision=1, preview_id=p.id, idempotency_key="confirm-1"),
                NOW,
                actor_id="offline-user",
            )
        store.last_sync_at = NOW - timedelta(days=2)
        with pytest.raises(HTTPException) as e:
            service.preview(db, g, NOW)
        assert e.value.status_code == 409
        store.last_sync_at = NOW
        store.window_end = NOW
        with pytest.raises(HTTPException):
            service.preview(db, g, NOW)
        store.window_end = None
        d.baseline_window = window(date(2026, 10, 1), date(2026, 11, 1))
        service.revise(db, g, d, "offline-user", NOW)
        with pytest.raises(HTTPException, match="historical baseline"):
            service.preview(db, g, NOW)


@pytest.mark.parametrize(
    "change",
    [
        {"target_micros": True},
        {"target_micros": -1},
        {"metric": "new_customers"},
        {"spending_authorized": True},
        {"deadline": "2026-12-02"},
    ],
)
def test_definition_rejects_unsafe_or_ambiguous_fields(change: dict[str, Any]) -> None:
    data = definition("a" * 32).model_dump(mode="json")
    with pytest.raises(ValidationError):
        GoalDefinition.model_validate({**data, **change})


def test_interpreter_schema_has_no_action_or_source_authority() -> None:
    with pytest.raises(ValidationError):
        InterpretationOutput.model_validate(
            {"status": "proposal", "candidate": {"store_id": "foreign"}}
        )
    with pytest.raises(ValidationError):
        InterpretationOutput.model_validate(
            {"status": "proposal", "candidate": {"target_micros": float("inf")}}
        )


def test_usage_idempotency_quota_invalid_and_uncertain(
    customer_engine: Engine, configuration: Settings
) -> None:
    class Invalid(GoalInterpreter):
        def interpret(self, milestone: str) -> str:
            return '{"status":"proposal","publish":true}'

    class Uncertain(GoalInterpreter):
        def interpret(self, milestone: str) -> str:
            raise RuntimeError("sensitive fixture must not escape")

    with Session(customer_engine) as db:
        g = seed(db, configuration)
        b = InterpretationInput(
            expected_revision=1, idempotency_key="request-1", milestone="100k monthly in six months"
        )
        output = run(db, g, "u", b, GoalInterpreter())
        assert output["status"] == "needs_clarification"
        assert g.confirmed_preview_id is None
        with pytest.raises(HTTPException) as duplicate:
            run(db, g, "u", b, GoalInterpreter())
        assert duplicate.value.status_code == 409
        with pytest.raises(HTTPException) as quota:
            run(
                db,
                g,
                "u",
                b.model_copy(update={"idempotency_key": "request-2"}),
                GoalInterpreter(),
                InterpretationLimits(workspace_daily_calls=1),
            )
        assert quota.value.status_code == 429
        out = run(db, g, "u", b.model_copy(update={"idempotency_key": "request-3"}), Invalid())
        assert out["reason"] == "invalid_interpretation"
        out = run(db, g, "u", b.model_copy(update={"idempotency_key": "request-4"}), Uncertain())
        assert out["usage_state"] == "uncertain" and "sensitive" not in str(out)
        with pytest.raises(HTTPException, match="outcome pending"):
            run(
                db, g, "u", b.model_copy(update={"idempotency_key": "request-5"}), GoalInterpreter()
            )
        # Manual editing does not require interpretation or release uncertain reservations.
        service.revise(db, g, None, "u", NOW)
        assert g.revision == 2
        assert all(
            r.reserved_micros == r.charged_micros == 0 for r in db.scalars(select(GoalUsage))
        )


def test_external_and_paid_adapters_are_rejected(
    customer_engine: Engine, configuration: Settings
) -> None:
    with Session(customer_engine) as db:
        g = seed(db, configuration)
        b = InterpretationInput(
            expected_revision=1, idempotency_key="request-1", milestone="anything"
        )
        for external, cost in [(True, 0), (False, 1)]:
            adapter = GoalInterpreter()
            adapter.external, adapter.reserved_cost_micros = external, cost
            with pytest.raises(HTTPException) as denied:
                run(db, g, "u", b, adapter)
            assert denied.value.status_code == 503
        assert db.scalar(select(func.count()).select_from(GoalUsage)) == 0


def test_postgres_concurrent_goal_edits_and_quota(
    customer_engine: Engine, configuration: Settings
) -> None:
    if customer_engine.dialect.name != "postgresql":
        return
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    with Session(customer_engine) as db:
        g = seed(db, configuration)
        gid, wid = g.id, g.workspace_id
    barrier = Barrier(2)

    def edit() -> int:
        with Session(customer_engine) as db:
            barrier.wait(timeout=10)
            goal = service.owned(db, wid, gid)
            try:
                service.expect(goal, 1)
                service.revise(db, goal, None, "u", NOW)
                db.commit()
                return 200
            except HTTPException as e:
                return e.status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(edit) for _ in range(2)]
        assert sorted(f.result(timeout=20) for f in futures) == [200, 409]
    with Session(customer_engine) as db:
        other = seed(db, configuration, "beta")
        other_id, other_wid = other.id, other.workspace_id
    barrier = Barrier(2)

    def reservation(gid: str, wid: int) -> int:
        with Session(customer_engine) as db:
            goal = service.owned(db, wid, gid)
            barrier.wait(timeout=10)
            try:
                reserve(
                    db,
                    goal,
                    "u",
                    InterpretationInput(
                        expected_revision=goal.revision,
                        idempotency_key="request-1",
                        milestone="monthly",
                    ),
                    GoalInterpreter(),
                    InterpretationLimits(global_daily_calls=1),
                    NOW,
                )
                return 200
            except HTTPException as e:
                return e.status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(reservation, *pair) for pair in [(gid, wid), (other_id, other_wid)]]
        assert sorted(f.result(timeout=20) for f in futures) == [200, 429]


@pytest.mark.parametrize("pending_state", ["reserved", "uncertain"])
def test_goal_api_identity_csrf_roles_and_source_isolation(
    customer_engine: Engine,
    configuration: Settings,
    monkeypatch: pytest.MonkeyPatch,
    pending_state: str,
) -> None:
    from collections.abc import Generator
    from unittest.mock import Mock

    from app.api import customer_goals as api
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
    monkeypatch.setattr(service, "datetime", clock)
    monkeypatch.setattr(settings, "customer_app_origin", ORIGIN)
    app = FastAPI()
    app.include_router(auth_router)
    app.include_router(api.router)

    def database() -> Generator[Session, None, None]:
        with Session(customer_engine, autoflush=False) as db:
            yield db

    provider = FakeProvider()
    app.dependency_overrides[get_db] = database
    app.dependency_overrides[get_identity_provider] = lambda: provider
    owner, outsider = TestClient(app, base_url=ORIGIN), TestClient(app, base_url=ORIGIN)
    user = login(owner, "owner:1")
    login(outsider, "outsider:1")
    with Session(customer_engine) as db:
        g = seed(db, configuration)
        other = seed(db, configuration, "beta")
        wid, gid, otherid = g.workspace_id, g.id, other.id
        body = service.current(db, g).definition
        otherbody = service.current(db, other).definition
        db.add(CustomerMembership(user_id=user, workspace_id=wid, role="owner", status="active"))
        db.commit()
    prefix = f"/api/customer/v1/workspaces/{wid}/goals"
    path = f"{prefix}/{gid}"
    headers = {"Origin": ORIGIN, "X-CSRF-Token": owner.cookies[CSRF_COOKIE]}
    create_headers = {**headers, "Idempotency-Key": "goal-lost-response"}
    first = owner.post(prefix, json={"definition": body}, headers=create_headers)
    retry = owner.post(prefix, json={"definition": body}, headers=create_headers)
    assert first.status_code == retry.status_code == 201
    assert first.json()["id"] == retry.json()["id"]
    assert body is not None
    rejected_headers = {**headers, "Idempotency-Key": "known-rejection-1"}
    assert (
        owner.post(
            prefix, json={"definition": {**body, "target_micros": 0}}, headers=rejected_headers
        ).status_code
        == 422
    )
    corrected = owner.post(prefix, json={"definition": body}, headers=rejected_headers)
    assert corrected.status_code == 201
    assert (
        owner.post(prefix, json={"definition": body}, headers=rejected_headers).json()["id"]
        == corrected.json()["id"]
    )

    assert owner.post(prefix, json={"definition": None}, headers=create_headers).status_code == 409
    assert owner.post(prefix, json={"definition": body}, headers=headers).status_code == 422
    assert (
        outsider.post(
            prefix,
            json={"definition": body},
            headers={
                "Origin": ORIGIN,
                "X-CSRF-Token": outsider.cookies[CSRF_COOKIE],
                "Idempotency-Key": "goal-lost-response",
            },
        ).status_code
        == 404
    )
    assert outsider.get(path).status_code == 404
    assert owner.get(f"{prefix}/{otherid}").status_code == 404
    assert owner.put(path, json={"expected_revision": 1, "definition": body}).status_code == 403
    assert (
        owner.put(
            path, json={"expected_revision": 1, "definition": otherbody}, headers=headers
        ).status_code
        == 404
    )
    with Session(customer_engine) as db:
        membership = db.get(CustomerMembership, (user, wid))
        assert membership is not None
        membership.status = "suspended"
        db.commit()
    assert owner.post(prefix, json={"definition": body}, headers=create_headers).status_code == 404
    with Session(customer_engine) as db:
        membership = db.get(CustomerMembership, (user, wid))
        assert membership is not None
        membership.status = "active"
        db.commit()
    assert owner.get(path).headers["Cache-Control"] == "no-store"
    preview = owner.post(path + "/preview", json={"expected_revision": 1}, headers=headers)
    assert preview.status_code == 200
    confirmation = {
        "expected_revision": 1,
        "preview_id": preview.json()["preview_id"],
        "idempotency_key": "confirm-api-1",
    }
    result = owner.post(path + "/confirm", json=confirmation, headers=headers)
    assert result.status_code == 200 and result.json()["assessment"] == "confirmed"
    assert not result.json()["spending_authorized"]
    assert owner.post(path + "/confirm", json=confirmation, headers=headers).status_code == 200
    with Session(customer_engine) as db:
        member = db.get(CustomerMembership, (user, wid))
        assert member is not None
        member.role = "analyst"
        db.commit()
    assert owner.post(path + "/confirm", json=confirmation, headers=headers).status_code == 403
    result = owner.put(path, json={"expected_revision": 1, "definition": body}, headers=headers)
    assert result.status_code == 200 and not result.json()["confirmation_recorded"]
    assert (
        owner.put(
            path, json={"expected_revision": 1, "definition": body}, headers=headers
        ).status_code
        == 409
    )
    interpreted = owner.post(
        path + "/interpret",
        json={
            "expected_revision": 2,
            "milestone": "Publish ads and raise spend now",
            "idempotency_key": "interpret-api-1",
        },
        headers=headers,
    )
    assert interpreted.status_code == 200 and interpreted.json()["status"] == "needs_clarification"
    assert owner.get(prefix + "/usage").json()["authorized_model_spend_micros"] == 0
    with Session(customer_engine) as db:
        usage_row = db.get(GoalUsage, (wid, "interpret-api-1"))
        assert usage_row is not None
        usage_row.state = pending_state
        usage_row.created_at = NOW - timedelta(days=1)
        db.commit()
    usage_result = owner.get(prefix + "/usage").json()
    assert usage_result["calls_reserved_today"] == 0
    assert usage_result["pending"] == 1
    pending = owner.post(
        path + "/interpret",
        json={
            "expected_revision": 2,
            "milestone": "same goal",
            "idempotency_key": "next-day-request",
        },
        headers=headers,
    )
    assert pending.status_code == 409 and "outcome pending" in pending.text
    with Session(customer_engine) as db:
        member = db.get(CustomerMembership, (user, wid))
        assert member is not None
        member.role = "viewer"
        db.commit()
    assert (
        owner.put(
            path, json={"expected_revision": 2, "definition": body}, headers=headers
        ).status_code
        == 403
    )
    assert owner.get(path + "/history").status_code == 200
    provider.revoked.add("owner")
    assert owner.get(path).status_code == 401


@pytest.mark.parametrize("different_keys", [False, True])
def test_postgres_confirmation_race_is_idempotent(
    customer_engine: Engine, configuration: Settings, different_keys: bool
) -> None:
    if customer_engine.dialect.name != "postgresql":
        return
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    from app.goals.models import GoalConfirmation

    with Session(customer_engine) as db:
        goal = seed(db, configuration)
        p = service.preview(db, goal, NOW)
        db.commit()
        gid, wid, pid = goal.id, goal.workspace_id, p.id
    barrier = Barrier(2)

    def confirm(index: int) -> tuple[str, str]:
        with Session(customer_engine) as db:
            barrier.wait(timeout=10)
            g = service.owned(db, wid, gid)
            service.confirm(
                db,
                g,
                ConfirmInput(
                    expected_revision=1,
                    preview_id=pid,
                    idempotency_key=f"confirm-{index}" if different_keys else "same-confirm",
                ),
                NOW + timedelta(seconds=index),
                actor_id=f"actor-{index}",
            )
            db.commit()
            revision = service.current(db, g)
            assert revision.confirmed_by is not None and revision.confirmed_at is not None
            from app.shopify.security import utc

            return revision.confirmed_by, utc(revision.confirmed_at).isoformat()

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(confirm, i) for i in range(2)]
        results = [f.result(timeout=20) for f in futures]
        assert len(set(results)) == 1
    with Session(customer_engine) as db:
        assert db.scalar(select(func.count()).select_from(GoalConfirmation)) == (
            2 if different_keys else 1
        )


def test_timeout_keeps_reservation_without_duplicate_call(
    customer_engine: Engine, configuration: Settings
) -> None:
    from threading import Event

    release = Event()

    class Slow(GoalInterpreter):
        calls = 0

        def interpret(self, milestone: str) -> str:
            self.calls += 1
            release.wait(timeout=2)
            return super().interpret(milestone)

    adapter = Slow()
    try:
        with Session(customer_engine) as db:
            g = seed(db, configuration)
            body = InterpretationInput(
                expected_revision=1, idempotency_key="timeout-1", milestone="monthly"
            )
            out = run(db, g, "u", body, adapter, InterpretationLimits(timeout_seconds=0.01))
            assert out["usage_state"] == "uncertain"
            with pytest.raises(HTTPException):
                run(db, g, "u", body, adapter)
            assert adapter.calls == 1
    finally:
        release.set()


def test_b06_populated_migration_and_snapshot_erasure(
    migration_customer_engine: Engine, configuration: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    if migration_customer_engine.dialect.name != "postgresql":
        return
    from alembic import command
    from alembic.config import Config
    from app.commerce.models import CommerceStore
    from app.settings import settings
    from sqlalchemy import delete, text

    with Session(migration_customer_engine) as db:
        goal = seed(db, configuration)
        store_id = GoalDefinition.model_validate(service.current(db, goal).definition).store_id
    with migration_customer_engine.connect() as connection:
        schema = connection.scalar(text("SELECT current_schema()"))
    scoped = migration_customer_engine.url.update_query_dict({"options": f"-csearch_path={schema}"})
    monkeypatch.setattr(settings, "database_url", scoped.render_as_string(hide_password=False))
    config = Config("alembic.ini")
    command.downgrade(config, "20261005_0025")
    command.upgrade(config, "heads")
    with Session(migration_customer_engine) as db:
        assert db.get(CommerceStore, store_id) is not None
        assert db.get(UsagePolicy, "global") is not None
        store = db.get(CommerceStore, store_id)
        assert store is not None
        goal = Goal(id=uuid4().hex, workspace_id=store.workspace_id, revision=0)
        db.add(goal)
        db.flush()
        service.revise(db, goal, definition(store_id), "u", NOW)
        p = service.preview(db, goal, NOW)
        service.confirm(
            db,
            goal,
            ConfirmInput(expected_revision=1, preview_id=p.id, idempotency_key="migrated-confirm"),
            NOW,
            actor_id="offline-user",
        )
        db.commit()
        db.execute(delete(CommerceSnapshot))
        db.commit()
        db.expire_all()
        assert service.serialize(db, goal, NOW)["assessment"] == "baseline_unavailable"


@pytest.mark.parametrize("same_key", [False, True])
def test_postgres_workspace_quota_and_duplicate_reservation_race(
    customer_engine: Engine, configuration: Settings, same_key: bool
) -> None:
    if customer_engine.dialect.name != "postgresql":
        return
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    with Session(customer_engine) as db:
        first = seed(db, configuration)
        second = Goal(id=uuid4().hex, workspace_id=first.workspace_id, revision=0)
        db.add(second)
        db.flush()
        service.revise(db, second, None, "u", NOW)
        db.commit()
        wid, ids = first.workspace_id, [first.id, second.id]
    barrier = Barrier(2)

    def reserve_one(index: int) -> int:
        with Session(customer_engine) as db:
            goal = service.owned(db, wid, ids[index])
            barrier.wait(timeout=10)
            try:
                reserve(
                    db,
                    goal,
                    "u",
                    InterpretationInput(
                        expected_revision=1,
                        idempotency_key="same-key" if same_key else f"request-{index}",
                        milestone="monthly",
                    ),
                    GoalInterpreter(),
                    InterpretationLimits(workspace_daily_calls=1),
                    NOW,
                )
                return 200
            except HTTPException as e:
                return e.status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(reserve_one, i) for i in range(2)]
        assert sorted(f.result(timeout=20) for f in futures) == [200, 409 if same_key else 429]
    with Session(customer_engine) as db:
        assert db.scalar(select(func.count()).select_from(GoalUsage)) == 1


def test_confirmation_rejects_foreign_preview_and_changed_idempotency(
    customer_engine: Engine, configuration: Settings
) -> None:
    with Session(customer_engine) as db:
        a, b = seed(db, configuration), seed(db, configuration, "beta")
        pa, pb = service.preview(db, a, NOW), service.preview(db, b, NOW)
        with pytest.raises(HTTPException):
            service.confirm(
                db,
                a,
                ConfirmInput(expected_revision=1, preview_id=pb.id, idempotency_key="confirm-1"),
                NOW,
                actor_id="offline-user",
            )
        service.confirm(
            db,
            a,
            ConfirmInput(expected_revision=1, preview_id=pa.id, idempotency_key="confirm-1"),
            NOW,
            actor_id="offline-user",
        )
        db.commit()
        with pytest.raises(HTTPException, match="idempotency conflict"):
            service.confirm(
                db,
                a,
                ConfirmInput(expected_revision=1, preview_id=pb.id, idempotency_key="confirm-1"),
                NOW,
                actor_id="offline-user",
            )


def test_cumulative_basis_and_currency_are_explicit(
    customer_engine: Engine, configuration: Settings
) -> None:
    with Session(customer_engine) as db:
        g = seed(db, configuration)
        d = GoalDefinition.model_validate(service.current(db, g).definition)
        data = d.model_dump(mode="json")
        data["target_window"].update(start="2026-11-01", end="2026-11-11", time_basis="cumulative")
        data["baseline_window"].update(
            start="2026-09-01", end="2026-09-11", time_basis="cumulative"
        )
        data["deadline"] = "2026-11-10"
        parsed = GoalDefinition.model_validate(data)
        service.revise(db, g, parsed, "u", NOW)
        assert service.preview(db, g, NOW).snapshot_id is not None
        data["baseline_window"]["currency"] = "EUR"
        with pytest.raises(ValidationError):
            GoalDefinition.model_validate(data)
        data["target_window"]["currency"] = "EUR"
        with pytest.raises(HTTPException):
            service.revise(db, g, GoalDefinition.model_validate(data), "u", NOW)


def test_revoked_source_allows_draft_edit_but_not_confirmation(
    customer_engine: Engine, configuration: Settings
) -> None:
    from app.commerce.models import CommerceStore

    with Session(customer_engine) as db:
        g = seed(db, configuration)
        d = GoalDefinition.model_validate(service.current(db, g).definition)
        store = db.get(CommerceStore, d.store_id)
        assert store is not None
        store.status = "revoked"
        db.flush()
        service.revise(db, g, d, "u", NOW)
        assert g.revision == 2
        with pytest.raises(HTTPException, match="source unavailable"):
            service.preview(db, g, NOW)


def test_confirmation_preserves_original_actor_and_time_across_keys(
    customer_engine: Engine, configuration: Settings
) -> None:
    from app.shopify.security import utc

    with Session(customer_engine) as db:
        goal = seed(db, configuration)
        p = service.preview(db, goal, NOW)
        first = ConfirmInput(expected_revision=1, preview_id=p.id, idempotency_key="owner-confirm")
        service.confirm(db, goal, first, NOW, actor_id="owner-A")
        db.commit()
        for key in ["admin-confirm", "owner-confirm"]:
            service.confirm(
                db,
                goal,
                first.model_copy(update={"idempotency_key": key}),
                NOW + timedelta(seconds=1),
                actor_id="admin-B",
            )
            db.commit()
            revision = service.current(db, goal)
            assert revision.confirmed_by == "owner-A"
            assert revision.confirmed_at is not None and utc(revision.confirmed_at) == NOW
