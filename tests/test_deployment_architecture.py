from pathlib import Path

from app.deployment import DeploymentProcess, validate_deployment_startup
from app.main import app
from app.settings import Settings
from fastapi.testclient import TestClient


def _settings(**overrides: object) -> Settings:
    defaults: dict[str, object] = {
        "APP_ENV": "production",
        "DATABASE_URL": "postgresql+psycopg://denticode:safe-secret@postgres:5432/denticode_ads_optimizer?sslmode=require",
        "DENTICODE_API_TOKEN": "safe-token",
        "DENTICODE_GOOGLE_ADS_WRITE_ENABLED": False,
        "DENTICODE_GOOGLE_ADS_EXECUTION_KILL_SWITCH": True,
        "DENTICODE_ALLOWED_EXECUTION_ACCOUNT_IDS": "",
        "DENTICODE_ALLOWED_GOOGLE_ADS_MUTATIONS": "",
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
        _settings(DENTICODE_GOOGLE_ADS_WRITE_ENABLED=True),
    )

    assert result.ok is False
    assert any(check.name == "write_guards" and not check.ok for check in result.checks)


def test_deployment_startup_rejects_nonempty_allowlists() -> None:
    result = validate_deployment_startup(
        DeploymentProcess.MIGRATION,
        _settings(DENTICODE_ALLOWED_EXECUTION_ACCOUNT_IDS="123"),
    )

    assert result.ok is False
    assert any(check.name == "production_allowlists" and not check.ok for check in result.checks)


def test_readiness_endpoint_reports_configuration_without_external_calls() -> None:
    client = TestClient(app)

    response = client.get("/ready")

    assert response.status_code == 200
    assert response.json()["write_access_enabled"] is False


def test_compose_defines_separate_provider_neutral_processes() -> None:
    compose = Path("deploy/docker-compose.yml").read_text()

    for service in ("web:", "worker:", "scheduler:", "migration:"):
        assert service in compose
    assert 'DENTICODE_GOOGLE_ADS_WRITE_ENABLED: "false"' in compose
    assert 'DENTICODE_GOOGLE_ADS_EXECUTION_KILL_SWITCH: "true"' in compose
    assert 'DENTICODE_ALLOWED_EXECUTION_ACCOUNT_IDS: ""' in compose


def test_env_example_preserves_phase_12_1_safety_defaults() -> None:
    env_example = Path(".env.example").read_text()

    assert "DATABASE_URL=postgresql+psycopg://" in env_example
    assert "DENTICODE_GOOGLE_ADS_WRITE_ENABLED=false" in env_example
    assert "DENTICODE_GOOGLE_ADS_EXECUTION_KILL_SWITCH=true" in env_example
    assert "DENTICODE_ALLOWED_EXECUTION_ACCOUNT_IDS=" in env_example
