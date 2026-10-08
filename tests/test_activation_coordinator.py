from datetime import timedelta
from pathlib import Path

import httpx
import pytest
from app.executors.google_activation import GoogleActivationHTTP
from app.publication import activation as a
from app.publication import activation_review as r
from app.publication import coordinator as c
from app.publication.activation_contracts import ActivationContext, ActivationRequest
from app.publication.execution_models import ProviderExecutionRun, ProviderExposureReservation
from app.settings import Settings
from fastapi import HTTPException
from pydantic import SecretStr
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from tests.test_activation_review import activation_ready
from tests.test_commerce_measurement import NOW
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_google_activation import Server
from tests.test_shopify_sales import configuration as configuration

pytestmark = [pytest.mark.retained_execution, pytest.mark.usefixtures("retained_execution_engine")]


def runtime_for(review: r.ActivationReviewRuntime, server: Server) -> a.ActivationRuntime:
    adapter = GoogleActivationHTTP(transport=httpx.MockTransport(server))

    def context(request: ActivationRequest) -> ActivationContext:
        return ActivationContext(
            account=request.account,
            access_token=SecretStr("mock-only"),
            expires_at=NOW + timedelta(hours=1),
        )

    return a.ActivationRuntime(review, adapter, adapter, adapter, context)


def test_actual_durable_google_activation_reuses_reservation_and_projects_state_only(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
) -> None:
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
        order = []
        while claim := a.claim_step(db, wid, run.id, actor, store, runtime, lambda: NOW):
            result = a.execute_claim(db, claim, actor, store, runtime, lambda: NOW)
            assert result.outcome == "verified_target_state"
            order.append(claim.request.target.step_id)
            projection = c.read_owned_outcome_receipt(db, wid, claim.attempt_id, actor)
            assert projection is not None and projection.purpose == "activate"
            assert projection.outcome == "verified_target_state"
            assert projection.effective_time_evidence == "unavailable"
            assert projection.effective_lower is None and projection.effective_upper is None
            before = server.activations
            with pytest.raises(HTTPException, match="claim unavailable"):
                a.execute_claim(db, claim, actor, store, runtime, lambda: NOW)
            db.rollback()
            assert server.activations == before
        assert order[-1] == "campaign" and len(order) == server.activations
        assert db.scalar(select(func.count()).select_from(ProviderExposureReservation)) == 1
        held = db.get(ProviderExposureReservation, run.reservation_id)
        assert held is not None and held.state == "held"
        finished = db.get(ProviderExecutionRun, run.id)
        assert finished is not None and finished.state == "activation_observed"


def test_unknown_activation_never_replaced_and_reconciles_original(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
) -> None:
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
        claim = a.claim_step(db, wid, run.id, actor, store, runtime, lambda: NOW)
        assert claim is not None
        server.delay, server.activation_timeout = True, True
        assert a.execute_claim(db, claim, actor, store, runtime, lambda: NOW).outcome == "unknown"
        assert a.claim_step(db, wid, run.id, actor, store, runtime, lambda: NOW) is None
        assert (
            a.reconcile_attempt(db, wid, claim.attempt_id, runtime, lambda: NOW).outcome
            == "unknown"
        )
        assert server.activations == 1
        server.rows[claim.request.target.resource_name]["status"] = "ENABLED"
        receipt = a.reconcile_attempt(
            db, wid, claim.attempt_id, runtime, lambda: NOW + timedelta(seconds=1)
        )
        assert receipt.outcome == "verified_target_state" and receipt.fence == claim.request.fence
        assert server.activations == 1
        projection = c.read_owned_outcome_receipt(db, wid, claim.attempt_id, actor)
        assert projection is not None and projection.sequence == 2


@pytest.mark.parametrize("change", ["cancel", "budget_drift"])
def test_after_claim_cancel_or_nonactivatable_drift_prevents_emission(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    change: str,
) -> None:
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
        claim = a.claim_step(db, wid, run.id, actor, store, runtime, lambda: NOW)
        assert claim is not None
        if change == "cancel":
            c.cancel_creation(db, wid, run.id, actor, lambda: NOW)
        else:
            budget = next(row for name, row in server.rows.items() if "/campaignBudgets/" in name)
            budget["amountMicros"] = "777777"
        with pytest.raises(HTTPException):
            a.execute_claim(db, claim, actor, store, runtime, lambda: NOW)
        assert server.activations == 0


def test_cancel_wins_activation_parent_claim_commit_gap(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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
        commit = db.commit
        canceled = False

        def cancel_gap() -> None:
            nonlocal canceled
            commit()
            if not canceled:
                canceled = True
                with Session(customer_engine) as other:
                    c.cancel_creation(other, wid, run.id, actor, lambda: NOW)

        monkeypatch.setattr(db, "commit", cancel_gap)
        with pytest.raises(HTTPException, match="canceled"):
            a.claim_step(db, wid, run.id, actor, store, runtime, lambda: NOW)
        assert server.activations == 0


def test_clock_expiry_during_full_graph_preflight_blocks_emission(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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
        claim = a.claim_step(db, wid, run.id, actor, store, runtime, lambda: NOW)
        assert claim is not None
        time = [NOW]
        original = a.preflight_graph

        def blocked_preflight(*args, **kwargs):  # type: ignore[no-untyped-def]
            original(*args, **kwargs)
            time[0] = NOW + timedelta(minutes=6)

        monkeypatch.setattr(a, "preflight_graph", blocked_preflight)
        with pytest.raises(HTTPException, match="fresh activation"):
            a.execute_claim(db, claim, actor, store, runtime, lambda: time[0])
        assert server.activations == 0
