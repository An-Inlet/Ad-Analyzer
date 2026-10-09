"""Synthetic filesystem transitions plus real local subprocess completion; no database."""

import hashlib
import json
import os
import signal
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from scripts import inlet_producer_source_lifetime as lifetime

from tests.retired_snapshot import run_bounded


def opened(path: Path, monkeypatch: pytest.MonkeyPatch) -> lifetime.SourceLifetime:
    """Small synthetic file manifest; real PIN/tree/driver provenance checks remain."""
    original = lifetime._git
    data = b"pass\n"
    oid = hashlib.sha1(b"blob 5\0" + data).hexdigest()

    def git(*args: str) -> bytes:
        if args[:2] == ("ls-tree", "-rz"):
            return f"100644 blob {oid}\tsample.py\0".encode()
        return original(*args)

    monkeypatch.setattr(lifetime, "_git", git)
    path.mkdir()
    lease = lifetime.SourceLifetime.open("candidate_dual", path)
    lease.source.mkdir()
    (lease.source / "sample.py").write_bytes(data)
    return lease


@pytest.mark.parametrize("code", [0, 7])
def test_completed_child_cleanup_preserves_sibling_outputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, code: int
) -> None:
    lease = opened(tmp_path / "artifacts", monkeypatch)
    sentinel = lease.source.parent / "ids.json"
    sentinel.write_bytes(b"actual-output")
    unrelated = lease.source.parent / "other-source"
    unrelated.mkdir()
    (unrelated / "unique").write_bytes(b"keep")
    with lease:
        lease.extracted()
        lease.child_started()
        result = run_bounded(
            [sys.executable, "-c", f"raise SystemExit({code})"],
            lease.source,
            dict(os.environ),
            lease.source.parent / "producer.log",
            5,
        )
        lease.after_reaped(result)
    assert not lease.source.exists()
    assert sentinel.read_bytes() == b"actual-output"
    assert (unrelated / "unique").read_bytes() == b"keep"
    record = json.loads(lease.record.read_text())
    assert record["state"] == "removed" and record["returncode"] == code
    assert record["pin"] == lifetime.PIN and len(record["driver_sha256"]) == 64
    assert set(record["trees"]) == {"app", "tests", "scripts"}


@pytest.mark.parametrize(
    "change", ["unique", "modified", "symlink", "wrong_cache", "empty_directory"]
)
def test_unique_or_modified_source_is_retained(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, change: str
) -> None:
    lease = opened(tmp_path / "artifacts", monkeypatch)
    lease.extracted()
    if change == "modified":
        (lease.source / "sample.py").write_bytes(b"changed")
    elif change == "empty_directory":
        (lease.source / "unique-empty").mkdir()
    elif change == "symlink":
        (lease.source / "link").symlink_to(tmp_path)
    else:
        path = lease.source / (
            "__pycache__/unknown.cpython-312.pyc" if change == "wrong_cache" else "unique.sqlite"
        )
        path.parent.mkdir(exist_ok=True)
        path.write_bytes(b"do-not-delete")
    with pytest.raises(lifetime.SourceLifetimeError):
        lease.close()
    assert lease.source.is_dir()
    record = json.loads(lease.record.read_text())
    assert record["state"] == "retained_cleanup_error"
    assert record["retained_entry"]["path"]


def test_expected_python_cache_is_disposable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    lease = opened(tmp_path / "artifacts", monkeypatch)
    with lease:
        lease.extracted()
        cache = lease.source / "__pycache__"
        cache.mkdir()
        (cache / f"sample.{sys.implementation.cache_tag}.pyc").write_bytes(b"derived-cache")
    assert not lease.source.exists()


def test_active_child_and_unconfirmed_exception_retain_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    lease = opened(tmp_path / "artifacts", monkeypatch)
    lease.extracted()
    lease.child_started()
    child = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(60)"],
        cwd=lease.source,
        start_new_session=True,
    )
    try:
        lease.close()
        assert child.poll() is None and lease.source.exists()
        assert json.loads(lease.record.read_text())["state"] == "retained_unconfirmed"
    finally:
        os.killpg(child.pid, signal.SIGTERM)
        child.wait(timeout=5)


def test_runner_exception_retains_source_and_primary_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    lease = opened(tmp_path / "artifacts", monkeypatch)
    with pytest.raises(RuntimeError, match="runner failure"), lease:
        lease.extracted()
        lease.child_started()
        raise RuntimeError("runner failure")
    assert lease.source.exists()
    assert json.loads(lease.record.read_text())["state"] == "retained_unconfirmed"


def test_record_failure_cannot_delete_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    lease = opened(tmp_path / "artifacts", monkeypatch)
    lease.extracted()

    def fail() -> Any:
        raise OSError("controlled record failure")

    monkeypatch.setattr(lease, "_record", fail)
    with pytest.raises(OSError, match="controlled"):
        lease.close()
    assert lease.source.exists()


def test_partial_extraction_owned_archive_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    lease = opened(tmp_path / "artifacts", monkeypatch)
    (lease.source / "sample.py").unlink()
    lease.archive.write_bytes(b"partial-reproducible-archive")
    sibling = lease.source.parent / "other.tar"
    sibling.write_bytes(b"unique")
    lease.close()
    assert not lease.source.exists() and not lease.archive.exists()
    assert sibling.read_bytes() == b"unique"
    assert json.loads(lease.record.read_text())["partial_archive"]["bytes"] > 0


@pytest.mark.parametrize("kind", ["unknown", "existing", "symlink"])
def test_registry_and_fresh_path_required(tmp_path: Path, kind: str) -> None:
    if kind == "existing":
        (tmp_path / "source").mkdir()
    elif kind == "symlink":
        (tmp_path / "source").symlink_to(tmp_path)
    with pytest.raises(lifetime.SourceLifetimeError):
        lifetime.SourceLifetime.open(
            "arbitrary" if kind == "unknown" else "candidate_dual", tmp_path
        )


def test_partial_extraction_exception_preserves_primary_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    lease = opened(tmp_path / "artifacts", monkeypatch)
    with pytest.raises(RuntimeError, match="extraction failed"), lease:
        (lease.source / "sample.py").unlink()
        lease.archive.write_bytes(b"partial archive")
        raise RuntimeError("extraction failed")
    assert not lease.source.exists() and not lease.archive.exists()
    assert json.loads(lease.record.read_text())["state"] == "removed"
