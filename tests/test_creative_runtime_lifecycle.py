"""Service-produced creative history, replay, export and semantic erasure."""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from app.billing.models import WorkspaceBilling
from app.campaign_review.models import MediaObject
from app.lifecycle.contracts import LifecycleInputV1, LifecycleScopeV1
from app.lifecycle.exports import Authority
from app.lifecycle.privacy import bump_workspace_export_revision
from app.lifecycle.service import begin
from app.planning_documents.models import (
    PlanDependencyRow,
    PlanEventRow,
    PlanInputRow,
    PlanRequestRow,
    PlanRow,
    PlanVersionRow,
)
from app.settings import Settings, settings
from fastapi import HTTPException
from sqlalchemy import Engine, delete, func, select, update
from sqlalchemy.orm import Session

from tests.creative_runtime_fixture import configured
from tests.test_creative_runtime_api import generation
from tests.test_customer_exports import build, unpack
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import login
from tests.test_customer_identity import replicas as replicas
from tests.test_customer_optimization_api import headers
from tests.test_selected_runtime_api import create
from tests.test_shopify_sales import configuration as configuration


def test_actual_media_loss_unpaid_history_archive_and_erasure(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    f, root, body, calls, reader, store = configured(
        customer_engine,
        configuration,
        replicas,
        monkeypatch,
        tmp_path,
    )
    created = f.alice.post(root, headers=headers(f.alice), json=body)
    assert created.status_code == 201, created.text
    url = root + "/" + created.json()["plan_id"]
    response = f.alice.post(url + "/generate", headers=headers(f.alice), json=generation())
    assert response.status_code == 200, response.text
    original = response.json()
    before = len(calls), len(f.calls)
    with Session(customer_engine) as db, db.begin():
        db.execute(delete(MediaObject).where(MediaObject.workspace_id == f.wid))
        db.execute(
            update(WorkspaceBilling)
            .where(WorkspaceBilling.workspace_id == f.wid)
            .values(status="canceled")
        )
    for path in tmp_path.rglob("*"):
        if path.is_file():
            path.unlink()

    def forbidden(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("Replay/history must not inspect current image bytes")

    monkeypatch.setattr(store, "read_exact", forbidden)
    current = f.alice.get(url)
    assert current.status_code == 200 and current.json()["freshness"] == "source_changed", (
        current.text
    )
    assert current.json()["document"] == original["document"]
    view = current.json()
    action = view["document"]["actions"][0]
    decision = f.alice.post(
        url + "/decisions",
        headers=headers(f.alice),
        json={
            "expected_version": 1,
            "expected_event_sequence": 0,
            "document_digest": view["document_digest"],
            "action_key": action["key"],
            "action_digest": view["action_digests"][action["key"]],
            "decision": "accepted_for_manual_application",
            "reason": "Review stale image basis",
            "supersedes_event_id": None,
            "request_key": "creative-stale-decision",
        },
    )
    assert decision.status_code == 409, decision.text
    with Session(customer_engine) as db:
        assert db.scalar(select(func.count()).select_from(PlanEventRow)) == 0
        assert (
            db.scalar(
                select(func.count())
                .select_from(PlanRequestRow)
                .where(PlanRequestRow.operation == "decide")
            )
            == 0
        )
    for suffix in ("/versions/1", "/export?version=1"):
        actual = f.alice.get(url + suffix)
        assert actual.status_code == 200 and actual.json()["document"] == original["document"]
    replay = f.alice.post(url + "/generate", headers=headers(f.alice), json=generation())
    assert replay.status_code == 200 and replay.json() == original
    replay_inputs = f.alice.post(root, headers=headers(f.alice), json=body)
    assert replay_inputs.status_code == 201 and replay_inputs.json() == created.json()
    login(f.bob, "outsider:1")
    assert f.bob.get(url + "/export?version=1").status_code in {403, 404}
    assert f.bob.get(root + "/requests/generate/creative-v5-generate").status_code in {403, 404}
    monkeypatch.setattr(settings, "customer_export_enabled", True)
    with Session(customer_engine) as db:
        request = begin(
            db,
            reader.principal,
            f.provider,
            LifecycleInputV1(scope=LifecycleScopeV1(workspace_id=f.wid), operation="export"),
            "creative-actual-export",
            datetime.now(UTC),
        )
        db.commit()
        authority = Authority(customer_engine, reader.principal, f.provider, f.wid, request.id)
    authority.claim()
    archive, _ = build(customer_engine, authority, store)
    try:
        _, entries = unpack(archive)
        records = [
            json.loads(line)
            for line in entries["data/planning_document_versions.jsonl"].splitlines()
        ]
        assert len(records) == 1 and records[0]["document"] == original["document"]
        dependencies = entries["data/planning_document_dependencies.jsonl"]
        assert b"local_creative_basis_v1" in dependencies
        authority.check()
        with Session(customer_engine) as db, db.begin():
            bump_workspace_export_revision(db, f.wid)
        with Session(customer_engine) as db:
            for model in (PlanRow, PlanInputRow, PlanVersionRow, PlanDependencyRow, PlanRequestRow):
                assert (
                    db.scalar(
                        select(func.count()).select_from(model).where(model.workspace_id == f.wid)
                    )
                    == 0
                )
        assert f.alice.get(url).status_code == 404
        with pytest.raises(HTTPException) as error:
            authority.check()
        assert error.value.status_code == 409
    finally:
        archive.close()
    assert (len(calls), len(f.calls)) == before


def test_actual_creative_input_correction_preserves_original_version(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    f, root, body, _, _, _ = configured(
        customer_engine,
        configuration,
        replicas,
        monkeypatch,
        tmp_path,
    )
    url = create(f, root, body)
    first = f.alice.post(url + "/generate", headers=headers(f.alice), json=generation())
    assert first.status_code == 200, first.text
    original = first.json()
    creative = body["inputs"]["creative"]
    corrected = {**creative, "product": {**creative["product"], "name": "Corrected Test Mug"}}
    edited = f.alice.post(
        url + "/inputs",
        headers=headers(f.alice),
        json={
            **body,
            "request_key": "creative-v5-correction",
            "expected_input_revision": 1,
            "expected_version": 1,
            "inputs": {**body["inputs"], "creative": corrected},
        },
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["input_revision"] == 2
    assert f.alice.get(url).json()["freshness"] == "input_changed"
    successor = f.alice.post(
        url + "/generate",
        headers=headers(f.alice),
        json={
            "expected_input_revision": 2,
            "expected_version": 1,
            "request_key": "creative-v5-successor",
        },
    )
    assert successor.status_code == 200, successor.text
    updated = successor.json()
    assert updated["version"] == 2
    assert updated["document"]["parent_digest"] == original["document_digest"]
    assert updated["document"]["creative_proof"]["basis"]["requested"] == corrected
    assert f.alice.get(url + "/versions/1").json()["document"] == original["document"]
    compared = f.alice.get(url + "/comparisons/1/2")
    assert compared.status_code == 200, compared.text
    assert compared.json()["current_digest"] == updated["document_digest"]
    assert compared.json()["decisions_carried_over"] is False
