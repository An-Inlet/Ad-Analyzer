from pathlib import Path

import app.main as main
import pytest
from app.deployment import DeploymentProcess, validate_deployment_startup
from app.main import app
from app.settings import Settings
from fastapi.testclient import TestClient


def _settings(**overrides: object) -> Settings:
    defaults: dict[str, object] = {
        "APP_ENV": "production",
        "DATABASE_URL": "postgresql+psycopg://ad_analyzer:safe-secret@postgres:5432/ad_analyzer?sslmode=require",
        "AD_ANALYZER_API_TOKEN": "safe-token",
        "AD_ANALYZER_GOOGLE_ADS_WRITE_ENABLED": False,
        "AD_ANALYZER_GOOGLE_ADS_EXECUTION_KILL_SWITCH": True,
        "AD_ANALYZER_ALLOWED_EXECUTION_ACCOUNT_IDS": "",
        "AD_ANALYZER_ALLOWED_GOOGLE_ADS_MUTATIONS": "",
    }
    defaults.update(overrides)
    return Settings(**defaults)


def test_deployment_startup_accepts_safe_production_web_config() -> None:
    result = validate_deployment_startup(DeploymentProcess.WEB, _settings())

    assert result.ok is True
    assert {check.name for check in result.checks} == {
        "database_url",
        "database_tls",
        "database_pooling",
        "api_token",
        "required_secrets",
        "write_guards",
        "production_allowlists",
    }


def test_deployment_startup_rejects_non_postgresql_database_url() -> None:
    result = validate_deployment_startup(
        DeploymentProcess.WEB,
        _settings(DATABASE_URL="sqlite:///local.db"),
    )

    assert result.ok is False
    assert any(check.name == "database_url" and not check.ok for check in result.checks)


def test_deployment_startup_rejects_enabled_write_access() -> None:
    result = validate_deployment_startup(
        DeploymentProcess.SCHEDULER,
        _settings(AD_ANALYZER_GOOGLE_ADS_WRITE_ENABLED=True),
    )

    assert result.ok is False
    assert any(check.name == "write_guards" and not check.ok for check in result.checks)


def test_deployment_startup_rejects_nonempty_allowlists() -> None:
    result = validate_deployment_startup(
        DeploymentProcess.MIGRATION,
        _settings(AD_ANALYZER_ALLOWED_EXECUTION_ACCOUNT_IDS="123"),
    )

    assert result.ok is False
    assert any(check.name == "production_allowlists" and not check.ok for check in result.checks)


@pytest.mark.parametrize("ready", [True, False])
def test_readiness_endpoint_reports_configuration_without_external_calls(
    ready: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    configuration = _settings() if ready else _settings(DATABASE_URL="sqlite:///local.db")
    result = validate_deployment_startup(DeploymentProcess.WEB, configuration)
    monkeypatch.setattr(main, "validate_deployment_startup", lambda _process: result)
    monkeypatch.setattr(main, "database_available", lambda: True)
    client = TestClient(app)
    response = client.get("/ready")
    assert response.status_code == (200 if ready else 503)
    assert response.json()["status"] == ("ready" if ready else "not_ready")
    assert response.json()["write_access_enabled"] is False
    assert response.headers["Cache-Control"] == "no-store"
    # Liveness is independent of whether startup configuration can serve traffic.
    assert client.get("/health").status_code == 200


def test_compose_defines_separate_provider_neutral_processes() -> None:
    compose = Path("deploy/docker-compose.yml").read_text()

    for service in ("web:", "worker:", "scheduler:", "migration:"):
        assert service in compose
    assert 'AD_ANALYZER_GOOGLE_ADS_WRITE_ENABLED: "false"' in compose
    assert 'AD_ANALYZER_GOOGLE_ADS_EXECUTION_KILL_SWITCH: "true"' in compose
    assert 'AD_ANALYZER_ALLOWED_EXECUTION_ACCOUNT_IDS: ""' in compose


def test_env_example_preserves_phase_12_1_safety_defaults() -> None:
    env_example = Path(".env.example").read_text()

    assert "DATABASE_URL=postgresql+psycopg://" in env_example
    assert "AD_ANALYZER_GOOGLE_ADS_WRITE_ENABLED=false" in env_example
    assert "AD_ANALYZER_GOOGLE_ADS_EXECUTION_KILL_SWITCH=true" in env_example
    assert "AD_ANALYZER_ALLOWED_EXECUTION_ACCOUNT_IDS=" in env_example
