"""Exact frozen Common Basis API cases; not expert or live-provider qualification."""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from app.campaign_review import service as media
from app.campaign_review.storage import LocalMediaStore
from app.customers.access import SESSION_COOKIE
from app.goals import service as goals
from app.goals.schemas import GoalDefinition
from app.publication.execution_models import ProviderExecutionAttempt, ProviderExecutionRun
from app.settings import Settings
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from tests.q16_fixture import IMAGE
from tests.selected_q01_q02_fixture import prepare_selected_common_basis
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_customer_optimization_api import headers
from tests.test_shopify_sales import configuration as configuration


@pytest.mark.parametrize(
    "value", ["10", "0", None], ids=["q01-positive", "q02-zero", "q02-missing"]
)
def test_common_basis_actual_selected_plan(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    value: str | None,
) -> None:
    basis, body, calls = prepare_selected_common_basis(
        customer_engine,
        configuration,
        replicas,
        monkeypatch,
        tmp_path,
        value=value,
    )
    alice, _, _ = replicas
    original_cookie = alice.cookies[SESSION_COOKIE]
    root = f"/api/customer/v1/workspaces/{basis.workspace_id}/planning/plans"
    created = alice.post(root, headers=headers(alice), json=body)
    assert created.status_code == 201, created.text
    url = root + "/" + created.json()["plan_id"]
    generated = alice.post(
        url + "/generate",
        headers=headers(alice),
        json=dict(
            expected_input_revision=1, expected_version=0, request_key="common-basis-generate"
        ),
    )
    assert generated.status_code == 200, generated.text
    document = generated.json()["document"]
    inputs = document["inputs"]
    assert document["policy_version"] == "inlet.descriptive-review.v4"
    assert document["quality_status"] == "not_expert_qualified"
    assert document["advertising_writes_enabled"] is False
    assert document["spending_authority"] == "none"
    assert inputs["accounts"][0]["account_id"] == basis.account_id
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
    goal = inputs["goal"]
    assert (goal["goal_id"], goal["revision"], goal["confirmation_reference"]) == (
        basis.goal_id,
        basis.goal_revision,
        basis.confirmation_id,
    )
    definition = goal["definition"]
    assert definition["metric"] == "shopify_merchandise_net_sales_v1"
    assert definition["store_id"] == basis.store_id
    assert definition["target_micros"] == 12_000_000_000
    assert definition["target_window"] == dict(
        currency="USD",
        time_zone="America/New_York",
        time_basis="calendar_month",
        start="2026-11-01",
        end="2026-12-01",
    )
    assert definition["baseline_window"]["start"] == "2026-09-01"
    assert definition["baseline_window"]["end"] == "2026-10-01"
    assert definition["baseline_window"] == dict(
        currency="USD",
        time_zone="America/New_York",
        time_basis="calendar_month",
        start="2026-09-01",
        end="2026-10-01",
    )
    assert inputs["budget_period"] == dict(
        starts_on="2026-11-01",
        ends_on_exclusive="2026-12-01",
        currency="USD",
        time_zone="America/New_York",
    )
    assert definition["deadline"] == "2026-11-30"
    assert inputs["total_ceiling_micros"] == definition["budget_micros"] == 1_000_000_000
    assert definition["budget_start"] == "2026-11-01" and definition["budget_end"] == "2026-12-01"
    assert definition["aggressiveness"] == "balanced"
    assert inputs["product_offer"] == body["inputs"]["product_offer"]
    assert "Reusable travel mug, $25 list price." in inputs["product_offer"]
    assert "No approved health claims or testimonials." in inputs["product_offer"]
    assert (
        basis.media_id in inputs["product_offer"] and basis.media_sha256 in inputs["product_offer"]
    )
    assert inputs["maximum_creative_assets"] == 1
    with Session(customer_engine) as db:
        owned_goal = goals.owned(db, basis.workspace_id, basis.goal_id)
        assert (
            goals.baseline(
                db, owned_goal, GoalDefinition.model_validate(definition), datetime.now(UTC)
            )["net_sales_micros"]
            == 8_000_000_000
        )
        asset, data = media.download(
            db, basis.workspace_id, basis.media_id, LocalMediaStore(tmp_path)
        )
        assert asset.workspace_id == basis.workspace_id
        assert asset.created_by == document["generated_by"]
        assert asset.sha256 == basis.media_sha256 and data == IMAGE.read_bytes()
        assert db.scalar(select(func.count()).select_from(ProviderExecutionAttempt)) == 0
        assert db.scalar(select(func.count()).select_from(ProviderExecutionRun)) == 0
    action = document["actions"][0]
    assert action["target"]["account"]["account_id"] == basis.account_id
    text = action["rationale"].split("Comparison")[0]
    assert "100 observed clicks" in text and "100 USD observed spend" in text
    assert "conversionActions/123" in text and "metric family conversions" in text
    assert (
        action["manual_steps"][0]
        == "Locate Google Ads advertiser 1234567890, campaign 1 (Mug Campaign) "
        "in your advertising account."
    )
    assert len(action["manual_steps"]) == 6
    assert action["manual_steps"][5] == (
        "Observed catalog location only: Google Ads advertiser 1234567890, adgroup 7, "
        "parent campaign 1 (Mug Ad Group). Campaign metrics are not child metrics; "
        "no child change is proposed."
    )
    assert all(item["target"]["kind"] == "campaign" for item in document["actions"])
    assert action["native_budget"] is None and action["proposed_fields"] == []
    assert ("Observed zero selected conversions" in text) == (value == "0")
    if value == "10":
        assert "selected count 10" in text and action["kind"] == "retain"
        assert "spend without" not in text.lower()
    elif value is None:
        assert "selected count unavailable" in text and "not full-window zero" in text
    else:
        assert "investigate the selected event" in text
    before = len(calls)
    retained = alice.get(url)
    assert retained.status_code == 200, retained.text
    assert retained.json()["document"] == document
    assert len(calls) == before

    exported = alice.get(url + "/export?version=1")
    assert exported.status_code == 200, exported.text
    assert exported.json()["document"] == document
    assert exported.json()["document_digest"] == generated.json()["document_digest"]
    assert alice.cookies[SESSION_COOKIE] == original_cookie
    assert all(":mutate" not in call for call in calls)

    # Synthetic real-API artifacts for separate human review, not an expert verdict.
    case = "q01-positive" if value == "10" else "q02-zero" if value == "0" else "q02-missing"
    prefix = f"{case}-{customer_engine.dialect.name}"
    (tmp_path / f"{prefix}-document.json").write_text(
        json.dumps(document, indent=2), encoding="utf-8"
    )
    (tmp_path / f"{prefix}-export.json").write_text(
        json.dumps(exported.json(), indent=2), encoding="utf-8"
    )
