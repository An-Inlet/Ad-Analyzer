"""Real app policy selection through parsed settings, never a planner replacement."""

import json
from pathlib import Path
from typing import Any

import pytest
from app.api import customer_planning_documents as api
from app.planning_documents.models import PlanRow
from app.planning_documents.runtime_policy import configured_policy
from app.planning_documents.service import PlanningDocumentService
from app.settings import Settings, settings
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from tests import test_google_reporting_assembled_browser as google_browser
from tests import test_meta_reporting_assembled_browser as meta_browser
from tests import test_planning_documents_browser as default_browser
from tests.google_reporting_assembly_fixture import GoogleAssembly
from tests.meta_customer_fixture import MetaFixture
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_shopify_sales import configuration as configuration


def configure(patch: pytest.MonkeyPatch, value: str | None) -> Settings:
    if value is None:
        patch.delenv("INLET_CUSTOMER_PLANNING_POLICY", raising=False)
    else:
        patch.setenv("INLET_CUSTOMER_PLANNING_POLICY", value)
    config = Settings(_env_file=None)
    patch.setattr(settings, "customer_planning_policy", config.customer_planning_policy)
    assert vars(api)["PlanningDocumentService"] is PlanningDocumentService
    return config


@pytest.mark.parametrize("value", [None, "v3", "v4", "v5", "v6"])
def test_configuration_selection(value: str | None, monkeypatch: pytest.MonkeyPatch) -> None:
    config = configure(monkeypatch, value)
    assert config.customer_planning_policy == (value or "v3")
    policy = configured_policy(config)
    if value in ("v4", "v5", "v6"):
        assert policy and policy.version == f"inlet.descriptive-review.{value}"
        assert policy.generator_version == f"inlet.descriptive-planning.{value}"
    else:
        assert policy is None
    assert not config.customer_google_reporting_enabled
    assert not config.customer_meta_reporting_enabled
    assert config.google_customer_runtime_mode == "disabled"


@pytest.mark.parametrize("value", ["", "v1", "v2", "v7", "V4", " v4", "unknown"])
def test_invalid_environment(value: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INLET_CUSTOMER_PLANNING_POLICY", value)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


@pytest.mark.parametrize("value", [None, True, "v7", ""])
def test_defensive_config_refusal(value: Any) -> None:
    config = Settings(_env_file=None).model_copy(update={"customer_planning_policy": value})
    with pytest.raises(HTTPException) as caught:
        configured_policy(config)
    assert caught.value.status_code == 503
    assert caught.value.detail == "Customer planning policy is not configured."


@pytest.mark.parametrize("value", [None, "v3", "v4", "invalid"])
def test_actual_app_capabilities(
    customer_engine: Engine, configuration: Settings, replicas: Any,
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, value: str | None,
) -> None:
    f = GoogleAssembly(
        customer_engine, configuration, replicas, monkeypatch, tmp_path / "basis", configured=True
    )
    configure(monkeypatch, None if value == "invalid" else value)
    if value == "invalid":
        monkeypatch.setattr(settings, "customer_planning_policy", "invalid")
    root = f"/api/customer/v1/workspaces/{f.wid}/planning/plans"
    before = list(f.native_calls)
    result = f.alice.get(root + "/capabilities")
    if value == "invalid":
        assert result.status_code == 503
        assert result.json() == {"detail": "Customer planning policy is not configured."}
        from tests.test_customer_optimization_api import headers

        created = f.alice.post(root, headers=headers(f.alice), json=f.body)
        assert created.status_code == 503
        with Session(customer_engine) as db:
            assert db.scalar(select(func.count()).select_from(PlanRow)) == 0
    else:
        assert result.status_code == 200
        assert result.json()["policy_version"] == f"inlet.descriptive-review.{value or 'v3'}"
        assert result.json()["selected_reporting_available"] == (value == "v4")
    assert not f.calls and f.native_calls == before


@pytest.mark.parametrize("value", ["10", "0", None])
def test_configured_google_journey(
    customer_engine: Engine, configuration: Settings, replicas: Any,
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, value: str | None,
) -> None:
    f = GoogleAssembly(
        customer_engine, configuration, replicas, monkeypatch, tmp_path / "basis", configured=True
    )
    configure(monkeypatch, "v4")
    google_browser.test_actual_google_reporting_to_plan(f, monkeypatch, tmp_path, value)
    assert vars(api)["PlanningDocumentService"] is PlanningDocumentService
    result = json.loads((tmp_path / "assembled-google-plan.json").read_text())
    for item in result.values():
        assert item["document"]["policy_version"] == "inlet.descriptive-review.v4"
        assert item["document"]["schema_version"] == "inlet.plan-version.v3"


def test_configured_meta_journey(
    customer_engine: Engine, configuration: Settings, replicas: Any,
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    f = MetaFixture(
        customer_engine, configuration, replicas, monkeypatch, tmp_path / "basis",
        configure_planning=False,
    )
    configure(monkeypatch, "v4")
    meta_browser.test_actual_meta_reporting_to_plan(f, monkeypatch, tmp_path, "10")
    assert vars(api)["PlanningDocumentService"] is PlanningDocumentService
    result = json.loads((tmp_path / "assembled-meta-plan.json").read_text())
    for item in result.values():
        assert item["document"]["policy_version"] == "inlet.descriptive-review.v4"
        assert item["document"]["schema_version"] == "inlet.plan-version.v3"


@pytest.mark.parametrize("value", [None, "v3"])
def test_default_customer_journey(
    customer_engine: Engine, configuration: Settings, replicas: Any,
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, value: str | None,
) -> None:
    configure(monkeypatch, value)
    default_browser.test_actual_planning_browser_lost_response_recovery_and_versions(
        "windows", "meta_ads", customer_engine, configuration, replicas, monkeypatch, tmp_path
    )
    assert vars(api)["PlanningDocumentService"] is PlanningDocumentService
    result = json.loads((tmp_path / "assembled-default-plan.json").read_text())
    for name in ("first", "second", "old"):
        doc = result[name]["document"]
        assert doc["policy_version"] == "inlet.descriptive-review.v3"
        assert doc["generator_version"] == "inlet.descriptive-planning.v3"
