"""Saved-document visibility; pure fixtures and genuine three-account API artifacts."""

import json
import shutil
from datetime import date
from pathlib import Path
from typing import Any

import pytest
from app.planning_documents.documents import PlanVersion
from app.settings import Settings
from sqlalchemy import Engine

from tests.creative_q05_fixture import prepare_creative_q05_basis
from tests.test_creative_common_basis import financial_counts
from tests.test_creative_plan_composer import compose as creative_compose
from tests.test_creative_plan_composer import ready as creative_ready
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_customer_optimization_api import headers
from tests.test_plan_target_picker import (
    test_target_picker_exact_choices_revocation_expiry_and_bounds as run_component,
)
from tests.test_planning_composer import compose as legacy_compose
from tests.test_planning_composer import fixture as legacy_fixture
from tests.test_selected_paired_composer import compose, ready
from tests.test_shopify_sales import configuration as configuration

pytestmark = pytest.mark.planning_boundary


def review_browser(tmp_path: Path, documents: dict[str, Any]) -> None:
    for name in ("plan-document.mjs", "plan-constraints.mjs", "plan-reporting-comparability.mjs"):
        shutil.copy(Path("app/portal/static") / name, tmp_path / name)
    (tmp_path / "reporting-documents.json").write_text(json.dumps(documents))
    run_component(tmp_path, "plan_reporting_comparability_dom")


def test_reporting_review_usable_missing_zero_legacy_and_scope(tmp_path: Path) -> None:
    docs = {
        "positive": compose(*ready()).model_dump(mode="json"),
        "partial": compose(*ready(complete=False)).model_dump(mode="json"),
        "missing": compose(*ready(value=None)).model_dump(mode="json"),
        "zero": compose(*ready(value="0")).model_dump(mode="json"),
        "legacy": legacy_compose(*legacy_fixture()).model_dump(mode="json"),
        "meta": creative_compose(creative_ready("meta")).model_dump(mode="json"),
        "tiktok": creative_compose(creative_ready("tiktok")).model_dump(mode="json"),
    }
    review_browser(tmp_path, docs)


@pytest.mark.parametrize("partial", [False, True])
def test_actual_three_platform_review_current_export_and_replay(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    partial: bool,
) -> None:
    fixture = prepare_creative_q05_basis(
        customer_engine,
        configuration,
        replicas,
        monkeypatch,
        tmp_path / "media",
        missing_selected_day=date(2026, 9, 12) if partial else None,
    )
    basis = fixture.creative.basis
    alice, _, _ = replicas
    counts = financial_counts(customer_engine)
    root = f"/api/customer/v1/workspaces/{basis.workspace_id}/planning/plans"
    created = alice.post(root, headers=headers(alice), json=fixture.body)
    assert created.status_code == 201, created.text
    path = root + "/" + created.json()["plan_id"]
    intent = dict(expected_input_revision=1, expected_version=0, request_key="q09-saved-review")
    generated = alice.post(path + "/generate", headers=headers(alice), json=intent)
    assert generated.status_code == 200, generated.text
    original = generated.json()
    document = PlanVersion.model_validate_json(json.dumps(original["document"]))
    assert document.digest() == original["document_digest"]
    explanations = [a.rationale for a in document.actions if a.key.startswith("review:")]
    google = next(a for a in explanations if "selected count 10" in a)
    assert ("1 selected calendar days absent" in google) is partial
    assert "0 selected calendar days absent" in google  # August stays complete.
    assert sum("unsupported_selected_mapping" in text for text in explanations) >= 2
    assert all(
        action.native_budget is None and not action.proposed_fields for action in document.actions
    )
    assert document.advertising_writes_enabled is False and document.spending_authority == "none"
    read = alice.get(path)
    exported = alice.get(path + "/export?version=1")
    assert read.status_code == exported.status_code == 200
    calls_before = len(fixture.native_calls), len(fixture.creative.calls)
    replay = alice.post(path + "/generate", headers=headers(alice), json=intent)
    assert replay.status_code == 200, replay.text
    assert (len(fixture.native_calls), len(fixture.creative.calls)) == calls_before
    artifacts = {
        "generated": original,
        "current": read.json(),
        "export": exported.json(),
        "replay": replay.json(),
    }
    for result in artifacts.values():
        retained = PlanVersion.model_validate_json(json.dumps(result["document"]))
        assert retained.digest() == document.digest() == result["document_digest"]
        assert retained.inputs.accounts == document.inputs.accounts
    assert financial_counts(customer_engine) == counts == (0,) * 6
    (tmp_path / "q09-api-artifacts.json").write_text(json.dumps(artifacts, indent=2))
    review_browser(tmp_path, {"mixed_partial" if partial else "mixed": original["document"]})
