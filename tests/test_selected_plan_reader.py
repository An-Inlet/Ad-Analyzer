"""Actual selected API/storage plus an explicitly synthetic bound native catalog."""

from datetime import UTC, datetime, time, timedelta
from decimal import Decimal
from typing import Any

import pytest
from app.ads.models import Campaign, DailyMetric
from app.campaign_performance.selected_models import CurrentEventSelectionRow, SelectedCaptureRow
from app.customers.access import CustomerPrincipal
from app.customers.models import CustomerMembership, CustomerSession, CustomerUser
from app.google_connections.models import GoogleCustomerConnection
from app.lifecycle.privacy import advance_workspace_export_revision
from app.planning_catalog.metadata_contracts import PlanningMetadataV1
from app.planning_catalog.projection_v2 import project_v2
from app.planning_documents.composer import targets
from app.planning_documents.context import AccountRef, EvidenceRef, ReportingWindow
from app.planning_documents.evidence_local import resolve_source_fences
from app.planning_documents.ports import CatalogEvidence
from app.planning_documents.read_context import PlanningReadContexts, snapshot
from app.planning_documents.selected_plan_reader import (
    OwnedSelectedPlanContext,
    load_selected_plan_graph,
)
from app.publication.contracts import fingerprint
from app.publication.customer_intents import account
from fastapi import HTTPException
from sqlalchemy import delete, update
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import set_committed_value

from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_google_customer_connections import configured as configured
from tests.test_planning_metadata_binding import bundle
from tests.test_selected_capture_api import prepare
from tests.test_selected_customer_api import CustomerFixture
from tests.test_selected_customer_api import customer as customer


def ready(f: CustomerFixture, value: str | None = "10") -> tuple[Any, ...]:
    body = prepare(f, value)
    response = f.post("/captures", body)
    assert response.status_code == 200, response.text
    with Session(f.engine) as db:
        user = db.get(CustomerUser, f.actor)
        session = db.get(CustomerSession, f.sid)
        assert user and session
        principal = snapshot(CustomerPrincipal(user, session))
        scope = account(db, f.wid, f.aid)
        ref = AccountRef(
            workspace_id=f.wid,
            account_id=f.aid,
            connection_id=scope.account.connection_id,
            platform="google_ads",
            connection_version=scope.connection_version,
        )
    contexts = PlanningReadContexts(
        lambda: Session(f.engine), principal, f.provider, f.wid, f.actor
    )
    with contexts.open() as db:
        source = resolve_source_fences(
            db, principal=principal, accounts=(ref,), now=datetime.now(UTC)
        )[0]
    # Catalog fixture is a closed validated server observation, not evidence of
    # a new native HTTP acquisition. The selected capture above is actual API IO.
    native, metadata = bundle("google")
    start = datetime.combine(f.day, time.min, UTC)
    end = start + timedelta(days=1)
    now = datetime.now(UTC)
    request = native.request.model_copy(
        update={"account": scope, "period_start": start, "period_end": end}
    )
    native = type(native).model_validate(
        native.model_copy(
            update={
                "request": request,
                "observation_started_at": now,
                "observed_at": now,
                "expires_at": now + timedelta(minutes=4),
            }
        )
    )
    metadata = PlanningMetadataV1.model_validate(
        metadata.model_copy(
            update={
                "workspace_id": f.wid,
                "account_id": f.aid,
                "connection_id": ref.connection_id,
                "connection_version": ref.connection_version,
                "source_binding_digest": fingerprint(
                    "inlet.planning-source.v1", scope.model_dump(mode="json")
                ),
                "native_inventory_digest": native.digest(),
                "request_digest": request.digest(),
                "reporting_starts_at": start,
                "reporting_ends_at": end,
                "observation_started_at": now,
                "observed_at": now,
                "expires_at": native.expires_at,
            }
        )
    )
    catalog = project_v2(native, metadata)
    evidence = CatalogEvidence(
        reference=EvidenceRef(
            key="catalog",
            workspace_id=f.wid,
            kind="native_catalog",
            account=ref,
            document_schema=catalog.schema_version,
            document_digest=catalog.composite_digest,
            source_binding_digest=source.source_binding_digest,
            source_revision=source.source_revision,
            privacy_revision=source.privacy_revision,
            reporting_window=ReportingWindow(starts_at=start, ends_at_exclusive=end),
            observation_started_at=now,
            observed_at=now,
            expires_at=catalog.expires_at,
            coverage="complete_in_declared_scope"
            if (
                all(c.status == "complete" for c in catalog.native_observation.coverage)
                and all(c.status == "complete" for c in metadata.coverage)
            )
            else "partial",
            declared_scope="Fixture native campaigns",
            reasons=("fixture_partial",),
            metric_basis="Native settings only",
        ),
        catalog=catalog,
    )
    target = next(
        x
        for x in targets(evidence)
        if x.kind == "campaign" and x.provider_reference.entity_id == "1"
    )
    return (
        contexts,
        dict(
            principal=principal,
            account=ref,
            expected_source=source,
            capture_id=body["request_id"],
            catalog=evidence,
            authorize=contexts.authorize,
            clock=lambda: datetime.now(UTC),
        ),
        target,
        ReportingWindow(starts_at=start, ends_at_exclusive=end),
    )


@pytest.mark.parametrize("value", ["10", "0", None])
def test_real_selected_capture_read_and_one_graph(
    customer: CustomerFixture, value: str | None, monkeypatch: pytest.MonkeyPatch
) -> None:
    f = customer
    contexts, kwargs, target, window = ready(f, value)
    from app.planning_documents import selected_plan_reader as module

    original = module.read_selected_capture
    reads = 0

    def counted(*args: Any, **kw: Any) -> Any:
        nonlocal reads
        reads += 1
        return original(*args, **kw)

    monkeypatch.setattr(module, "read_selected_capture", counted)
    calls = len(f.calls)
    with contexts.open() as db, OwnedSelectedPlanContext(db, **kwargs) as reader:
        result = reader.read(target, window)
        assert reader.read(target, window) == result
        assert reader.snapshot().pin() == reader.pin == result.pin
        assert reads == 1
        assert not db.new and not db.dirty and not db.deleted
        assert len(f.calls) == calls
        assert result.summary.conversions.value == (Decimal(value) if value is not None else None)
    assert not reader._hooks
    with pytest.raises(HTTPException):
        reader.snapshot()


@pytest.mark.parametrize(
    "kind",
    [
        "resident",
        "resident_source",
        "dirty",
        "metric",
        "mapping",
        "privacy",
        "selection",
        "capture_delete",
        "source",
        "role",
        "session",
        "rollback",
        "commit",
        "nested",
        "expiry",
    ],
)
def test_currentness_mutations_deny(customer: CustomerFixture, kind: str) -> None:
    f = customer
    contexts, kwargs, target, window = ready(f)
    with contexts.open() as db:
        reader = OwnedSelectedPlanContext(db, **kwargs)
        try:
            if kind in {"resident", "dirty"}:
                row = db.get(SelectedCaptureRow, kwargs["capture_id"])
                assert row
                if kind == "resident":
                    set_committed_value(row, "canonical_json", "{}")
                else:
                    row.canonical_json = "{}"
            elif kind == "resident_source":
                row_source = db.get(GoogleCustomerConnection, f.source_id)
                assert row_source
                set_committed_value(row_source, "status", "disconnected")
            elif kind == "metric":
                db.execute(update(DailyMetric).values(cost_micros=DailyMetric.cost_micros + 1))
            elif kind == "mapping":
                db.execute(
                    update(Campaign)
                    .where(Campaign.account_id == f.aid)
                    .values(external_campaign_id="999")
                )
            elif kind == "privacy":
                advance_workspace_export_revision(db, f.wid)
            elif kind == "selection":
                db.execute(
                    update(CurrentEventSelectionRow)
                    .where(CurrentEventSelectionRow.account_id == f.aid)
                    .values(invalidated=True)
                )
            elif kind == "capture_delete":
                db.execute(
                    delete(SelectedCaptureRow).where(SelectedCaptureRow.id == kwargs["capture_id"])
                )
            elif kind == "source":
                db.execute(
                    update(GoogleCustomerConnection)
                    .where(GoogleCustomerConnection.id == f.source_id)
                    .values(generation=99)
                )
            elif kind == "role":
                db.execute(
                    update(CustomerMembership)
                    .where(CustomerMembership.user_id == f.actor)
                    .values(role="viewer")
                )
            elif kind == "session":
                db.execute(
                    update(CustomerSession)
                    .where(CustomerSession.digest == f.sid)
                    .values(revoked_at=int(datetime.now(UTC).timestamp()))
                )
            elif kind == "rollback":
                db.rollback()
            elif kind == "commit":
                db.commit()
            elif kind == "nested":
                db.begin_nested()
            else:
                reader.clock = lambda: datetime.now(UTC) + timedelta(hours=1)
            with pytest.raises(HTTPException):
                reader.read(target, window)
        finally:
            reader.close()
            db.rollback()
        assert not reader._hooks


def test_shared_loader_rejects_scope_and_successful_exit_rechecks(
    customer: CustomerFixture,
) -> None:
    f = customer
    contexts, kwargs, target, window = ready(f)
    with contexts.open() as db:
        graph = load_selected_plan_graph(
            db,
            account=kwargs["account"],
            expected_source=kwargs["expected_source"],
            capture_id=kwargs["capture_id"],
        )
        assert graph.capture.request.capture_id == kwargs["capture_id"]
        foreign = kwargs["account"].model_copy(update={"account_id": f.aid + 1})
        with pytest.raises(HTTPException):
            load_selected_plan_graph(
                db,
                account=foreign,
                expected_source=kwargs["expected_source"],
                capture_id=kwargs["capture_id"],
            )
        with pytest.raises(HTTPException), OwnedSelectedPlanContext(db, **kwargs) as reader:
            assert reader.read(target, window).summary.conversions.value == Decimal("10")
            reader.clock = lambda: datetime.now(UTC) + timedelta(hours=1)
        assert not reader._hooks


def test_exception_cleanup_preserves_original_error(customer: CustomerFixture) -> None:
    contexts, kwargs, _, _ = ready(customer)
    with contexts.open() as db:
        with (
            pytest.raises(RuntimeError, match="original"),
            OwnedSelectedPlanContext(db, **kwargs) as reader,
        ):
            raise RuntimeError("original")
        assert not reader._hooks


def test_preexisting_resident_tamper_is_not_refreshed_away(customer: CustomerFixture) -> None:
    contexts, kwargs, _, _ = ready(customer)
    with contexts.open() as db:
        row = db.get(SelectedCaptureRow, kwargs["capture_id"])
        assert row
        set_committed_value(row, "canonical_json", "{}")
        with pytest.raises(HTTPException):
            OwnedSelectedPlanContext(db, **kwargs)
        db.expire(row)


def test_final_authority_after_witness_wait(
    customer: CustomerFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    import time as clock_time

    contexts, kwargs, target, window = ready(customer)
    original_clock = clock_time.monotonic
    offset = [0.0]
    monkeypatch.setattr(clock_time, "monotonic", lambda: original_clock() + offset[0])
    with contexts.open() as db:
        reader = OwnedSelectedPlanContext(db, **kwargs)
        original = reader._raw_witness

        def delayed(*, initialize: bool = False) -> tuple[Any, ...]:
            result = original(initialize=initialize)
            offset[0] = 6.0
            return result

        monkeypatch.setattr(reader, "_raw_witness", delayed)
        try:
            with pytest.raises(HTTPException):
                reader.read(target, window)
        finally:
            offset[0] = 0.0
            reader.close()
