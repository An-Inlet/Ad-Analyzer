"""Actual retained receipt discovery, never native reads or spending authority."""

import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from app.api import customer_planning_budget_owners, customer_planning_documents
from app.customers.access import SESSION_COOKIE
from app.lifecycle.privacy import bump_workspace_export_revision
from app.planning_documents import google_budget_owner_discovery as discovery
from app.planning_documents.catalog_receipt_models import CatalogReceiptRow
from app.planning_documents.catalog_receipts import _load
from app.planning_documents.google_budget_owner_discovery_contracts import GoogleBudgetOwnersViewV1
from app.planning_documents.service import PlanningDocumentService
from app.settings import Settings
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from tests.creative_q07_fixture import planning_snapshot
from tests.google_budget_owner_discovery_fixture import acquired_owner_catalog
from tests.test_catalog_receipt_runtime_adverse import counts
from tests.test_creative_common_basis import financial_counts
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import login
from tests.test_customer_identity import replicas as replicas
from tests.test_customer_optimization_api import headers
from tests.test_shopify_sales import configuration as configuration

pytestmark = pytest.mark.planning_boundary


@pytest.mark.parametrize(
    "case",
    [
        "available",
        "partial",
        "window",
        "digest",
        "session",
        "foreign",
        "expired",
        "default",
        "tamper",
        "privacy",
        "csrf",
    ],
)
def test_actual_original_receipt_owner_discovery(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    case: str,
) -> None:
    fixture, catalog, calls = acquired_owner_catalog(
        customer_engine, configuration, replicas, monkeypatch, tmp_path, partial=case == "partial"
    )
    alice, bob, _ = replicas
    for client in (alice, bob):
        client.app.include_router(customer_planning_budget_owners.router)
    url = f"/api/customer/v1/workspaces/{fixture.basis.workspace_id}/planning/google-budget-owners"
    intent = dict(
        account_id=fixture.basis.account_id,
        catalog_composite_digest=catalog["composite_digest"],
        reporting_window=fixture.body["inputs"]["reporting_window"],
    )
    if case == "window":
        intent["reporting_window"] = fixture.body["inputs"]["comparison_window"]
    if case == "digest":
        intent["catalog_composite_digest"] = "0" * 64
    if case == "session":
        login(alice, "q16-owner:replacement")
    if case == "foreign":
        login(bob, "q06-other:one")
    expiry_calls: list[str] = []
    if case == "expired":
        expiry = datetime.fromisoformat(catalog["expires_at"])

        def expired_load(*args: Any, **kwargs: Any) -> Any:
            expiry_calls.append(kwargs["receipt_id"])
            kwargs["now"] = expiry + timedelta(seconds=1)
            return _load(*args, **kwargs)

        monkeypatch.setattr(discovery, "_load", expired_load)
    if case == "privacy":
        with Session(customer_engine) as db:
            bump_workspace_export_revision(db, fixture.basis.workspace_id)
            db.commit()
    if case == "default":
        monkeypatch.setattr(
            customer_planning_documents, "PlanningDocumentService", PlanningDocumentService
        )
    if case == "tamper":
        original_payload = _load

        def corrupt(*args: Any, **kwargs: Any) -> Any:
            row, evidence = original_payload(*args, **kwargs)
            # An unsafe resident copy is rejected by strict owner reconstruction.
            broken = evidence.model_copy(
                update={"reference": evidence.reference.model_copy(update={"source_revision": -1})}
            )
            return row, broken

        monkeypatch.setattr(discovery, "_load", corrupt)
    before = (
        planning_snapshot(customer_engine),
        counts(customer_engine),
        financial_counts(customer_engine),
    )
    native_calls = len(calls)
    client = bob if case == "foreign" else alice
    cookie = client.cookies.get(SESSION_COOKIE)
    response = client.post(url, headers={} if case == "csrf" else headers(client), json=intent)
    if case in {"available", "partial"}:
        assert response.status_code == 200, response.text
        view = GoogleBudgetOwnersViewV1.model_validate(response.json())
        assert view.account_id == fixture.basis.account_id
        assert response.headers["cache-control"] == "no-store"
        if case == "available":
            assert view.status == "available" and len(view.owners) == 1
            owner = view.owners[0]
            assert owner.current_amount_micros == 10_000_000 and owner.currency == "USD"
            assert {t.provider_reference.entity_id for t in owner.affected_campaigns} == {"1", "2"}
            assert owner.representative in owner.affected_campaigns
            assert (
                owner.economic_qualification == "not_assessed"
                and owner.spending_authority == "none"
            )
            assert owner.expires_at.astimezone(UTC) == datetime.fromisoformat(
                catalog["expires_at"]
            ).astimezone(UTC)
        else:
            assert view.status == "unavailable" and view.owners == ()
            assert view.reason == "google_budget_owner_unavailable"
        for label, value in (("catalog", catalog), ("discovery", response.json())):
            path = tmp_path / f"owner-{customer_engine.dialect.name}-{case}-{label}.json"
            path.write_text(json.dumps(value, indent=2), encoding="utf-8")
            path.with_suffix(".sha256").write_text(hashlib.sha256(path.read_bytes()).hexdigest())
        replay = client.post(url, headers=headers(client), json=intent)
        assert replay.status_code == 200 and replay.json() == response.json()
        with Session(customer_engine) as db:
            rows = db.scalars(select(CatalogReceiptRow)).all()
            assert all(row.session_digest not in response.text for row in rows)
    elif case == "csrf":
        assert response.status_code == 403, response.text
    elif case == "foreign":
        assert response.status_code == 404, response.text
    else:
        assert response.status_code == 409, response.text
    if case == "expired":
        assert len(expiry_calls) == 1
        with Session(customer_engine) as db:
            receipt = db.get(CatalogReceiptRow, (fixture.basis.workspace_id, expiry_calls[0]))
            assert (
                receipt is not None
                and receipt.composite_digest == intent["catalog_composite_digest"]
            )
        assert response.json() == {
            "detail": (
                "This budget owner receipt is unavailable. Read fresh targets and review again."
            )
        }
    assert client.cookies.get(SESSION_COOKIE) == cookie
    assert len(calls) == native_calls
    assert (
        planning_snapshot(customer_engine),
        counts(customer_engine),
        financial_counts(customer_engine),
    ) == before


@pytest.mark.parametrize("callback", ["identity", "clock"])
def test_discovery_callback_exception_is_not_receipt_unavailability(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    callback: str,
) -> None:
    fixture, catalog, calls = acquired_owner_catalog(
        customer_engine, configuration, replicas, monkeypatch, tmp_path
    )
    alice, _, provider = replicas
    alice.app.include_router(customer_planning_budget_owners.router)
    original = customer_planning_documents.service

    def fail(*args: Any, **kwargs: Any) -> Any:
        raise ValueError("unexpected test callback")

    def configured(*args: Any, **kwargs: Any) -> Any:
        result = original(*args, **kwargs)
        if callback == "identity":
            monkeypatch.setattr(provider, "check_active", fail)
        else:
            result.clock = fail
        return result

    monkeypatch.setattr(customer_planning_documents, "service", configured)
    before = (
        planning_snapshot(customer_engine),
        counts(customer_engine),
        financial_counts(customer_engine),
        len(calls),
    )
    with pytest.raises(ValueError, match="unexpected test callback"):
        alice.post(
            f"/api/customer/v1/workspaces/{fixture.basis.workspace_id}/planning/google-budget-owners",
            headers=headers(alice),
            json=dict(
                account_id=fixture.basis.account_id,
                catalog_composite_digest=catalog["composite_digest"],
                reporting_window=fixture.body["inputs"]["reporting_window"],
            ),
        )
    assert (
        planning_snapshot(customer_engine),
        counts(customer_engine),
        financial_counts(customer_engine),
        len(calls),
    ) == before
