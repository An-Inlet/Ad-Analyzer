"""Actual configured creative-proposal decision; not a generic plan-action substitute."""

import json
from pathlib import Path
from typing import Any

import pytest
from app.api import customer_planning_documents as api
from app.campaign_review.storage import get_media_store
from app.main import app
from app.planning_documents.documents import PlanVersion
from app.planning_documents.events import CustomerDecision
from app.planning_documents.models import PlanEventRow, PlanRequestRow, PlanRow
from app.planning_documents.service import PlanningDocumentService
from app.settings import Settings
from fastapi.testclient import TestClient
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from tests.creative_common_basis_fixture import prepare_creative_common_basis
from tests.test_creative_common_basis import financial_counts
from tests.test_creative_runtime_api import generation
from tests.test_creative_runtime_composition import media_config
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_customer_optimization_api import headers
from tests.test_shopify_sales import configuration as configuration


def test_exact_creative_proposal_manual_decision(
    customer_engine: Engine, configuration: Settings, replicas: Any,
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    media_config(monkeypatch, tmp_path / "media")
    f = prepare_creative_common_basis(
        customer_engine, configuration, replicas, monkeypatch, tmp_path / "media",
        platform="meta_ads", configured_runtime=True,
    )
    original = replicas[0]
    monkeypatch.setattr(app, "dependency_overrides", dict(original.app.dependency_overrides))
    assert get_media_store not in app.dependency_overrides
    assert vars(api)["PlanningDocumentService"] is PlanningDocumentService
    alice = TestClient(app, base_url=str(original.base_url))
    alice.cookies.update(original.cookies)
    root = f"/api/customer/v1/workspaces/{f.basis.workspace_id}/planning/plans"
    made = alice.post(root, headers=headers(alice), json=f.body)
    assert made.status_code == 201, made.text
    url = root + "/" + made.json()["plan_id"]
    generated = alice.post(url + "/generate", headers=headers(alice), json=generation())
    assert generated.status_code == 200, generated.text
    current = alice.get(url)
    assert current.status_code == 200, current.text
    view = current.json()
    doc = PlanVersion.model_validate(view["document"])
    assert doc.digest() == view["document_digest"]
    assert doc.policy_version == "inlet.descriptive-review.v5"
    assert doc.creative_composition and len(doc.creative_composition.proposals) == 1
    proposal = doc.creative_composition.proposals[0]
    assert proposal.production.deliverable_status == "production_required"
    assert proposal.production.visual_assessment == "not_assessed"
    assert proposal.action == next(a for a in doc.actions if a.key == proposal.action.key)
    assert "unsupported_selected_mapping" in doc.model_dump_json()
    intent = dict(
        expected_version=1, expected_event_sequence=0, document_digest=doc.digest(),
        action_key=proposal.action.key, action_digest=view["action_digests"][proposal.action.key],
        decision="accepted_for_manual_application", reason="Review this exact creative brief",
        supersedes_event_id=None, request_key="configured-creative-proposal",
    )
    counts, calls = financial_counts(customer_engine), list(f.calls)
    wrong = alice.post(url + "/decisions", headers=headers(alice), json={
        **intent, "action_digest": "0" * 64, "request_key": "configured-creative-wrong"
    })
    assert wrong.status_code == 409, wrong.text
    assert wrong.json() == {"detail": "plan version or action binding changed"}
    with Session(customer_engine) as db:
        plan = db.get(PlanRow, (f.basis.workspace_id, doc.inputs.plan_id))
        assert plan and (plan.input_head, plan.version_head, plan.event_sequence) == (1, 1, 0)
        assert db.scalar(select(func.count()).select_from(PlanEventRow)) == 0
        assert db.scalar(select(func.count()).select_from(PlanRequestRow).where(
            PlanRequestRow.operation == "decide"
        )) == 0
    accepted = alice.post(url + "/decisions", headers=headers(alice), json=intent)
    assert accepted.status_code == 200, accepted.text
    event = accepted.json()["event"]
    CustomerDecision.model_validate(event).assert_document(doc)
    assert event["actor_id"] == doc.generated_by
    assert accepted.json()["event_sequence"] == 1
    assert event["action_key"] == proposal.action.key
    assert event["action_digest"] == intent["action_digest"]
    assert event["decision"] == "accepted_for_manual_application"
    assert event["advertising_writes_enabled"] is False and event["spending_authority"] == "none"
    replay = alice.post(url + "/decisions", headers=headers(alice), json=intent)
    assert replay.status_code == 200 and replay.json() == accepted.json()
    exported = alice.get(url + "/export?version=1")
    assert exported.status_code == 200 and exported.json()["document"] == view["document"]
    assert financial_counts(customer_engine) == counts and f.calls == calls
    with Session(customer_engine) as db:
        plan = db.get(PlanRow, (f.basis.workspace_id, doc.inputs.plan_id))
        assert plan and (plan.input_head, plan.version_head, plan.event_sequence) == (1, 1, 1)
        assert db.scalar(select(func.count()).select_from(PlanEventRow)) == 1
        assert db.scalar(select(func.count()).select_from(PlanRequestRow).where(
            PlanRequestRow.operation == "decide"
        )) == 1
    (tmp_path / "configured-creative-proposal-review.json").write_text(json.dumps(dict(
        document=view["document"], document_digest=doc.digest(),
        decision=accepted.json(), rejected_digest_status=wrong.status_code,
    ), indent=2))
