"""Real captured-input graph retraction; no execution or financial record synthesis."""

from pathlib import Path

import pytest
from app.initial_planning.automatic_models import (
    InitialRuleCandidateDependency,
    InitialRuleCandidateObservation,
)
from app.initial_planning.models import ObservationRow, PreviewRow
from app.initial_planning.start_models import InitialRuleSessionStart
from app.optimization_candidates.models import CandidateJob
from app.publication.execution_models import ProviderExecutionMandate
from sqlalchemy import Engine, delete, func, select
from sqlalchemy.orm import Session

from tests.retired_producer_fixture import retained_initial_rule_fixture
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_shopify_sales import configuration as configuration


@pytest.mark.parametrize("erase", ["historical_input", "selected_input", "dependency"])
def test_any_retained_input_retracts_whole_candidate(
    customer_engine: Engine,
    tmp_path: Path,
    erase: str,
) -> None:
    with retained_initial_rule_fixture(customer_engine, tmp_path / "seed") as (engine, ids):
        with Session(engine) as db:
            row = db.get(PreviewRow, ids.preview_id)
            assert row
            dependency = db.get(InitialRuleCandidateDependency, ids.candidate_job_id)
            assert dependency and dependency.preview_id == row.id
            inputs = list(
                db.scalars(
                    select(InitialRuleCandidateObservation.observation_id).where(
                        InitialRuleCandidateObservation.candidate_job_id == ids.candidate_job_id
                    )
                )
            )
            assert len(inputs) >= 2
            if erase == "dependency":
                db.execute(
                    delete(InitialRuleCandidateObservation).where(
                        InitialRuleCandidateObservation.candidate_job_id == ids.candidate_job_id,
                        InitialRuleCandidateObservation.observation_id == inputs[0],
                    )
                )
            else:
                identifier = (
                    row.observation_id
                    if erase == "selected_input"
                    else next(i for i in inputs if i != row.observation_id)
                )
                db.execute(delete(ObservationRow).where(ObservationRow.id == identifier))
            db.commit()
        with Session(engine) as db:
            assert db.get(CandidateJob, ids.candidate_job_id) is None
            assert db.get(InitialRuleCandidateDependency, ids.candidate_job_id) is None
            assert db.scalar(select(func.count()).select_from(InitialRuleCandidateObservation)) == 0
            assert db.get(ProviderExecutionMandate, ids.mandate_id) is not None
            retained = db.get(InitialRuleSessionStart, ids.session_run_id)
            assert retained and retained.candidate_job_id is None
        assert ids.provider_posts == 0
