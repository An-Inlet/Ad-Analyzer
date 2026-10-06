"""0053 populated workspace upgrade/rollback against disposable PostgreSQL."""

import os
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from app.settings import settings
from scripts.reset_disposable_postgres import validate_disposable_url
from sqlalchemy import create_engine, inspect, make_url, text

from tests.test_customer_lifecycle import NOW


def test_workspace_privacy_migration_populated_roundtrip(monkeypatch: pytest.MonkeyPatch) -> None:
    if (
        not os.environ.get("AD_ANALYZER_TEST_POSTGRES_URL")
        or os.environ.get("AD_ANALYZER_CI_DISPOSABLE_POSTGRES") != "true"
    ):
        pytest.skip("explicit disposable PostgreSQL required")
    url = validate_disposable_url()
    schema = "inlet_export_privacy_" + uuid4().hex
    admin = create_engine(url)
    with admin.begin() as db:
        db.execute(text(f'CREATE SCHEMA "{schema}"'))
    scoped = make_url(url).update_query_dict({"options": f"-csearch_path={schema}"})
    engine = create_engine(scoped)
    monkeypatch.setattr(settings, "database_url", scoped.render_as_string(hide_password=False))
    config = Config("alembic.ini")
    try:
        command.upgrade(config, "20261006_0047")
        with engine.begin() as db:
            db.execute(
                text(
                    "INSERT INTO workspaces "
                    "(slug,name,client_name,status,is_default,created_at,updated_at) "
                    "VALUES ('preserved','Preserved','Preserved','closing',false,:now,:now)"
                ),
                {"now": NOW},
            )
        command.upgrade(config, "20261006_0053")
        with engine.begin() as db:
            assert (
                db.execute(
                    text("SELECT export_privacy_revision FROM workspaces WHERE slug='preserved'")
                ).scalar_one()
                == 0
            )
            db.execute(
                text("UPDATE workspaces SET export_privacy_revision=19 WHERE slug='preserved'")
            )
        command.downgrade(config, "20261006_0047")
        assert "export_privacy_revision" not in {
            c["name"] for c in inspect(engine).get_columns("workspaces")
        }
        with engine.connect() as db:
            assert (
                db.execute(
                    text("SELECT status FROM workspaces WHERE slug='preserved'")
                ).scalar_one()
                == "closing"
            )
        command.upgrade(config, "20261006_0053")
        with engine.connect() as db:
            assert (
                db.execute(
                    text("SELECT export_privacy_revision FROM workspaces WHERE slug='preserved'")
                ).scalar_one()
                == 0
            )
    finally:
        engine.dispose()
        with admin.begin() as db:
            db.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()
