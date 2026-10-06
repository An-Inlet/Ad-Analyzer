"""Isolated populated PostgreSQL lifecycle migration, preserving prior tenant state."""

import os
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from app.settings import settings
from scripts.reset_disposable_postgres import validate_disposable_url
from sqlalchemy import create_engine, inspect, make_url, text
from sqlalchemy.exc import IntegrityError

from tests.test_inlet_release_migrations import NOW, insert


def test_lifecycle_migration_reserved_parent() -> None:
    scripts = ScriptDirectory.from_config(Config("alembic.ini"))
    revision = scripts.get_revision("20261006_0044")
    assert revision is not None and revision.down_revision == "20261006_0042"


def test_lifecycle_populated_upgrade_downgrade(monkeypatch: pytest.MonkeyPatch) -> None:
    if (
        not os.environ.get("AD_ANALYZER_TEST_POSTGRES_URL")
        or os.environ.get("AD_ANALYZER_CI_DISPOSABLE_POSTGRES") != "true"
    ):
        pytest.skip("explicit disposable PostgreSQL configuration required")
    url = validate_disposable_url()
    schema = "inlet_lifecycle_" + uuid4().hex
    admin = create_engine(url)
    with admin.begin() as db:
        db.execute(text(f'CREATE SCHEMA "{schema}"'))
    scoped = make_url(url).update_query_dict({"options": f"-csearch_path={schema}"})
    engine = create_engine(scoped)
    monkeypatch.setattr(settings, "database_url", scoped.render_as_string(hide_password=False))
    config = Config("alembic.ini")
    try:
        command.upgrade(config, "20261006_0042")
        with engine.begin() as db:
            for wid in (901, 902):
                insert(
                    db,
                    "workspaces",
                    id=wid,
                    slug=f"closure-{wid}",
                    name="Fixture",
                    client_name="Fixture",
                    status="active",
                    is_default=False,
                    created_at=NOW,
                    updated_at=NOW,
                )
            insert(
                db,
                "customer_users",
                id="u" * 32,
                issuer="fixture",
                subject="owner",
                email="owner@example.test",
                status="active",
            )
            before = db.execute(text("SELECT * FROM workspaces ORDER BY id")).all()
        command.upgrade(config, "20261006_0044")
        with engine.begin() as db:
            assert db.execute(text("SELECT * FROM workspaces ORDER BY id")).all() == before
            insert(
                db,
                "customer_lifecycle_requests",
                id="a" * 32,
                workspace_id=901,
                requested_by="u" * 32,
                operation="close",
                key_digest="b" * 64,
                request_digest="c" * 64,
                schema_version="inlet.lifecycle.request.v1",
                state="requested",
                revision=1,
                fence="d" * 32,
                disposition_policy=None,
                blockers=[],
                created_at=NOW,
                updated_at=NOW,
            )
            insert(
                db,
                "customer_lifecycle_steps",
                request_id="a" * 32,
                step_key="inventory",
                workspace_id=901,
                request_revision=1,
                fence="d" * 32,
                state="running",
                attempts=1,
            )
            for sql in [
                "UPDATE customer_lifecycle_steps SET workspace_id=902",
                "UPDATE customer_lifecycle_requests SET disposition_policy='invented'",
                "UPDATE customer_lifecycle_requests SET operation='purge'",
            ]:
                with pytest.raises(IntegrityError), db.begin_nested():
                    db.execute(text(sql))
        command.downgrade(config, "20261006_0042")
        with engine.connect() as db:
            assert db.execute(text("SELECT * FROM workspaces ORDER BY id")).all() == before
            assert "customer_lifecycle_requests" not in inspect(db).get_table_names()
        command.upgrade(config, "20261006_0044")
        with engine.connect() as db:
            assert db.scalar(text("SELECT count(*) FROM customer_lifecycle_requests")) == 0
            assert db.scalar(text("SELECT count(*) FROM customer_users")) == 1
    finally:
        engine.dispose()
        with admin.begin() as db:
            db.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()
