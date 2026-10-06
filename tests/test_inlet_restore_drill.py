"""Restore-tool guards plus real native PostgreSQL custom-archive roundtrip."""

import os
import shutil
import subprocess
from typing import Any
from uuid import uuid4

import pytest
from scripts import inlet_restore_drill as drill
from sqlalchemy import create_engine, make_url, text


@pytest.mark.parametrize(
    "url",
    [
        "postgresql+psycopg://postgres@127.0.0.1/inlet_prod_ci",
        "postgresql+psycopg://postgres@127.0.0.1/inlet",
        "postgresql+psycopg://postgres@remote.invalid/inlet_test",
        "postgresql+psycopg://postgres@127.0.0.1/inlet_test?options=anything",
        "sqlite:///inlet_test",
    ],
)
def test_unsafe_restore_targets_fail_before_tools(
    monkeypatch: pytest.MonkeyPatch, url: str
) -> None:
    monkeypatch.setenv("AD_ANALYZER_TEST_POSTGRES_URL", url)
    monkeypatch.setenv("AD_ANALYZER_CI_DISPOSABLE_POSTGRES", "true")
    with pytest.raises((SystemExit, drill.DrillError)):
        drill.target()


def test_restore_requires_explicit_disposable_marker(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "AD_ANALYZER_TEST_POSTGRES_URL", "postgresql://postgres@127.0.0.1/inlet_test"
    )
    monkeypatch.delenv("AD_ANALYZER_CI_DISPOSABLE_POSTGRES", raising=False)
    with pytest.raises(SystemExit):
        drill.target()


def test_tools_keep_password_out_of_argv_and_sanitize_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(shutil, "which", lambda name: "/fixture/tool")
    calls = []

    def failed(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[bytes]:
        calls.append((args, kwargs))
        return subprocess.CompletedProcess(
            args, 1, b"fixture-sensitive-output", b"fixture-sensitive-error"
        )

    monkeypatch.setattr(subprocess, "run", failed)
    tools = drill.PostgresTools(
        make_url("postgresql://postgres:synthetic-password@127.0.0.1/inlet_test"), "fixture-pg"
    )
    with pytest.raises(drill.DrillError) as error:
        tools.run("pg_dump", ["--format=custom"])
    assert str(error.value) == "PostgreSQL drill operation failed"
    assert "synthetic-password" not in repr(calls[0][0])
    assert "postgresql://" not in repr(calls[0][0])
    assert "PGPASSWORD" in calls[0][0]
    assert calls[0][1]["env"]["PGPASSWORD"] == "synthetic-password"
    assert calls[0][1]["timeout"] == 120 and calls[0][1]["capture_output"] is True


def test_container_identity_mismatch_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(shutil, "which", lambda name: "/fixture/tool")
    tools = drill.PostgresTools(
        make_url("postgresql://postgres@127.0.0.1/inlet_test"), "fixture-pg"
    )
    monkeypatch.setattr(tools, "run", lambda *args, **kwargs: b"different-server-db")

    class Connection:
        def scalar(self, statement: Any) -> str:
            return "expected-server-db"

    with pytest.raises(drill.DrillError, match="identity mismatch"):
        tools.prove_server(Connection())  # type: ignore[arg-type]


def test_cli_accepts_no_external_backup(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.argv", ["inlet_restore_drill", "--archive", "arbitrary.dump"])
    with pytest.raises(SystemExit) as error:
        drill.main()
    assert error.value.code == 2


def test_cli_suppresses_unexpected_database_diagnostics(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("sys.argv", ["inlet_restore_drill"])

    def fail(container: str | None) -> dict[str, Any]:
        raise RuntimeError("synthetic-secret-and-private-row")

    monkeypatch.setattr(drill, "run_drill", fail)
    assert drill.main() == 1
    output = capsys.readouterr()
    assert "synthetic-secret" not in output.err + output.out
    assert "no database details" in output.err


@pytest.mark.parametrize("failure", [None, "archive", "restore"])
def test_native_synthetic_backup_restore_preserves_isolation(
    monkeypatch: pytest.MonkeyPatch,
    failure: str | None,
) -> None:
    if (
        not os.environ.get("AD_ANALYZER_TEST_POSTGRES_URL")
        or os.environ.get("AD_ANALYZER_CI_DISPOSABLE_POSTGRES") != "true"
    ):
        pytest.skip("explicit disposable PostgreSQL configuration required")
    container = os.environ.get("INLET_RESTORE_POSTGRES_CONTAINER")
    if not container and not all(shutil.which(tool) for tool in ("pg_dump", "pg_restore", "psql")):
        if os.environ.get("CI") == "true":
            pytest.fail("hosted CI requires PostgreSQL dump/restore tools")
        pytest.skip("local PostgreSQL tools or explicit test-container selection required")
    url = drill.target()
    admin = create_engine(url)
    sentinel = "inlet_restore_sentinel_" + uuid4().hex
    with admin.begin() as db:
        db.execute(text(f'CREATE SCHEMA "{sentinel}"'))
    run_id = uuid4()
    monkeypatch.setattr(drill, "uuid4", lambda: run_id)
    try:
        original = drill.PostgresTools.run

        def injected(
            self: drill.PostgresTools, tool: str, args: list[str], payload: bytes | None = None
        ) -> bytes:
            if failure == "archive" and tool == "pg_dump":
                return b"invalid synthetic archive"
            if failure == "restore" and tool == "pg_restore":
                raise drill.DrillError("injected restore failure")
            return original(self, tool, args, payload)

        monkeypatch.setattr(drill.PostgresTools, "run", injected)
        if failure:
            with pytest.raises(drill.DrillError):
                drill.run_drill(container)
        else:
            result = drill.run_drill(container)
            assert result["status"] == "passed" and result["workspaces"] == 2
            assert result["tables_verified"] > 20 and result["rows_verified"] >= 16
            assert result["archive_bytes"] > 0 and result["isolation_verified"] is True
            assert result["live_restore_qualified"] is False
        with admin.connect() as db:
            assert (
                db.scalar(
                    text("SELECT count(*) FROM pg_namespace WHERE nspname=:name"),
                    {"name": sentinel},
                )
                == 1
            )
            assert (
                db.scalar(
                    text("SELECT count(*) FROM pg_namespace WHERE nspname=:name"),
                    {"name": "inlet_restore_" + run_id.hex},
                )
                == 0
            )
    finally:
        with admin.begin() as db:
            db.execute(text(f'DROP SCHEMA "{sentinel}" CASCADE'))
        admin.dispose()


@pytest.mark.parametrize(
    "before,after",
    [
        (
            "status::text = ANY (ARRAY['a'::character varying, 'b'::character varying]::text[])",
            "status::text = ANY (ARRAY['a'::character varying::text, "
            "'b'::character varying::text])",
        ),
        (
            "x AND ((status)::text = ANY ((ARRAY['a'::character varying])::text[]))",
            "x AND ((status)::text = ANY (ARRAY[('a'::character varying)::text]))",
        ),
    ],
)
def test_equivalent_postgresql_text_array_casts(before: str, after: str) -> None:
    assert drill.normalized_text_casts(before) == drill.normalized_text_casts(after)


@pytest.mark.parametrize(
    "before,after",
    [
        ("a AND (b OR c)", "(a AND b) OR c"),
        ("status::text = ANY (ARRAY['a'::text])", "status::text = ANY (ARRAY['b'::text])"),
        ("'literal'::character varying(8)", "'literal'::text"),
        ("amount > 0", "amount >= 0"),
    ],
)
def test_normalization_does_not_hide_changed_constraints(before: str, after: str) -> None:
    assert drill.normalized_text_casts(before) != drill.normalized_text_casts(after)
