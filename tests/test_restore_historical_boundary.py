"""Closed tool provenance, target and process cleanup; no advertising authority bypass."""

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from app.settings import settings
from scripts import inlet_restore_drill as drill
from scripts import inlet_restore_historical as historical
from scripts.inlet_restore_bootstrap import expected_bootstrap
from sqlalchemy import Engine, create_engine, text

from tests.test_customer_identity import customer_engine as customer_engine


@pytest.mark.parametrize("argument", ["--seed", "--source", "--target", "--archive"])
def test_no_new_cli_inputs(monkeypatch: pytest.MonkeyPatch, argument: str) -> None:
    monkeypatch.setattr(sys, "argv", ["inlet_restore_drill", argument, "untrusted"])
    with pytest.raises(SystemExit) as caught:
        drill.main()
    assert caught.value.code == 2


@pytest.mark.parametrize("changed", ["commit", "app", "tests", "scripts"])
def test_source_identity_rejected_before_archive(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    changed: str,
) -> None:
    calls: list[tuple[str, ...]] = []

    def git(*arguments: str) -> str:
        calls.append(arguments)
        if arguments[-1] == historical.PIN + "^{commit}":
            return "0" * 40 if changed == "commit" else historical.PIN
        name = arguments[-1].split(":")[-1]
        return "0" * 40 if changed == name else historical.TREES[name]

    monkeypatch.setattr(historical, "_git", git)
    actual_run = subprocess.run

    def run(args: list[str], **kwargs: Any) -> Any:
        assert args[3] == "merge-base", "archive must not start after identity mismatch"
        return actual_run(args, **kwargs)

    monkeypatch.setattr("scripts.inlet_restore_historical.subprocess.run", run)
    with pytest.raises(historical.HistoricalSeedError):
        historical.extract(tmp_path / "source")
    assert calls and not (tmp_path / "source").exists()


def test_child_deadline_reaps_actual_process(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    processes: list[subprocess.Popen[bytes]] = []
    original = subprocess.Popen

    def start(*args: Any, **kwargs: Any) -> subprocess.Popen[bytes]:
        process = original(*args, **kwargs)
        processes.append(process)
        return process

    monkeypatch.setattr("scripts.inlet_restore_historical.subprocess.Popen", start)
    ticks = iter([0.0, 181.0])
    monkeypatch.setattr(
        "scripts.inlet_restore_historical.time.monotonic", lambda: next(ticks, 181.0)
    )
    with pytest.raises(historical.HistoricalSeedError):
        historical._run(
            [sys.executable, "-c", "import time; time.sleep(60)"],
            tmp_path,
            dict(os.environ),
            tmp_path / "child.log",
        )
    assert len(processes) == 1 and processes[0].poll() is not None


def test_default_native_does_not_accept_fixture_schema(
    customer_engine: Engine, tmp_path: Path
) -> None:
    with pytest.raises(historical.HistoricalSeedError):
        historical.seed_retained_graph(customer_engine, tmp_path / "denied")
    assert not (tmp_path / "denied").exists()


def test_metadata_sqlite_target_requires_owned_path(tmp_path: Path) -> None:
    engine = create_engine("sqlite:///" + str(tmp_path / "unowned.sqlite"))
    try:
        with engine.begin() as db:
            db.execute(text("CREATE TABLE harmless (id INTEGER)"))
        with pytest.raises(historical.HistoricalSeedError):
            historical.guard(engine, "fixture")
    finally:
        engine.dispose()


def test_actual_migration_bootstrap_rejects_changed_content(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if not os.environ.get("AD_ANALYZER_TEST_POSTGRES_URL") or (
        os.environ.get("AD_ANALYZER_CI_DISPOSABLE_POSTGRES") != "true"
    ):
        pytest.skip("explicit disposable PostgreSQL required")
    url = drill.target()
    schema = "inlet_restore_" + uuid4().hex
    admin = create_engine(url)
    engine = create_engine(url.update_query_dict({"options": f"-csearch_path={schema}"}))
    with admin.begin() as db:
        db.execute(text(f'CREATE SCHEMA "{schema}"'))
    monkeypatch.setattr(settings, "database_url", engine.url.render_as_string(hide_password=False))
    try:
        command.upgrade(Config("alembic.ini"), "head")
        before = historical.guard(engine, "native")
        assert set(before) == set(expected_bootstrap())
        changes = [
            ("workspaces", "name", "wrong", "Denticode Ad Analyzer", "id=1"),
            (
                "workspace_configurations",
                "automation",
                '{"live_writes_enabled":true}',
                '{"live_writes_enabled":false}',
                "workspace_id=1",
            ),
            (
                "workspace_configurations",
                "automation",
                '{"live_writes_enabled":0}',
                '{"live_writes_enabled":false}',
                "workspace_id=1",
            ),
            ("workspace_integrations", "status", "active", "configured", "id=1"),
            ("measurement_contracts", "click_lookback_days", 91, 90, "workspace_id=1"),
            (
                "measurement_stage_definitions",
                "description",
                "wrong",
                "A new lead entered the CRM.",
                "stage_key='lead'",
            ),
            (
                "measurement_event_mappings",
                "value_behavior",
                "adjust",
                "ignore",
                "source_event_type='lead_created'",
            ),
            ("platform_automation_controls", "enabled", False, True, "key='all_data_syncs'"),
            ("goal_usage_policies", "call_limit", 999, 1000, "scope='global'"),
        ]
        for table, column, changed, original, where in changes:
            statement = text(f"UPDATE {table} SET {column}=:value WHERE {where}")
            with engine.begin() as db:
                db.execute(statement, {"value": changed})
            with pytest.raises(historical.HistoricalSeedError, match="bootstrap mismatch"):
                historical.guard(engine, "native")
            with engine.begin() as db:
                db.execute(statement, {"value": original})
        historical.unchanged_bootstrap(engine, before)
        after = historical.guard(engine, "native")
        for name in before:
            assert sorted(map(str, after[name])) == sorted(map(str, before[name]))
        with engine.begin() as db:
            db.execute(
                text(
                    "INSERT INTO customer_users (id,issuer,subject,email,status) "
                    "VALUES (:id,'fixture','fixture','fixture@example.invalid','active')"
                ),
                {"id": "a" * 32},
            )
        with pytest.raises(historical.HistoricalSeedError):
            historical.guard(engine, "native")
        with engine.begin() as db:
            db.execute(text("DELETE FROM customer_users WHERE id=:id"), {"id": "a" * 32})
        with engine.begin() as db:
            db.execute(text("UPDATE alembic_version SET version_num='unexpected'"))
        with pytest.raises(historical.HistoricalSeedError):
            historical.guard(engine, "native")
    finally:
        engine.dispose()
        with admin.begin() as db:
            db.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


def test_real_cli_success(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    if not os.environ.get("AD_ANALYZER_TEST_POSTGRES_URL") or (
        os.environ.get("AD_ANALYZER_CI_DISPOSABLE_POSTGRES") != "true"
    ):
        pytest.skip("explicit disposable PostgreSQL required")
    container = os.environ.get("INLET_RESTORE_POSTGRES_CONTAINER")
    args = ["inlet_restore_drill"]
    if container:
        args += ["--postgres-container", container]
    monkeypatch.setattr(sys, "argv", args)
    assert drill.main() == 0
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "passed" and result["unknown_attempt_replay_denied"] is True
    assert result["live_restore_qualified"] is False
