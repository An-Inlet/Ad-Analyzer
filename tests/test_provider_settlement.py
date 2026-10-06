from datetime import datetime, timedelta
from pathlib import Path

import pytest
from app.publication import coordinator as c
from app.publication import settlement as s
from app.publication.execution_models import (
    ProviderExecutionAttempt,
    ProviderExecutionRun,
    ProviderExposureReservation,
    ProviderPeriodLedger,
)
from app.settings import Settings
from fastapi import HTTPException
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from tests.test_activation_review import activation_ready
from tests.test_commerce_measurement import NOW
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_google_activation import Server
from tests.test_provider_coordinator import ready
from tests.test_shopify_sales import configuration as configuration


def qualified(snapshot: s.SettlementSnapshot, now: datetime) -> s.SettlementObservation:
    return s.SettlementObservation(
        snapshot_digest=snapshot.digest(),
        environment="contract_test",
        observed_at=now,
        expires_at=now + timedelta(minutes=2),
        status="qualified",
        qualification_profile="controlled_terminal_scenario_v1",
        proof_kind="contract_scenario",
        proof_digest="f" * 64,
        terminal_effect_upper=now,
        reporting_watermark=now,
        reported_portfolio_spend_micros=25,
        remaining_future_upper_micros=0,
        closed_attempt_ids=[r.attempt_id for r in snapshot.receipts],
        complete_account_ids=snapshot.original_exposure.covered_account_ids,
        missing=[],
    )


def test_completed_paused_graph_requires_terminal_proof_and_preserves_accounting(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
) -> None:
    with Session(customer_engine) as db:
        server = Server()
        wid, parent, actor, _, _, _ = activation_ready(db, configuration, tmp_path, server)
        run = db.get(ProviderExecutionRun, parent)
        assert run is not None and run.reservation_id is not None
        rid = run.reservation_id
        with pytest.raises(HTTPException, match="cancel all"):
            s.settle(
                db, wid, rid, actor, s.SettlementRuntime("contract_test", qualified), lambda: NOW
            )
        db.rollback()
        c.cancel_creation(db, wid, parent, actor, lambda: NOW)
        with pytest.raises(HTTPException, match="terminal reporting"):
            s.settle_unemitted(db, wid, rid, actor, lambda: NOW)
        db.rollback()
        reservation = db.get(ProviderExposureReservation, rid)
        assert reservation is not None
        ledger = db.get(ProviderPeriodLedger, reservation.ledger_id)
        assert ledger is not None
        actions = ledger.action_count
        mutations = server.posts
        result = s.settle(
            db, wid, rid, actor, s.SettlementRuntime("contract_test", qualified), lambda: NOW
        )
        assert result.state == "settled" and result.amount_micros == 40
        assert result.settled_evidence is not None
        assert result.settled_evidence["kind"] == "qualified_terminal"
        db.refresh(ledger)
        assert ledger.spent_high_water_micros == 25 and ledger.action_count == actions
        assert server.posts == mutations  # settlement never invokes provider mutations
        with pytest.raises(HTTPException, match="no longer held"):
            s.settle(
                db, wid, rid, actor, s.SettlementRuntime("contract_test", qualified), lambda: NOW
            )


@pytest.mark.parametrize(
    "change", ["unavailable", "scope", "expiry", "highwater", "snapshot", "inflight"]
)
def test_incomplete_stale_or_foreign_terminal_proof_retains_reservation(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    change: str,
) -> None:
    with Session(customer_engine) as db:
        wid, parent, actor, _, _, _ = activation_ready(db, configuration, tmp_path, Server())
        run = db.get(ProviderExecutionRun, parent)
        assert run is not None and run.reservation_id is not None
        rid = run.reservation_id
        c.cancel_creation(db, wid, parent, actor, lambda: NOW)
        time = [NOW]

        def read(snapshot: s.SettlementSnapshot, now: datetime) -> s.SettlementObservation:
            value = qualified(snapshot, now)
            if change == "unavailable":
                value = value.model_copy(
                    update={"status": "unavailable", "missing": ["native_terminal_unavailable"]}
                )
            elif change == "inflight":
                value = value.model_copy(update={"closed_attempt_ids": []})
            elif change == "scope":
                value = value.model_copy(update={"complete_account_ids": [99999]})
            elif change == "expiry":
                time[0] += timedelta(minutes=3)
            elif change == "highwater":
                ledger = db.get(ProviderPeriodLedger, snapshot.ledger_id)
                assert ledger is not None
                ledger.spent_high_water_micros = 26
                db.commit()
            else:
                value = value.model_copy(update={"snapshot_digest": "0" * 64})
            return value

        with pytest.raises(HTTPException, match="current authoritative"):
            s.settle(
                db, wid, rid, actor, s.SettlementRuntime("contract_test", read), lambda: time[0]
            )
        db.rollback()
        reservation = db.get(ProviderExposureReservation, rid)
        assert reservation is not None and reservation.state == "held"
        assert reservation.settled_evidence is None


def test_committed_unknown_attempt_blocks_even_after_period_end(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
) -> None:
    with Session(customer_engine) as db:
        server = Server()
        wid, run_id, actor, store, runtime = ready(db, configuration, tmp_path, server)
        claim = c.claim_creation_step(db, wid, run_id, actor, store, runtime, lambda: NOW)
        assert claim is not None
        c.cancel_creation(db, wid, run_id, actor, lambda: NOW)
        run = db.get(ProviderExecutionRun, run_id)
        assert run is not None and run.reservation_id is not None
        calls = []

        def read(snapshot: s.SettlementSnapshot, now: datetime) -> s.SettlementObservation:
            calls.append(snapshot)
            return qualified(snapshot, now)

        with pytest.raises(HTTPException, match="unresolved original"):
            s.settle(
                db,
                wid,
                run.reservation_id,
                actor,
                s.SettlementRuntime("contract_test", read),
                lambda: NOW + timedelta(days=100),
            )
        assert calls == []
        with pytest.raises(HTTPException, match="unresolved original"):
            s.settle_unemitted(db, wid, run.reservation_id, actor, lambda: NOW)


def test_canceled_parent_with_no_original_attempt_can_release_locally(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with Session(customer_engine) as db:
        wid, run_id, actor, store, runtime = ready(db, configuration, tmp_path, Server())
        commit = db.commit
        canceled = False

        def cancel_gap() -> None:
            nonlocal canceled
            commit()
            if not canceled:
                canceled = True
                with Session(customer_engine) as other:
                    c.cancel_creation(other, wid, run_id, actor, lambda: NOW)

        monkeypatch.setattr(db, "commit", cancel_gap)
        with pytest.raises(HTTPException, match="canceled"):
            c.claim_creation_step(db, wid, run_id, actor, store, runtime, lambda: NOW)
        db.rollback()
        run = db.get(ProviderExecutionRun, run_id)
        assert run is not None and run.reservation_id is not None
        assert db.scalar(select(func.count()).select_from(ProviderExecutionAttempt)) == 0
        result = s.settle_unemitted(db, wid, run.reservation_id, actor, lambda: NOW)
        assert result.state == "settled" and result.settled_evidence is not None
        assert result.settled_evidence["kind"] == "no_committed_attempt"


def test_default_settlement_runtime_is_disabled() -> None:
    assert s.get_settlement_runtime() is None


def test_new_unknown_during_terminal_read_invalidates_snapshot(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
) -> None:
    with Session(customer_engine) as db:
        wid, parent, actor, _, _, _ = activation_ready(db, configuration, tmp_path, Server())
        run = db.get(ProviderExecutionRun, parent)
        assert run is not None and run.reservation_id is not None
        c.cancel_creation(db, wid, parent, actor, lambda: NOW)

        def read(snapshot: s.SettlementSnapshot, now: datetime) -> s.SettlementObservation:
            attempt_id = snapshot.receipts[0].attempt_id
            _, _, _, request = c.evidence_lock(db, wid, attempt_id)
            c.record_receipt(
                db,
                wid,
                attempt_id,
                c.unknown(request, now + timedelta(seconds=1)),
                lambda: now + timedelta(seconds=1),
            )
            return qualified(snapshot, now)

        with pytest.raises(HTTPException, match="unresolved original"):
            s.settle(
                db,
                wid,
                run.reservation_id,
                actor,
                s.SettlementRuntime("contract_test", read),
                lambda: NOW + timedelta(seconds=2),
            )
        reservation = db.get(ProviderExposureReservation, run.reservation_id)
        assert reservation is not None and reservation.state == "held"


def test_no_effect_later_step_does_not_erase_earlier_provider_resource(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
) -> None:
    with Session(customer_engine) as db:
        wid, run_id, actor, store, runtime = ready(db, configuration, tmp_path, Server())
        first = c.claim_creation_step(db, wid, run_id, actor, store, runtime, lambda: NOW)
        assert first is not None
        assert (
            c.execute_claim(db, first, actor, store, runtime, lambda: NOW).outcome
            == "verified_effect"
        )
        second = c.claim_creation_step(db, wid, run_id, actor, store, runtime, lambda: NOW)
        assert second is not None
        # Explicit test authority; production absence is never converted into no-effect.
        receipt = c.unknown(second.request, NOW).model_copy(
            update={
                "outcome": "verified_no_effect",
                "evidence": "authoritative_no_effect",
            }
        )
        c.record_receipt(db, wid, second.attempt_id, receipt, lambda: NOW)
        c.cancel_creation(db, wid, run_id, actor, lambda: NOW)
        run = db.get(ProviderExecutionRun, run_id)
        assert run is not None and run.reservation_id is not None
        with pytest.raises(HTTPException, match="terminal reporting proof"):
            s.settle_unemitted(db, wid, run.reservation_id, actor, lambda: NOW)
        reservation = db.get(ProviderExposureReservation, run.reservation_id)
        assert reservation is not None and reservation.state == "held"


def test_full_activation_settlement_requires_canceling_both_related_runs(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
) -> None:
    from app.publication import activation as a
    from app.publication import activation_review as r

    from tests.test_activation_coordinator import runtime_for

    with Session(customer_engine) as db:
        server = Server()
        wid, parent, actor, store, review, binding = activation_ready(
            db, configuration, tmp_path, server
        )
        row = r.prepare_activation(db, wid, parent, binding, actor, store, review, lambda: NOW)
        r.approve_activation(
            db, wid, row.id, row.digest, row.plan_digest, actor, store, review, lambda: NOW
        )
        run = r.create_run(db, wid, row.id, actor, store, review, lambda: NOW)
        runtime = runtime_for(review, server)
        while claim := a.claim_step(db, wid, run.id, actor, store, runtime, lambda: NOW):
            assert (
                a.execute_claim(db, claim, actor, store, runtime, lambda: NOW).outcome
                == "verified_target_state"
            )
        assert run.reservation_id is not None
        c.cancel_creation(db, wid, run.id, actor, lambda: NOW)
        with pytest.raises(HTTPException, match="cancel all"):
            s.settle(
                db,
                wid,
                run.reservation_id,
                actor,
                s.SettlementRuntime("contract_test", qualified),
                lambda: NOW,
            )
        db.rollback()
        c.cancel_creation(db, wid, parent, actor, lambda: NOW)
        reservation = s.settle(
            db,
            wid,
            run.reservation_id,
            actor,
            s.SettlementRuntime("contract_test", qualified),
            lambda: NOW,
        )
        assert reservation.state == "settled" and reservation.settled_evidence is not None
        document = reservation.settled_evidence["snapshot"]
        assert set(document["canceled_run_ids"]) == {parent, run.id}
        assert {receipt["purpose"] for receipt in document["receipts"]} == {
            "create_paused",
            "activate",
        }
