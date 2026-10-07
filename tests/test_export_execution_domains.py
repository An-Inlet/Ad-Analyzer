"""Export real owned coordinator records through strict versioned serializers."""

from pathlib import Path

import pytest
from app.customers.models import CustomerMembership
from app.lifecycle.contracts import LifecycleInputV1, LifecycleScopeV1
from app.lifecycle.exports import Authority
from app.lifecycle.service import begin
from app.publication import coordinator
from app.settings import Settings
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from tests.test_commerce_measurement import NOW as PROVIDER_NOW
from tests.test_customer_exports import build, unpack
from tests.test_customer_exports import export_engine as export_engine
from tests.test_customer_identity import FakeProvider
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_lifecycle import NOW, seed
from tests.test_provider_coordinator import GoogleServer, ready
from tests.test_shopify_sales import configuration as configuration


def test_owned_execution_json_export_is_complete_and_strict(
    export_engine: Engine, configuration: Settings, tmp_path: Path
) -> None:
    with Session(export_engine) as db:
        wid, run_id, actor, store, runtime = ready(db, configuration, tmp_path, GoogleServer())
        claim = coordinator.claim_creation_step(
            db, wid, run_id, actor, store, runtime, lambda: PROVIDER_NOW
        )
        assert claim is not None
        receipt = coordinator.execute_claim(db, claim, actor, store, runtime, lambda: PROVIDER_NOW)
        assert receipt.outcome == "verified_effect"
        principal, _ = seed(db, "exporting-owner")
        db.add(
            CustomerMembership(
                user_id=principal.user.id, workspace_id=wid, role="owner", status="active"
            )
        )
        db.commit()
        request = begin(
            db,
            principal,
            FakeProvider(),
            LifecycleInputV1(scope=LifecycleScopeV1(workspace_id=wid), operation="export"),
            "coordinator-export-request",
            NOW,
        )
        db.commit()
        authority = Authority(export_engine, principal, FakeProvider(), wid, request.id)
    authority.claim()
    file, manifest = build(export_engine, authority, store)
    try:
        _, entries = unpack(file)
        assert manifest["supported_customer_data_complete"], [
            s for s in manifest["sections"] if not s["complete"]
        ]
        for table, field in {
            "provider_execution_revisions": "policy",
            "provider_execution_reviews": "document",
            "provider_execution_attempts": "request",
            "provider_execution_responses": "response",
            "provider_execution_receipts": "projection",
            "provider_exposure_reservations": "evidence",
        }.items():
            assert f'"{field}":'.encode() in entries[f"data/{table}.jsonl"]
        assert (
            b"inlet.provider-receipt-projection.v1"
            in entries["data/provider_execution_receipts.jsonl"]
        )
        assert b"access_token" not in b"".join(entries.values())
    finally:
        file.close()


@pytest.mark.parametrize(
    "table,field",
    [
        ("action_outcome_assessments", "assessment"),
        ("provider_execution_revisions", "policy"),
        ("provider_execution_reviews", "document"),
        ("provider_execution_attempts", "request"),
        ("provider_execution_responses", "response"),
        ("provider_execution_receipts", "receipt"),
        ("provider_execution_receipts", "projection"),
        ("provider_exposure_reservations", "evidence"),
        ("provider_exposure_reservations", "settled_evidence"),
    ],
)
def test_future_or_raw_execution_json_is_reported_unsupported(table: str, field: str) -> None:
    from app.lifecycle.export_serializers import fields, serialize

    row = dict.fromkeys(fields(table))
    row[field] = {"schema_version": "future.unreviewed.v9", "raw_body": "not-exportable"}
    result, missing = serialize(table, row)
    assert field not in result and field in missing
