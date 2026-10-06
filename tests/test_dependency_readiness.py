import os
from typing import Any
from unittest.mock import MagicMock

import pytest
from app import main, readiness
from app.deployment import DeploymentProcess, validate_deployment_startup
from fastapi.testclient import TestClient
from sqlalchemy import make_url
from sqlalchemy.exc import OperationalError
from sqlalchemy.pool import NullPool

from tests.test_deployment_architecture import _settings


@pytest.mark.parametrize("configured,available", [(True, True), (True, False), (False, False)])
def test_dependency_failure_is_not_ready_but_remains_live(
    monkeypatch: pytest.MonkeyPatch, configured: bool, available: bool
) -> None:
    result = validate_deployment_startup(
        DeploymentProcess.WEB,
        _settings() if configured else _settings(DATABASE_URL="sqlite:///local.db"),
    )
    probe = MagicMock(return_value=available)
    monkeypatch.setattr(main, "validate_deployment_startup", lambda _: result)
    monkeypatch.setattr(main, "database_available", probe)
    with TestClient(main.app) as client:
        response = client.get("/ready")
        assert response.status_code == (200 if configured and available else 503)
        assert response.json()["database_available"] is (configured and available)
        assert response.headers["Cache-Control"] == "no-store"
        assert client.get("/health").status_code == 200
    assert probe.call_count == int(configured)


@pytest.mark.parametrize("failure", [False, True])
def test_fresh_read_only_connection_is_closed_and_errors_sanitized(
    monkeypatch: pytest.MonkeyPatch, failure: bool
) -> None:
    engine = MagicMock()
    connection = engine.connect.return_value.__enter__.return_value
    connection.scalar.return_value = 1
    if failure:
        engine.connect.side_effect = OperationalError("private host", {}, Exception("private"))
    captured: dict[str, Any] = {}

    def create(url: Any, **kwargs: Any) -> Any:
        captured.update(kwargs)
        assert url.drivername == "postgresql+psycopg"
        return engine

    monkeypatch.setattr(readiness, "create_engine", create)
    assert readiness.database_available(make_url("postgresql://localhost/synthetic")) is not failure
    assert captured["connect_args"]["connect_timeout"] == 2
    assert "statement_timeout=1000" in captured["connect_args"]["options"]
    assert "default_transaction_read_only=on" in captured["connect_args"]["options"]
    assert captured["poolclass"] is NullPool
    engine.dispose.assert_called_once()
    if not failure:
        assert str(connection.scalar.call_args.args[0]) == "SELECT 1"
        engine.connect.return_value.__exit__.assert_called_once()


def test_local_disposable_postgres_dependency() -> None:
    raw = os.environ.get("AD_ANALYZER_TEST_POSTGRES_URL")
    if not raw:
        pytest.skip("disposable PostgreSQL not configured")
    url = make_url(raw)
    assert os.environ.get("AD_ANALYZER_CI_DISPOSABLE_POSTGRES") == "true"
    assert url.database and url.database.endswith("_ci")
    assert readiness.database_available(url)
