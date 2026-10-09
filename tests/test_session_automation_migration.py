"""0072 reversible only while empty; semantic consumption cannot be downgraded away."""

import os
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from app.session_automation.models import SessionAutomationRun
from app.settings import Settings, settings
from scripts.reset_disposable_postgres import validate_disposable_url
from sqlalchemy import create_engine, inspect, make_url, text
from sqlalchemy.orm import Session

from tests.session_migration_retained_fixture import retained_session_migration_source
from tests.test_shopify_sales import configuration as configuration


def test_0072_empty_roundtrip_and_populated_refusal(
    monkeypatch: pytest.MonkeyPatch, configuration: Settings, tmp_path: Path
) -> None:
    if not os.environ.get("AD_ANALYZER_TEST_POSTGRES_URL") or (
        os.environ.get("AD_ANALYZER_CI_DISPOSABLE_POSTGRES") != "true"
    ):
        pytest.skip("explicit disposable PostgreSQL required")
    admin = create_engine(validate_disposable_url())
    schema = "inlet_auto_" + uuid4().hex
    with admin.begin() as db:
        db.execute(text(f'CREATE SCHEMA "{schema}"'))
    scoped = make_url(validate_disposable_url()).update_query_dict(
        {"options": f"-csearch_path={schema}"}
    )
    engine = create_engine(scoped)
    monkeypatch.setattr(settings, "database_url", scoped.render_as_string(hide_password=False))
    config = Config("alembic.ini")
    try:
        command.upgrade(config, "20261006_0072")
        command.downgrade(config, "20261006_0068")
        assert "session_automation_runs" not in inspect(engine).get_table_names()
        command.upgrade(config, "heads")
        with retained_session_migration_source(engine, tmp_path / "original") as ids:
            identifier = ids.run_id
            with pytest.raises(RuntimeError, match="cannot be discarded"):
                command.downgrade(config, "20261006_0068")
            with Session(engine) as db:
                assert db.get(SessionAutomationRun, identifier)
    finally:
        engine.dispose()
        with admin.begin() as db:
            db.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()
