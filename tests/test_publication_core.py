"""Publication coordinator fixtures never instantiate provider transports."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from app.campaign_review import service as review_service
from app.campaign_review.storage import LocalMediaStore
from app.customers.models import CustomerMembership, CustomerUser
from app.google_connections.models import GoogleCustomerConnection
from app.mandates.models import Mandate
from app.publication import service as s
from app.publication.contracts import FixtureReviewFields, PublishPlan, PublishReceipt
from app.publication.fixture import FixturePublicationTransport
from app.publication.models import (
    PublicationPlanRecord,
    PublicationReceiptRecord,
    PublicationStepRecord,
)
from app.settings import Settings
from fastapi import HTTPException
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from tests.test_campaign_review import definition
from tests.test_commerce_measurement import NOW
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_google_action_plans import setup
from tests.test_shopify_sales import configuration as configuration


def seed(
    db: Session, config: Settings, path: Path
) -> tuple[str, int, str, s.DatabaseFixtureAuthority]:
    mandate, scope, _ = setup(db, config)
    actor = uuid4().hex
    db.add(CustomerUser(id=actor, issuer="fixture", subject=actor, email="fixture@example.invalid"))
    db.flush()
    db.add(CustomerMembership(user_id=actor, workspace_id=mandate.workspace_id, role="owner"))
    db.commit()
    store = LocalMediaStore(path)
    d = definition(db, mandate, scope).model_copy(update={"budget_micros": 40})
    revision = review_service.revise(db, mandate.workspace_id, d, actor, store, NOW)
    review_service.approve(
        db,
        mandate.workspace_id,
        revision.draft_id,
        revision.revision,
        revision.digest,
        actor,
        store,
        NOW,
    )
    authority = s.DatabaseFixtureAuthority(store)
    plan = s.prepare(
        db,
        mandate.workspace_id,
        revision.draft_id,
        "fixture_v1",
        FixtureReviewFields(
            tracking="synthetic_conversion",
            bidding="synthetic_fixed_bound",
            budget_semantics="synthetic_horizon_exposure",
        ),
        actor,
        authority,
        NOW,
    )
    return plan.id, mandate.workspace_id, actor, authority


def approved(
    db: Session, config: Settings, path: Path
) -> tuple[str, int, str, s.DatabaseFixtureAuthority]:
    pid, wid, actor, authority = seed(db, config, path)
    row = db.get(PublicationPlanRecord, pid)
    assert row is not None
    plan = PublishPlan.model_validate(row.document)
    s.approve(db, wid, pid, plan.review_digest, row.digest, actor, authority, NOW)
    return pid, wid, actor, authority


def test_exact_separate_review_and_server_compiler(
    customer_engine: Engine, configuration: Settings, tmp_path: Path
) -> None:
    with Session(customer_engine) as db:
        pid, wid, actor, authority = seed(db, configuration, tmp_path)
        row = db.get(PublicationPlanRecord, pid)
        assert row is not None
        plan = PublishPlan.model_validate(row.document)
        with pytest.raises(HTTPException):
            s.dispatch_next(
                db,
                wid,
                pid,
                "publication-one",
                actor,
                authority,
                FixturePublicationTransport(),
                NOW,
            )
        db.rollback()
        with pytest.raises(HTTPException):
            s.approve(db, wid, pid, plan.review.source_digest, row.digest, actor, authority, NOW)
        db.rollback()
        with pytest.raises(ValueError, match="compiler unavailable"):
            s.prepare(
                db,
                wid,
                plan.review.source.draft_id,
                "customer_http",
                plan.review.configuration,
                actor,
                authority,
                NOW,
            )
        db.rollback()
        s.approve(db, wid, pid, plan.review_digest, row.digest, actor, authority, NOW)
        replay = s.prepare(
            db,
            wid,
            plan.review.source.draft_id,
            "fixture_v1",
            plan.review.configuration,
            actor,
            authority,
            NOW,
        )
        assert replay.id == pid


def test_paused_dag_one_reservation_and_distinct_activation_review(
    customer_engine: Engine, configuration: Settings, tmp_path: Path
) -> None:
    adapter = FixturePublicationTransport()
    with Session(customer_engine) as db:
        pid, wid, actor, authority = approved(db, configuration, tmp_path)
        for _ in range(4):
            assert (
                s.dispatch_next(db, wid, pid, "publication-one", actor, authority, adapter, NOW)
                is not None
            )
        assert (
            s.dispatch_next(db, wid, pid, "publication-one", actor, authority, adapter, NOW) is None
        )
        assert adapter.calls == 4
        row, plan, mandate, _ = s.locked(db, wid, pid)
        assert (
            row.state == "paused_verified"
            and mandate.reserved_micros == 40
            and mandate.actions_used == 1
        )
        assert row.activation_approved_by is None
        with pytest.raises(HTTPException):
            s.approve_activation(db, wid, pid, plan.review_digest, actor, authority, NOW)
        db.rollback()
        digest = s.activation_preview(db, wid, pid)
        s.approve_activation(db, wid, pid, digest, actor, authority, NOW)
        assert row.activation_approved_by == actor and adapter.calls == 4
        assert all(r.status == "PAUSED" for r in adapter.resources.values())
        with pytest.raises(HTTPException, match="request conflict"):
            s.dispatch_next(db, wid, pid, "different-request", actor, authority, adapter, NOW)


def test_timeout_after_effect_reconciles_without_duplicate_creation(
    customer_engine: Engine, configuration: Settings, tmp_path: Path
) -> None:
    adapter = FixturePublicationTransport()
    adapter.timeout_after_apply = True
    with Session(customer_engine) as db:
        pid, wid, actor, authority = approved(db, configuration, tmp_path)
        request = s.dispatch_next(db, wid, pid, "publication-one", actor, authority, adapter, NOW)
        assert request is not None
        assert (
            s.dispatch_next(
                db,
                wid,
                pid,
                "publication-one",
                actor,
                authority,
                adapter,
                NOW + timedelta(seconds=10),
            )
            is None
        )
        assert adapter.calls == 1
        s.reconcile_step(db, wid, pid, request.step.step_id, adapter, NOW + timedelta(seconds=11))
        row, _, mandate, _ = s.locked(db, wid, pid)
        assert mandate.reserved_micros == 40 and row.state == "creating_paused"
        adapter.timeout_after_apply = False
        s.dispatch_next(
            db, wid, pid, "publication-one", actor, authority, adapter, NOW + timedelta(seconds=12)
        )
        assert adapter.calls == 2 and len(adapter.resources) == 2
        assert db.scalar(select(func.count()).select_from(PublicationReceiptRecord)) == 3


def test_crash_before_emission_requires_authoritative_no_effect(
    customer_engine: Engine, configuration: Settings, tmp_path: Path
) -> None:
    adapter = FixturePublicationTransport()
    with Session(customer_engine) as db:
        pid, wid, actor, authority = approved(db, configuration, tmp_path)
        request = s.claim_next(db, wid, pid, "publication-one", actor, authority, NOW)
        assert request is not None
        adapter.no_proof = True
        s.reconcile_step(db, wid, pid, request.step.step_id, adapter, NOW + timedelta(seconds=1))
        assert (
            s.dispatch_next(
                db,
                wid,
                pid,
                "publication-one",
                actor,
                authority,
                adapter,
                NOW + timedelta(seconds=2),
            )
            is None
        )
        assert adapter.calls == 0
        adapter.no_proof = False
        s.reconcile_step(db, wid, pid, request.step.step_id, adapter, NOW + timedelta(seconds=3))
        new = s.dispatch_next(
            db, wid, pid, "publication-one", actor, authority, adapter, NOW + timedelta(seconds=4)
        )
        assert new is not None and new.fence != request.fence and adapter.calls == 1
        stale = adapter.reconcile(request, NOW + timedelta(seconds=5))
        with pytest.raises(HTTPException, match="fence mismatch"):
            s.record_receipt(db, wid, pid, stale, NOW + timedelta(seconds=5))


@pytest.mark.parametrize("after_dispatch", [False, True])
def test_cancel_releases_only_before_dispatch(
    customer_engine: Engine, configuration: Settings, tmp_path: Path, after_dispatch: bool
) -> None:
    adapter = FixturePublicationTransport()
    with Session(customer_engine) as db:
        pid, wid, actor, authority = approved(db, configuration, tmp_path)
        if after_dispatch:
            s.claim_next(db, wid, pid, "publication-one", actor, authority, NOW)
        s.cancel(db, wid, pid, actor, NOW)
        with pytest.raises(HTTPException):
            s.dispatch_next(db, wid, pid, "publication-one", actor, authority, adapter, NOW)
        row, _, mandate, _ = s.locked(db, wid, pid)
        assert mandate.reserved_micros == (40 if after_dispatch else 0)
        assert row.state == ("cancel_requested" if after_dispatch else "cancelled")
        assert adapter.calls == 0


@pytest.mark.parametrize(
    "change", ["generation", "owner", "entitlement", "mandate", "kill", "high_water"]
)
def test_current_authority_checked_before_each_step(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    change: str,
) -> None:
    from app.settings import settings

    adapter = FixturePublicationTransport()
    with Session(customer_engine) as db:
        pid, wid, actor, authority = approved(db, configuration, tmp_path)
        s.dispatch_next(db, wid, pid, "publication-one", actor, authority, adapter, NOW)
        if change == "generation":
            connection = db.scalar(
                select(GoogleCustomerConnection).where(GoogleCustomerConnection.workspace_id == wid)
            )
            assert connection is not None
            connection.generation += 1
        elif change == "owner":
            membership = db.get(CustomerMembership, (actor, wid))
            assert membership is not None
            membership.status = "suspended"
        elif change == "mandate":
            mandate = db.scalar(select(Mandate).where(Mandate.workspace_id == wid))
            assert mandate is not None
            mandate.paused = True
        elif change == "kill":
            monkeypatch.setattr(settings, "mandate_simulation_enabled", False)
        elif change == "high_water":
            mandate = db.scalar(select(Mandate).where(Mandate.workspace_id == wid))
            assert mandate is not None
            mandate.observed_micros = 80
        else:
            monkeypatch.setattr(settings, "billing_required", True)
        db.commit()
        with pytest.raises(HTTPException):
            s.dispatch_next(db, wid, pid, "publication-one", actor, authority, adapter, NOW)
        assert adapter.calls == 1


def test_concurrent_claims_one_attempt(
    customer_engine: Engine, configuration: Settings, tmp_path: Path
) -> None:
    if customer_engine.dialect.name != "postgresql":
        pytest.skip("requires PostgreSQL row locks")
    with Session(customer_engine) as db:
        pid, wid, actor, authority = approved(db, configuration, tmp_path)

    def worker(_: int) -> bool:
        with Session(customer_engine) as db:
            return s.claim_next(db, wid, pid, "publication-one", actor, authority, NOW) is not None

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(worker, [1, 2])) == [False, True]
    with Session(customer_engine) as db:
        _, _, mandate, _ = s.locked(db, wid, pid)
        assert mandate.reserved_micros == 40 and mandate.actions_used == 1
        assert db.scalar(select(func.sum(PublicationStepRecord.attempt))) == 1


def test_transport_substitution_and_foreign_receipts_rejected(
    customer_engine: Engine, configuration: Settings, tmp_path: Path
) -> None:
    class PretendLive(FixturePublicationTransport):
        pass

    with Session(customer_engine) as db:
        pid, wid, actor, authority = approved(db, configuration, tmp_path)
        with pytest.raises(ValueError, match="exact offline"):
            s.dispatch_next(db, wid, pid, "publication-one", actor, authority, PretendLive(), NOW)
        request = s.claim_next(db, wid, pid, "publication-one", actor, authority, NOW)
        assert request is not None
        receipt = PublishReceipt(
            scope=request.scope.model_copy(update={"workspace_id": wid + 1}),
            plan_id=pid,
            step_id=request.step.step_id,
            fence=request.fence,
            request_digest=request.digest(),
            outcome="verified_effect",
            resource_id="foreign",
            status="PAUSED",
            observed_at=NOW,
        )
        with pytest.raises(HTTPException, match="scope/fence"):
            s.record_receipt(db, wid, pid, receipt, NOW)


@pytest.mark.parametrize("seconds", [-1, 1])
def test_receipt_cannot_predate_attempt_or_come_from_future(
    customer_engine: Engine, configuration: Settings, tmp_path: Path, seconds: int
) -> None:
    adapter = FixturePublicationTransport()
    with Session(customer_engine) as db:
        pid, wid, actor, authority = approved(db, configuration, tmp_path)
        request = s.claim_next(db, wid, pid, "publication-one", actor, authority, NOW)
        assert request is not None
        receipt = adapter.apply_once(request, NOW).model_copy(
            update={"observed_at": NOW + timedelta(seconds=seconds)}
        )
        with pytest.raises(HTTPException, match="freshness"):
            s.record_receipt(db, wid, pid, receipt, NOW)
        assert db.scalar(select(func.count()).select_from(PublicationReceiptRecord)) == 0


def test_original_request_archived_and_partial_no_effect_keeps_full_reservation(
    customer_engine: Engine, configuration: Settings, tmp_path: Path
) -> None:
    adapter = FixturePublicationTransport()
    with Session(customer_engine) as db:
        pid, wid, actor, authority = approved(db, configuration, tmp_path)
        s.dispatch_next(db, wid, pid, "publication-one", actor, authority, adapter, NOW)
        request = s.claim_next(db, wid, pid, "publication-one", actor, authority, NOW)
        assert request is not None and request.step.step_id == "campaign"
        s.reconcile_step(db, wid, pid, request.step.step_id, adapter, NOW)
        archived = db.scalar(
            select(PublicationReceiptRecord).where(PublicationReceiptRecord.step_id == "campaign")
        )
        assert archived is not None and archived.request == request.model_dump(mode="json")
        _, _, mandate, _ = s.locked(db, wid, pid)
        assert mandate.reserved_micros == 40 and mandate.actions_used == 1
        s.cancel(db, wid, pid, actor, NOW)
        assert mandate.reserved_micros == 40
