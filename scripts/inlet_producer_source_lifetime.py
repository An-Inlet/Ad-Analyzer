"""Allowlisted immutable extraction lifetime; never a generic directory cleaner."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from types import TracebackType
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PIN = "2155ff3e3ab00cd62057dd86cb49d45359d4f49f"
BUDGET_PIN = "745acee533638f6f937339110944454cd8ce2a83"
TREES = {
    "app": "6507ee4da861c63ebbc9ce0210c558c0de19d873",
    "tests": "06cc6a9ecb7466c3e94a5bd6558ea73befbbe4cc",
    "scripts": "c49d7769faa20df001536e6f819a1e1f7c860c57",
}
BUDGET_TREES = {
    "app": "e2abf13cbbca4f80001b2054da449360d0bfe5f2",
    "tests": "a4be5cd63965896d8f04cf2f43dbda0fa368bb82",
    "scripts": TREES["scripts"],
}


@dataclass(frozen=True)
class Profile:
    helper: str
    driver: str
    leaf: str = "source"
    pin: str = PIN
    archive: str = "historical-source.tar"


def _test(
    helper: str,
    driver: str,
    leaf: str = "source",
    *,
    pin: str = PIN,
    archive: str = "historical-source.tar",
) -> Profile:
    return Profile(
        f"tests/{helper}.py", f"tests/fixtures/retired_execution/{driver}.py", leaf, pin, archive
    )


PROFILES = {
    "meta_review_lock": _test("meta_review_lock_retained_fixture", "meta_review_lock_seed_driver"),
    "provider_ddl": _test("provider_ddl_retained_fixture", "provider_ddl_seed_driver"),
    "google_created": _test("google_created_retained_fixture", "google_created_seed_driver"),
    "late_publication": _test("late_publication_retained_fixture", "late_publication_seed_driver"),
    "google_completion": _test(
        "google_completion_retained_fixture", "google_completion_seed_driver"
    ),
    "configured_candidate": _test(
        "configured_candidate_retained_fixture", "configured_candidate_seed_driver"
    ),
    "candidate_review_link": _test(
        "candidate_review_link_retained_fixture", "candidate_review_link_seed_driver"
    ),
    "session_migration": _test(
        "session_migration_retained_fixture", "session_migration_seed_driver"
    ),
    "financial_origin": _test("financial_origin_retained_fixture", "financial_origin_seed_driver"),
    **{
        name: _test("retired_producer_fixture", "seed_driver", "historical-source")
        for name in ("review", "initial_rule", "native_diagnostic", "commerce_publication_0053")
    },
    **{
        name: _test("retired_migration_producer", "migration_seed_driver", "historical-source")
        for name in ("candidate_result_0062", "replacement_0058")
    },
    "budget_preparation_0079": _test(
        "retired_migration_producer",
        "migration_seed_driver",
        "historical-source",
        pin=BUDGET_PIN,
        archive="historical-budget-source.tar",
    ),
    "candidate_read": _test("candidate_read_retained_fixture", "candidate_read_seed_driver"),
    "campaign_review": _test("campaign_review_retained_fixture", "campaign_review_seed_driver"),
    "social_producer": _test("social_producer_retained_fixture", "social_producer_seed_driver"),
    "configured_draft": _test("configured_draft_retained_fixture", "configured_draft_seed_driver"),
    "tiktok_draft": _test("tiktok_draft_retained_fixture", "tiktok_draft_seed_driver"),
    "optimization_source": _test(
        "optimization_source_retained_fixture", "optimization_source_seed_driver"
    ),
    "reported_original": _test("reported_original_fixture", "reported_original_seed_driver"),
    "reported_planning_original": _test(
        "reported_planning_original_fixture", "reported_planning_original_seed_driver"
    ),
    "reported_planning_relative_original": _test(
        "reported_planning_relative_fixture", "reported_planning_relative_seed_driver"
    ),
    "directional_held": _test("directional_held_retained_fixture", "directional_held_seed_driver"),
    "candidate_receipt": _test("candidate_receipt_fixture", "candidate_receipt_seed_driver"),
    "feedback_erasure": _test("feedback_erasure_retained_fixture", "feedback_erasure_seed_driver"),
    "candidate_dual": _test("candidate_worker_fixture", "candidate_worker_seed_driver"),
    "reported_restore": _test(
        "reported_restore_retained_fixture", "reported_restore_seed_driver", archive="source.tar"
    ),
    "social_configuration": _test(
        "social_migration_retained_fixture", "social_migration_seed_driver", archive="source.tar"
    ),
    "restore_fixture": Profile(
        "scripts/inlet_restore_historical.py",
        "scripts/inlet_restore_seed_child.py",
        "historical-source",
        archive="source.tar",
    ),
}


class SourceLifetimeError(RuntimeError):
    pass


def _require(value: bool, message: str) -> None:
    if not value:
        raise SourceLifetimeError(message)


def _git(*args: str) -> bytes:
    return subprocess.check_output(["git", "-C", str(ROOT), *args], timeout=30)


class SourceLifetime:
    """Trusted allowlisted caller protocol; a runner exception never implies reap."""

    @classmethod
    def open(cls, profile: str, artifacts: Path) -> SourceLifetime:
        return cls(profile, artifacts)

    def __init__(self, profile: str, artifacts: Path) -> None:
        _require(profile in PROFILES, "unregistered producer source profile")
        spec = PROFILES[profile]
        _require(
            artifacts.is_dir() and artifacts.resolve() == artifacts.absolute(),
            "artifact directory must be canonical and owned",
        )
        self.source = artifacts / spec.leaf
        self.archive = artifacts / spec.archive
        self.record = artifacts / "source-lifetime.json"
        _require(
            not any(
                p.exists() or p.is_symlink()
                for p in (self.source, self.archive, self.record, self.record.with_suffix(".tmp"))
            ),
            "source lifetime cannot adopt existing content",
        )
        _require(
            _git("rev-parse", spec.pin + "^{commit}").decode().strip() == spec.pin,
            "literal source commit unavailable",
        )
        subprocess.run(
            ["git", "-C", str(ROOT), "merge-base", "--is-ancestor", spec.pin, "HEAD"],
            check=True,
            timeout=30,
        )
        trees = BUDGET_TREES if spec.pin == BUDGET_PIN else TREES
        for name, value in trees.items():
            _require(
                _git("rev-parse", spec.pin + ":" + name).decode().strip() == value,
                "literal source tree unavailable",
            )
        self.expected: dict[str, str] = {}
        for row in _git("ls-tree", "-rz", spec.pin).split(b"\0"):
            if not row:
                continue
            info, path = row.split(b"\t", 1)
            mode, kind, oid = info.split()
            _require(
                kind == b"blob" and mode in {b"100644", b"100755"},
                "unsupported immutable source entry",
            )
            self.expected[path.decode()] = oid.decode()
        self.identity: tuple[int, int] | None = None
        self.started = False
        self.reaped = False
        self.complete = False
        self.closed = False
        stat = artifacts.stat()
        self.parent_identity = (stat.st_dev, stat.st_ino)
        self.data: dict[str, Any] = {
            "schema": "inlet.producer-source-lifetime.v1",
            "profile": profile,
            "source": str(self.source),
            "pin": spec.pin,
            "root_tree": _git("rev-parse", spec.pin + "^{tree}").decode().strip(),
            "trees": trees,
            "helper": spec.helper,
            "driver": spec.driver,
            "driver_sha256": hashlib.sha256((ROOT / spec.driver).read_bytes()).hexdigest(),
            "extractor_archive": spec.archive,
            "state": "allocated",
        }
        self._record()

    def _record(self) -> None:
        raw = json.dumps(self.data, sort_keys=True, indent=2) + "\n"
        _require(len(raw.encode()) <= 1024 * 1024, "source provenance exceeds bound")
        pending = self.record.with_suffix(".tmp")
        pending.write_text(raw)
        pending.replace(self.record)

    def _inventory(self, *, partial: bool = False) -> None:
        parent = self.source.parent.stat()
        _require(
            (parent.st_dev, parent.st_ino) == self.parent_identity,
            "artifact directory identity changed",
        )
        _require(
            not self.source.is_symlink() and self.source.resolve() == self.source.absolute(),
            "source path identity changed",
        )
        stat = self.source.stat()
        identity = (stat.st_dev, stat.st_ino)
        _require(self.identity is None or self.identity == identity, "source directory replaced")
        self.identity = identity
        entries = []
        observed = set()
        directories = {
            parent.as_posix()
            for path in self.expected
            for parent in Path(path).parents
            if parent != Path(".")
        }
        python_parents = {
            Path(path).parent.as_posix() for path in self.expected if path.endswith(".py")
        }

        for directory, folders, files in os.walk(self.source, followlinks=False):
            for name in folders + files:
                item = Path(directory) / name
                directory_entry = item.relative_to(self.source).as_posix()
                if item.is_symlink():
                    self.data["retained_entry"] = {"path": directory_entry, "kind": "symlink"}
                    raise SourceLifetimeError("source contains symlink")
                if name in folders and not (
                    directory_entry in directories
                    or (
                        name == "__pycache__"
                        and item.relative_to(self.source).parent.as_posix() in python_parents
                    )
                ):
                    self.data["retained_entry"] = {
                        "path": directory_entry,
                        "kind": "unknown_directory",
                    }
                    raise SourceLifetimeError("source contains unknown directory")
            for name in files:
                path = Path(directory) / name
                relative = path.relative_to(self.source)
                value = path.read_bytes()
                key = relative.as_posix()
                if key in self.expected:
                    oid = hashlib.sha1(
                        b"blob " + str(len(value)).encode() + b"\0" + value
                    ).hexdigest()
                    if oid != self.expected[key]:
                        self.data["retained_entry"] = {
                            "path": key,
                            "sha256": hashlib.sha256(value).hexdigest(),
                        }
                        raise SourceLifetimeError("immutable source bytes changed")
                    observed.add(key)
                else:
                    original = relative.parent.parent / (name.split(".", 1)[0] + ".py")
                    if not (
                        relative.parent.name == "__pycache__"
                        and name.endswith(f".{sys.implementation.cache_tag}.pyc")
                        and original.as_posix() in self.expected
                    ):
                        self.data["retained_entry"] = {
                            "path": key,
                            "sha256": hashlib.sha256(value).hexdigest(),
                        }
                        raise SourceLifetimeError("source contains unique or unknown output")
                entries.append((key, len(value), hashlib.sha256(value).hexdigest()))
        _require(partial or observed == set(self.expected), "immutable source inventory incomplete")
        self.data["inventory"] = {
            "files": len(entries),
            "bytes": sum(v[1] for v in entries),
            "sha256": hashlib.sha256(json.dumps(sorted(entries)).encode()).hexdigest(),
            "device": identity[0],
            "inode": identity[1],
        }

    def extracted(self) -> None:
        _require(not self.started and not self.complete, "invalid extraction transition")
        self._inventory()
        self.complete = True
        self.data["state"] = "extracted"
        self._record()

    def child_started(self) -> None:
        _require(self.complete and not self.started, "invalid child transition")
        self.started = True
        self.data["state"] = "child_started"
        self._record()

    def after_reaped(self, returncode: int) -> None:
        _require(
            self.started and not self.reaped and type(returncode) is int,
            "invalid child completion transition",
        )
        self.reaped = True
        self.data["completion"] = "success" if returncode == 0 else "nonzero_reaped"
        self.data["returncode"] = returncode
        self._record()

    def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        if self.started and not self.reaped:
            self.data["state"] = "retained_unconfirmed"
            self._record()
            return
        try:
            _require(not self.complete or self.source.exists(), "source disappeared")
            if self.source.exists() or self.source.is_symlink():
                self._inventory(partial=not self.complete)
            if self.archive.exists() or self.archive.is_symlink():
                _require(not self.archive.is_symlink(), "extractor archive is a symlink")
                self.data["partial_archive"] = {
                    "bytes": self.archive.stat().st_size,
                    "sha256": hashlib.sha256(self.archive.read_bytes()).hexdigest(),
                }
            self.data["state"] = "cleanup_authorized"
            self._record()
            if self.source.exists():
                shutil.rmtree(self.source)
            if self.archive.exists():
                self.archive.unlink()
            self.data["state"] = "removed"
            self._record()
        except Exception:
            self.data["state"] = "retained_cleanup_error"
            self._record()
            raise

    def __enter__(self) -> SourceLifetime:
        return self

    def __exit__(
        self,
        kind: type[BaseException] | None,
        error: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        try:
            self.close()
        except Exception:
            if error is None:
                raise
            error.add_note(
                "Producer source cleanup retained content or could not complete provenance"
            )
