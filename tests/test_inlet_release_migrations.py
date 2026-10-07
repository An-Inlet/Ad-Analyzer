"""Guarded populated PostgreSQL roundtrip across media and context branches."""

import os
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from app.settings import settings
from scripts.reset_disposable_postgres import validate_disposable_url
from sqlalchemy import MetaData, Table, create_engine, inspect, make_url, select, text
from sqlalchemy.engine import Connection

NEW_TABLES = {
    "customer_media_objects",
    "customer_campaign_drafts",
    "customer_campaign_revisions",
    "customer_context_checkpoints",
    "customer_context_quotas",
}
OLD_TABLES = (
    "workspaces",
    "workspace_integrations",
    "advertising_accounts",
    "meta_connections",
    "customer_source_connections",
    "customer_goals",
    "customer_goal_revisions",
    "job_runs",
)
NOW = datetime(2026, 10, 6, tzinfo=UTC)


def test_release_migrations_have_one_merge_head() -> None:
    scripts = ScriptDirectory.from_config(Config("alembic.ini"))
    heads = scripts.get_heads()
    assert len(heads) == 1
    # New packages may extend the release merge without weakening its ancestry.
    assert "20261006_0039" in {
        r.revision for r in scripts.iterate_revisions(heads[0], "20261006_0036")
    }
    merge = scripts.get_revision("20261006_0039")
    assert merge is not None and isinstance(merge.down_revision, tuple)
    assert set(merge.down_revision) == {"20261006_0037", "20261006_0038"}
    assert {r.revision for r in scripts.iterate_revisions("20261006_0039", "20261006_0036")} == {
        "20261006_0037",
        "20261006_0038",
        "20261006_0039",
    }


def insert(db: Connection, table_name: str, **values: Any) -> None:
    table = Table(table_name, MetaData(), autoload_with=db)
    db.execute(table.insert().values(**values))


def snapshot(db: Connection) -> dict[str, list[dict[str, Any]]]:
    return {
        name: [
            dict(row)
            for row in db.execute(select(Table(name, MetaData(), autoload_with=db))).mappings()
        ]
        for name in OLD_TABLES
    }


def preserved(db: Connection, before: dict[str, list[dict[str, Any]]]) -> None:
    after = snapshot(db)
    for name, rows in before.items():
        assert len(after[name]) == len(rows), name
        for row in rows:
            assert any(
                all(new[key] == value for key, value in row.items()) for new in after[name]
            ), name


def test_populated_release_roundtrip(monkeypatch: pytest.MonkeyPatch) -> None:
    if (
        not os.environ.get("AD_ANALYZER_TEST_POSTGRES_URL")
        or os.environ.get("AD_ANALYZER_CI_DISPOSABLE_POSTGRES") != "true"
    ):
        pytest.skip("explicit disposable PostgreSQL configuration required")
    url = validate_disposable_url()
    schema = "inlet_release_" + uuid4().hex
    admin = create_engine(url)
    with admin.begin() as db:
        db.execute(text(f'CREATE SCHEMA "{schema}"'))
    scoped = make_url(url).update_query_dict({"options": f"-csearch_path={schema}"})
    engine = create_engine(scoped)
    monkeypatch.setattr(settings, "database_url", scoped.render_as_string(hide_password=False))
    config = Config("alembic.ini")
    timestamps = {"created_at": NOW, "updated_at": NOW}
    try:
        command.upgrade(config, "20261006_0036")
        with engine.begin() as db:
            insert(
                db,
                "workspaces",
                id=901,
                slug="release-fixture",
                name="Fixture",
                client_name="Fixture",
                status="active",
                is_default=False,
                **timestamps,
            )
            for number, provider in [(901, "meta_ads"), (902, "klaviyo")]:
                insert(
                    db,
                    "workspace_integrations",
                    id=number,
                    workspace_id=901,
                    integration_key=provider,
                    provider=provider,
                    display_name="Fixture",
                    status="active",
                    configuration={},
                    **timestamps,
                )
            insert(
                db,
                "advertising_accounts",
                id=901,
                connection_id=901,
                workspace_id=901,
                platform="meta_ads",
                external_account_id="12345",
                name="Fixture",
                currency_code="USD",
                time_zone="UTC",
                **timestamps,
            )
            insert(
                db,
                "meta_connections",
                id=901,
                workspace_integration_id=901,
                workspace_id=901,
                account_id=901,
                external_account_id="12345",
                status="connected",
                encrypted_credentials="synthetic-encrypted-fixture",
                connected_at=NOW,
                phase="campaigns",
            )
            insert(
                db,
                "customer_source_connections",
                id="source-fixture",
                workspace_id=901,
                integration_id=902,
                provider="klaviyo",
                external_id="fixture-account",
                encrypted_grant="synthetic-encrypted-grant",
                status="connected",
                generation=3,
                window_start=NOW.date(),
                window_end=NOW.date(),
                staged={},
            )
            insert(db, "customer_goals", id="goal-fixture", workspace_id=901, revision=1)
            insert(
                db,
                "customer_goal_revisions",
                goal_id="goal-fixture",
                revision=1,
                workspace_id=901,
                definition={"milestone": "Fixture"},
                editor_id="fixture-user",
                created_at=NOW,
            )
            insert(
                db,
                "job_runs",
                id=901,
                connection_id=901,
                workspace_id=901,
                account_id=901,
                platform="meta_ads",
                job_name="fixture-import",
                status="succeeded",
                started_at=NOW,
                finished_at=NOW,
                records_processed=2,
                **timestamps,
            )
            before = snapshot(db)
            assert NEW_TABLES.isdisjoint(inspect(db).get_table_names())
            assert "generation" not in {
                c["name"] for c in inspect(db).get_columns("meta_connections")
            }
        command.upgrade(config, "20261006_0039")
        with engine.begin() as db:
            preserved(db, before)
            assert set(inspect(db).get_table_names()) >= NEW_TABLES
            assert db.scalar(text("SELECT generation FROM meta_connections WHERE id=901")) == 1
            generation = next(
                c for c in inspect(db).get_columns("meta_connections") if c["name"] == "generation"
            )
            assert generation["nullable"] is False and "1" in str(generation["default"])
            insert(
                db,
                "customer_media_objects",
                id="media-fixture",
                workspace_id=901,
                sha256="a" * 64,
                size=12,
                mime="image/png",
                width=1,
                height=1,
                created_by="fixture-user",
                created_at=NOW,
            )
            insert(db, "customer_campaign_drafts", id="draft-fixture", workspace_id=901, revision=1)
            insert(
                db,
                "customer_campaign_revisions",
                draft_id="draft-fixture",
                revision=1,
                workspace_id=901,
                artifact={"fixture": True},
                digest="b" * 64,
                created_by="fixture-user",
                created_at=NOW,
                approved_by="fixture-user",
                approved_at=NOW,
            )
            insert(
                db,
                "customer_context_quotas",
                key="c" * 64,
                due_at=NOW,
                lease_until=NOW,
                fence="f" * 32,
            )
            insert(
                db,
                "customer_context_checkpoints",
                connection_id="source-fixture",
                generation=3,
                grant_digest="d" * 64,
                encrypted_progress="synthetic-encrypted-progress",
                state="awaiting_ack",
                fence="f" * 32,
                lease_until=NOW,
                ack_digest="e" * 64,
            )
            for name in NEW_TABLES:
                assert db.scalar(text(f"SELECT count(*) FROM {name}")) == 1
            assert db.scalar(text("SELECT version_num FROM alembic_version")) == "20261006_0039"
        command.downgrade(config, "20261006_0036")
        with engine.connect() as db:
            preserved(db, before)
            assert NEW_TABLES.isdisjoint(inspect(db).get_table_names())
            assert "generation" not in {
                c["name"] for c in inspect(db).get_columns("meta_connections")
            }
            assert db.scalar(text("SELECT version_num FROM alembic_version")) == "20261006_0036"
        command.upgrade(config, "20261006_0039")
        with engine.connect() as db:
            preserved(db, before)
            assert set(inspect(db).get_table_names()) >= NEW_TABLES
            for name in NEW_TABLES:
                assert db.scalar(text(f"SELECT count(*) FROM {name}")) == 0
            assert db.scalar(text("SELECT generation FROM meta_connections WHERE id=901")) == 1
            assert db.scalar(text("SELECT version_num FROM alembic_version")) == "20261006_0039"
    finally:
        engine.dispose()
        with admin.begin() as db:
            db.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()
