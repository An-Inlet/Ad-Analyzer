"""Real captured-input graph retraction; no execution or financial record synthesis."""

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from app.initial_planning.automatic_models import (
    InitialRuleCandidateDependency,
    InitialRuleCandidateObservation,
    InitialRuleOpportunity,
)
from app.initial_planning.models import CalibrationDependency, ObservationRow, PreviewRow
from app.optimization_candidates.models import CandidateJob
from app.publication.execution_models import ProviderExecutionMandate
from app.settings import Settings
from sqlalchemy import Engine, delete, func, select, text
from sqlalchemy.orm import Session

from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_shopify_sales import configuration as configuration
from tests.v2_execution_fixture import ready


@pytest.mark.parametrize("erase", ["historical_input", "selected_input", "dependency"])
def test_any_retained_input_retracts_whole_candidate(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    replicas: Any,
    erase: str,
) -> None:
    if customer_engine.dialect.name == "sqlite":
        with customer_engine.connect() as connection:
            connection.execute(text("PRAGMA foreign_keys=ON"))
    _, _, _, _, preview, _, _, planning = ready(
        customer_engine,
        configuration,
        tmp_path,
        monkeypatch,
        replicas,
    )
    with Session(customer_engine) as db:
        row = db.get(PreviewRow, preview["id"])
        assert row
        mandate = db.get(ProviderExecutionMandate, planning["mandate_id"])
        assert mandate
        now = datetime.now(UTC)
        from app.shopify.security import utc

        expires = min(now + timedelta(seconds=30), utc(row.expires_at))
        origin = InitialRuleOpportunity(
            id="a" * 32,
            workspace_id=row.workspace_id,
            environment="contract_test",
            ledger_id=mandate.ledger_id,
            native_account_identity_digest="b" * 64,
            budget_owner_identity_digest="c" * 64,
            semantic_key_digest="a" * 64,
            created_at=now,
            pending_expires_at=now + timedelta(seconds=60),
        )
        # This test exercises schema ownership/retraction only; queued work is never
        # run and this empty document is not a valid worker input or authority proof.
        from app.commerce.models import CommerceMeasurementPublication
        from app.commerce.sync import CommerceSyncService

        from tests.test_commerce_measurement import FakeMeasurement

        imported = CommerceSyncService(
            db, configuration, FakeMeasurement(configuration, [([], None)])
        ).page(
            row.workspace_id,
            now=now + timedelta(minutes=configuration.shopify_sync_interval_minutes + 1),
        )
        assert imported["status"] == "complete", imported
        publication = db.scalar(
            select(CommerceMeasurementPublication).where(
                CommerceMeasurementPublication.workspace_id == row.workspace_id,
            )
        )
        assert publication
        job = CandidateJob(
            id=uuid4().hex,
            workspace_id=row.workspace_id,
            environment="contract_test",
            publication_id=publication.id,
            attempt_id=None,
            actor_id=row.original_actor_id,
            auth_session_digest=row.original_session_digest,
            input_digest="d" * 64,
            work={},
            state="pending",
            attempts=0,
            due_at=now,
            created_at=now,
        )
        db.add_all([origin, job])
        db.flush()
        db.add(
            InitialRuleCandidateDependency(
                candidate_job_id=job.id,
                workspace_id=row.workspace_id,
                account_id=row.account_id,
                campaign_id=row.campaign_id,
                opportunity_id=origin.id,
                preview_id=row.id,
                calibration_id=row.calibration_id,
                selected_observation_id=row.observation_id,
                expires_at=expires,
            )
        )
        db.flush()
        ids = list(
            db.scalars(
                select(CalibrationDependency.observation_id).where(
                    CalibrationDependency.calibration_id == row.calibration_id,
                )
            )
        )
        assert len(ids) >= 2
        for identifier in ids:
            db.add(
                InitialRuleCandidateObservation(
                    candidate_job_id=job.id,
                    observation_id=identifier,
                    expires_at=expires,
                    workspace_id=row.workspace_id,
                    account_id=row.account_id,
                    campaign_id=row.campaign_id,
                )
            )
        db.commit()
        job_id, mandate_id = job.id, mandate.id
        if erase == "dependency":
            db.execute(
                delete(InitialRuleCandidateObservation).where(
                    InitialRuleCandidateObservation.candidate_job_id == job_id,
                    InitialRuleCandidateObservation.observation_id == ids[0],
                )
            )
        else:
            identifier = (
                row.observation_id
                if erase == "selected_input"
                else next(i for i in ids if i != row.observation_id)
            )
            db.execute(delete(ObservationRow).where(ObservationRow.id == identifier))
        db.commit()
        db.expire_all()
        assert db.get(CandidateJob, job_id) is None
        assert db.get(InitialRuleCandidateDependency, job_id) is None
        assert db.scalar(select(func.count()).select_from(InitialRuleCandidateObservation)) == 0
        assert db.get(ProviderExecutionMandate, mandate_id) is not None
