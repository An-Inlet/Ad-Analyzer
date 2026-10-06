"""Populated PostgreSQL upgrade/downgrade across independent customer branches."""

import os
from typing import Any
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from app.settings import settings
from sqlalchemy import create_engine, inspect, make_url, text
from sqlalchemy.engine import Connection


def test_customer_foundation_has_one_coherent_migration_head() -> None:
    scripts = ScriptDirectory.from_config(Config("alembic.ini"))
    assert len(scripts.get_heads()) == 1
    assert "20261006_0036" in {r.revision for r in scripts.walk_revisions()}
    merge = scripts.get_revision("20261006_0036")
    assert merge is not None
    assert isinstance(merge.down_revision, tuple)
    assert set(merge.down_revision) == {"20261006_0032", "20261006_0035"}
    assert {r.revision for r in scripts.iterate_revisions("20261006_0036", "20261006_0031")} == {
        "20261006_0036",
        "20261006_0035",
        "20261006_0034",
        "20261006_0032",
    }


def test_populated_customer_foundation_roundtrip(monkeypatch: pytest.MonkeyPatch) -> None:
    url = os.environ.get("AD_ANALYZER_TEST_POSTGRES_URL")
    if not url or os.environ.get("AD_ANALYZER_CI_DISPOSABLE_POSTGRES") != "true":
        pytest.skip("explicit disposable PostgreSQL configuration required")
    schema = "inlet_migration_" + uuid4().hex
    admin = create_engine(url)
    with admin.begin() as db:
        db.execute(text(f'CREATE SCHEMA "{schema}"'))
    scoped = make_url(url).update_query_dict({"options": f"-csearch_path={schema}"})
    engine = create_engine(scoped)
    monkeypatch.setattr(settings, "database_url", scoped.render_as_string(hide_password=False))
    config = Config("alembic.ini")
    tables = (
        "workspaces",
        "customer_goals",
        "customer_goal_revisions",
        "analysis_runs",
        "job_runs",
        "google_customer_import_completions",
    )

    def snapshot(db: Connection) -> dict[str, list[dict[str, Any]]]:
        # Only static table names from the tuple above; preserve every original column.
        return {
            table: [dict(row) for row in db.execute(text(f"SELECT * FROM {table}")).mappings()]
            for table in tables
        }

    def preserved(db: Connection, before: dict[str, list[dict[str, Any]]]) -> None:
        current = snapshot(db)
        for table in tables:
            assert len(current[table]) == len(before[table])
            for old in before[table]:
                assert any(
                    all(new[key] == value for key, value in old.items()) for new in current[table]
                )

    try:
        command.upgrade(config, "20261006_0031")
        with engine.begin() as db:
            db.execute(
                text("""INSERT INTO workspaces
                (id, slug, name, client_name, status, is_default, created_at, updated_at)
                VALUES (919, 'migration-fixture', 'Fixture', 'Fixture', 'active', false,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)""")
            )
            db.execute(
                text("""INSERT INTO customer_goals (id, workspace_id, revision)
                VALUES ('existing-goal', 919, 1)""")
            )
            db.execute(
                text("""INSERT INTO customer_goal_revisions
                (goal_id, revision, workspace_id, definition, editor_id, created_at)
                VALUES ('existing-goal', 1, 919, '{"milestone":"Fixture"}', 'fixture-user',
                CURRENT_TIMESTAMP)""")
            )
            db.execute(
                text("""INSERT INTO job_runs
                (id, workspace_id, platform, job_name, status, started_at, finished_at,
                 records_processed, created_at, updated_at)
                VALUES (919, 919, 'tiktok_ads', 'fixture_import', 'succeeded', CURRENT_TIMESTAMP,
                CURRENT_TIMESTAMP, 3, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)""")
            )
            db.execute(
                text("""INSERT INTO google_customer_import_completions (job_id, state)
                VALUES (919, 'pending')""")
            )
            db.execute(
                text("""INSERT INTO analysis_runs
                (id, workspace_id, run_key, cadence, status, schedule_policy_version,
                 scheduled_for, metric_date_from, metric_date_to, outcome_date_from,
                 outcome_date_to, started_at, finished_at, accounts_analyzed, findings_count,
                 high_severity_findings_count, recommendations_created_count,
                 recommendations_deduplicated_count, outcome_analysis_ready,
                 outcome_campaign_count, attributed_journey_count, unattributed_journey_count,
                 blocking_reasons, error_code, created_at, updated_at)
                VALUES (919, 919, 'fixture-existing-failure', 'nightly', 'failed', 'v1',
                 CURRENT_TIMESTAMP, '2026-10-01', '2026-10-05', '2026-10-01', '2026-10-05',
                 CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 0, 0, 0, 0, 0, false, 0, 0, 0, '[]',
                 'analysis_unavailable', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)""")
            )
            before = snapshot(db)
        command.upgrade(config, "head")
        with engine.begin() as db:
            preserved(db, before)
            assert db.execute(
                text("SELECT retry_history, retry_count FROM analysis_runs WHERE id=919")
            ).one() == ([], 0)
            assert (
                db.scalar(
                    text(
                        "SELECT next_attempt_at FROM google_customer_import_completions "
                        "WHERE job_id=919"
                    )
                )
                is None
            )
            db.execute(
                text("""INSERT INTO customer_goal_creations
                (workspace_id, user_id, request_key, fingerprint, goal_id)
                VALUES (919, 'fixture-user', 'fixture-request',
                        'fixture-fingerprint', 'existing-goal')""")
            )
            db.execute(
                text(
                    """UPDATE analysis_runs
                    SET retry_history='[{"error_code":"analysis_unavailable"}]',
                    retry_count=1 WHERE id=919"""
                )
            )
            db.execute(
                text(
                    """UPDATE google_customer_import_completions
                    SET next_attempt_at=CURRENT_TIMESTAMP
                    WHERE job_id=919"""
                )
            )
        command.downgrade(config, "20261006_0031")
        with engine.connect() as db:
            preserved(db, before)
            assert "customer_goal_creations" not in inspect(db).get_table_names()
            assert "retry_history" not in {
                c["name"] for c in inspect(db).get_columns("analysis_runs")
            }
            assert "next_attempt_at" not in {
                c["name"] for c in inspect(db).get_columns("google_customer_import_completions")
            }
        command.upgrade(config, "head")
        with engine.connect() as db:
            preserved(db, before)
            assert db.scalar(text("SELECT count(*) FROM customer_goal_creations")) == 0
            assert db.execute(
                text("SELECT retry_history, retry_count FROM analysis_runs WHERE id=919")
            ).one() == ([], 0)
            assert (
                db.scalar(
                    text(
                        "SELECT next_attempt_at FROM google_customer_import_completions "
                        "WHERE job_id=919"
                    )
                )
                is None
            )
            assert (
                db.scalar(text("SELECT version_num FROM alembic_version"))
                == ScriptDirectory.from_config(config).get_current_head()
            )
    finally:
        engine.dispose()
        with admin.begin() as db:
            db.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()
