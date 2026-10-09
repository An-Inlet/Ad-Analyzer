"""Actual Google captures close only complete original request sets, never financial holds."""

from copy import deepcopy
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
from app.publication import execution_mandates as mandates
from app.publication import optimization as o
from app.publication import replacement as r
from app.publication.execution_authorization import owner_authorizer
from app.publication.execution_models import (
    GoogleOriginalCompletion,
    ProviderExposureReservation,
    ProviderPeriodLedger,
)
from app.publication.google_completion_contracts import GoogleCompletionDocument
from app.publication.google_request_terminal import GoogleTerminalBatch, read_terminal_batch
from app.publication.replacement_contracts import ReplacementEvidence
from app.settings import Settings
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from tests.test_commerce_measurement import NOW
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_durable_optimization import ready
from tests.test_repeat_optimization import admit, reader
from tests.test_shopify_sales import configuration as configuration


def chain(db: Session, config: Settings, path: Path, timeout: bool = False) -> Any:
    wid, actor, binding, scope, target, action, runtime, server = ready(
        db, config, path, "google_ads"
    )
    initial = o.prepare_optimization(
        db, wid, binding, scope, target, action, "a" * 64, actor, runtime, lambda: NOW
    )
    run, claim = admit(db, wid, actor, initial, runtime)
    assert (
        o.execute_claim(db, claim, actor, runtime, lambda: NOW).outcome == "verified_target_state"
    )
    # Only test fixture transition/portfolio proof admits this second request.
    # The production terminal reader is never registered as a ReplacementReader.
    fixture_runtime = replace(runtime, replacement_reader=reader(runtime))
    action = action.model_copy(update={"amount_micros": 44_000_000})
    review = r.prepare_repeat_optimization(
        db,
        wid,
        binding,
        scope,
        run.reservation_id,
        target,
        action,
        "b" * 64,
        actor,
        fixture_runtime,
        lambda: NOW,
    )
    run, claim = admit(db, wid, actor, review, fixture_runtime)
    server.timeout = timeout
    receipt = o.execute_claim(db, claim, actor, fixture_runtime, lambda: NOW)
    assert receipt.outcome == "verified_target_state"  # Readback is not original closure.
    ledger, policy = mandates.checked(db, wid, binding, actor, lambda: NOW)
    snapshot = r.snapshot(db, wid, run.reservation_id, actor, ledger, policy, scope)
    db.commit()
    return wid, actor, binding, snapshot, runtime, target, action


@pytest.mark.retained_execution
@pytest.mark.usefixtures("retained_execution_engine")
@pytest.mark.parametrize(
    "failure",
    [
        None,
        "timeout",
        "omitted_ancestor",
        "fence",
        "environment",
        "capture_tamper",
        "future_capture",
        "ledger_epoch",
        "foreign_actor",
        "session",
        "legacy_first",
        "unsupported",
    ],
)
def test_exact_batch_all_or_nothing(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    failure: str | None,
) -> None:
    with Session(customer_engine) as db:
        wid, actor, binding, snapshot, runtime, target, action = chain(
            db, configuration, tmp_path, failure == "timeout"
        )
        assert len(snapshot.receipts) == 2
        before = [
            (x.id, x.state, x.amount_micros)
            for x in db.scalars(select(ProviderExposureReservation))
        ]
        if failure == "omitted_ancestor":
            snapshot = snapshot.model_copy(update={"receipts": snapshot.receipts[1:]})
        elif failure == "fence":
            snapshot = snapshot.model_copy(
                update={
                    "receipts": [
                        snapshot.receipts[0].model_copy(update={"fence": "f" * 32}),
                        snapshot.receipts[1],
                    ]
                }
            )
        elif failure == "environment":
            snapshot = snapshot.model_copy(update={"environment": "live"})
        elif failure in {"capture_tamper", "future_capture"}:
            row = db.get(GoogleOriginalCompletion, snapshot.receipts[0].attempt_id)
            assert row is not None
            raw = deepcopy(row.document)
            if failure == "capture_tamper":
                raw["capture"]["operation_digest"] = "f" * 64
            else:
                raw["recorded_at"] = (NOW + timedelta(seconds=1)).isoformat()
            row.document = raw
            if failure == "future_capture":
                future = GoogleCompletionDocument.model_validate(raw)
                row.digest, row.recorded_at = future.digest(), future.recorded_at
            db.commit()
        elif failure == "ledger_epoch":
            ledger = db.get(ProviderPeriodLedger, binding.ledger_id)
            assert ledger is not None
            ledger.spent_high_water_micros += 1
            db.commit()
        if failure == "legacy_first":
            # Simulate a retained generic acknowledgment from before typed capture existed.
            old = db.get(GoogleOriginalCompletion, snapshot.receipts[0].attempt_id)
            assert old is not None
            db.delete(old)
            db.commit()
        elif failure == "unsupported":
            account = snapshot.account.model_copy(
                update={
                    "account": snapshot.account.account.model_copy(update={"platform": "meta_ads"})
                }
            )
            snapshot = snapshot.model_copy(update={"account": account})
        if failure == "foreign_actor":
            actor = "foreign-user"

        def authorize(session: Session, workspace: int, current_actor: str) -> None:
            if failure == "session":
                raise HTTPException(401, "original session revoked")
            owner_authorizer(session, workspace, current_actor)

        if failure:
            with pytest.raises(HTTPException):
                read_terminal_batch(db, wid, binding, snapshot, actor, NOW, authorize=authorize)
            db.rollback()
        else:
            batch = read_terminal_batch(db, wid, binding, snapshot, actor, NOW, authorize=authorize)
            assert len(batch.closed_requests) == 2
            assert all(c.basis == "authoritative_request_terminal" for c in batch.closed_requests)
            assert {c.evidence_digest for c in batch.closed_requests} == {
                x.digest for x in db.scalars(select(GoogleOriginalCompletion))
            }
            batch.bind(snapshot, binding, NOW)
            assert (
                "portfolio" not in batch.model_dump()
                and "transition_evidence_digest" not in batch.model_dump()
            )
            with pytest.raises(ValidationError):
                ReplacementEvidence.model_validate(batch.model_dump())
            # Request closure alone never supplies the independent transition source.
            assert runtime.replacement_reader is None
            with pytest.raises(HTTPException, match="closure and transition"):
                r.prepare_repeat_optimization(
                    db,
                    wid,
                    binding,
                    snapshot.account,
                    snapshot.predecessor_id,
                    target,
                    action,
                    "c" * 64,
                    actor,
                    runtime,
                    lambda: NOW,
                )
            for bad_now in (NOW - timedelta(seconds=1), batch.expires_at):
                with pytest.raises(ValueError):
                    batch.bind(snapshot, binding, bad_now)
            raw = batch.model_dump()
            raw["closed_requests"][0]["basis"] = "authoritative_later_effect_impossible"
            with pytest.raises(ValidationError):
                GoogleTerminalBatch.model_validate(raw)
        assert [
            (x.id, x.state, x.amount_micros)
            for x in db.scalars(select(ProviderExposureReservation))
        ] == before
