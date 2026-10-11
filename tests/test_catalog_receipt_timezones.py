"""Offset-aware native receipt storage preserves original payload and UTC instants."""

from datetime import timedelta, timezone
from typing import Any

import pytest
from app.api import customer_planning_documents, customer_planning_target_catalog
from app.planning_documents.catalog_receipt_models import CatalogReceiptRow, InputCatalogReceiptRow
from app.planning_documents.catalog_receipts import (
    CatalogReceiptUnavailable,
    ReceiptPayloadV1,
    validate_retained_receipt,
)
from app.planning_documents.storage import canonical
from app.settings import Settings
from app.shopify.security import utc
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_customer_optimization_api import headers
from tests.test_planning_documents_api import create_body
from tests.test_planning_evidence_adapter import setup_evidence
from tests.test_shopify_sales import configuration as configuration

pytestmark = pytest.mark.planning_boundary


def test_offset_window_receipt_reloads_and_resolves_original_selection(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, ticket, _, calls = setup_evidence(
        customer_engine, configuration, replicas, monkeypatch, "google_ads"
    )
    alice, _, _ = replicas
    alice.app.include_router(customer_planning_target_catalog.router)
    alice.app.include_router(customer_planning_documents.router)
    window = ticket.inputs.reporting_window
    start = window.starts_at.astimezone(timezone(timedelta(hours=-4)))
    end = window.ends_at_exclusive.astimezone(timezone(timedelta(hours=-4)))
    assert start.isoformat().endswith("-04:00") and end.isoformat().endswith("-04:00")
    root = f"/api/customer/v1/workspaces/{ticket.inputs.workspace_id}/planning"
    response = alice.post(
        root + "/target-catalog-v2",
        headers=headers(alice),
        json=dict(
            account_id=ticket.inputs.accounts[0].account_id,
            starts_at=start.isoformat(),
            ends_at=end.isoformat(),
        ),
    )
    assert response.status_code == 200, response.text
    catalog = response.json()
    with Session(customer_engine) as db:
        row = db.scalar(select(CatalogReceiptRow))
        assert row is not None
        original_raw, original_digest = row.canonical_json, row.payload_digest
        db.expire_all()
        row = db.scalar(select(CatalogReceiptRow))
        assert row is not None
        payload, projected = validate_retained_receipt(db, row)
        assert projected.model_dump(mode="json") == catalog
        assert canonical(payload) == row.canonical_json == original_raw
        assert payload.digest() == row.payload_digest == original_digest
        assert ReceiptPayloadV1.model_validate_json(original_raw) == payload
        assert payload.metadata.reporting_starts_at.isoformat() == start.isoformat()
        assert payload.metadata.reporting_ends_at.isoformat() == end.isoformat()
        native = projected.native_observation
        expected = dict(
            reporting_starts_at=utc(start),
            reporting_ends_at=utc(end),
            observation_started_at=min(
                utc(native.observation_started_at), utc(payload.metadata.observation_started_at)
            ),
            observed_at=max(utc(native.observed_at), utc(payload.metadata.observed_at)),
            expires_at=utc(projected.expires_at),
        )
        for field, instant in expected.items():
            assert utc(getattr(row, field)) == instant, field
        assert utc(row.observed_at) <= utc(row.created_at) < utc(row.expires_at)
    target = next(t for t in catalog["targets"] if t["entity"]["kind"] == "campaign")
    body = create_body(ticket.inputs)
    body["inputs"]["reporting_window"] = dict(
        starts_at=start.isoformat(), ends_at_exclusive=end.isoformat()
    )
    body["inputs"]["fixed_allocations"] = [
        dict(
            target=dict(
                account_id=ticket.inputs.accounts[0].account_id,
                canonical_entity_key=target["canonical_entity_key"],
                selection_key=target["selection_key"],
            ),
            amount_micros=0,
        )
    ]
    count = len(calls)
    created = alice.post(root + "/plans", headers=headers(alice), json=body)
    assert created.status_code == 201, created.text
    url = root + "/plans/" + created.json()["plan_id"]
    generated = alice.post(
        url + "/generate",
        headers=headers(alice),
        json=dict(
            request_key="offset-receipt-generation", expected_input_revision=1, expected_version=0
        ),
    )
    assert generated.status_code == 200, generated.text
    assert (
        generated.json()["document"]["inputs"]["fixed_allocations"][0]["target"]["selection_key"]
        == target["selection_key"]
    )
    assert len(calls) == count
    with Session(customer_engine) as db:
        row = db.scalar(select(CatalogReceiptRow))
        assert (
            row is not None
            and row.canonical_json == original_raw
            and row.payload_digest == original_digest
        )
        validate_retained_receipt(db, row)
        assert db.scalar(select(func.count()).select_from(InputCatalogReceiptRow)) == 1

        db.expunge(row)
        row.reporting_starts_at += timedelta(hours=1)
        with pytest.raises(CatalogReceiptUnavailable, match="integrity_unavailable"):
            validate_retained_receipt(db, row)
        assert row.canonical_json == original_raw and row.payload_digest == original_digest
