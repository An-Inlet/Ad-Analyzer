from pathlib import Path

import pytest
from app.deployment import DeploymentProcess, validate_deployment_startup
from app.settings import Settings

CONNECTION_NAME = "totemic-alchemy-502420-p4:us-west1:ad-analyzer-postgres"


def _cloud_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "APP_ENV": "production",
        "CLOUD_SQL_CONNECTION_NAME": CONNECTION_NAME,
        "DATABASE_USER": "ad_analyzer_app",
        "DATABASE_PASSWORD": "p@ss:/?#[]!$&'()*+,;=word",
        "DATABASE_NAME": "ad_analyzer",
        "AD_ANALYZER_API_TOKEN": "safe-token",
        "AD_ANALYZER_GOOGLE_ADS_WRITE_ENABLED": False,
        "AD_ANALYZER_GOOGLE_ADS_EXECUTION_KILL_SWITCH": True,
        "AD_ANALYZER_ALLOWED_EXECUTION_ACCOUNT_IDS": "",
        "AD_ANALYZER_ALLOWED_GOOGLE_ADS_MUTATIONS": "",
    }
    values.update(overrides)
    return Settings(**values)


def test_local_database_url_remains_the_resolved_configuration() -> None:
    url = "postgresql+psycopg://local:secret@localhost:5432/local_database"
    settings = Settings(DATABASE_URL=url)

    assert settings.resolved_database_url.render_as_string(hide_password=False) == url


def test_cloud_sql_socket_url_is_constructed_and_password_is_safely_encoded() -> None:
    settings = _cloud_settings()
    url = settings.resolved_database_url

    assert url.host is None
    assert url.query["host"] == f"/cloudsql/{CONNECTION_NAME}"
    assert url.password == "p@ss:/?#[]!$&'()*+,;=word"
    assert "p%40ss%3A%2F%3F%23%5B%5D" in url.render_as_string(hide_password=False)


@pytest.mark.parametrize(
    "missing",
    ["CLOUD_SQL_CONNECTION_NAME", "DATABASE_USER", "DATABASE_PASSWORD", "DATABASE_NAME"],
)
def test_missing_cloud_sql_variables_fail_production_startup(missing: str) -> None:
    result = validate_deployment_startup(
        DeploymentProcess.WEB, _cloud_settings(**{missing: None})
    )

    assert result.ok is False
    assert next(check for check in result.checks if check.name == "database_url").ok is False


def test_cloud_sql_production_startup_accepts_socket_without_sslmode() -> None:
    result = validate_deployment_startup(DeploymentProcess.WEB, _cloud_settings())

    assert result.ok is True
    assert next(check for check in result.checks if check.name == "database_tls").ok is True
    assert next(check for check in result.checks if check.name == "required_secrets").ok is True


def test_cloud_sql_password_is_the_required_database_secret() -> None:
    settings = _cloud_settings(DATABASE_PASSWORD="replace-with-external-secret")
    result = validate_deployment_startup(DeploymentProcess.WEB, settings)

    assert next(check for check in result.checks if check.name == "required_secrets").ok is False


def test_alembic_uses_the_shared_resolved_database_url() -> None:
    source = Path("migrations/env.py").read_text()

    assert "resolved_database_url = settings.resolved_database_url" in source
    assert "url=resolved_database_url" in source
