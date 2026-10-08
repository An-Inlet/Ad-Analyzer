"""Actual customer V2 denial/rollback and separately committed maintenance boundaries."""

import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from app.api import customer_planning_documents, customer_planning_target_catalog
from app.collectors import account_diagnostics
from app.collectors.native_diagnostics import NativeDiagnosticService
from app.planning_documents import authority, catalog_receipts, catalog_runtime
from app.planning_documents.catalog_receipt_models import (
    CatalogReceiptRow,
    CatalogReceiptSelectionRow,
    InputCatalogReceiptRow,
)
from app.planning_documents.models import PlanInputRow, PlanRow, PlanVersionRow
from app.publication.execution_models import ProviderExecutionAttempt
from app.settings import Settings
from sqlalchemy import Engine, event, func, select
from sqlalchemy.orm import Session

from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_customer_optimization_api import headers
from tests.test_planning_documents_api import create_body
from tests.test_planning_evidence_adapter import setup_evidence
from tests.test_shopify_sales import configuration as configuration

pytestmark = pytest.mark.planning_boundary


@dataclass
class Clock:
    offset: timedelta = timedelta(0)

    def now(self) -> datetime:
        return datetime.now(UTC) + self.offset

    def reach(self, instant: datetime) -> None:
        self.offset = instant - datetime.now(UTC)


def prepare(
    engine: Engine,
    config: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> Any:
    _, ticket, _, calls = setup_evidence(engine, config, replicas, monkeypatch, "google_ads")
    alice, _, provider = replicas
    alice.app.include_router(customer_planning_target_catalog.router)
    alice.app.include_router(customer_planning_documents.router)
    root = f"/api/customer/v1/workspaces/{ticket.inputs.workspace_id}/planning"
    query = dict(
        account_id=ticket.inputs.accounts[0].account_id,
        starts_at=ticket.inputs.reporting_window.starts_at.isoformat(),
        ends_at=ticket.inputs.reporting_window.ends_at_exclusive.isoformat(),
    )
    clock = Clock()
    monkeypatch.setattr(customer_planning_target_catalog, "utc_now", clock.now)
    return alice, provider, ticket, calls, root, query, clock


def counts(engine: Engine) -> dict[str, int]:
    with Session(engine) as db:
        return {
            model.__tablename__: db.scalar(select(func.count()).select_from(model)) or 0
            for model in (
                CatalogReceiptRow,
                CatalogReceiptSelectionRow,
                InputCatalogReceiptRow,
                PlanRow,
                PlanInputRow,
                PlanVersionRow,
                ProviderExecutionAttempt,
            )
        }


@pytest.mark.parametrize(
    "boundary", ["provider", "identity", "selection_flush", "after_writer", "authority_after_flush"]
)
def test_actual_v2_expiry_boundaries_save_nothing(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    boundary: str,
) -> None:
    alice, provider, _, calls, root, query, clock = prepare(
        customer_engine, configuration, replicas, monkeypatch
    )
    reached: list[str] = []
    observed: dict[str, Any] = {}
    monotonic_offset = 0.0
    original_monotonic = time.monotonic
    monkeypatch.setattr(
        authority,
        "time",
        SimpleNamespace(time=time.time, monotonic=lambda: original_monotonic() + monotonic_offset),
    )
    original_read = NativeDiagnosticService.read_catalog

    def read(service: Any, *args: Any, **kwargs: Any) -> Any:
        result = original_read(service, *args, **kwargs)
        observed["expires"] = min(result[0].expires_at, result[1].expires_at)
        return result

    monkeypatch.setattr(NativeDiagnosticService, "read_catalog", read)
    original_check = provider.check_active

    def check(*args: Any, **kwargs: Any) -> None:
        original_check(*args, **kwargs)
        if boundary == "identity" and observed and not reached:
            reached.append("identity")
            clock.reach(observed["expires"])

    monkeypatch.setattr(provider, "check_active", check)
    transport_factory = account_diagnostics.diagnostic_transport
    inner = transport_factory()
    assert inner is not None

    def wire(request: httpx.Request) -> httpx.Response:
        response = inner.handle_request(request)
        if (
            boundary == "provider"
            and request.url.host == "googleads.googleapis.com"
            and not reached
        ):
            # Explicit injected clock, crossing the existing five-minute read bound.
            # OAuth grant remains within its genuine one-hour fixture lifetime.
            reached.append("provider")
            clock.offset += timedelta(minutes=5, seconds=1)
        return response

    monkeypatch.setattr(
        account_diagnostics, "diagnostic_transport", lambda: httpx.MockTransport(wire)
    )
    original_writer = catalog_receipts.write_catalog_receipt

    def write(*args: Any, **kwargs: Any) -> Any:
        result = original_writer(*args, **kwargs)
        if boundary == "after_writer":
            reached.append("after_writer")
            clock.reach(result.expires_at)
        return result

    monkeypatch.setattr(catalog_runtime, "write_catalog_receipt", write)

    def after_sql(
        connection: Any,
        cursor: Any,
        statement: str,
        parameters: Any,
        context: Any,
        executemany: bool,
    ) -> None:
        nonlocal monotonic_offset
        if statement.lower().startswith("insert into planning_catalog_receipt_selections") and (
            boundary in {"selection_flush", "authority_after_flush"} and not reached
        ):
            reached.append(boundary)
            if boundary == "selection_flush":
                clock.reach(observed["expires"])
            else:
                monotonic_offset = 5.001

    event.listen(customer_engine, "after_cursor_execute", after_sql)
    try:
        response = alice.post(root + "/target-catalog-v2", headers=headers(alice), json=query)
    finally:
        event.remove(customer_engine, "after_cursor_execute", after_sql)
        inner.close()
    assert reached == [boundary], "test must reach the actual requested production boundary"
    assert calls
    assert response.status_code == 409, response.text
    if boundary == "authority_after_flush":
        assert response.json()["detail"] == "planning_authority_expired"
    assert not any(counts(customer_engine).values()), "no partial receipt or planning/ad effects"


@pytest.mark.parametrize("failure", ["capacity", "native_read"])
def test_actual_v2_committed_cleanup_survives_later_failure(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    failure: str,
) -> None:
    alice, _, ticket, _, root, query, clock = prepare(
        customer_engine, configuration, replicas, monkeypatch
    )
    observations = []
    for _ in range(3):
        response = alice.post(root + "/target-catalog-v2", headers=headers(alice), json=query)
        assert response.status_code == 200, response.text
        observations.append(response.json())
    target = observations[0]["targets"][0]
    body = create_body(ticket.inputs)
    body["inputs"]["exclusions"] = [
        dict(
            account_id=query["account_id"],
            canonical_entity_key=target["canonical_entity_key"],
            selection_key=target["selection_key"],
        )
    ]
    created = alice.post(root + "/plans", headers=headers(alice), json=body)
    assert created.status_code == 201, created.text
    with Session(customer_engine) as db:
        link = db.scalars(select(InputCatalogReceiptRow)).one()
        preserved = link.receipt_id
        linked_selector_count = db.scalar(
            select(func.count())
            .select_from(CatalogReceiptSelectionRow)
            .where(CatalogReceiptSelectionRow.receipt_id == preserved)
        )
    expiry = max(
        datetime.fromisoformat(o["expires_at"].replace("Z", "+00:00")) for o in observations
    )
    clock.reach(expiry + timedelta(seconds=1))
    maintenance_calls: list[tuple[int, int]] = []
    original_cleanup = catalog_receipts.cleanup_expired_unused_receipts

    def cleanup(*args: Any, **kwargs: Any) -> int:
        result = original_cleanup(*args, **kwargs)
        maintenance_calls.append((kwargs["limit"], result))
        return result

    monkeypatch.setattr(catalog_runtime, "cleanup_expired_unused_receipts", cleanup)
    if failure == "capacity":
        # One linked receipt already occupies this explicitly reduced test quota.
        monkeypatch.setattr(catalog_receipts, "MAX_RECEIPTS", 1)
    old_transport = account_diagnostics.diagnostic_transport
    inner = old_transport()
    assert inner is not None
    observed_committed: list[str] = []

    def wire(request: httpx.Request) -> httpx.Response:
        # A new connection can already see deletion BEFORE the later read responds.
        with Session(customer_engine) as db:
            remaining = list(db.scalars(select(CatalogReceiptRow.id)))
            assert remaining == [preserved]
            assert db.scalar(select(func.count()).select_from(PlanInputRow)) == 1
        observed_committed.append(request.url.host)
        if failure == "native_read" and request.url.host == "googleads.googleapis.com":
            return httpx.Response(503, json={"error": "synthetic_read_failure"})
        return inner.handle_request(request)

    monkeypatch.setattr(
        account_diagnostics, "diagnostic_transport", lambda: httpx.MockTransport(wire)
    )
    try:
        failed = alice.post(root + "/target-catalog-v2", headers=headers(alice), json=query)
    finally:
        inner.close()
    assert "googleads.googleapis.com" in observed_committed
    assert maintenance_calls == [(100, 2)]
    assert failed.status_code == 409, failed.text
    if failure == "capacity":
        assert "storage limit" in failed.json()["detail"]
    after = counts(customer_engine)
    assert after == {
        "planning_catalog_receipts": 1,
        "planning_catalog_receipt_selections": linked_selector_count,
        "planning_input_catalog_receipts": 1,
        "planning_documents": 1,
        "planning_input_revisions": 1,
        "planning_document_versions": 0,
        "provider_execution_attempts": 0,
    }


def test_actual_v2_stale_maintenance_authority_rolls_cleanup_back(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    alice, _, _, calls, root, query, clock = prepare(
        customer_engine, configuration, replicas, monkeypatch
    )
    first = alice.post(root + "/target-catalog-v2", headers=headers(alice), json=query)
    assert first.status_code == 200, first.text
    clock.reach(
        datetime.fromisoformat(first.json()["expires_at"].replace("Z", "+00:00"))
        + timedelta(seconds=1)
    )
    previous = counts(customer_engine)
    previous_calls = len(calls)
    original_monotonic = time.monotonic
    offset = 0.0
    monkeypatch.setattr(
        authority,
        "time",
        SimpleNamespace(time=time.time, monotonic=lambda: original_monotonic() + offset),
    )
    original_cleanup = catalog_receipts.cleanup_expired_unused_receipts
    deleted: list[int] = []

    def cleanup(*args: Any, **kwargs: Any) -> int:
        nonlocal offset
        result = original_cleanup(*args, **kwargs)
        deleted.append(result)
        offset = 5.001
        return result

    monkeypatch.setattr(catalog_runtime, "cleanup_expired_unused_receipts", cleanup)
    denied = alice.post(root + "/target-catalog-v2", headers=headers(alice), json=query)
    assert deleted == [1]
    assert denied.status_code == 409, denied.text
    assert denied.json()["detail"] == "planning_authority_expired"
    assert counts(customer_engine) == previous
    assert len(calls) == previous_calls, "failed maintenance must stop before provider IO"
