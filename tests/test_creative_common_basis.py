"""Actual private-v5 Common Basis artifacts; partial deterministic qualification only."""

import hashlib
import json
import re
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal

import pytest
from app.campaign_review import service as media
from app.campaign_review.models import MediaObject
from app.customers.access import SESSION_COOKIE
from app.goals import service as goals
from app.goals.schemas import GoalDefinition
from app.planning_documents.documents import PlanVersion
from app.planning_documents.models import PlanDependencyRow, PlanVersionRow
from app.publication.execution_models import (
    ProviderExecutionApproval,
    ProviderExecutionAttempt,
    ProviderExecutionRun,
    ProviderExposureReservation,
)
from app.publication.provider_models import ProviderReviewApproval
from app.publication.social_review_models import SocialConfigurationApproval
from app.settings import Settings
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from tests.creative_common_basis_fixture import Platform, prepare_creative_common_basis
from tests.q16_fixture import IMAGE
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_customer_optimization_api import headers
from tests.test_shopify_sales import configuration as configuration


def financial_counts(engine: Engine) -> tuple[int, ...]:
    with Session(engine) as db:
        return tuple(
            int(db.scalar(select(func.count()).select_from(model)) or 0)
            for model in (
                ProviderExecutionRun,
                ProviderExecutionAttempt,
                ProviderExecutionApproval,
                ProviderExposureReservation,
                ProviderReviewApproval,
                SocialConfigurationApproval,
            )
        )


@pytest.mark.parametrize(
    "platform,value",
    [
        ("google_ads", "10"),
        ("google_ads", "0"),
        ("google_ads", None),
        ("meta_ads", None),
        ("tiktok_ads", None),
    ],
    ids=["q01-positive", "q02-zero", "q02-missing", "q03-meta", "q04-tiktok"],
)
def test_actual_v5_common_basis_artifact(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    platform: Platform,
    value: Literal["10", "0"] | None,
) -> None:
    fixture = prepare_creative_common_basis(
        customer_engine,
        configuration,
        replicas,
        monkeypatch,
        tmp_path,
        platform=platform,
        selected_value=value,
    )
    basis, body, calls = fixture.basis, fixture.body, fixture.calls
    alice, _, _ = replicas
    cookie = alice.cookies[SESSION_COOKIE]
    counts = financial_counts(customer_engine)
    assert counts == (0,) * 6
    root = f"/api/customer/v1/workspaces/{basis.workspace_id}/planning/plans"
    created = alice.post(root, headers=headers(alice), json=body)
    assert created.status_code == 201, created.text
    url = root + "/" + created.json()["plan_id"]
    intent = dict(expected_input_revision=1, expected_version=0, request_key="creative-common-v5")
    result = alice.post(url + "/generate", headers=headers(alice), json=intent)
    assert result.status_code == 200, result.text
    saved = result.json()
    document = saved["document"]
    doc = PlanVersion.model_validate(document)
    inputs = document["inputs"]
    definition = inputs["goal"]["definition"]
    assert (doc.policy_version, doc.generator_version) == (
        "inlet.descriptive-review.v5",
        "inlet.descriptive-planning.v5",
    )
    assert document["quality_status"] == "not_expert_qualified"
    assert document["advertising_writes_enabled"] is False
    assert document["spending_authority"] == "none"
    assert inputs["accounts"][0]["account_id"] == basis.account_id
    assert inputs["accounts"][0]["platform"] == platform
    assert len(inputs["accounts"]) == 1
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
    assert (
        inputs["goal"]["goal_id"],
        inputs["goal"]["revision"],
        inputs["goal"]["confirmation_reference"],
    ) == (
        basis.goal_id,
        basis.goal_revision,
        basis.confirmation_id,
    )
    assert definition["store_id"] == basis.store_id
    assert definition["metric"] == "shopify_merchandise_net_sales_v1"
    assert definition["target_micros"] == 12_000_000_000
    assert definition["target_window"] == dict(
        currency="USD",
        time_zone="America/New_York",
        time_basis="calendar_month",
        start="2026-11-01",
        end="2026-12-01",
    )
    assert definition["baseline_window"] == dict(
        currency="USD",
        time_zone="America/New_York",
        time_basis="calendar_month",
        start="2026-09-01",
        end="2026-10-01",
    )
    assert definition["deadline"] == "2026-11-30"
    assert inputs["total_ceiling_micros"] == definition["budget_micros"] == 1_000_000_000
    assert inputs["budget_period"] == dict(
        starts_on="2026-11-01",
        ends_on_exclusive="2026-12-01",
        currency="USD",
        time_zone="America/New_York",
    )
    assert inputs["aggressiveness"] == definition["aggressiveness"] == "balanced"
    assert inputs["maximum_creative_assets"] == 1
    assert inputs["product_offer"] == body["inputs"]["product_offer"]
    assert inputs["creative"] == body["inputs"]["creative"]
    assert inputs["selected_reporting"] == body["inputs"]["selected_reporting"]
    for field in ("constraints", "assumptions", "fixed_allocations", "scenario_intents"):
        assert inputs[field] == body["inputs"][field] == []
    assert inputs["excluded_entity_keys"] == body["inputs"]["exclusions"] == []
    proof, composition = doc.creative_proof, doc.creative_composition
    assert proof is not None and composition is not None
    assert proof.basis.requested == doc.inputs.creative
    assert composition.basis_digest == proof.basis.digest()
    assert len(proof.images) == len(proof.basis.images) == 1
    image = proof.basis.images[0]
    assert image.media_id == basis.media_id and image.sha256 == basis.media_sha256
    assert image.visual_assessment == "not_assessed"
    assert image.sha256 == hashlib.sha256(IMAGE.read_bytes()).hexdigest()
    with Session(customer_engine) as db:
        goal = goals.owned(db, basis.workspace_id, basis.goal_id)
        assert (
            goals.baseline(db, goal, GoalDefinition.model_validate(definition), datetime.now(UTC))[
                "net_sales_micros"
            ]
            == 8_000_000_000
        )
        asset, data = media.download(db, basis.workspace_id, basis.media_id, fixture.store)
        assert data == IMAGE.read_bytes() and asset.sha256 == image.sha256
        assert asset.created_by == doc.generated_by and asset.workspace_id == basis.workspace_id
        assert db.scalar(select(func.count()).select_from(MediaObject)) == 1
        assert db.scalar(select(func.count()).select_from(PlanVersionRow)) == 1
        kinds = list(db.scalars(select(PlanDependencyRow.kind)))
        assert kinds.count("creative_basis") == kinds.count("local_creative_basis_v1") == 1
        assert kinds.count("local_reporting_v3") == 1
    reviews = [action for action in doc.actions if action.key.startswith("review:")]
    assert len(reviews) == (2 if platform == "meta_ads" else 1)
    for action in reviews:
        assert action.target.account.account_id == basis.account_id
        assert action.native_budget is None and not action.proposed_fields
        assert len(action.manual_steps) == 6
        assert "Observed catalog location only" in action.manual_steps[-1]
    if platform == "google_ads":
        text, comparison = reviews[0].rationale.split("Comparison", 1)
        clicks = re.search(r"([0-9.]+) observed clicks", text)
        spend = re.search(r"([0-9.]+) USD observed spend", text)
        assert clicks is not None and Decimal(clicks.group(1)) == 100
        assert spend is not None and Decimal(spend.group(1)) == 100
        assert "conversionActions/123" in text and "metric family conversions" in text
        assert ("Observed zero selected conversions" in text) == (value == "0")
        if value is None:
            assert "selected count unavailable" in text and "not full-window zero" in text
            assert "selected count unavailable" in comparison
        else:
            count = re.search(r"selected count ([0-9.]+) \(", text)
            comparison_count = re.search(r"selected count ([0-9.]+) \(", comparison)
            assert count is not None and Decimal(count.group(1)) == Decimal(value)
            assert comparison_count is not None and Decimal(comparison_count.group(1)) == 0
        if value == "10":
            assert reviews[0].kind == "retain" and "spend without" not in text.lower()
        assert composition.proposals == ()
    else:
        assert len(composition.proposals) == len(doc.briefs) == 1
        proposal = composition.proposals[0]
        production = proposal.production
        assert production.deliverable_status == "production_required"
        assert production.visual_assessment == "not_assessed"
        assert production.source_image_status == "owned_bytes_observed"
        assert production.selected_image_id == basis.media_id
        assert production.source_images == proof.basis.requested.media_selections
        assert len(production.storyboard) == (3 if platform == "tiktok_ads" else 0)
        assert proposal.action.target.account.account_id == basis.account_id
        assert "Reusable travel mug" in proposal.model_dump_json()
        assert "25 USD" in proposal.model_dump_json()
        assert "No approved health claims or testimonials." in proposal.model_dump_json()
        assert all("unsupported_selected_mapping" in action.rationale for action in reviews)
        assert all("observed clicks" not in action.rationale for action in reviews)
        assert all("Observed zero" not in action.rationale for action in reviews)
        assert not any(item.kind == "reported_metrics" for item in doc.evidence)
        catalog = [item for item in doc.evidence if item.kind == "native_catalog"]
        assert len(catalog) == 1 and catalog[0].coverage == "partial"
        if platform == "tiktok_ads":
            assert production.deliverable == "video"
            assert (
                "No video witness supplied; video production required."
                in proposal.model_dump_json()
            )
    assert financial_counts(customer_engine) == counts
    call_count = len(calls)
    replay = alice.post(url + "/generate", headers=headers(alice), json=intent)
    assert replay.status_code == 200 and replay.json() == saved, replay.text
    current = alice.get(url)
    assert current.status_code == 200 and current.json()["document"] == document, current.text
    assert current.json()["freshness"] == "current"
    exported = alice.get(url + "/export?version=1")
    assert exported.status_code == 200 and exported.json()["document"] == document, exported.text
    assert exported.json()["document_digest"] == saved["document_digest"]
    assert len(calls) == call_count and alice.cookies[SESSION_COOKIE] == cookie
    assert financial_counts(customer_engine) == counts
    assert calls and all(":mutate" not in call for call in calls)
    case = (
        f"google-{value if value is not None else 'missing'}"
        if platform == "google_ads"
        else platform
    )
    prefix = f"creative-common-{case}-{customer_engine.dialect.name}"
    for suffix, payload in (("document", document), ("export", exported.json())):
        (tmp_path / f"{prefix}-{suffix}.json").write_text(
            json.dumps(payload, indent=2),
            encoding="utf-8",
        )
