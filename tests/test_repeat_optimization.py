from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
from app.publication import coordinator as c
from app.publication import optimization as o
from app.publication import replacement as r
from app.publication import settlement
from app.publication.execution_contracts import ExposureEvidence
from app.publication.execution_models import (
    ProviderExposureReservation,
    ProviderReservationReplacement,
)
from app.publication.replacement_contracts import (
    ClosedOriginalRequest,
    RepeatOptimizationReview,
    ReplacementEvidence,
)
from app.settings import Settings
from fastapi import HTTPException
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from tests.test_commerce_measurement import NOW
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_durable_optimization import ready
from tests.test_provider_settlement import qualified
from tests.test_shopify_sales import configuration as configuration

pytestmark = [pytest.mark.retained_execution, pytest.mark.usefixtures("retained_execution_engine")]


def reader(runtime: Any) -> Any:
    def qualify(db, binding, intent, before, qualification, snapshot, now):  # type: ignore[no-untyped-def]
        raw = runtime.exposure_reader(db, intent, before, qualification, now).model_dump()
        raw["existing_reservations_micros"] -= snapshot.ancestry[-1].amount_micros
        raw["portfolio_upper_micros"] -= snapshot.ancestry[-1].amount_micros
        return ReplacementEvidence(
            snapshot_digest=snapshot.digest(),
            intent_digest=intent.digest(),
            environment="contract_test",
            qualification_profile="mock_complete_transition",
            qualification_revision=1,
            proof_kind="contract_scenario",
            observed_at=now,
            expires_at=now + timedelta(minutes=2),
            closed_requests=[
                ClosedOriginalRequest(
                    attempt_id=x.attempt_id,
                    request_digest=x.request_digest,
                    fence=x.fence,
                    basis="authoritative_request_terminal",
                    evidence_digest="a" * 64,
                )
                for x in snapshot.receipts
            ],
            closure_evidence_digest="b" * 64,
            transition_evidence_digest="c" * 64,
            transition_semantics="current_proposed_delayed_no_effect_and_residual",
            portfolio=ExposureEvidence.model_validate(raw),
            unresolved=[],
        )

    return qualify


def admit(db: Any, wid: int, actor: str, row: Any, runtime: Any) -> Any:
    o.approve_optimization(
        db, wid, row.id, row.digest, row.plan_digest, actor, runtime, lambda: NOW
    )
    run = o.create_run(db, wid, row.id, actor, runtime, lambda: NOW)
    claim = o.claim_step(db, wid, run.id, actor, runtime, lambda: NOW)
    assert claim is not None
    return run, claim


@pytest.mark.parametrize("provider", ["google_ads", "meta_ads", "tiktok_ads"])
def test_three_sequential_real_adapter_requests_preserve_all_original_attempts(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    provider: str,
) -> None:
    with Session(customer_engine) as db:
        wid, actor, binding, scope, target, action, runtime, _ = ready(
            db, configuration, tmp_path, provider
        )
        original = o.prepare_optimization(
            db, wid, binding, scope, target, action, "a" * 64, actor, runtime, lambda: NOW
        )
        run, claim = admit(db, wid, actor, original, runtime)
        first = o.execute_claim(db, claim, actor, runtime, lambda: NOW)
        assert first.outcome == "verified_target_state"
        runtime = replace(runtime, replacement_reader=reader(runtime))
        attempt_ids = {claim.attempt_id}
        for amount in (44_000_000, 43_000_000):
            action = action.model_copy(update={"amount_micros": amount})
            previous = run.reservation_id
            assert previous is not None
            row = r.prepare_repeat_optimization(
                db,
                wid,
                binding,
                scope,
                previous,
                target,
                action,
                "b" * 64,
                actor,
                runtime,
                lambda: NOW,
            )
            document = RepeatOptimizationReview.model_validate(row.document)
            assert {x.attempt_id for x in document.predecessor.receipts} == attempt_ids
            run, claim = admit(db, wid, actor, row, runtime)
            receipt = o.execute_claim(db, claim, actor, runtime, lambda: NOW)
            assert receipt.outcome == "verified_target_state"
            attempt_ids.add(claim.attempt_id)
            old = db.get(ProviderExposureReservation, previous)
            assert old is not None and old.state == "superseded"
            assert (
                len(
                    list(
                        db.scalars(
                            select(ProviderExposureReservation).where(
                                ProviderExposureReservation.state == "held"
                            )
                        )
                    )
                )
                == 1
            )
        assert len(list(db.scalars(select(ProviderReservationReplacement)))) == 2
        c.cancel_creation(db, wid, run.id, actor, lambda: NOW)
        assert run.reservation_id is not None
        _, _, snapshot = settlement.locked_snapshot(db, wid, run.reservation_id, actor)
        assert {x.attempt_id for x in snapshot.receipts} == attempt_ids
        with pytest.raises(HTTPException) as error:
            settlement.settle_unemitted(db, wid, run.reservation_id, actor, lambda: NOW)
        assert error.value.status_code == 409
        settled = settlement.settle(
            db,
            wid,
            run.reservation_id,
            actor,
            settlement.SettlementRuntime("contract_test", qualified),
            lambda: NOW,
        )
        assert settled.state == "settled"
        assert settled.settled_evidence is not None
        assert len(settled.settled_evidence["snapshot"]["receipts"]) == 3
        assert o.positive_changes_used(db, wid, binding.ledger_id) == 0


def prepared(db: Any, configuration: Settings, tmp_path: Path) -> Any:
    wid, actor, binding, scope, target, action, runtime, server = ready(
        db, configuration, tmp_path, "google_ads"
    )
    row = o.prepare_optimization(
        db, wid, binding, scope, target, action, "a" * 64, actor, runtime, lambda: NOW
    )
    old, claim = admit(db, wid, actor, row, runtime)
    assert (
        o.execute_claim(db, claim, actor, runtime, lambda: NOW).outcome == "verified_target_state"
    )
    runtime = replace(runtime, replacement_reader=reader(runtime))
    action = action.model_copy(update={"amount_micros": 44_000_000})
    row = r.prepare_repeat_optimization(
        db,
        wid,
        binding,
        scope,
        old.reservation_id,
        target,
        action,
        "b" * 64,
        actor,
        runtime,
        lambda: NOW,
    )
    o.approve_optimization(
        db, wid, row.id, row.digest, row.plan_digest, actor, runtime, lambda: NOW
    )
    run = o.create_run(db, wid, row.id, actor, runtime, lambda: NOW)
    return wid, actor, old, run, row, runtime, server


def test_inherited_no_attempt_is_not_refundable(
    customer_engine: Engine, configuration: Settings, tmp_path: Path
) -> None:
    with Session(customer_engine) as db:
        wid, actor, old, run, row, runtime, _ = prepared(db, configuration, tmp_path)
        document = RepeatOptimizationReview.model_validate(row.document)
        r.transfer(db, wid, run, document, actor, runtime, lambda: NOW)
        c.cancel_creation(db, wid, run.id, actor, lambda: NOW)
        assert run.reservation_id is not None
        with pytest.raises(HTTPException) as error:
            settlement.settle_unemitted(db, wid, run.reservation_id, actor, lambda: NOW)
        assert error.value.status_code == 409
        reservation = db.get(ProviderExposureReservation, run.reservation_id)
        assert reservation is not None and reservation.state == "held"
        _, _, snapshot = settlement.locked_snapshot(db, wid, reservation.id, actor)
        assert len(snapshot.receipts) == 1 and old.id in snapshot.canceled_run_ids


@pytest.mark.parametrize(
    "failure", ["changed_proof", "missing_source", "cancel_after_source", "expired_after_source"]
)
def test_replacement_source_failures_preserve_original_hold(
    customer_engine: Engine, configuration: Settings, tmp_path: Path, failure: str
) -> None:
    with Session(customer_engine) as db:
        wid, actor, old, run, row, runtime, _ = prepared(db, configuration, tmp_path)
        clock = [NOW]
        original_reader = runtime.replacement_reader
        assert original_reader is not None

        def qualify(*args):  # type: ignore[no-untyped-def]
            result = original_reader(*args)
            if failure == "changed_proof":
                return result.model_copy(update={"closure_evidence_digest": "d" * 64})
            if failure == "cancel_after_source":
                c.cancel_creation(db, wid, run.id, actor, lambda: NOW)
            if failure == "expired_after_source":
                clock[0] = NOW + timedelta(minutes=3)
            return result

        runtime = replace(
            runtime, replacement_reader=None if failure == "missing_source" else qualify
        )
        with pytest.raises(HTTPException):
            o.claim_step(db, wid, run.id, actor, runtime, lambda: clock[0])
        db.rollback()
        predecessor = db.get(ProviderExposureReservation, old.reservation_id)
        assert predecessor is not None and predecessor.state == "held"
        assert db.scalar(select(ProviderReservationReplacement.id)) is None


def test_atomic_transfer_failure_rolls_back_old_and_new(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with Session(customer_engine) as db:
        wid, actor, old, run, row, runtime, _ = prepared(db, configuration, tmp_path)
        original_flush = db.flush

        def failing_flush(*args, **kwargs):  # type: ignore[no-untyped-def]
            if any(isinstance(item, ProviderReservationReplacement) for item in db.new):
                raise RuntimeError("controlled audit persistence failure")
            return original_flush(*args, **kwargs)

        monkeypatch.setattr(db, "flush", failing_flush)
        with pytest.raises(RuntimeError, match="controlled audit"):
            o.claim_step(db, wid, run.id, actor, runtime, lambda: NOW)
        monkeypatch.setattr(db, "flush", original_flush)
        db.commit()  # even a caller catching the error cannot persist a half transfer
        predecessor = db.get(ProviderExposureReservation, old.reservation_id)
        assert predecessor is not None and predecessor.state == "held"
        saved_run = db.get(type(run), run.id)
        assert saved_run is not None and saved_run.reservation_id is None
        assert db.scalar(select(ProviderReservationReplacement.id)) is None


def test_replacement_export_and_omitted_ancestor_rejected(
    customer_engine: Engine, configuration: Settings, tmp_path: Path
) -> None:
    from app.lifecycle.export_serializers import serialize
    from app.lifecycle.inventory import verify_registry
    from pydantic import ValidationError

    verify_registry()
    with Session(customer_engine) as db:
        wid, actor, old, run, row, runtime, _ = prepared(db, configuration, tmp_path)
        document = RepeatOptimizationReview.model_validate(row.document)
        invalid = document.model_dump(mode="json")
        invalid["replacement"]["closed_requests"][0]["fence"] = "f" * 32
        with pytest.raises(ValidationError):
            RepeatOptimizationReview.model_validate(invalid)
        r.transfer(db, wid, run, document, actor, runtime, lambda: NOW)
        audit = db.execute(select(ProviderReservationReplacement.__table__)).mappings().one()
        output, missing = serialize("provider_reservation_replacements", dict(audit))
        assert "document" not in missing
        assert output["document"]["snapshot"]["receipts"]
        changed = dict(audit)
        changed["workspace_id"] = wid + 1
        _, missing = serialize("provider_reservation_replacements", changed)
        assert "document" in missing
        review = (
            db.execute(select(type(row).__table__).where(type(row).id == row.id)).mappings().one()
        )
        output, missing = serialize("provider_execution_reviews", dict(review))
        assert "document" not in missing
        assert output["document"]["schema_version"] == document.schema_version


def test_concurrent_replacement_claim_has_one_successor_and_one_attempt(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
) -> None:
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    if customer_engine.dialect.name != "postgresql":
        pytest.skip("real PostgreSQL workspace locks required")
    with Session(customer_engine) as db:
        wid, actor, old, run, row, runtime, _ = prepared(db, configuration, tmp_path)
        run_id = run.id
        predecessor_id = old.reservation_id
    barrier = Barrier(2)

    def worker():  # type: ignore[no-untyped-def]
        with Session(customer_engine) as db:
            barrier.wait(timeout=10)
            try:
                return o.claim_step(db, wid, run_id, actor, runtime, lambda: NOW)
            except HTTPException as exc:
                assert exc.status_code == 409
                return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(worker) for _ in range(2)]
        claims = [f.result(timeout=30) for f in futures]
    assert sum(claim is not None for claim in claims) == 1
    with Session(customer_engine) as db:
        audits = list(db.scalars(select(ProviderReservationReplacement)))
        assert len(audits) == 1 and audits[0].predecessor_id == predecessor_id
        assert (
            len(
                list(
                    db.scalars(
                        select(ProviderExposureReservation).where(
                            ProviderExposureReservation.state == "held"
                        )
                    )
                )
            )
            == 1
        )


def test_unknown_repeat_retains_transition_and_original_fence(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
) -> None:
    with Session(customer_engine) as db:
        wid, actor, old, run, row, runtime, server = prepared(db, configuration, tmp_path)
        claim = o.claim_step(db, wid, run.id, actor, runtime, lambda: NOW)
        assert claim is not None
        server.ignore = server.timeout = True
        receipt = o.execute_claim(db, claim, actor, runtime, lambda: NOW)
        assert receipt.outcome == "unknown"
        assert o.claim_step(db, wid, run.id, actor, runtime, lambda: NOW) is None
        document = RepeatOptimizationReview.model_validate(row.document)
        with pytest.raises(HTTPException, match="unknown original"):
            r.prepare_repeat_optimization(
                db,
                wid,
                document.plan.intent.mandate,
                document.plan.intent.scope,
                run.reservation_id,
                document.plan.intent.target,
                document.plan.intent.action,
                "c" * 64,
                actor,
                runtime,
                lambda: NOW,
            )
        db.rollback()
        held = db.get(ProviderExposureReservation, run.reservation_id)
        assert held is not None and held.state == "held" and held.amount_micros == 40_000_000
        assert len(server.writes) == 2  # first original and one replacement; no replay


@pytest.mark.parametrize("stage", ["after_claim", "final_context"])
def test_later_ancestor_contradiction_blocks_successor_emission(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    stage: str,
) -> None:
    with Session(customer_engine) as db:
        wid, actor, old, run, row, runtime, server = prepared(db, configuration, tmp_path)
        claim = o.claim_step(db, wid, run.id, actor, runtime, lambda: NOW)
        assert claim is not None
        document = RepeatOptimizationReview.model_validate(row.document)
        previous = document.predecessor.receipts[0]
        _, _, _, original = o.evidence_lock(db, wid, previous.attempt_id)

        def contradict() -> None:
            o.record_receipt(
                db, wid, previous.attempt_id, o.unknown(original, lambda: NOW), lambda: NOW
            )

        if stage == "after_claim":
            contradict()
        else:
            context = runtime.context
            calls = 0

            def resolving_context(scope: Any) -> Any:
                nonlocal calls
                calls += 1
                if calls == 3:
                    contradict()
                return context(scope)

            runtime = replace(runtime, context=resolving_context)
        with pytest.raises(HTTPException, match="ancestor evidence changed"):
            o.execute_claim(db, claim, actor, runtime, lambda: NOW)
        assert len(server.writes) == 1
        reservation = db.get(ProviderExposureReservation, run.reservation_id)
        assert reservation is not None and reservation.state == "held"
