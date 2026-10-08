"""The final readable reservation must stay settleable; never admit a 33rd."""

from dataclasses import replace
from datetime import timedelta
from pathlib import Path

import pytest
from app.publication import coordinator as c
from app.publication import execution_mandates as mandates
from app.publication import optimization as o
from app.publication import replacement as r
from app.publication import settlement
from app.publication.execution_models import ProviderExposureReservation
from app.publication.replacement_contracts import RepeatOptimizationReview
from app.settings import Settings
from fastapi import HTTPException
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from tests.test_commerce_measurement import NOW
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_durable_optimization import ready
from tests.test_provider_settlement import qualified
from tests.test_repeat_optimization import admit, reader
from tests.test_shopify_sales import configuration as configuration

pytestmark = [pytest.mark.retained_execution, pytest.mark.usefixtures("retained_execution_engine")]


def test_exact_history_limit_rejects_successor_and_preserves_terminal_settlement(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
) -> None:
    with Session(customer_engine) as db:
        wid, actor, binding, scope, target, action, runtime, _ = ready(
            db, configuration, tmp_path, "google_ads"
        )
        _, mandate = mandates.owned(db, wid, binding.mandate_id)
        policy = mandates.policy(db, mandate).model_copy(update={"action_limit": 100})
        mandate = mandates.revise(
            db,
            wid,
            policy,
            actor,
            lambda: NOW,
            mandate_id=mandate.id,
            expected_revision=mandate.revision,
        )
        binding = mandates.consent(
            db, wid, mandate.id, mandate.revision, policy.digest(), actor, lambda: NOW
        )
        review = o.prepare_optimization(
            db, wid, binding, scope, target, action, "a" * 64, actor, runtime, lambda: NOW
        )
        run, claim = admit(db, wid, actor, review, runtime)
        assert (
            o.execute_claim(db, claim, actor, runtime, lambda: NOW).outcome
            == "verified_target_state"
        )
        runtime = replace(runtime, replacement_reader=reader(runtime))
        action = action.model_copy(update={"amount_micros": 44_000_000})
        # Each canceled unattempted successor still inherits the first real request.
        # The chain, not the number of emitted requests, is the capacity boundary.
        for _ in range(31):
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
                runtime,
                lambda: NOW,
            )
            o.approve_optimization(
                db, wid, review.id, review.digest, review.plan_digest, actor, runtime, lambda: NOW
            )
            run = o.create_run(db, wid, review.id, actor, runtime, lambda: NOW)
            r.transfer(
                db,
                wid,
                run,
                RepeatOptimizationReview.model_validate(review.document),
                actor,
                runtime,
                lambda: NOW,
            )
            c.cancel_creation(db, wid, run.id, actor, lambda: NOW)
        assert run.reservation_id is not None
        retained = run.reservation_id
        with pytest.raises(HTTPException, match="history capacity"):
            r.prepare_repeat_optimization(
                db,
                wid,
                binding,
                scope,
                retained,
                target,
                action,
                "c" * 64,
                actor,
                runtime,
                lambda: NOW,
            )
        db.rollback()
        reservation = db.get(ProviderExposureReservation, retained)
        assert reservation is not None and reservation.state == "held"
        _, _, snapshot = settlement.locked_snapshot(db, wid, retained, actor)
        assert len(snapshot.canceled_run_ids) == 32
        assert len(snapshot.receipts) == 1
        # At capacity, later contradictory evidence must still retain the hold;
        # a read-only original-fence reconciliation remains usable afterward.
        o.record_receipt(
            db, wid, claim.attempt_id, o.unknown(claim.request, lambda: NOW), lambda: NOW
        )
        with pytest.raises(HTTPException, match="unresolved original"):
            settlement.locked_snapshot(db, wid, retained, actor)
        db.rollback()
        later = NOW + timedelta(seconds=1)
        receipt = o.reconcile_attempt(db, wid, claim.attempt_id, runtime, lambda: later)
        assert receipt.outcome == "verified_target_state"
        settled = settlement.settle(
            db,
            wid,
            retained,
            actor,
            settlement.SettlementRuntime("contract_test", qualified),
            lambda: later,
        )
        assert settled.state == "settled"
