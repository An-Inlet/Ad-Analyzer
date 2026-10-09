"""One genuine original receipt, then exactly one current reconciliation append."""

import json
import os
import re
import sys
from collections.abc import Iterator
from copy import deepcopy
from dataclasses import asdict, dataclass, replace
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
from app import advertising_capabilities
from app.commerce.evidence import digest
from app.database.session import Base
from app.publication import optimization as optimization
from app.publication.execution_models import ProviderExecutionReceipt
from app.publication.optimization_contracts import GoogleBudgetSetV1, OptimizationRequest
from scripts.reset_disposable_postgres import validate_disposable_url
from sqlalchemy import Engine, create_engine, event, inspect, make_url, select, text
from sqlalchemy.orm import Session

from tests.retired_snapshot import PIN, extract, run_bounded


@dataclass(frozen=True)
class CandidateReceiptIds:
    workspace_id: int
    actor_id: str
    session_digest: str
    mandate_id: str
    mandate_revision: int
    consent_id: str
    policy_digest: str
    ledger_id: str
    account_id: int
    store_id: str
    publication_id: str
    provider: str
    provider_posts: int
    attempt_id: str
    receipt_id: str


def effects(engine: Engine) -> dict[str, list[dict[str, Any]]]:
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
            if table.name.startswith("provider_") or table.name == "mandate_actions"
        }


def load_receipt_candidate(db: Session, ids: CandidateReceiptIds) -> tuple[Any, ...]:
    from tests.candidate_read_retained_fixture import CandidateReadIds, load_candidate_read_fixture

    base = {
        key: value
        for key, value in asdict(ids).items()
        if key in CandidateReadIds.__dataclass_fields__
    }
    principal, work, observation, policy, runtime, server = load_candidate_read_fixture(
        db, CandidateReadIds(**base)
    )
    receipt = optimization.read_owned_outcome_receipt(
        db, ids.workspace_id, ids.attempt_id, ids.actor_id
    )
    assert receipt and receipt.receipt_id == ids.receipt_id and receipt.sequence == 1
    assert receipt.outcome == "verified_target_state"
    source = work.scope.source.model_copy(
        update={
            "attempt_id": ids.attempt_id,
            "receipt_id": receipt.receipt_id,
            "receipt_sequence": receipt.sequence,
            "receipt_digest": receipt.receipt_digest,
            "projection_digest": digest(
                ["inlet.owned-receipt.v1", receipt.model_dump(mode="json")]
            ),
        }
    )
    scope = work.scope.model_copy(update={"source": source})
    work = work.model_copy(update={"scope": scope})
    observation = observation.model_copy(
        update={
            "scope": scope,
            "evidence": observation.evidence.model_copy(update={"scope_digest": scope.digest()}),
        }
    )
    runtime = replace(runtime, reader=lambda db, scope, now: observation)
    assert not server.writes
    return principal, work, observation, policy, runtime, server


def reconciled(
    engine: Engine, ids: CandidateReceiptIds, before: dict[str, list[dict[str, Any]]]
) -> None:
    from tests.test_commerce_measurement import NOW

    after = effects(engine)
    original = before["provider_execution_receipts"]
    assert len(original) == 1 and original[0]["id"] == ids.receipt_id
    appended = [row for row in after["provider_execution_receipts"] if row["id"] != ids.receipt_id]
    assert len(appended) == 1 and len(after["provider_execution_receipts"]) == 2
    new = appended[0]
    assert new["workspace_id"] == ids.workspace_id and new["attempt_id"] == ids.attempt_id
    assert new["sequence"] == 2 and new["supersedes_id"] == ids.receipt_id
    with Session(engine) as db:
        run, _, _, request = optimization.evidence_lock(db, ids.workspace_id, ids.attempt_id)
        expected_receipt = optimization.unknown(request, lambda: NOW + timedelta(seconds=1))
        assert new["receipt"] == expected_receipt.model_dump(mode="json")
        latest = optimization.read_owned_outcome_receipt(
            db, ids.workspace_id, ids.attempt_id, ids.actor_id
        )
        assert latest and latest.receipt_id == new["id"] and latest.sequence == 2
        assert latest.outcome == "unknown" and latest.model_dump(mode="json") == new["projection"]
        assert db.get(ProviderExecutionReceipt, ids.receipt_id)
        run_id = run.id
    expected = deepcopy(before)
    expected["provider_execution_receipts"].append(new)
    expected["provider_execution_receipts"].sort(key=lambda row: row["id"])
    for table in ("provider_execution_runs", "provider_execution_steps"):
        assert len(expected[table]) == 1
        row = expected[table][0]
        assert (row["id"] if table == "provider_execution_runs" else row["run_id"]) == run_id
        assert row["state"] == "verified_target_state"
        row["state"] = "unknown"
    assert after == expected


@pytest.fixture
def receipt_candidate_source(
    customer_engine: Engine, tmp_path: Path
) -> Iterator[tuple[Engine, CandidateReceiptIds]]:
    artifacts = tmp_path / "candidate-receipt-source"
    artifacts.mkdir()
    engine = customer_engine
    if engine.dialect.name == "sqlite":
        engine = create_engine(f"sqlite:///{artifacts / 'current.sqlite'}")
        event.listen(engine, "connect", lambda db, _: db.execute("PRAGMA foreign_keys=ON"))
        Base.metadata.create_all(engine)
        target = str(engine.url)
    else:
        url = make_url(validate_disposable_url())
        assert url.host in {"localhost", "127.0.0.1", "::1"} and not url.query
        assert engine.url == url
        with engine.connect() as connection:
            target = str(connection.scalar(text("SELECT current_schema()")))
        assert re.fullmatch(r"inlet_test_[a-f0-9]{32}", target)
    try:
        assert all(not rows for rows in effects(engine).values())
        tables = set(inspect(engine).get_table_names())
        root = Path(__file__).resolve().parents[1]
        snapshot = artifacts / "source"
        extract(root, snapshot)
        output, log = artifacts / "ids.json", artifacts / "producer.log"
        code = run_bounded(
            [
                sys.executable,
                str(root / "tests/fixtures/retired_execution/candidate_receipt_seed_driver.py"),
                target,
                str(output),
            ],
            snapshot,
            dict(os.environ, INLET_RETIRED_EXECUTION_CHILD=PIN, PYTHONPATH=str(snapshot)),
            log,
            180,
        )
        assert code == 0, log.read_text()[-6000:]
        assert 0 < output.stat().st_size <= 4096
        raw = json.loads(output.read_text())
        assert type(raw) is dict and set(raw) == set(CandidateReceiptIds.__dataclass_fields__)
        for key, value in raw.items():
            if key in {"workspace_id", "mandate_revision", "account_id", "provider_posts"}:
                assert type(value) is int and value > 0
            elif key == "provider":
                assert value == "google_ads"
            else:
                assert type(value) is str and re.fullmatch(
                    r"[a-f0-9]{64}"
                    if key in {"session_digest", "policy_digest"}
                    else r"[a-f0-9]{32}",
                    value,
                )
        ids = CandidateReceiptIds(**raw)
        assert ids.provider_posts == 1
        assert set(inspect(engine).get_table_names()) == tables
        before = effects(engine)
        for table in (
            "provider_execution_attempts",
            "provider_execution_responses",
            "provider_execution_receipts",
            "provider_exposure_reservations",
        ):
            assert len(before[table]) == 1
        assert before["provider_execution_attempts"][0]["id"] == ids.attempt_id
        request = OptimizationRequest.model_validate(
            before["provider_execution_attempts"][0]["request"]
        )
        assert isinstance(request.intent.action, GoogleBudgetSetV1)
        assert request.intent.action.amount_micros == 45_000_000
        assert before["provider_exposure_reservations"][0]["state"] == "held"
        try:
            yield engine, ids
        finally:
            reconciled(engine, ids, before)
    finally:
        if engine is not customer_engine:
            engine.dispose()
