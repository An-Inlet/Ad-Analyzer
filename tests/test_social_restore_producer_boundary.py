"""Bounded child lifecycle, independent of any database or provider."""

import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from tests.social_migration_retained_fixture import stop_child, wait_child
from tests.social_restore_boundary import read_output


def test_waiting_child_deadline_terminates_and_reaps(tmp_path: Path) -> None:
    log = tmp_path / "child.log"
    with log.open("wb") as output:
        child = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(60)"],
            stdout=output,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        try:
            with pytest.raises(AssertionError, match="deadline"):
                wait_child(child, log, time.monotonic() - 181, tmp_path / "ready.json")
        finally:
            stop_child(child)
        assert child.poll() is not None
        with pytest.raises(ProcessLookupError):
            os.kill(child.pid, 0)


def test_failed_child_is_not_a_successful_handoff(tmp_path: Path) -> None:
    log = tmp_path / "child.log"
    with log.open("wb") as output:
        child = subprocess.Popen(
            [sys.executable, "-c", "raise SystemExit(7)"],
            stdout=output,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        try:
            with pytest.raises(AssertionError):
                wait_child(child, log, time.monotonic(), tmp_path / "ready.json")
        finally:
            stop_child(child)
        assert child.returncode == 7


@pytest.mark.parametrize("body", ['{"workspace_id":true}', '{"workspace_id":1,"extra":1}'])
def test_scalar_handoff_rejects_coercion_and_extra_fields(tmp_path: Path, body: str) -> None:
    path = tmp_path / "ids.json"
    path.write_text(body)
    with pytest.raises(AssertionError):
        read_output(path, {"workspace_id"})


def test_actual_parent_schema_cleanup_after_child_deadline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.settings import settings
    from scripts.reset_disposable_postgres import validate_disposable_url
    from sqlalchemy import create_engine, make_url, text

    from tests import social_migration_retained_fixture as helper
    from tests.test_social_configuration_migration import test_populated_no_dsa_review_roundtrip

    if not os.environ.get("AD_ANALYZER_TEST_POSTGRES_URL") or (
        os.environ.get("AD_ANALYZER_CI_DISPOSABLE_POSTGRES") != "true"
    ):
        pytest.skip("explicit disposable PostgreSQL required")
    original = helper.wait_child
    observed: list[tuple[str, subprocess.Popen[bytes]]] = []

    def expired(
        process: subprocess.Popen[bytes], log: Path, started: float, output: Path | None = None
    ) -> None:
        if output is None:
            options = make_url(settings.database_url).query["options"]
            assert isinstance(options, str)
            schema = options.removeprefix("-csearch_path=")
            observed.append((schema, process))
            original(process, log, time.monotonic() - 181, output)
        else:
            original(process, log, started, output)

    monkeypatch.setattr(helper, "wait_child", expired)
    with pytest.raises(AssertionError, match="deadline"):
        test_populated_no_dsa_review_roundtrip(monkeypatch, tmp_path)
    assert len(observed) == 1
    schema, process = observed[0]
    assert process.poll() is not None
    admin = create_engine(validate_disposable_url())
    try:
        with admin.connect() as db:
            assert (
                db.scalar(
                    text("SELECT count(*) FROM pg_namespace WHERE nspname=:schema"),
                    {"schema": schema},
                )
                == 0
            )
    finally:
        admin.dispose()
