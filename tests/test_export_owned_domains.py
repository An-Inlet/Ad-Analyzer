"""Actual mocked execution and commerce receipts enter the owned archive."""

import json
from copy import deepcopy
from pathlib import Path

import pytest
from app.customers.models import CustomerMembership
from app.lifecycle.contracts import LifecycleInputV1, LifecycleScopeV1
from app.lifecycle.export_serializers import serialize
from app.lifecycle.exports import SLOTS, Authority, Download
from app.lifecycle.service import begin
from app.outcomes import owned
from app.outcomes.models import ActionOutcomeAssessment
from app.publication import activation as activation
from app.publication import activation_review as reviews
from app.publication import coordinator, settlement
from app.publication.service import owner
from app.settings import Settings
from app.shopify.privacy import process_event
from fastapi import HTTPException
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from tests.test_activation_coordinator import runtime_for
from tests.test_activation_review import activation_ready
from tests.test_commerce_measurement import NOW as PROVIDER_NOW
from tests.test_customer_exports import build, unpack
from tests.test_customer_exports import export_engine as export_engine
from tests.test_customer_identity import FakeProvider
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_lifecycle import NOW, seed
from tests.test_google_activation import Server
from tests.test_owned_outcomes import evidence
from tests.test_provider_settlement import qualified
from tests.test_shopify_sales import SHOP
from tests.test_shopify_sales import configuration as configuration


def authorize_export(db: Session, engine: Engine, wid: int) -> Authority:
    principal, _ = seed(db, "archive-owner")
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
        "owned-domain-archive-key",
        NOW,
    )
    db.commit()
    return Authority(engine, principal, FakeProvider(), wid, request.id)


def test_create_activate_settle_then_export_actual_owned_records(
    export_engine: Engine, configuration: Settings, tmp_path: Path
) -> None:
    with Session(export_engine) as db:
        server = Server()
        wid, parent, actor, store, review, binding = activation_ready(
            db, configuration, tmp_path, server
        )
        row = reviews.prepare_activation(
            db, wid, parent, binding, actor, store, review, lambda: PROVIDER_NOW
        )
        reviews.approve_activation(
            db, wid, row.id, row.digest, row.plan_digest, actor, store, review, lambda: PROVIDER_NOW
        )
        run = reviews.create_run(db, wid, row.id, actor, store, review, lambda: PROVIDER_NOW)
        runtime = runtime_for(review, server)
        while claim := activation.claim_step(
            db, wid, run.id, actor, store, runtime, lambda: PROVIDER_NOW
        ):
            assert (
                activation.execute_claim(
                    db, claim, actor, store, runtime, lambda: PROVIDER_NOW
                ).outcome
                == "verified_target_state"
            )
        assert run.reservation_id is not None
        coordinator.cancel_creation(db, wid, run.id, actor, lambda: PROVIDER_NOW)
        coordinator.cancel_creation(db, wid, parent, actor, lambda: PROVIDER_NOW)
        settled = settlement.settle(
            db,
            wid,
            run.reservation_id,
            actor,
            settlement.SettlementRuntime("contract_test", qualified),
            lambda: PROVIDER_NOW,
        )
        assert settled.state == "settled"
        authority = authorize_export(db, export_engine, wid)
    authority.claim()
    file, manifest = build(export_engine, authority, store)
    try:
        _, entries = unpack(file)
        assert manifest["supported_customer_data_complete"], [
            s for s in manifest["sections"] if not s["complete"]
        ]
        rows = [
            json.loads(line)
            for line in entries["data/provider_execution_reviews.jsonl"].splitlines()
        ]
        assert {row["document"]["purpose"] for row in rows} == {"create_paused", "activate"}
        assert b'"target":' in entries["data/provider_execution_attempts.jsonl"]
        assert b"verified_target_state" in entries["data/provider_execution_receipts.jsonl"]
        assert (
            b"inlet.provider-settlement.v1" in entries["data/provider_exposure_reservations.jsonl"]
        )
        assert b"qualified_terminal" in entries["data/provider_exposure_reservations.jsonl"]
        assert b"access_token" not in b"".join(entries.values())
        responses = [
            json.loads(line)
            for line in entries["data/provider_execution_responses.jsonl"].splitlines()
        ]
        response = next(item for item in responses if "resource_name" not in item["response"])
        response["digest"] = "f" * 64
        projected, missing = serialize("provider_execution_responses", response)
        assert "response" not in projected and "response" in missing
        for table, field in [
            ("provider_execution_reviews", "document"),
            ("provider_execution_attempts", "request"),
            ("provider_execution_receipts", "receipt"),
            ("provider_exposure_reservations", "settled_evidence"),
        ]:
            candidates = [json.loads(line) for line in entries[f"data/{table}.jsonl"].splitlines()]
            candidate = next(
                row
                for row in candidates
                if row[field] is not None
                and (
                    table == "provider_exposure_reservations"
                    or row[field].get("purpose") == "activate"
                    or "target" in row[field]
                    or row[field].get("outcome") == "verified_target_state"
                )
            )
            foreign = deepcopy(candidate)
            foreign["workspace_id"] += 100
            projected, missing = serialize(table, foreign)
            assert field not in projected and field in missing
            raw = deepcopy(candidate)
            raw[field]["raw_provider_body"] = {"private": "must-not-export"}
            projected, missing = serialize(table, raw)
            assert field not in projected and field in missing

    finally:
        file.close()


def test_owned_assessment_export_preserves_insufficient_not_lift(
    export_engine: Engine, configuration: Settings, tmp_path: Path
) -> None:
    from app.campaign_review.storage import LocalMediaStore

    with Session(export_engine) as db:
        wid, actor, body, _, _ = evidence(db, configuration, tmp_path)
        row = owned.create(
            db, wid, actor, body, lambda: owner(db, wid, actor), lambda: PROVIDER_NOW
        )
        db.commit()
        expected = row.assessment
        authority = authorize_export(db, export_engine, wid)
    authority.claim()
    file, manifest = build(export_engine, authority, LocalMediaStore(tmp_path))
    try:
        _, entries = unpack(file)
        assert manifest["supported_customer_data_complete"], [
            s for s in manifest["sections"] if not s["complete"]
        ]
        rows = [
            json.loads(line)
            for line in entries["data/action_outcome_assessments.jsonl"].splitlines()
        ]
        assert len(rows) == 1 and rows[0]["assessment"] == expected
        assert rows[0]["assessment"]["status"] == "insufficient"
        assert rows[0]["assessment"]["causal_lift"] is None
        assert rows[0]["assessment"]["spending_authority"] == "none"
        for field, value in [
            ("workspace_id", wid + 100),
            ("publication_id", "f" * 32),
            ("assessment_digest", "f" * 64),
            ("receipt_sequence", 999),
        ]:
            foreign = deepcopy(rows[0])
            foreign[field] = value
            projected, missing = serialize("action_outcome_assessments", foreign)
            assert "assessment" not in projected and "assessment" in missing
        for key, value in [
            ("status", "success"),
            ("schema_version", "future.v3"),
            ("raw_body", "private"),
            ("causal_lift", "100"),
        ]:
            unsafe = deepcopy(rows[0])
            unsafe["assessment"][key] = value
            projected, missing = serialize("action_outcome_assessments", unsafe)
            assert "assessment" not in projected and "assessment" in missing

        oversized = deepcopy(rows[0])
        oversized["assessment"]["before"]["value"] = "1" * (256 * 1024)
        projected, missing = serialize("action_outcome_assessments", oversized)
        assert "assessment" not in projected and "assessment" in missing
        # Even an already-built archive must stop after the actual source erasure
        # cascades through the owned assessment and advances the privacy revision.
        authority.finish(manifest)
        assert SLOTS.acquire(blocking=False)
        download = Download(file, authority)
        chunks = download.chunks()
        assert next(chunks)
        with Session(export_engine) as db:
            process_event(db, configuration, "orders/delete", SHOP, {"id": 1}, NOW)
            assert db.scalar(select(func.count()).select_from(ActionOutcomeAssessment)) == 0
        with pytest.raises(HTTPException, match="invalidated"):
            next(chunks)
        assert file.closed
    finally:
        file.close()
