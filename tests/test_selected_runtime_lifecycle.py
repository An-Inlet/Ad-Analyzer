"""Actual chosen-capture API generation: immutable history, archives and erasure."""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from app.ads.models import Campaign, DailyMetric
from app.campaign_performance.presence_models import MetricPresenceRow, ReportingSemanticsRow
from app.campaign_performance.range_receipt_models import RangeReceiptRow
from app.campaign_performance.selected_models import (
    CurrentEventSelectionRow,
    EventSelectionRow,
    SelectedCaptureRow,
    SelectedFactRow,
)
from app.campaign_review.storage import LocalMediaStore
from app.lifecycle.contracts import LifecycleInputV1, LifecycleScopeV1
from app.lifecycle.export_serializers import serialize
from app.lifecycle.exports import Authority
from app.lifecycle.privacy import bump_workspace_export_revision
from app.lifecycle.service import begin
from app.planning_documents import repository
from app.planning_documents.documents import PlanVersion
from app.planning_documents.models import (
    PlanDependencyRow,
    PlanInputRow,
    PlanRequestRow,
    PlanRow,
    PlanVersionRow,
)
from app.settings import Settings, settings
from fastapi import HTTPException
from sqlalchemy import Engine, delete, func, select, update
from sqlalchemy.orm import Session

from tests.test_customer_exports import build, unpack
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_customer_optimization_api import headers
from tests.test_selected_runtime_api import configured, create, generation
from tests.test_shopify_sales import configuration as configuration


def generated(engine: Engine, config: Settings, replicas: Any, patch: pytest.MonkeyPatch) -> Any:
    f, root, body, calls, reader = configured(engine, config, replicas, patch)
    url = create(f, root, body)
    response = f.alice.post(url + "/generate", headers=headers(f.alice), json=generation())
    assert response.status_code == 200, response.text
    document = PlanVersion.model_validate(response.json()["document"])
    proof = document.selected_reporting_proof
    assert proof is not None
    account = proof.accounts[0]
    assert account.capture_pin is not None and account.traffic_pin is not None
    assert account.capture_pin.capture_id == body["inputs"]["selected_reporting"][0]["capture_id"]
    assert account.capture_pin.aggregate == account.traffic_pin.aggregate
    current = f.alice.get(url)
    assert current.status_code == 200 and current.json()["freshness"] == "current"
    return f, url, document, reader, calls


def test_actual_chosen_capture_archive_after_refresh_and_semantic_erasure(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    f, url, document, reader, calls = generated(
        customer_engine, configuration, replicas, monkeypatch
    )
    wid, pid = document.inputs.workspace_id, document.inputs.plan_id
    original = document.model_dump(mode="json")
    before_calls = len(calls), len(f.calls)
    with Session(customer_engine) as db, db.begin():
        db.execute(
            update(DailyMetric)
            .where(
                DailyMetric.campaign_id.in_(select(Campaign.id).where(Campaign.account_id == f.aid))
            )
            .values(clicks=DailyMetric.clicks + 1, cost_micros=DailyMetric.cost_micros + 1)
        )
    current = f.alice.get(url)
    assert current.status_code == 200, current.text
    assert current.json()["freshness"] == "source_changed"
    assert current.json()["document"] == original
    with Session(customer_engine) as db:
        row, actual = repository.version(db, repository.owned(db, wid, pid))
        assert actual == document
        values = repository.values(row)
        exported, missing = serialize("planning_document_versions", values, db=db)
        assert not missing and exported["document"] == original
    monkeypatch.setattr(settings, "customer_export_enabled", True)
    with Session(customer_engine) as db:
        request = begin(
            db,
            reader.principal,
            f.provider,
            LifecycleInputV1(scope=LifecycleScopeV1(workspace_id=wid), operation="export"),
            "chosen-capture-export",
            datetime.now(UTC),
        )
        db.commit()
        authority = Authority(customer_engine, reader.principal, f.provider, wid, request.id)
    authority.claim()
    archive, _ = build(customer_engine, authority, LocalMediaStore(tmp_path / "media"))
    try:
        _, entries = unpack(archive)
        records = [
            json.loads(line)
            for line in entries["data/planning_document_versions.jsonl"].splitlines()
        ]
        assert len(records) == 1 and records[0]["document"] == original
        proof = original["selected_reporting_proof"]["accounts"][0]
        assert (
            proof["capture_pin"]["capture_id"].encode()
            in entries["data/selected_reporting_captures.jsonl"]
        )
        assert (
            proof["traffic_pin"]["range_request_id"].encode()
            in entries["data/google_reporting_range_receipts.jsonl"]
        )
        authority.check()
        with Session(customer_engine) as db, db.begin():
            bump_workspace_export_revision(db, wid)
        with Session(customer_engine) as db:
            for model in (
                PlanRow,
                PlanInputRow,
                PlanVersionRow,
                PlanDependencyRow,
                PlanRequestRow,
                EventSelectionRow,
                CurrentEventSelectionRow,
                SelectedCaptureRow,
                SelectedFactRow,
                RangeReceiptRow,
                ReportingSemanticsRow,
                MetricPresenceRow,
            ):
                assert (
                    db.scalar(
                        select(func.count()).select_from(model).where(model.workspace_id == wid)
                    )
                    == 0
                )
            with pytest.raises(ValueError):
                serialize("planning_document_versions", values, db=db)
        assert f.alice.get(url).status_code == 404
        with pytest.raises(HTTPException) as revoked:
            authority.check()
        assert revoked.value.status_code == 409
    finally:
        archive.close()
    assert (len(calls), len(f.calls)) == before_calls


@pytest.mark.parametrize("damage", ["chosen_capture", "range_receipt", "traffic_fact"])
def test_actual_chosen_capture_history_and_export_reject_missing_graph(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    damage: str,
) -> None:
    f, url, document, _, calls = generated(customer_engine, configuration, replicas, monkeypatch)
    proof = document.selected_reporting_proof
    assert proof is not None
    pin, traffic = proof.accounts[0].capture_pin, proof.accounts[0].traffic_pin
    assert pin is not None and traffic is not None
    wid, pid = document.inputs.workspace_id, document.inputs.plan_id
    with Session(customer_engine) as db:
        row, actual = repository.version(db, repository.owned(db, wid, pid))
        assert actual == document
        values = repository.values(row)
    before_calls = len(calls), len(f.calls)
    with Session(customer_engine) as db, db.begin():
        if damage == "chosen_capture":
            db.execute(delete(SelectedCaptureRow).where(SelectedCaptureRow.id == pin.capture_id))
        elif damage == "range_receipt":
            db.execute(
                delete(RangeReceiptRow).where(
                    RangeReceiptRow.request_id == traffic.range_request_id
                )
            )
        else:
            db.execute(
                delete(MetricPresenceRow).where(
                    MetricPresenceRow.completion_id == traffic.aggregate.completion_id
                )
            )
    with Session(customer_engine) as db:
        # Raw graph deletion preserves the saved plan row but cannot make it readable.
        assert db.get(PlanVersionRow, (wid, pid, document.version)) is not None
        with pytest.raises(HTTPException) as rejected:
            repository.version(db, repository.owned(db, wid, pid))
        assert rejected.value.status_code == 409
        with pytest.raises(ValueError):
            serialize("planning_document_versions", values, db=db)
    assert f.alice.get(url).status_code == 409
    assert (len(calls), len(f.calls)) == before_calls
