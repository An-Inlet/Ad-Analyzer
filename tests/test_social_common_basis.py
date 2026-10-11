"""Provider-alone fixture acceptance; not complete Q03/Q04 or creative quality."""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from app.campaign_review import service as media
from app.campaign_review.models import MediaObject
from app.campaign_review.storage import LocalMediaStore
from app.goals import service as goals
from app.goals.schemas import GoalDefinition
from app.publication.execution_models import ProviderExecutionAttempt, ProviderExecutionRun
from app.settings import Settings
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from tests.q16_fixture import IMAGE
from tests.social_common_basis_fixture import Platform, prepare_social_common_basis
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_customer_optimization_api import headers
from tests.test_shopify_sales import configuration as configuration


@pytest.mark.parametrize("platform", ["meta_ads", "tiktok_ads"])
def test_actual_social_common_basis(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    platform: Platform,
) -> None:
    basis, body, calls = prepare_social_common_basis(
        customer_engine, configuration, replicas, monkeypatch, tmp_path, platform=platform
    )
    alice, _, _ = replicas
    root = f"/api/customer/v1/workspaces/{basis.workspace_id}/planning/plans"
    created = alice.post(root, headers=headers(alice), json=body)
    assert created.status_code == 201, created.text
    url = root + "/" + created.json()["plan_id"]
    result = alice.post(
        url + "/generate",
        headers=headers(alice),
        json=dict(
            expected_input_revision=1, expected_version=0, request_key="social-common-generate"
        ),
    )
    assert result.status_code == 200, result.text
    document = result.json()["document"]
    inputs = document["inputs"]
    definition = inputs["goal"]["definition"]
    assert inputs["selected_reporting"] == []
    assert inputs["accounts"][0]["account_id"] == basis.account_id
    assert inputs["accounts"][0]["platform"] == platform
    assert inputs["reporting_window"] == dict(
        starts_at="2026-09-01T00:00:00-04:00", ends_at_exclusive="2026-10-01T00:00:00-04:00"
    )
    assert inputs["comparison_window"] == dict(
        starts_at="2026-08-01T00:00:00-04:00", ends_at_exclusive="2026-09-01T00:00:00-04:00"
    )
    assert definition["target_micros"] == 12_000_000_000
    assert definition["target_window"] == dict(
        currency="USD",
        time_zone="America/New_York",
        time_basis="calendar_month",
        start="2026-11-01",
        end="2026-12-01",
    )
    assert inputs["total_ceiling_micros"] == definition["budget_micros"] == 1_000_000_000
    assert inputs["budget_period"] == dict(
        starts_on="2026-11-01",
        ends_on_exclusive="2026-12-01",
        currency="USD",
        time_zone="America/New_York",
    )
    assert inputs["aggressiveness"] == "balanced" and inputs["maximum_creative_assets"] == 1
    assert inputs["product_offer"] == body["inputs"]["product_offer"]
    assert "Reusable travel mug, $25 list price." in inputs["product_offer"]
    assert "No approved health claims or testimonials." in inputs["product_offer"]
    assert (
        basis.media_id in inputs["product_offer"] and basis.media_sha256 in inputs["product_offer"]
    )
    with Session(customer_engine) as db:
        goal = goals.owned(db, basis.workspace_id, basis.goal_id)
        assert (goal.revision, goal.confirmed_preview_id) == (
            basis.goal_revision,
            basis.confirmation_id,
        )
        assert (
            goals.baseline(db, goal, GoalDefinition.model_validate(definition), datetime.now(UTC))[
                "net_sales_micros"
            ]
            == 8_000_000_000
        )
        asset, data = media.download(
            db, basis.workspace_id, basis.media_id, LocalMediaStore(tmp_path)
        )
        assert asset.created_by == document["generated_by"] and data == IMAGE.read_bytes()
        assert asset.sha256 == basis.media_sha256 and asset.mime == "image/png"
        assert db.scalar(select(func.count()).select_from(MediaObject)) == 1
        assert db.scalar(select(func.count()).select_from(ProviderExecutionAttempt)) == 0
        assert db.scalar(select(func.count()).select_from(ProviderExecutionRun)) == 0
    assert document["policy_version"] == "inlet.descriptive-review.v4"
    assert document["quality_status"] == "not_expert_qualified"
    assert not document["advertising_writes_enabled"] and document["spending_authority"] == "none"
    reviews = [a for a in document["actions"] if a["key"].startswith("review:")]
    assert len(reviews) == (2 if platform == "meta_ads" else 1)
    assert len(document["actions"]) == len(reviews) + 1
    assert len(document["briefs"]) == 1
    assert {a["target"]["provider_reference"]["entity_id"] for a in reviews} == (
        {"5", "7"} if platform == "meta_ads" else {"5"}
    )
    assert (
        len([x for x in document["section_limitations"] if "unsupported_selected_mapping" in x])
        == 2
    )
    for action in reviews:
        assert action["target"]["account"]["account_id"] == basis.account_id
        assert action["target"]["kind"] == "campaign"
        assert action["native_budget"] is None and action["proposed_fields"] == []
        assert "unavailable" in action["rationale"].lower()
        assert "unsupported_selected_mapping" in action["rationale"]
        assert "observed clicks" not in action["rationale"]
        assert "observed spend" not in action["rationale"]
        assert "Observed zero" not in action["rationale"]
        assert len(action["manual_steps"]) == 6
        assert "Observed catalog location only" in action["manual_steps"][-1]
    catalog = [x for x in document["evidence"] if x["kind"] == "native_catalog"]
    assert len(catalog) == 1 and catalog[0]["coverage"] == "partial"
    assert not any(x["kind"] == "reported_metrics" for x in document["evidence"])
    proof = document["selected_reporting_proof"]["accounts"][0]
    assert proof["capture_pin"] is None and "traffic_pin" not in proof
    assert calls and all("google" not in x for x in calls)
    exported = alice.get(url + "/export?version=1")
    assert exported.status_code == 200, exported.text
    assert exported.json()["document"] == document
    # Actual initial output for later creative work, not a quality endorsement.
    prefix = f"social-common-{platform}-{customer_engine.dialect.name}"
    (tmp_path / f"{prefix}-document.json").write_text(
        json.dumps(document, indent=2), encoding="utf-8"
    )
    (tmp_path / f"{prefix}-export.json").write_text(
        json.dumps(exported.json(), indent=2), encoding="utf-8"
    )
