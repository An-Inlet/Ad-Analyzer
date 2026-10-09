"""Actual closed child rejects invalid handoff without adding a successor."""

import time
from pathlib import Path

import pytest
from sqlalchemy import create_engine

from tests import directional_held_retained_fixture as fixture


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
