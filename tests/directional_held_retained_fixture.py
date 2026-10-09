"""One closed staged source; current reads bracket a genuine original successor claim."""

import json
import os
import re
import signal
import subprocess
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC
from pathlib import Path
from typing import Any

from app import advertising_capabilities
from app.database.session import Base
from app.publication import optimization
from app.publication.optimization_contracts import GoogleBudgetSetV1
from app.publication.replacement_contracts import RepeatOptimizationReview, ReplacementAuditDocument
from scripts.inlet_producer_source_lifetime import SourceLifetime
from scripts.reset_disposable_postgres import validate_disposable_url
from sqlalchemy import Engine, create_engine, event, inspect, make_url, select, text
from sqlalchemy.orm import Session

from tests.candidate_receipt_fixture import CandidateReceiptIds, load_receipt_candidate
from tests.retired_snapshot import MAX_LOG_BYTES, PIN, extract
from tests.test_commerce_measurement import NOW


def graph(engine: Engine) -> dict[str, list[dict[str, Any]]]:
    assert advertising_capabilities.advertising_writes_enabled() is False
    with engine.connect() as connection:
        return {
            table.name: [
                dict(row)
                for row in connection.execute(
                    select(table).order_by(*table.primary_key.columns)
                ).mappings()
            ]
            for table in Base.metadata.sorted_tables
        }


def read_json(path: Path, fields: set[str]) -> dict[str, Any]:
    assert path.is_file() and not path.is_symlink() and 0 < path.stat().st_size <= 8192
    value = json.loads(path.read_text())
    assert type(value) is dict and set(value) == fields
    for key, item in value.items():
        if key in {"workspace_id", "account_id", "mandate_revision", "provider_posts"}:
            assert type(item) is int and item > 0
        elif key == "provider":
            assert item == "google_ads"
        else:
            assert type(item) is str and re.fullmatch(
                r"[a-f0-9]{64}" if key in {"session_digest", "policy_digest"} else r"[a-f0-9]{32}",
                item,
            )
    return value


@dataclass(frozen=True)
class RetainedHeldClaimIds:
    workspace_id: int
    first_attempt_id: str
    attempt_id: str
    run_id: str
    review_id: str
    predecessor_id: str
    successor_id: str
    replacement_id: str


@dataclass
class StagedHeldSource:
    engine: Engine
    original: CandidateReceiptIds
    process: subprocess.Popen[bytes]
    log: Path
    artifacts: Path
    deadline: float
    before: dict[str, list[dict[str, Any]]]
    used: bool = False

    def check_bound(self) -> None:
        assert time.monotonic() < self.deadline, "staged source exceeded total180s"
        assert self.log.stat().st_size <= MAX_LOG_BYTES, "staged source exceeded log bound"

    def claim_successor(self) -> RetainedHeldClaimIds:
        assert not self.used and self.process.poll() is None
        self.used = True
        assert graph(self.engine) == self.before, "current first read changed source"
        self.check_bound()
        assert self.process.stdin
        self.process.stdin.write(b"claim\n")
        self.process.stdin.close()
        while self.process.poll() is None:
            self.check_bound()
            time.sleep(0.05)
        assert self.process.returncode == 0, self.log.read_text()[-6000:]
        self.check_bound()
        result = RetainedHeldClaimIds(
            **read_json(
                self.artifacts / "second.json", set(RetainedHeldClaimIds.__dataclass_fields__)
            )
        )
        validate_transition(self.engine, self.original, result, self.before)
        return result


def validate_transition(
    engine: Engine,
    original: CandidateReceiptIds,
    claim: RetainedHeldClaimIds,
    before: dict[str, list[dict[str, Any]]],
) -> None:
    assert claim.workspace_id == original.workspace_id
    assert claim.first_attempt_id == original.attempt_id != claim.attempt_id
    after = graph(engine)
    expected = deepcopy(before)
    with Session(engine) as db:
        run, review, attempt, request = optimization.evidence_lock(
            db, claim.workspace_id, claim.attempt_id
        )
        assert isinstance(review, RepeatOptimizationReview)
        assert run.id == claim.run_id and run.review_id == claim.review_id
        assert run.reservation_id == claim.successor_id and run.state == "dispatching"
        assert attempt.run_id == run.id and isinstance(request.intent.action, GoogleBudgetSetV1)
        assert request.intent.action.amount_micros == 46_000_000
        _, _, _, first = optimization.evidence_lock(db, claim.workspace_id, original.attempt_id)
        assert request.intent.scope == first.intent.scope
        assert request.intent.mandate == first.intent.mandate
        assert request.intent.target == first.intent.target
        assert request.intent.budget_owner == first.intent.budget_owner
        reported = review.plan.exposure.reported_spend_micros
    added_counts = {
        "provider_execution_reviews": 1,
        "provider_execution_approvals": 1,
        "provider_execution_runs": 1,
        "provider_execution_steps": 1,
        "provider_execution_attempts": 1,
        "provider_exposure_reservations": 1,
        "provider_reservation_replacements": 1,
    }
    added = {}
    for name, count in added_counts.items():
        table = Base.metadata.tables[name]
        keys = [c.name for c in table.primary_key.columns]
        old_keys = {tuple(r[k] for k in keys) for r in before[name]}
        new = [r for r in after[name] if tuple(r[k] for k in keys) not in old_keys]
        assert len(new) == count and all(r["workspace_id"] == original.workspace_id for r in new)
        added[name] = new[0]
        expected[name].extend(new)
        expected[name].sort(key=lambda r: tuple(r[k] for k in keys))
    audit = next(
        r for r in after["provider_reservation_replacements"] if r["id"] == claim.replacement_id
    )
    assert audit["predecessor_id"] == claim.predecessor_id
    assert audit["successor_id"] == claim.successor_id
    assert audit["successor_run_id"] == claim.run_id and audit["review_id"] == claim.review_id
    assert audit["ledger_id"] == original.ledger_id
    document = ReplacementAuditDocument.model_validate(audit["document"])
    assert document.digest() == audit["digest"]
    assert document.predecessor_id == claim.predecessor_id
    assert document.successor_id == claim.successor_id and document.successor_run_id == claim.run_id
    assert document.review_id == claim.review_id and document.review_digest == review.digest()
    assert document.actor == original.actor_id and document.replaced_at == NOW
    assert document.snapshot == review.predecessor and document.evidence == review.replacement
    assert audit["actor"] == original.actor_id and audit["replaced_at"].replace(tzinfo=UTC) == NOW
    approval = added["provider_execution_approvals"]
    assert approval["review_id"] == claim.review_id and approval["review_digest"] == review.digest()
    assert (
        approval["plan_digest"] == review.plan.digest() and approval["actor"] == original.actor_id
    )
    assert approval["approved_at"].replace(tzinfo=UTC) == NOW
    step = added["provider_execution_steps"]
    assert step["run_id"] == claim.run_id and step["step_id"] == optimization.STEP
    assert step["state"] == "dispatching"
    reservation = added["provider_exposure_reservations"]
    assert (
        reservation["id"] == claim.successor_id and reservation["ledger_id"] == original.ledger_id
    )
    assert reservation["amount_micros"] == review.plan.exposure.proposed_owner_upper_micros
    assert reservation["evidence"] == review.plan.exposure.model_dump(mode="json")
    assert reservation["budget_owner_key"] == review.predecessor.budget_owner_key
    assert audit["budget_owner_key"] == reservation["budget_owner_key"]
    assert audit["new_amount_micros"] == reservation["amount_micros"]
    predecessor = next(
        r for r in before["provider_exposure_reservations"] if r["id"] == claim.predecessor_id
    )
    assert audit["old_amount_micros"] == predecessor["amount_micros"]
    for row in expected["provider_exposure_reservations"]:
        if row["id"] == claim.predecessor_id:
            assert row["state"] == "held"
            row["state"] = "superseded"
    held = [r for r in after["provider_exposure_reservations"] if r["state"] == "held"]
    assert len(held) == 1 and held[0]["id"] == claim.successor_id
    first_attempt = next(
        r for r in before["provider_execution_attempts"] if r["id"] == original.attempt_id
    )
    for row in expected["provider_execution_runs"]:
        if row["id"] == first_attempt["run_id"]:
            current = next(r for r in after["provider_execution_runs"] if r["id"] == row["id"])
            value = current["canceled_at"]
            assert value and value.replace(tzinfo=UTC) == NOW
            row["state"] = "canceled"
            row["canceled_at"] = row["canceled_at"] or value
    for row in expected["provider_period_ledgers"]:
        if row["id"] == original.ledger_id:
            current = next(r for r in after["provider_period_ledgers"] if r["id"] == row["id"])
            assert current["last_dispatch_at"].replace(tzinfo=UTC) == NOW
            row["action_count"] += 1
            row["last_dispatch_at"] = current["last_dispatch_at"]
            row["spent_high_water_micros"] = max(row["spent_high_water_micros"], reported)
    assert after == expected
    for name in ("provider_execution_responses", "provider_execution_receipts"):
        assert len(after[name]) == 1 and after[name] == before[name]


@contextmanager
def staged_held_source(customer_engine: Engine, artifacts: Path) -> Iterator[StagedHeldSource]:
    artifacts.mkdir()
    assert artifacts.resolve() == artifacts and not artifacts.is_symlink()
    engine = customer_engine
    if engine.dialect.name == "sqlite":
        engine = create_engine(f"sqlite:///{artifacts / 'current.sqlite'}")
        event.listen(engine, "connect", lambda db, _: db.execute("PRAGMA foreign_keys=ON"))
        Base.metadata.create_all(engine)
        target = str(engine.url)
    else:
        url = make_url(validate_disposable_url())
        assert url.host in {"127.0.0.1", "localhost", "::1"} and not url.query
        assert engine.url == url
        with engine.connect() as db:
            target = str(db.scalar(text("SELECT current_schema()")))
        assert re.fullmatch(r"inlet_test_[a-f0-9]{32}", target)
    lifetime = SourceLifetime.open("directional_held", artifacts)
    process = None
    successful = False
    try:
        tables = set(inspect(engine).get_table_names())
        with engine.connect() as db:
            for name in tables - {"alembic_version"}:
                quoted = engine.dialect.identifier_preparer.quote(name)
                assert db.scalar(text(f"SELECT count(*) FROM {quoted}")) == 0
        root = Path(__file__).resolve().parents[1]
        extract(root, lifetime.source)
        lifetime.extracted()
        log, first = artifacts / "producer.log", artifacts / "first.json"
        with log.open("wb") as output:
            lifetime.child_started()
            started = time.monotonic()
            process = subprocess.Popen(
                [
                    sys.executable,
                    str(root / "tests/fixtures/retired_execution/directional_held_seed_driver.py"),
                    target,
                    str(first),
                ],
                cwd=lifetime.source,
                stdin=subprocess.PIPE,
                stdout=output,
                stderr=subprocess.STDOUT,
                start_new_session=True,
                env=dict(
                    os.environ, INLET_RETIRED_EXECUTION_CHILD=PIN, PYTHONPATH=str(lifetime.source)
                ),
            )
            while not first.exists():
                assert time.monotonic() - started < 180
                assert log.stat().st_size <= MAX_LOG_BYTES
                assert process.poll() is None, log.read_text()[-6000:]
                time.sleep(0.05)
            original = CandidateReceiptIds(
                **read_json(first, set(CandidateReceiptIds.__dataclass_fields__))
            )
            assert original.provider_posts == 1 and process.poll() is None
            assert not (artifacts / "second.json").exists()
            assert set(inspect(engine).get_table_names()) == tables
            with Session(engine) as session:
                load_receipt_candidate(session, original)
            before = graph(engine)
            assert len(before["provider_execution_attempts"]) == 1
            assert len(before["provider_execution_receipts"]) == 1
            source = StagedHeldSource(
                engine, original, process, log, artifacts, started + 180, before
            )
            yield source
            assert source.used and process.poll() == 0
            successful = True
    finally:
        if process is not None:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait(timeout=5)
            if process.stdin and not process.stdin.closed:
                process.stdin.close()
            lifetime.after_reaped(process.returncode)
        if successful:
            lifetime.close()
        if engine is not customer_engine:
            engine.dispose()
