"""Durable production-table evidence, with actual mock-HTTP coordinator receipts."""

from datetime import timedelta
from pathlib import Path

import pytest
from app import advertising_capabilities
from app.operations.attention import OVERDUE_SECONDS, ROW_LIMIT, attention
from app.publication import coordinator as c
from app.publication.execution_models import (
    ProviderExecutionRun,
    ProviderExecutionStep,
    ProviderExposureReservation,
    ProviderPeriodLedger,
)
from app.publication.provider_contracts import ProviderResponse
from app.settings import Settings
from app.workspaces.models import Workspace
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from tests.test_commerce_measurement import NOW
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_provider_coordinator import GoogleServer, ready
from tests.test_shopify_sales import configuration as configuration

pytestmark = pytest.mark.planning_boundary


def test_latest_real_receipt_controls_attention_even_after_cancel_and_close(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = GoogleServer()
    server.timeout = True
    with Session(customer_engine) as db:
        # Seed authentic pre-MVP history; attention runs with the default policy.
        with monkeypatch.context() as historical:
            historical.setattr(advertising_capabilities, "require_advertising_write", lambda: None)
            wid, run_id, actor, store, runtime = ready(db, configuration, tmp_path, server)
            claim = c.claim_creation_step(db, wid, run_id, actor, store, runtime, lambda: NOW)
            assert claim
        assert advertising_capabilities.advertising_writes_enabled() is False
        held = attention(db, NOW)
        assert not [s for s in held.signals if s.code.startswith("provider_")]
        assert held.provider_held_exposure[0].observed_held_count == 1
        assert held.provider_held_exposure[1].observed_held_count == 0
        with monkeypatch.context() as historical:
            historical.setattr(advertising_capabilities, "require_advertising_write", lambda: None)
            historical_receipt = c.execute_claim(db, claim, actor, store, runtime, lambda: NOW)
            assert historical_receipt.outcome == "unknown"
        with pytest.raises(advertising_capabilities.AdvertisingWritesDisabled):
            advertising_capabilities.require_advertising_write()
        observed = [s for s in attention(db, NOW).signals if s.code.startswith("provider_")]
        assert len(observed) == 1 and observed[0].code == "provider_creation_unknown"
        assert observed[0].environment == "contract_test"
        c.record_response(
            db,
            wid,
            claim.attempt_id,
            ProviderResponse(
                request_digest=claim.request.digest(),
                outcome="acknowledged",
                resource_name=next(iter(server.rows)),
            ),
            lambda: NOW,
        )
        assert (
            c.reconcile_attempt(db, wid, claim.attempt_id, runtime, lambda: NOW).outcome
            == "verified_effect"
        )
        assert not [s for s in attention(db, NOW).signals if s.code.startswith("provider_")]
        c.cancel_creation(db, wid, run_id, actor, lambda: NOW)
        workspace = db.get(Workspace, wid)
        assert workspace
        workspace.status = "closing"
        db.commit()
        server.absent = True
        assert (
            c.reconcile_attempt(
                db, wid, claim.attempt_id, runtime, lambda: NOW + timedelta(seconds=1)
            ).outcome
            == "unknown"
        )
        result = attention(db, NOW + timedelta(seconds=1))
        observed = [s for s in result.signals if s.code.startswith("provider_")]
        assert len(observed) == 1 and observed[0].code == "provider_creation_unknown"
        assert observed[0].observed_count == 1 and observed[0].severity == "critical"
        run = db.get(ProviderExecutionRun, run_id)
        assert run and run.state == "canceled"
        reservation = db.get(ProviderExposureReservation, run.reservation_id)
        assert reservation and reservation.state == "held" and reservation.amount_micros == 40
        assert server.posts == 1  # Attention never emits, reclaims, or retries.
        assert "1234567890" not in result.model_dump_json()


@pytest.mark.parametrize("state", ["dispatching", "emitting", "conflict", "verified_no_effect"])
def test_current_production_state_and_dispatch_age_do_not_release_exposure(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    state: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with Session(customer_engine) as db:
        with monkeypatch.context() as historical:
            historical.setattr(advertising_capabilities, "require_advertising_write", lambda: None)
            wid, run_id, actor, store, runtime = ready(db, configuration, tmp_path, GoogleServer())
            claim = c.claim_creation_step(db, wid, run_id, actor, store, runtime, lambda: NOW)
            assert claim
        with pytest.raises(advertising_capabilities.AdvertisingWritesDisabled):
            advertising_capabilities.require_advertising_write()
        step = db.get(ProviderExecutionStep, (run_id, claim.request.step.step_id))
        assert step
        step.state = state
        db.commit()
        before = [
            s
            for s in attention(db, NOW + timedelta(seconds=OVERDUE_SECONDS - 1)).signals
            if s.code.startswith("provider_")
        ]
        if state in {"dispatching", "emitting"}:
            assert before == []
            after = [
                s
                for s in attention(db, NOW + timedelta(seconds=OVERDUE_SECONDS)).signals
                if s.code.startswith("provider_")
            ]
            assert [s.code for s in after] == ["provider_dispatch_overdue"]
        else:
            assert [s.code for s in before] == [
                "provider_creation_unknown"
                if state == "conflict"
                else "provider_creation_no_effect"
            ]
        reservation = db.scalar(select(ProviderExposureReservation))
        assert reservation and reservation.state == "held"


def test_held_exposure_environment_expiry_and_cap_are_explicit(customer_engine: Engine) -> None:
    with Session(customer_engine) as db:
        workspace = Workspace(
            slug="exposure", name="fixture", client_name="fixture", status="closing"
        )
        db.add(workspace)
        db.flush()
        for environment in ("contract_test", "live"):
            ledger = ProviderPeriodLedger(
                id=environment,
                workspace_id=workspace.id,
                environment=environment,
                currency="USD" if environment == "live" else "EUR",
                starts_at=NOW - timedelta(days=1),
                ends_at=NOW + timedelta(seconds=1),
            )
            db.add(ledger)
            db.flush()
            db.add(
                ProviderExposureReservation(
                    id=environment,
                    workspace_id=workspace.id,
                    ledger_id=ledger.id,
                    environment=environment,
                    budget_owner_key=environment,
                    amount_micros=123,
                    state="held",
                    evidence={"private": "fixture"},
                )
            )
        db.commit()
        fresh = attention(db, NOW)
        assert fresh.signals == []
        assert [(s.environment, s.observed_held_count) for s in fresh.provider_held_exposure] == [
            ("contract_test", 1),
            ("live", 1),
        ]
        expired = attention(db, NOW + timedelta(seconds=1))
        assert [(s.environment, s.code, s.observed_count) for s in expired.signals] == [
            ("contract_test", "provider_exposure_period_ended", 1),
            ("live", "provider_exposure_period_ended", 1),
        ]
        assert all(s.severity == "warning" for s in expired.signals)
        assert "USD" not in expired.model_dump_json() and "EUR" not in expired.model_dump_json()
        for index in range(ROW_LIMIT):
            db.add(
                ProviderExposureReservation(
                    id=str(index),
                    workspace_id=workspace.id,
                    ledger_id="live",
                    environment="live",
                    budget_owner_key=str(index),
                    amount_micros=1,
                    state="held",
                    evidence={},
                )
            )
        db.commit()
        bounded = attention(db, NOW)
        assert bounded.evidence_truncated and bounded.counts_are_lower_bounds
        assert sum(s.observed_held_count for s in bounded.provider_held_exposure) == ROW_LIMIT
