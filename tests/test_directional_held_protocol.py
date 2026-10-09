"""Actual closed child rejects invalid handoff without adding a successor."""

import signal
import sys
import time
from pathlib import Path

import pytest
from sqlalchemy import create_engine

from tests import directional_held_retained_fixture as fixture
from tests.retired_snapshot import PIN


@pytest.mark.parametrize("change", ["unknown", "duplicate", "eof", "deadline", "output"])
def test_staged_source_failure_preserves_original_and_reaps(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, change: str
) -> None:
    engine = create_engine("sqlite://")
    artifacts = tmp_path / "closed-source"
    process = None
    before = None
    source_engine = None
    try:
        with pytest.raises(AssertionError), fixture.staged_held_source(engine, artifacts) as source:
            process, before, source_engine = source.process, source.before, source.engine
            assert process.stdin
            if change in {"unknown", "duplicate", "eof"}:
                command = {"unknown": b"other\n", "duplicate": b"claim\nclaim\n", "eof": b""}[
                    change
                ]
                process.stdin.write(command)
                process.stdin.close()
                while process.poll() is None:
                    source.check_bound()
                    time.sleep(0.05)
                assert process.returncode != 0
                assert fixture.graph(source.engine) == before
                assert not (artifacts / "second.json").exists()
                raise AssertionError("intentional rejected command")
            if change == "deadline":
                source.deadline = time.monotonic() - 1
            else:
                monkeypatch.setattr(fixture, "MAX_LOG_BYTES", 1)
                source.log.write_bytes(b"xx")
            source.claim_successor()
        assert process is not None and process.poll() is not None
        assert source_engine is not None and fixture.graph(source_engine) == before
        assert (artifacts / "source").is_dir()
        assert not (artifacts / "second.json").exists()
    finally:
        engine.dispose()


@pytest.mark.parametrize("kind", ["relative", "dotdot", "symlink", "ancestor"])
def test_artifact_alias_rejected_before_mkdir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    target = tmp_path / "missing"
    if kind == "relative":
        target = Path("relative")
    elif kind == "dotdot":
        target = tmp_path / "unused" / ".." / "missing"
    elif kind == "symlink":
        target.symlink_to(tmp_path / "absent", target_is_directory=True)
    else:
        alias = tmp_path / "alias"
        alias.symlink_to(tmp_path, target_is_directory=True)
        target = alias / "missing"
    engine = create_engine("sqlite://")
    monkeypatch.setattr(Path, "mkdir", lambda *a, **k: pytest.fail("mkdir before validation"))
    try:
        with pytest.raises(AssertionError), fixture.staged_held_source(engine, target):
            pytest.fail("accepted unsafe artifacts")
    finally:
        engine.dispose()


@pytest.mark.parametrize("kind", ["query", "other", "dotdot", "symlink", "ancestor"])
def test_parent_and_child_reject_sqlite_alias_before_factory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    import app

    from tests.fixtures.retired_execution import directional_held_seed_driver as child

    database = tmp_path / "current.sqlite"
    database.touch()
    target = f"sqlite:///{database}"
    if kind == "query":
        target += "?mode=rw"
    elif kind == "other":
        other = tmp_path / "other.sqlite"
        other.touch()
        target = f"sqlite:///{other}"
    elif kind == "dotdot":
        target = f"sqlite:///{tmp_path / 'unused' / '..' / 'current.sqlite'}"
    elif kind == "symlink":
        alias = tmp_path / "alias.sqlite"
        alias.symlink_to(database)
        target = f"sqlite:///{alias}"
    else:
        alias = tmp_path / "alias"
        alias.symlink_to(tmp_path, target_is_directory=True)
        target = f"sqlite:///{alias / 'current.sqlite'}"
    with pytest.raises(AssertionError):
        fixture.owned_sqlite_target(target, database)
    monkeypatch.setattr(child, "create_engine", lambda *a, **k: pytest.fail("factory reached"))
    monkeypatch.setattr(signal, "alarm", lambda seconds: None)
    monkeypatch.setenv("INLET_RETIRED_EXECUTION_CHILD", PIN)
    monkeypatch.setenv("PYTHONPATH", str(Path(app.__file__).resolve().parent.parent))
    monkeypatch.setattr(sys, "argv", ["driver", target, str(tmp_path / "first.json")])
    with pytest.raises(AssertionError):
        child.main()
