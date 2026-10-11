"""Actual three-platform private V5 alternatives; no expert/full-Q05 qualification."""

import hashlib
import json
import re
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from app.campaign_review import service as media
from app.customers.access import SESSION_COOKIE
from app.goals import service as goals
from app.goals.schemas import GoalDefinition
from app.planning_documents.catalog_receipt_models import InputCatalogReceiptRow
from app.planning_documents.documents import PlanVersion
from app.planning_documents.models import PlanVersionRow
from app.settings import Settings
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from tests.creative_q05_fixture import prepare_creative_q05_basis
from tests.q16_fixture import IMAGE
from tests.test_creative_common_basis import financial_counts
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_customer_optimization_api import headers
from tests.test_shopify_sales import configuration as configuration

pytestmark = pytest.mark.planning_boundary


def test_actual_v5_q05_three_platform_common_basis(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    fixture = prepare_creative_q05_basis(
        customer_engine, configuration, replicas, monkeypatch, tmp_path / "media"
    )
    basis, body = fixture.creative.basis, fixture.body
    alice, _, _ = replicas
    original_session = alice.cookies[SESSION_COOKIE]
    counts = financial_counts(customer_engine)
    assert counts == (0,) * 6
    root = f"/api/customer/v1/workspaces/{basis.workspace_id}/planning/plans"
    created = alice.post(root, headers=headers(alice), json=body)
    assert created.status_code == 201, created.text
    url = root + "/" + created.json()["plan_id"]
    intent = dict(expected_input_revision=1, expected_version=0, request_key="creative-q05-v5")
    result = alice.post(url + "/generate", headers=headers(alice), json=intent)
    assert result.status_code == 200, result.text
    document = result.json()["document"]
    doc = PlanVersion.model_validate(document)
    inputs = document["inputs"]
    definition = inputs["goal"]["definition"]
    assert doc.policy_version == "inlet.descriptive-review.v5"
    assert doc.generator_version == "inlet.descriptive-planning.v5"
    assert doc.quality_status == "not_expert_qualified"
    assert doc.spending_authority == "none" and not doc.advertising_writes_enabled
    assert [account["account_id"] for account in inputs["accounts"]] == list(fixture.account_ids)
    assert [account["platform"] for account in inputs["accounts"]] == [
        "google_ads",
        "meta_ads",
        "tiktok_ads",
    ]
    assert all(account["workspace_id"] == basis.workspace_id for account in inputs["accounts"])
    assert (
        inputs["reporting_window"]
        == body["inputs"]["reporting_window"]
        == dict(
            starts_at="2026-09-01T00:00:00-04:00", ends_at_exclusive="2026-10-01T00:00:00-04:00"
        )
    )
    assert (
        inputs["comparison_window"]
        == body["inputs"]["comparison_window"]
        == dict(
            starts_at="2026-08-01T00:00:00-04:00", ends_at_exclusive="2026-09-01T00:00:00-04:00"
        )
    )
    assert (
        inputs["goal"]["goal_id"],
        inputs["goal"]["revision"],
        inputs["goal"]["confirmation_reference"],
    ) == (basis.goal_id, basis.goal_revision, basis.confirmation_id)
    assert definition["store_id"] == basis.store_id
    assert definition["metric"] == "shopify_merchandise_net_sales_v1"
    assert definition["deadline"] == "2026-11-30"
    assert definition["baseline_window"] == dict(
        currency="USD",
        time_zone="America/New_York",
        time_basis="calendar_month",
        start="2026-09-01",
        end="2026-10-01",
    )
    assert definition["target_micros"] == 12_000_000_000
    assert definition["target_window"] == dict(
        currency="USD",
        time_zone="America/New_York",
        time_basis="calendar_month",
        start="2026-11-01",
        end="2026-12-01",
    )
    assert inputs["budget_period"] == dict(
        currency="USD",
        time_zone="America/New_York",
        starts_on="2026-11-01",
        ends_on_exclusive="2026-12-01",
    )
    assert inputs["total_ceiling_micros"] == definition["budget_micros"] == 1_000_000_000
    assert inputs["aggressiveness"] == definition["aggressiveness"] == "balanced"
    assert inputs["maximum_creative_assets"] == 1
    assert inputs["creative"] == body["inputs"]["creative"]
    assert inputs["product_offer"] == body["inputs"]["product_offer"]
    assert inputs["selected_reporting"] == body["inputs"]["selected_reporting"]
    assert len(inputs["selected_reporting"]) == 1
    assert inputs["selected_reporting"][0]["account_id"] == basis.account_id
    for name in ("constraints", "assumptions", "fixed_allocations"):
        assert inputs[name] == body["inputs"][name] == []
    assert inputs["excluded_entity_keys"] == body["inputs"]["exclusions"] == []
    with Session(customer_engine) as db:
        goal = goals.owned(db, basis.workspace_id, basis.goal_id)
        assert (
            goals.baseline(db, goal, GoalDefinition.model_validate(definition), datetime.now(UTC))[
                "net_sales_micros"
            ]
            == 8_000_000_000
        )
        asset, raw = media.download(db, basis.workspace_id, basis.media_id, fixture.creative.store)
        assert raw == IMAGE.read_bytes()
        assert asset.sha256 == hashlib.sha256(raw).hexdigest() == basis.media_sha256
        assert asset.created_by == doc.generated_by
        assert db.scalar(select(func.count()).select_from(PlanVersionRow)) == 1
        assert db.scalar(select(func.count()).select_from(InputCatalogReceiptRow)) == 3
    alternatives = {
        s.customer_intent_key: s
        for s in doc.scenarios
        if s.provenance == "customer_supplied_hypothesis"
    }
    assert set(alternatives) == {"option_a", "option_b"}
    for key, amounts in (("option_a", (400, 300, 200)), ("option_b", (300, 400, 200))):
        scenario = alternatives[key]
        assert [a.amount_micros for a in scenario.allocations] == [
            amount * 1_000_000 for amount in amounts
        ]
        assert [a.target.account.account_id for a in scenario.allocations] == list(
            fixture.account_ids
        )
        assert [a.target.selection_key for a in scenario.allocations] == [
            s["selection_key"] for s in fixture.selectors
        ]
        assert scenario.unallocated_micros == 100_000_000
        assert (
            sum(a.amount_micros for a in scenario.allocations) + scenario.unallocated_micros
            == scenario.ceiling_micros
            == 1_000_000_000
        )
        assert scenario.semantics == "independent_alternative"
        assert scenario.native_conversion == "not_assessed" and scenario.forecast is None
        assert scenario.spending_authority == "none" and not scenario.advertising_writes_enabled
    reviews = [a for a in doc.actions if a.key.startswith("review:")]
    assert len(reviews) == 4
    google = [a for a in reviews if a.target.account.account_id == basis.account_id]
    assert len(google) == 1
    primary, comparison = google[0].rationale.split("Comparison", 1)
    for pattern, text, expected in (
        (r"selected count ([0-9.]+) \(", primary, 10),
        (r"selected count ([0-9.]+) \(", comparison, 0),
        (r"([0-9.]+) observed clicks", primary, 100),
        (r"([0-9.]+) USD observed spend", primary, 100),
    ):
        match = re.search(pattern, text)
        assert match is not None and Decimal(match.group(1)) == expected
    assert google[0].kind == "retain"
    for action in reviews:
        assert action.native_budget is None and not action.proposed_fields
        assert any("Observed catalog location only" in step for step in action.manual_steps)
        if action.target.account.account_id != basis.account_id:
            assert "unsupported_selected_mapping" in action.rationale
            assert (
                "observed clicks" not in action.rationale
                and "Observed zero" not in action.rationale
            )
    catalogs = {
        ref.account.account_id: ref
        for ref in doc.evidence
        if ref.kind == "native_catalog" and ref.account is not None
    }
    assert set(catalogs) == set(fixture.account_ids)
    assert all(catalogs[aid].coverage == "partial" for aid in fixture.account_ids[1:])
    assert all(
        ref.account is not None and ref.account.account_id == basis.account_id
        for ref in doc.evidence
        if ref.kind == "reported_metrics"
    )
    assert all(a.native_budget is None for a in doc.actions)
    assert (
        "Provider reports do not establish causal lift, unique customers or future sales."
        in doc.limitations
    )
    proof, composition = doc.creative_proof, doc.creative_composition
    assert proof is not None and composition is not None
    assert proof.basis.requested == doc.inputs.creative
    assert len(proof.images) == len(proof.basis.images) == 1
    assert proof.basis.images[0].sha256 == basis.media_sha256
    assert proof.basis.images[0].visual_assessment == "not_assessed"
    assert len(composition.proposals) <= 1 and len(doc.briefs) <= 1
    # Global capacity is authoritative: never demand one produced asset per platform.
    for proposal in composition.proposals:
        production = proposal.production
        assert production.deliverable_status == "production_required"
        assert production.visual_assessment == "not_assessed"
        assert production.source_image_status == "owned_bytes_observed"
        assert production.selected_image_id == basis.media_id
        assert production.source_images == proof.basis.requested.media_selections
        assert proposal.action.target.account.account_id in fixture.account_ids[1:]
        assert len(production.storyboard) == (
            3 if proposal.action.target.account.platform == "tiktok_ads" else 0
        )
        assert "Reusable travel mug" in proposal.model_dump_json()
        assert "25 USD" in proposal.model_dump_json()
        assert "No approved health claims or testimonials." in proposal.model_dump_json()
    assert financial_counts(customer_engine) == counts
    native_count, google_count = len(fixture.native_calls), len(fixture.creative.calls)
    replay = alice.post(url + "/generate", headers=headers(alice), json=intent)
    assert replay.status_code == 200 and replay.json() == result.json(), replay.text
    current = alice.get(url)
    assert current.status_code == 200 and current.json()["document"] == document, current.text
    assert current.json()["freshness"] == "current"
    historical = alice.get(url + "/versions/1")
    assert historical.status_code == 200 and historical.json()["document"] == document, (
        historical.text
    )
    exported = alice.get(url + "/export?version=1")
    assert exported.status_code == 200 and exported.json()["document"] == document, exported.text
    assert exported.json()["document_digest"] == doc.digest()
    assert (len(fixture.native_calls), len(fixture.creative.calls)) == (native_count, google_count)
    assert alice.cookies[SESSION_COOKIE] == original_session
    assert financial_counts(customer_engine) == counts
    assert fixture.native_calls
    assert all(
        method
        == ("POST" if host in {"googleads.googleapis.com", "oauth2.googleapis.com"} else "GET")
        for host, method in fixture.native_calls
    )
    prefix = f"creative-common-q05-{customer_engine.dialect.name}"
    for label, payload in (("document", document), ("export", exported.json())):
        (tmp_path / f"{prefix}-{label}.json").write_text(
            json.dumps(payload, indent=2), encoding="utf-8"
        )
