"""0062 disposable PostgreSQL upgrade and derived-only downgrade."""

import os
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from app.optimization_candidates.models import CandidateJob, CandidateResult
from app.optimization_candidates.service import enqueue, process
from app.publication.execution_models import ProviderExecutionMandate
from app.settings import Settings, settings
from scripts.reset_disposable_postgres import validate_disposable_url
from sqlalchemy import create_engine, inspect, make_url, select, text
from sqlalchemy.orm import Session

from tests.feedback_historical_schema import without_feedback
from tests.test_optimization_candidates import fixture
from tests.test_shopify_sales import configuration as configuration


def test_derived_candidate_migration_roundtrip(
    monkeypatch: pytest.MonkeyPatch, configuration: Settings, tmp_path: Path
) -> None:
    if (
        not os.environ.get("AD_ANALYZER_TEST_POSTGRES_URL")
        or os.environ.get("AD_ANALYZER_CI_DISPOSABLE_POSTGRES") != "true"
    ):
        pytest.skip("explicit disposable PostgreSQL required")
    url = validate_disposable_url()
    schema = "inlet_candidates_" + uuid4().hex
    admin = create_engine(url)
    with admin.begin() as db:
        db.execute(text(f'CREATE SCHEMA "{schema}"'))
    scoped = make_url(url).update_query_dict({"options": f"-csearch_path={schema}"})
    engine = create_engine(scoped)
    monkeypatch.setattr(settings, "database_url", scoped.render_as_string(hide_password=False))
    config = Config("alembic.ini")
    try:
        command.upgrade(config, "20261006_0062")
        without_feedback(monkeypatch, engine)
        from tests.candidate_historical_schema import (
            without_candidate_reviews,
            without_initial_planning,
        )

        without_candidate_reviews(monkeypatch, engine)
        without_initial_planning(monkeypatch, engine)
        with Session(engine) as db:
            principal, work, _, _, runtime, _ = fixture(db, configuration, tmp_path)
            row = enqueue(db, principal, work, runtime)
            wid, identifier = row.workspace_id, row.id
        assert process(engine, wid, identifier, runtime) == "completed"
        with Session(engine) as db:
            assert db.scalar(select(CandidateResult.id))
            mandate_ids = set(db.scalars(select(ProviderExecutionMandate.id)))
        command.downgrade(config, "20261006_0060")
        assert CandidateJob.__tablename__ not in inspect(engine).get_table_names()
        assert CandidateResult.__tablename__ not in inspect(engine).get_table_names()
        with Session(engine) as db:
            assert set(db.scalars(select(ProviderExecutionMandate.id))) == mandate_ids
        command.upgrade(config, "20261006_0062")
        with Session(engine) as db:
            assert db.scalar(select(CandidateJob.id)) is None
    finally:
        engine.dispose()
        with admin.begin() as db:
            db.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()
