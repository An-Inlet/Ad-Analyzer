"""Actual owned empty declared Meta query and confirmed zero-budget V5 preparation."""

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest
from app.api import customer_planning_target_catalog
from app.customers.access import SESSION_COOKIE
from app.planning_documents.context import AccountTarget
from app.planning_documents.creative_plan_bundle import CreativePairedEvidenceV1
from app.planning_documents.creative_plan_composer import CreativePlanComposer
from app.planning_documents.documents import PlanVersion
from app.planning_documents.ports import GenerationTicket, PlanningCompositionPolicy
from app.settings import Settings
from sqlalchemy import Engine

from tests.creative_q07_fixture import planning_snapshot
from tests.creative_q08_fixture import prepare_creative_q08_basis
from tests.test_creative_common_basis import financial_counts
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_customer_optimization_api import headers
from tests.test_shopify_sales import configuration as configuration

pytestmark = pytest.mark.planning_boundary


def test_actual_v5_q08_empty_owned_query_zero_goal_preparation(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    fixture = prepare_creative_q08_basis(
        customer_engine, configuration, replicas, monkeypatch, tmp_path / "media"
    )
    alice, _, _ = replicas
    original_session = alice.cookies[SESSION_COOKIE]
    wid, aid = fixture.basis.workspace_id, fixture.basis.account_id
    revision = fixture.basis.goal_revision
    body, calls = fixture.body, fixture.calls
    root = f"/api/customer/v1/workspaces/{wid}"
    alice.app.include_router(customer_planning_target_catalog.router)
    window = body["inputs"]["reporting_window"]
    catalog = alice.post(
        root + "/planning/target-catalog-v2",
        headers=headers(alice),
        json=dict(
            account_id=aid, starts_at=window["starts_at"], ends_at=window["ends_at_exclusive"]
        ),
    )
    assert catalog.status_code == 200, catalog.text
    assert catalog.json()["targets"] == []
    baseline = financial_counts(customer_engine)
    assert baseline == (0,) * 6
    created = alice.post(root + "/planning/plans", headers=headers(alice), json=body)
    assert created.status_code == 201, created.text
    url = root + "/planning/plans/" + created.json()["plan_id"]
    intent = dict(expected_input_revision=1, expected_version=0, request_key="q08-generate-zero")
    result = alice.post(url + "/generate", headers=headers(alice), json=intent)
    assert result.status_code == 200, result.text
    document = result.json()["document"]
    doc = PlanVersion.model_validate(document)
    inputs = document["inputs"]
    definition = inputs["goal"]["definition"]
    assert len(inputs["accounts"]) == 1
    assert inputs["accounts"][0]["account_id"] == aid
    assert inputs["accounts"][0]["platform"] == "meta_ads"
    assert (
        inputs["reporting_window"]
        == body["inputs"]["reporting_window"]
        == dict(
            starts_at="2026-09-01T00:00:00-04:00",
            ends_at_exclusive="2026-10-01T00:00:00-04:00",
        )
    )
    assert (
        inputs["comparison_window"]
        == body["inputs"]["comparison_window"]
        == dict(
            starts_at="2026-08-01T00:00:00-04:00",
            ends_at_exclusive="2026-09-01T00:00:00-04:00",
        )
    )
    assert inputs["goal"]["goal_id"] == fixture.basis.goal_id
    assert definition["store_id"] == fixture.basis.store_id
    assert definition["target_micros"] == 12_000_000_000
    assert definition["metric"] == "shopify_merchandise_net_sales_v1"
    assert definition["budget_micros"] == 0
    assert definition["target_window"] == dict(
        currency="USD",
        time_zone="America/New_York",
        time_basis="calendar_month",
        start="2026-11-01",
        end="2026-12-01",
    )
    assert inputs["creative"] == body["inputs"]["creative"]
    assert inputs["product_offer"] == body["inputs"]["product_offer"]
    assert inputs["creative"]["product"]["name"] == "Reusable travel mug"
    assert inputs["creative"]["product"]["list_price"] == dict(
        micros=25_000_000,
        currency="USD",
        spending_authority="none",
        advertising_writes_enabled=False,
    )
    assert doc.policy_version == "inlet.descriptive-review.v5"
    assert doc.inputs.goal.revision == revision
    assert doc.inputs.total_ceiling_micros == 0
    assert doc.creative_proof is not None and len(doc.creative_proof.basis.images) == 1
    assert doc.creative_proof.basis.images[0].sha256 == fixture.basis.media_sha256
    assert doc.creative_composition is not None
    assert len(doc.creative_composition.proposals) == len(doc.briefs) == 1
    preparation = doc.creative_composition.proposals[0]
    assert preparation.target_basis == "observed_empty_account"
    witness = preparation.empty_catalog_witness
    assert witness is not None
    assert witness.catalog_evidence.catalog.targets == ()
    assert witness.catalog_evidence.catalog.native_observation.targets == ()
    assert witness.catalog_evidence.catalog.metadata_observation.entities == ()
    assert preparation.production.deliverable_status == "production_required"
    assert preparation.production.visual_assessment == "not_assessed"
    assert (
        preparation.production.source_images == doc.creative_proof.basis.requested.media_selections
    )
    assert len(doc.actions) == 2
    action = next(a for a in doc.actions if a.kind == "investigate")
    assert preparation.action.prerequisites == (action.key,) == (witness.prerequisite_action_key,)
    assert preparation.action.target == action.target == preparation.brief.target
    assert witness.catalog_evidence.reference in doc.evidence
    assert witness.catalog_evidence.reference.account == action.target.account
    assert doc.inputs.goal.confirmation_reference == fixture.basis.confirmation_id
    assert isinstance(action.target, AccountTarget)
    assert (action.target.account.workspace_id, action.target.account.account_id) == (wid, aid)
    assert (
        action.kind == "investigate" and action.native_budget is None and not action.proposed_fields
    )
    assert "No included native campaign" in action.rationale
    assert "do not replace absent events with zero" in " ".join(action.manual_steps)
    assert all(ref.kind != "reported_metrics" for ref in doc.evidence)
    assert doc.selected_reporting_proof is not None
    assert all(p.capture_pin is None for p in doc.selected_reporting_proof.accounts)
    assert doc.scenarios
    for scenario in doc.scenarios:
        assert scenario.ceiling_micros == scenario.unallocated_micros == 0
        assert scenario.allocations == () and scenario.forecast is None
    assert doc.spending_authority == "none" and not doc.advertising_writes_enabled
    count = len(calls)
    assert count > 0
    replay = alice.post(url + "/generate", headers=headers(alice), json=intent)
    assert replay.status_code == 200 and replay.json() == result.json(), replay.text
    current = alice.get(url)
    assert current.status_code == 200 and current.json()["document"] == document, current.text
    assert current.json()["freshness"] == "current"
    exported = alice.get(url + "/export?version=1")
    assert exported.status_code == 200 and exported.json()["document"] == document, exported.text
    assert exported.json()["document_digest"] == doc.digest()
    assert len(calls) == count and financial_counts(customer_engine) == baseline
    assert alice.cookies[SESSION_COOKIE] == original_session
    prefix = f"q08-runtime-{customer_engine.dialect.name}"
    manifest = {}
    for label, payload in (
        ("catalog", catalog.json()),
        ("document", document),
        ("export", exported.json()),
    ):
        path = tmp_path / f"{prefix}-{label}.json"
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        manifest[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    (tmp_path / f"{prefix}-manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )


def test_actual_q08_save_rejects_substituted_valid_empty_witness(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    fixture = prepare_creative_q08_basis(
        customer_engine, configuration, replicas, monkeypatch, tmp_path / "media"
    )
    alice, _, _ = replicas
    cookie = alice.cookies[SESSION_COOKIE]
    root = f"/api/customer/v1/workspaces/{fixture.basis.workspace_id}/planning/plans"
    created = alice.post(root, headers=headers(alice), json=fixture.body)
    assert created.status_code == 201, created.text
    before = planning_snapshot(customer_engine)
    effects = financial_counts(customer_engine)
    assert effects == (0,) * 6
    original = CreativePlanComposer.compose
    validated: list[bool] = []

    def substitute(
        self: CreativePlanComposer,
        *,
        ticket: GenerationTicket,
        evidence: CreativePairedEvidenceV1,
        policy: PlanningCompositionPolicy,
        generated_at: datetime,
    ) -> PlanVersion:
        candidate = original(
            self, ticket=ticket, evidence=evidence, policy=policy, generated_at=generated_at
        )
        raw = candidate.model_dump(mode="python")
        embedded = raw["creative_composition"]["proposals"][0]["empty_catalog_witness"]
        native = embedded["catalog_evidence"]["catalog"]["native_observation"]
        assert native["currency"] == "USD"
        native["currency"] = "EUR"
        changed = PlanVersion.model_validate(raw)
        # The only changed field is in the returned candidate, never the actual evidence.
        native["currency"] = "USD"
        assert raw == candidate.model_dump(mode="python")
        assert evidence.reporting.selected.catalogs[0].catalog.native_observation.currency == "USD"
        validated.append(True)
        return changed

    monkeypatch.setattr(CreativePlanComposer, "compose", substitute)
    response = alice.post(
        root + "/" + created.json()["plan_id"] + "/generate",
        headers=headers(alice),
        json=dict(expected_input_revision=1, expected_version=0, request_key="q08-invalid-witness"),
    )
    assert validated == [True]
    assert response.status_code == 409, response.text
    assert response.json() == {
        "detail": "empty catalog witness differs from actual collected evidence"
    }
    assert planning_snapshot(customer_engine) == before
    assert financial_counts(customer_engine) == effects
    assert alice.cookies[SESSION_COOKIE] == cookie
