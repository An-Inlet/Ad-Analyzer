"""Current populated 0085 refusal from a genuine pinned Start, no current authority."""

import importlib
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from app.initial_planning.start_models import InitialRuleSessionStart
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from tests.retired_producer_fixture import retained_initial_rule_fixture
from tests.test_customer_identity import customer_engine as customer_engine

pytestmark = pytest.mark.planning_boundary


def test_current_populated_0085_refuses_downgrade(customer_engine: Engine, tmp_path: Path) -> None:
    with retained_initial_rule_fixture(customer_engine, tmp_path / "seed") as (engine, ids):
        migration = importlib.import_module(
            "migrations.versions.20261007_0085_initial_rule_session_starts"
        )
        with (
            engine.begin() as connection,
            Operations.context(MigrationContext.configure(connection)),
            pytest.raises(RuntimeError, match="cannot discard retained initial Start"),
        ):
            migration.downgrade()
        with Session(engine) as db:
            row = db.get(InitialRuleSessionStart, ids.session_run_id)
            assert row and row.candidate_job_id == ids.candidate_job_id
            assert row.workspace_id == ids.workspace_id
        assert ids.provider_posts == 0
