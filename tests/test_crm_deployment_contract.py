from pathlib import Path

import pytest
import yaml  # type: ignore[import-untyped]
from app.api.crm import router
from app.crm import dependencies
from app.settings import Settings
from fastapi import FastAPI, HTTPException


def test_declared_gateway_route_matches_scoped_application_contract() -> None:
    document = yaml.safe_load(Path("infra/gcp/openapi.yaml.tftpl").read_text())
    app = FastAPI()
    app.include_router(router)
    path = "/v1/crm/workspaces/{workspace_id}/connections/{connection_id}/events"
    assert path in app.openapi()["paths"]
    operation = document["paths"][path]["post"]
    assert {p["name"] for p in operation["parameters"] if p["in"] == "path"} == {
        "workspace_id",
        "connection_id",
    }
    assert "/v1/crm/events" not in document["paths"]
    assert "503" in operation["responses"]


def test_gateway_requires_explicit_database_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings.model_construct()
    monkeypatch.setattr(dependencies, "settings", settings)
    with pytest.raises(HTTPException) as error:
        next(dependencies.get_ingress_db())
    assert error.value.status_code == 503
    assert error.value.detail == "crm_ownership_database_not_configured"
