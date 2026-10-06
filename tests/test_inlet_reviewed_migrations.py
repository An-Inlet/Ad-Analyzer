"""Populated guarded PostgreSQL roundtrip for publication and Meta child state."""

import os
from datetime import timedelta
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
from sqlalchemy.exc import IntegrityError

from tests.test_inlet_release_migrations import NOW, OLD_TABLES, insert

NEW_TABLES = {
    "publication_plans",
    "publication_steps",
    "publication_receipts",
    "meta_detail_checkpoints",
    "meta_detail_staged_pages",
}
PRESERVED = (
    *OLD_TABLES,
    "customer_media_objects",
    "customer_campaign_drafts",
    "customer_campaign_revisions",
    "customer_context_quotas",
    "customer_context_checkpoints",
    "spending_mandates",
    "mandate_actions",
)


def snapshot(db: Connection) -> dict[str, list[dict[str, Any]]]:
    return {
        name: [
            dict(row)
            for row in db.execute(select(Table(name, MetaData(), autoload_with=db))).mappings()
        ]
        for name in PRESERVED
    }


def test_reviewed_migrations_have_one_merge_head() -> None:
    scripts = ScriptDirectory.from_config(Config("alembic.ini"))
    assert scripts.get_heads() == ["20261006_0042"]
    merge = scripts.get_revision("20261006_0042")
    assert merge is not None and isinstance(merge.down_revision, tuple)
    assert set(merge.down_revision) == {"20261006_0040", "20261006_0041"}
    assert {r.revision for r in scripts.iterate_revisions("head", "20261006_0039")} == {
        "20261006_0040",
        "20261006_0041",
        "20261006_0042",
    }


def test_populated_reviewed_roundtrip(monkeypatch: pytest.MonkeyPatch) -> None:
    if (
        not os.environ.get("AD_ANALYZER_TEST_POSTGRES_URL")
        or os.environ.get("AD_ANALYZER_CI_DISPOSABLE_POSTGRES") != "true"
    ):
        pytest.skip("explicit disposable PostgreSQL configuration required")
    url = validate_disposable_url()
    schema = "inlet_reviewed_" + uuid4().hex
    admin = create_engine(url)
    with admin.begin() as db:
        db.execute(text(f'CREATE SCHEMA "{schema}"'))
    scoped = make_url(url).update_query_dict({"options": f"-csearch_path={schema}"})
    engine = create_engine(scoped)
    monkeypatch.setattr(settings, "database_url", scoped.render_as_string(hide_password=False))
    config = Config("alembic.ini")
    timestamps = {"created_at": NOW, "updated_at": NOW}
    try:
        command.upgrade(config, "20261006_0039")
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
            insert(
                db,
                "workspaces",
                id=902,
                slug="other-reviewed-fixture",
                name="Other Fixture",
                client_name="Other Fixture",
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
            insert(
                db,
                "spending_mandates",
                id="mandate-fixture",
                workspace_id=901,
                revision=1,
                starts_at=NOW,
                ends_at=NOW + timedelta(days=1),
                state="approved",
                paused=True,
                observed_micros=0,
                reserved_micros=0,
                changes_used=0,
                actions_used=0,
            )
            insert(
                db,
                "mandate_actions",
                id="action-fixture",
                mandate_id="mandate-fixture",
                workspace_id=901,
                draft={"synthetic": True},
                digest="1" * 64,
                state="draft",
                cancel_requested=False,
            )
            before = snapshot(db)
            assert NEW_TABLES.isdisjoint(inspect(db).get_table_names())
        command.upgrade(config, "20261006_0042")
        with engine.begin() as db:
            assert snapshot(db) == before
            assert set(inspect(db).get_table_names()) >= NEW_TABLES
            insert(
                db,
                "publication_plans",
                id="plan-fixture",
                workspace_id=901,
                action_id="action-fixture",
                digest="2" * 64,
                document={"synthetic": True},
                state="draft",
            )
            insert(
                db,
                "publication_steps",
                plan_id="plan-fixture",
                step_id="step-fixture",
                workspace_id=901,
                state="pending",
                attempt=0,
                request={"synthetic": True},
            )
            insert(
                db,
                "publication_receipts",
                id="receipt-fixture",
                plan_id="plan-fixture",
                step_id="step-fixture",
                workspace_id=901,
                digest="3" * 64,
                request={"synthetic": True},
                receipt={"synthetic": True},
                recorded_at=NOW,
            )
            insert(
                db,
                "meta_detail_checkpoints",
                connection_id=901,
                workspace_id=901,
                account_id=901,
                integration_id=901,
                generation=1,
                window_start=NOW.date(),
                window_end=NOW.date(),
                phase="ads",
                cursor="synthetic-cursor",
                seen_cursors=[],
                page_count=1,
                row_count=1,
                byte_count=10,
            )
            insert(
                db,
                "meta_detail_staged_pages",
                connection_id=901,
                page_number=1,
                payload={"synthetic": True},
            )
            for name in NEW_TABLES:
                assert db.scalar(text(f"SELECT count(*) FROM {name}")) == 1
            # Composite ownership must reject references with a mismatched workspace.
            for statement in (
                "UPDATE publication_plans SET workspace_id=902",
                "UPDATE publication_steps SET workspace_id=902",
                "UPDATE publication_receipts SET workspace_id=902",
                "UPDATE meta_detail_checkpoints SET workspace_id=902",
                "UPDATE meta_detail_staged_pages SET connection_id=902",
            ):
                with pytest.raises(IntegrityError), db.begin_nested():
                    db.execute(text(statement))
            assert db.scalar(text("SELECT version_num FROM alembic_version")) == "20261006_0042"
        command.downgrade(config, "20261006_0039")
        with engine.connect() as db:
            assert snapshot(db) == before
            assert NEW_TABLES.isdisjoint(inspect(db).get_table_names())
            assert "uq_mandate_action_scope" not in {
                c["name"] for c in inspect(db).get_unique_constraints("mandate_actions")
            }
            assert db.scalar(text("SELECT version_num FROM alembic_version")) == "20261006_0039"
        command.upgrade(config, "20261006_0042")
        with engine.connect() as db:
            assert snapshot(db) == before
            assert set(inspect(db).get_table_names()) >= NEW_TABLES
            for name in NEW_TABLES:
                assert db.scalar(text(f"SELECT count(*) FROM {name}")) == 0
            assert "uq_mandate_action_scope" in {
                c["name"] for c in inspect(db).get_unique_constraints("mandate_actions")
            }
            assert db.scalar(text("SELECT version_num FROM alembic_version")) == "20261006_0042"
    finally:
        engine.dispose()
        with admin.begin() as db:
            db.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()
