"""Actual Q10 constraints join; global freeform constraints remain a known deferral."""

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
from app.api import customer_planning_target_catalog
from app.customers.access import SESSION_COOKIE
from app.planning_documents.context import TargetRef
from app.planning_documents.documents import PlanVersion
from app.settings import Settings
from sqlalchemy import Engine

from tests.creative_common_basis_fixture import CreativeCommonBasis, prepare_creative_common_basis
from tests.test_creative_common_basis import financial_counts
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_customer_optimization_api import headers
from tests.test_shopify_sales import configuration as configuration

pytestmark = pytest.mark.planning_boundary
RESTRICTIONS = ["No approved health claims or testimonials.", "No discount claims."]


def _prepare(
    engine: Engine,
    config: Settings,
    replicas: Any,
    patch: pytest.MonkeyPatch,
    path: Path,
    *,
    global_constraint: bool,
) -> tuple[CreativeCommonBasis, dict[str, Any], list[dict[str, Any]]]:
    fixture = prepare_creative_common_basis(
        engine, config, replicas, patch, path, platform="meta_ads"
    )
    alice, _, _ = replicas
    alice.app.include_router(customer_planning_target_catalog.router)
    body = copy.deepcopy(fixture.body)
    inputs = body["inputs"]
    window = inputs["reporting_window"]
    response = alice.post(
        f"/api/customer/v1/workspaces/{fixture.basis.workspace_id}/planning/target-catalog-v2",
        headers=headers(alice),
        json=dict(
            account_id=fixture.basis.account_id,
            starts_at=window["starts_at"],
            ends_at=window["ends_at_exclusive"],
        ),
    )
    assert response.status_code == 200, response.text
    targets = response.json()["targets"]
    campaigns = {
        t["entity"]["reference"]["entity_id"]: t
        for t in targets
        if t["entity"]["kind"] == "campaign"
    }
    assert set(campaigns) == {"5", "7"}

    def selector(native_id: str) -> dict[str, Any]:
        target = campaigns[native_id]
        return dict(
            account_id=fixture.basis.account_id,
            canonical_entity_key=target["canonical_entity_key"],
            selection_key=target["selection_key"],
        )

    assert inputs["constraints"] == inputs["exclusions"] == inputs["fixed_allocations"] == []
    inputs["exclusions"] = [selector("5")]
    inputs["fixed_allocations"] = [dict(target=selector("7"), amount_micros=200_000_000)]
    inputs["maximum_creative_assets"] = 1
    inputs["creative"]["product"]["restrictions"] = RESTRICTIONS.copy()
    if global_constraint:
        inputs["constraints"] = ["No discount claims."]
    return fixture, body, targets


@pytest.mark.parametrize(
    "global_constraint", [False, True], ids=["typed-product", "global-deferred"]
)
def test_actual_v5_q10_exclusion_fixed_capacity_and_restrictions(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    global_constraint: bool,
) -> None:
    fixture, body, targets = _prepare(
        customer_engine,
        configuration,
        replicas,
        monkeypatch,
        tmp_path / "media",
        global_constraint=global_constraint,
    )
    alice, _, _ = replicas
    cookie = alice.cookies[SESSION_COOKIE]
    baseline = financial_counts(customer_engine)
    assert baseline == (0,) * 6
    root = f"/api/customer/v1/workspaces/{fixture.basis.workspace_id}/planning/plans"
    created = alice.post(root, headers=headers(alice), json=body)
    assert created.status_code == 201, created.text
    url = root + "/" + created.json()["plan_id"]
    request = dict(expected_input_revision=1, expected_version=0, request_key="creative-q10-v5")
    generated = alice.post(url + "/generate", headers=headers(alice), json=request)
    assert generated.status_code == 200, generated.text
    document = generated.json()["document"]
    doc = PlanVersion.model_validate(document)
    assert doc.policy_version == "inlet.descriptive-review.v5"
    assert doc.inputs.creative is not None and doc.inputs.creative.product is not None
    assert doc.inputs.creative.product.restrictions == tuple(RESTRICTIONS)
    assert doc.inputs.maximum_creative_assets == 1
    assert doc.inputs.total_ceiling_micros == 1_000_000_000
    assert len(doc.inputs.fixed_allocations) == 1
    fixed = doc.inputs.fixed_allocations[0]
    assert fixed.amount_micros == 200_000_000
    assert fixed.target.provider_reference.entity_id == "7"
    assert fixed.target.account.workspace_id == fixture.basis.workspace_id
    assert fixed.target.account.account_id == fixture.basis.account_id
    assert fixed.target.account.platform == "meta_ads"
    assert fixed.target.provider_reference.advertiser_id == "123"
    assert doc.inputs.constraints == tuple(body["inputs"]["constraints"])
    assert doc.inputs.excluded_entity_keys == (
        body["inputs"]["exclusions"][0]["canonical_entity_key"],
    )
    forbidden_keys = {
        target["canonical_entity_key"]
        for target in targets
        if target["entity"]["reference"]["entity_id"] == "5"
        or target["entity"]["reference"].get("parent_campaign_id") == "5"
    }
    assert len(forbidden_keys) == 2  # A and its observed child, not display-name matching.

    def allowed(target: Any) -> None:
        assert target.account == fixed.target.account
        if isinstance(target, TargetRef):
            assert target.canonical_entity_key not in forbidden_keys
            ref = target.provider_reference
            assert ref.platform == "meta_ads"
            assert ref.advertiser_id == fixed.target.provider_reference.advertiser_id
            assert ref.entity_id != "5" and ref.parent_campaign_id != "5"

    composition = doc.creative_composition
    proof = doc.creative_proof
    assert composition is not None and proof is not None
    assert len(proof.images) == 1
    assert proof.basis.requested == doc.inputs.creative
    assert proof.basis.images[0].sha256 == fixture.basis.media_sha256
    assert len(composition.proposals) <= 1 and len(doc.briefs) <= 1
    for action in doc.actions:
        allowed(action.target)
        assert action.native_budget is None and not action.proposed_fields
    for brief in doc.briefs:
        allowed(brief.target)
    for scenario in doc.scenarios:
        assert scenario.forecast is None and scenario.native_conversion == "not_assessed"
        assert len(scenario.allocations) == 1
        allocation = scenario.allocations[0]
        allowed(allocation.target)
        assert allocation.target == fixed.target
        assert allocation.amount_micros == 200_000_000
        assert scenario.unallocated_micros == 800_000_000
        assert scenario.ceiling_micros == 1_000_000_000
        assert scenario.semantics == "independent_alternative"
        assert (
            sum(item.amount_micros for item in scenario.allocations) + scenario.unallocated_micros
            == scenario.ceiling_micros
        )
    assert doc.scenarios
    if global_constraint:
        assert composition.proposals == () and doc.briefs == ()
        assert any("constraint" in text.lower() for text in composition.limitations)
    else:
        assert len(composition.proposals) == len(doc.briefs) == 1
    for proposal in composition.proposals:
        allowed(proposal.action.target)
        allowed(proposal.brief.target)
        assert proposal.production.selected_image_id == fixture.basis.media_id
        assert proposal.production.deliverable == "image_creative"
        assert proposal.production.deliverable_status == "production_required"
        assert proposal.brief.product_facts == ("Customer-declared product: Reusable travel mug",)
        assert proposal.brief.hooks == ("Meet Reusable travel mug.",)
        assert proposal.brief.offer == (
            "Reusable travel mug; customer-supplied list price 25 USD; verify the current offer."
        )
        assert proposal.brief.copy_directions == (
            "Use only customer-declared substantiated facts and verify the offer.",
            "Customer restrictions (verbatim):\n" + "\n".join(RESTRICTIONS),
        )
        assert "visual suitability and rights are not assessed" in " ".join(
            proposal.brief.visual_directions
        )
        assert proposal.production.storyboard == ()
        assert proposal.production.visual_assessment == "not_assessed"
        for restriction in RESTRICTIONS:
            assert restriction in proposal.model_dump_json()
    assert doc.spending_authority == "none" and not doc.advertising_writes_enabled
    assert financial_counts(customer_engine) == baseline
    native_count = len(fixture.calls)
    assert native_count > 0
    replay = alice.post(url + "/generate", headers=headers(alice), json=request)
    assert replay.status_code == 200 and replay.json() == generated.json(), replay.text
    current = alice.get(url)
    assert current.status_code == 200 and current.json()["document"] == document, current.text
    assert current.json()["freshness"] == "current"
    exported = alice.get(url + "/export?version=1")
    assert exported.status_code == 200 and exported.json()["document"] == document, exported.text
    assert exported.json()["document_digest"] == doc.digest()
    assert len(fixture.calls) == native_count
    assert financial_counts(customer_engine) == baseline
    assert alice.cookies[SESSION_COOKIE] == cookie
    variant = "global-deferred" if global_constraint else "typed-product"
    prefix = f"q10-{customer_engine.dialect.name}-{variant}"
    manifest: dict[str, str] = {}
    for label, payload in (("document", document), ("export", exported.json())):
        path = tmp_path / f"{prefix}-{label}.json"
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        manifest[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    (tmp_path / f"{prefix}-manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
