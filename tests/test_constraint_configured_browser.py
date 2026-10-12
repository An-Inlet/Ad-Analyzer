"""Real configured v7 HTTPS editor/controller; local SQL, synthetic identity/providers."""

import json
from pathlib import Path
from typing import Any

import pytest
from app.api import customer_planning_documents as api
from app.campaign_review.storage import get_media_store
from app.main import app
from app.planning_documents.documents import PlanVersion
from app.planning_documents.models import PlanEventRow, PlanRequestRow, PlanRow
from app.planning_documents.service import PlanningDocumentService
from app.settings import Settings
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from tests import test_creative_planning_browser as browser
from tests.test_creative_runtime_composition import media_config
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_planning_runtime_composition import configure
from tests.test_shopify_sales import configuration as configuration


def test_configured_constraint_customer_workflow(
    customer_engine: Engine,
    request: pytest.FixtureRequest,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    media_config(monkeypatch, tmp_path / "media")
    configure(monkeypatch, "v7")
    browser.test_actual_creative_planning_browser(
        customer_engine, request, configuration, replicas, monkeypatch, tmp_path,
        "q10", "meta_ads", configured_runtime=True,
    )
    assert vars(api)["PlanningDocumentService"] is PlanningDocumentService
    assert get_media_store not in app.dependency_overrides
    result = json.loads((tmp_path / "creative-browser-result.json").read_text())
    versions = result["retained_versions"]
    assert len(versions) == 2 and len(result["browser"]["mutations"]) == 5
    by_version = {item["document"]["version"]: item for item in versions}
    for item in versions + result["browser"]["exported"]:
        doc = PlanVersion.model_validate(item["document"])
        assert doc.digest() == item["document_digest"]
        assert doc.policy_version == "inlet.descriptive-review.v7"
        assert doc.generator_version == "inlet.descriptive-planning.v7"
        assert doc.schema_version == "inlet.plan-version.v4"
        assert item["document"] == by_version[doc.version]["document"]
        assert doc.constraint_interpretation is not None
        assert doc.constraint_interpretation.disposition == (
            "fully_recognized" if doc.version == 1 else "unresolved"
        )
        assert len(doc.briefs) == (1 if doc.version == 1 else 0)
        assert doc.inputs.total_ceiling_micros == 1_000_000_000
        assert doc.inputs.fixed_allocations[0].amount_micros == 200_000_000
        assert not doc.advertising_writes_enabled and doc.spending_authority == "none"
    assert by_version[2]["document"]["parent_digest"] == by_version[1]["document_digest"]
    assert result["browser"]["stale_workspace_rejected"]
    assert result["browser"]["stale_session_rejected"]
    first = PlanVersion.model_validate(by_version[1]["document"])
    assert first.creative_composition is not None
    action = first.creative_composition.proposals[0].action
    with Session(customer_engine) as db:
        plans = db.scalars(select(PlanRow).where(
            PlanRow.workspace_id == first.inputs.workspace_id
        )).all()
        assert len(plans) == 1 and plans[0].id == first.inputs.plan_id
        events = db.scalars(select(PlanEventRow).where(
            PlanEventRow.workspace_id == first.inputs.workspace_id,
            PlanEventRow.plan_id == first.inputs.plan_id,
        )).all()
        assert len(events) == 1
        event = events[0]
        assert event.kind == "decision" and event.version == 1 and event.sequence == 1
        assert event.action_key == action.key and event.action_digest == action.digest()
        stored_event = json.loads(event.canonical_json)
        assert stored_event["document_digest"] == first.digest()
        assert stored_event["decision"] == "deferred"
        receipts = db.scalars(select(PlanRequestRow).where(
            PlanRequestRow.workspace_id == first.inputs.workspace_id,
            PlanRequestRow.plan_id == first.inputs.plan_id,
        )).all()
        expected = set()
        for mutation in result["browser"]["mutations"]:
            tail = mutation["url"].rsplit("/", 1)[-1]
            operation = {"plans": "create", "inputs": "revise", "decisions": "decide",
                         "generate": "generate"}[tail]
            expected.add((operation, mutation["body"]["request_key"]))
        assert len(receipts) == len(expected) == 5
        assert {(r.operation, r.request_key) for r in receipts} == expected
        assert sorted(r.version or 0 for r in receipts if r.operation == "generate") == [1, 2]
        assert [r.event_sequence for r in receipts if r.operation == "decide"] == [1]
        assert sorted(r.input_revision or 0 for r in receipts if r.result_kind == "input") == [1, 2]
    assert result["browser"]["stale_export_not_downloaded"]
