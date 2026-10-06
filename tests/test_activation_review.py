from datetime import datetime
from pathlib import Path

import pytest
from app.publication import activation_review as a
from app.publication import coordinator as c
from app.publication.coordinator_contracts import CreationExecutionReview, CreationPlan
from app.publication.execution_contracts import ExposureEvidence, ProviderMandateBinding
from app.publication.execution_models import (
    ProviderExecutionReview,
    ProviderExecutionRun,
    ProviderExposureReservation,
)
from app.settings import Settings
from fastapi import HTTPException
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from tests.test_commerce_measurement import NOW
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_google_activation import Server
from tests.test_provider_coordinator import ready
from tests.test_shopify_sales import configuration as configuration


def activation_ready(db: Session, config: Settings, path: Path, server: Server):  # type: ignore[no-untyped-def]
    wid, parent, actor, store, runtime = ready(db, config, path, server)
    while claim := c.claim_creation_step(db, wid, parent, actor, store, runtime, lambda: NOW):
        assert (
            c.execute_claim(db, claim, actor, store, runtime, lambda: NOW).outcome
            == "verified_effect"
        )
    run = db.get(ProviderExecutionRun, parent)
    assert run is not None
    row = db.get(ProviderExecutionReview, run.review_id)
    assert row is not None
    binding = CreationExecutionReview.model_validate(row.document).mandate

    def exposure(
        db: Session,
        binding: ProviderMandateBinding,
        plan: CreationPlan,
        reservation_id: str,
        now: datetime,
    ) -> ExposureEvidence:
        base = runtime.exposure_reader(db, binding, plan, now)
        reservation = db.get(ProviderExposureReservation, reservation_id)
        assert reservation is not None and base.portfolio_upper_micros is not None
        return ExposureEvidence.model_validate(
            base.model_copy(
                update={
                    "existing_reservations_micros": base.existing_reservations_micros
                    - reservation.amount_micros,
                    "portfolio_upper_micros": base.portfolio_upper_micros
                    - reservation.amount_micros,
                }
            ).model_dump(mode="json")
        )

    return wid, parent, actor, store, a.ActivationReviewRuntime(runtime, exposure), binding


def test_exact_separate_activation_review_retains_parent_reservation(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
) -> None:
    with Session(customer_engine) as db:
        server = Server()
        wid, parent, actor, store, runtime, binding = activation_ready(
            db, configuration, tmp_path, server
        )
        row = a.prepare_activation(db, wid, parent, binding, actor, store, runtime, lambda: NOW)
        document = a.ActivationExecutionReview.model_validate(row.document)
        assert len(document.graph) == len(document.creation_plan.steps)
        assert document.plan.targets[-1].step_id == "campaign"
        with pytest.raises(HTTPException, match="separate exact"):
            a.create_run(db, wid, row.id, actor, store, runtime, lambda: NOW)
        db.rollback()
        with pytest.raises(HTTPException, match="separate exact"):
            a.approve_activation(
                db, wid, row.id, "0" * 64, row.plan_digest, actor, store, runtime, lambda: NOW
            )
        db.rollback()
        a.approve_activation(
            db, wid, row.id, row.digest, row.plan_digest, actor, store, runtime, lambda: NOW
        )
        run = a.create_run(db, wid, row.id, actor, store, runtime, lambda: NOW)
        assert run.parent_run_id == parent and run.reservation_id == document.reservation_id
        assert a.create_run(db, wid, row.id, actor, store, runtime, lambda: NOW).id == run.id
        assert db.scalar(select(func.count()).select_from(ProviderExposureReservation)) == 1
        assert server.activations == 0


def test_non_activatable_budget_drift_blocks_activation_review(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
) -> None:
    with Session(customer_engine) as db:
        server = Server()
        wid, parent, actor, store, runtime, binding = activation_ready(
            db, configuration, tmp_path, server
        )
        budget = next(row for name, row in server.rows.items() if "/campaignBudgets/" in name)
        budget["amountMicros"] = "999999"
        with pytest.raises(HTTPException, match="original graph"):
            a.prepare_activation(db, wid, parent, binding, actor, store, runtime, lambda: NOW)
        assert server.activations == 0
        assert db.scalar(select(func.count()).select_from(ProviderExposureReservation)) == 1
