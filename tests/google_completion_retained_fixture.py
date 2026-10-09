"""Exact original completion source, current readers and closed expected deltas."""

import json
import os
import re
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app import advertising_capabilities
from app.database.models import register_models
from app.database.session import Base
from app.publication import customer_intents, optimization
from app.publication.contracts import fingerprint
from app.publication.execution_models import (
    GoogleOriginalCompletion,
    ProviderExecutionReceipt,
    ProviderExecutionResponse,
    ProviderExposureReservation,
)
from app.publication.google_completion import read_owned
from app.publication.optimization_contracts import OptimizationReceipt, OptimizationResponse
from app.publication.service import owner
from app.shopify.security import utc
from scripts.inlet_producer_source_lifetime import SourceLifetime
from scripts.reset_disposable_postgres import validate_disposable_url
from sqlalchemy import Engine, create_engine, event, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from tests.financial_origin_retained_fixture import fresh_rows, schema_snapshot
from tests.retired_snapshot import PIN, extract, run_bounded
from tests.test_commerce_measurement import NOW


@dataclass(frozen=True)
class GoogleCompletionIds:
    workspace_id: int
    actor_id: str
    attempt_id: str
    fence: str
    request_digest: str
    completion_digest: str
    response_digest: str
    receipt_id: str
    receipt_sequence: int
    receipt_digest: str
    reservation_id: str
    reservation_amount_micros: int
    provider_posts: int


def graph(engine: Engine) -> dict[str, list[dict[str, Any]]]:
    assert not advertising_capabilities.advertising_writes_enabled()
    with engine.connect() as connection:
        return {
            table.name: [
                dict(row)
                for row in connection.execute(
                    select(table).order_by(*table.primary_key.columns)
                ).mappings()
            ]
            for table in Base.metadata.sorted_tables
            if table.name.startswith("provider_")
            or table.name
            in {
                "mandate_actions",
                "optimization_mandate_preparations",
                "google_original_completions",
            }
        }


def assert_delta(
    before: dict[str, list[dict[str, Any]]],
    after: dict[str, list[dict[str, Any]]],
    ids: GoogleCompletionIds,
    purpose: str,
    tamper: str | None,
) -> None:
    expected = deepcopy(before)
    row = expected["google_original_completions"][0]
    assert row["attempt_id"] == ids.attempt_id
    if tamper == "document":
        row["document"]["capture"]["operation_digest"] = "f" * 64
    elif tamper == "scope":
        row["document"]["capture"]["account"]["workspace_id"] += 1000
    elif tamper in {"fence", "request", "digest"}:
        field = "request_digest" if tamper == "request" else tamper
        row[field] = "f" * (32 if tamper == "fence" else 64)
    if purpose == "closure":
        for mandate in expected["provider_execution_mandates"]:
            assert mandate["workspace_id"] == ids.workspace_id
            mandate["state"] = "revoked"
        for run in expected["provider_execution_runs"]:
            assert run["workspace_id"] == ids.workspace_id
            if run["canceled_at"] is None:
                run["state"] = "canceled"
                # SQLite stores naive datetimes; preserve the database's own representation.
                observed = next(r for r in after["provider_execution_runs"] if r["id"] == run["id"])
                assert utc(observed["canceled_at"]) == NOW
                run["canceled_at"] = observed["canceled_at"]
        for action in expected["mandate_actions"]:
            assert action["workspace_id"] == ids.workspace_id
            action["cancel_requested"] = True
    assert after == expected


@contextmanager
def retained_google_completion(
    original: Engine,
    artifacts: Path,
    *,
    purpose: str,
    tamper: str | None = None,
) -> Iterator[tuple[Engine, GoogleCompletionIds]]:
    assert purpose in {"reader", "closure"}
    assert tamper in {None, "document", "fence", "request", "digest", "scope"}
    assert purpose == "reader" or tamper is None
    artifacts.mkdir(parents=True)
    root = Path(__file__).resolve().parents[1]
    engine = original
    if original.dialect.name == "sqlite":
        engine = create_engine(f"sqlite:///{artifacts / 'current.sqlite'}")
        event.listen(engine, "connect", lambda db, _: db.execute("PRAGMA foreign_keys=ON"))
        register_models().create_all(engine)
        target = str(engine.url)
    else:
        base = make_url(validate_disposable_url())
        assert (
            base.host in {"localhost", "127.0.0.1", "::1"} and not base.query and engine.url == base
        )
        with engine.connect() as connection:
            target = str(connection.scalar(text("SELECT current_schema()")))
        assert re.fullmatch(r"inlet_test_[a-f0-9]{32}", target)
    try:
        assert fresh_rows(engine) == {}
        schema = schema_snapshot(engine)
        with SourceLifetime.open("google_completion", artifacts) as lifetime:
            extract(root, lifetime.source)
            lifetime.extracted()
            output, log = artifacts / "ids.json", artifacts / "producer.log"
            lifetime.child_started()
            code = run_bounded(
                [
                    sys.executable,
                    str(root / "tests/fixtures/retired_execution/google_completion_seed_driver.py"),
                    target,
                    str(output),
                ],
                lifetime.source,
                dict(
                    os.environ, INLET_RETIRED_EXECUTION_CHILD=PIN, PYTHONPATH=str(lifetime.source)
                ),
                log,
                180,
            )
            lifetime.after_reaped(code)
        assert code == 0, log.read_text()[-6000:]
        assert schema_snapshot(engine) == schema and output.stat().st_size <= 4096
        raw = json.loads(output.read_text())
        assert type(raw) is dict and set(raw) == set(GoogleCompletionIds.__dataclass_fields__)
        for key, value in raw.items():
            if key in {
                "workspace_id",
                "receipt_sequence",
                "reservation_amount_micros",
                "provider_posts",
            }:
                assert type(value) is int and value > 0
            else:
                assert type(value) is str and re.fullmatch(
                    r"[a-f0-9]{64}" if key.endswith("digest") else r"[a-f0-9]{32}", value
                )
        ids = GoogleCompletionIds(**raw)
        assert ids.provider_posts == 1
        with Session(engine) as db:
            owner(db, ids.workspace_id, ids.actor_id)
            run, _, attempt, request = optimization.evidence_lock(
                db, ids.workspace_id, ids.attempt_id
            )
            assert attempt.fence == ids.fence and request.digest() == ids.request_digest
            document = read_owned(db, ids.workspace_id, ids.attempt_id, ids.actor_id, NOW)
            assert document and document.digest() == ids.completion_digest
            binding = customer_intents.binding(
                db,
                ids.workspace_id,
                request.intent.mandate.mandate_id,
                request.intent.mandate.revision,
            )
            assert binding == request.intent.mandate
            response = db.scalars(select(ProviderExecutionResponse)).one()
            assert response.attempt_id == ids.attempt_id and response.digest == ids.response_digest
            normalized = OptimizationResponse.model_validate(response.response)
            assert normalized.request_digest == ids.request_digest
            assert (
                fingerprint("inlet.optimization-response.v1", normalized.model_dump(mode="json"))
                == ids.response_digest
            )
            receipt = db.scalars(select(ProviderExecutionReceipt)).one()
            assert receipt.id == ids.receipt_id and receipt.sequence == ids.receipt_sequence
            assert receipt.attempt_id == ids.attempt_id and receipt.digest == ids.receipt_digest
            parsed = OptimizationReceipt.model_validate(receipt.receipt)
            optimization.validate_receipt(request, parsed)
            assert parsed.outcome == "verified_target_state"
            assert (
                fingerprint("inlet.optimization-receipt.v1", parsed.model_dump(mode="json"))
                == ids.receipt_digest
            )
            hold = db.scalars(select(ProviderExposureReservation)).one()
            assert hold.id == ids.reservation_id == run.reservation_id
            assert hold.ledger_id == binding.ledger_id and hold.state == "held"
            assert hold.amount_micros == ids.reservation_amount_micros
            assert db.scalars(select(GoogleOriginalCompletion)).one().attempt_id == ids.attempt_id
        before = graph(engine)
        try:
            yield engine, ids
        finally:
            assert_delta(before, graph(engine), ids, purpose, tamper)
    finally:
        if engine is not original:
            engine.dispose()
