from pathlib import Path

from app.deployment import (
    DeploymentCheck,
    DeploymentProcess,
    DeploymentValidationResult,
    runtime_process_config,
    validate_deployment_startup,
)
from app.settings import Settings
from pytest import MonkeyPatch


def _settings(**overrides: object) -> Settings:
    defaults: dict[str, object] = {
        "APP_ENV": "production",
        "DATABASE_URL": "postgresql+psycopg://ad_analyzer:safe-secret@db.example.invalid:5432/ad_analyzer?sslmode=require",
        "DATABASE_SSL_MODE": "require",
        "AD_ANALYZER_API_TOKEN": "safe-secret-token",
        "AD_ANALYZER_REQUIRED_SECRET_NAMES": "AD_ANALYZER_API_TOKEN,DATABASE_URL",
        "AD_ANALYZER_GOOGLE_ADS_WRITE_ENABLED": False,
        "AD_ANALYZER_GOOGLE_ADS_EXECUTION_KILL_SWITCH": True,
        "AD_ANALYZER_ALLOWED_EXECUTION_ACCOUNT_IDS": "",
        "AD_ANALYZER_ALLOWED_GOOGLE_ADS_MUTATIONS": "",
    }
    defaults.update(overrides)
    return Settings(**defaults)


def _check(result: DeploymentValidationResult, name: str) -> DeploymentCheck:
    return next(check for check in result.checks if check.name == name)


def test_production_configuration_validation_accepts_safe_managed_postgresql() -> None:
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


def test_postgresql_url_validation_rejects_sqlite_and_malformed_production_urls() -> None:
    for url in ("sqlite:///prod.db", "postgresql+psycopg:///missing-host", "not-a-url"):
        result = validate_deployment_startup(DeploymentProcess.WEB, _settings(DATABASE_URL=url))
        assert _check(result, "database_url").ok is False


def test_tls_configuration_requires_production_tls_mode() -> None:
    result = validate_deployment_startup(
        DeploymentProcess.WEB,
        _settings(
            DATABASE_URL="postgresql+psycopg://ad_analyzer:safe-secret@db/ad_analyzer",
            DATABASE_SSL_MODE="disable",
        ),
    )

    assert _check(result, "database_tls").ok is False


def test_pool_and_timeout_configuration_is_exposed_on_settings() -> None:
    settings = _settings(
        DATABASE_POOL_SIZE=7,
        DATABASE_MAX_OVERFLOW=3,
        DATABASE_CONNECT_TIMEOUT_SECONDS=12,
        DATABASE_POOL_RECYCLE_SECONDS=600,
    )
    result = validate_deployment_startup(DeploymentProcess.WORKER, settings)

    assert _check(result, "database_pooling").ok is True
    assert settings.database_pool_size == 7
    assert settings.database_max_overflow == 3
    assert settings.database_connect_timeout_seconds == 12
    assert settings.database_pool_recycle_seconds == 600


def test_missing_and_placeholder_production_secrets_are_redacted() -> None:
    result = validate_deployment_startup(
        DeploymentProcess.WEB,
        _settings(
            DATABASE_URL="postgresql+psycopg://ad_analyzer:replace-with-external-secret@db/ad_analyzer?sslmode=require",
            AD_ANALYZER_API_TOKEN="replace-with-external-secret",
        ),
    )

    assert result.ok is False
    details = " ".join(check.detail for check in result.checks)
    assert "replace-with-external-secret" not in details
    assert _check(result, "api_token").ok is False
    assert _check(result, "required_secrets").ok is False


def test_process_specific_runtime_configuration_is_provider_neutral() -> None:
    settings = _settings(AD_ANALYZER_WEB_CONCURRENCY=3, AD_ANALYZER_GRACEFUL_SHUTDOWN_SECONDS=45)

    configs = {process: runtime_process_config(process, settings) for process in DeploymentProcess}

    assert configs[DeploymentProcess.WEB].concurrency == 3
    assert configs[DeploymentProcess.WEB].restart_policy == "on-failure"
    assert configs[DeploymentProcess.WORKER].restart_policy == "no"
    assert configs[DeploymentProcess.SCHEDULER].command == (
        "python",
        "-m",
        "app.jobs.google_ads_scheduler",
    )
    assert configs[DeploymentProcess.MIGRATION].command == ("alembic", "upgrade", "head")
    assert all(config.graceful_shutdown_seconds == 45 for config in configs.values())


def test_write_disabled_kill_switch_enabled_and_empty_allowlists_are_required() -> None:
    unsafe = [
        _settings(AD_ANALYZER_GOOGLE_ADS_WRITE_ENABLED=True),
        _settings(AD_ANALYZER_GOOGLE_ADS_EXECUTION_KILL_SWITCH=False),
        _settings(AD_ANALYZER_ALLOWED_EXECUTION_ACCOUNT_IDS="123"),
        _settings(AD_ANALYZER_ALLOWED_GOOGLE_ADS_MUTATIONS="budget_update"),
    ]

    results = [
        validate_deployment_startup(DeploymentProcess.SCHEDULER, settings) for settings in unsafe
    ]

    assert all(not result.ok for result in results)
    assert any(not _check(result, "write_guards").ok for result in results)
    assert any(not _check(result, "production_allowlists").ok for result in results)


def test_readiness_validation_does_not_import_google_ads_collector(
    monkeypatch: MonkeyPatch,
) -> None:
    def fail_import(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("external Google Ads calls are not allowed")

    monkeypatch.setattr("app.collectors.google_ads.collect_account", fail_import)

    result = validate_deployment_startup(DeploymentProcess.WEB, _settings())

    assert result.ok is True


def test_provider_neutral_examples_and_roadmap_status_are_updated() -> None:
    roadmap = Path("docs/roadmap-status.md").read_text()
    managed = Path("deploy/managed-environment.example.yml").read_text()

    phase_12_2_status = (
        "12.2 Managed infrastructure configuration | Complete for provider-neutral "
        "non-production managed infrastructure configuration"
    )
    assert phase_12_2_status in roadmap
    assert "94% (16 of 17 units complete or superseded)" in roadmap
    assert "Phase 12.4 production release approval remains blocked" in roadmap
    assert "AWS" not in managed and "Azure" not in managed and "Google Cloud" not in managed
    assert 'AD_ANALYZER_GOOGLE_ADS_WRITE_ENABLED: "false"' in managed
