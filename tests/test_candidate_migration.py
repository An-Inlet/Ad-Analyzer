"""0062 disposable PostgreSQL upgrade and derived-only downgrade."""

import os
from collections.abc import Callable
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from app.optimization_candidates.models import CandidateJob, CandidateResult
from app.publication.execution_models import ProviderExecutionMandate
from app.settings import Settings, settings
from scripts.reset_disposable_postgres import validate_disposable_url
from sqlalchemy import Engine, create_engine, inspect, make_url, select, text
from sqlalchemy.orm import Session

from tests.optimization_origin_historical_schema import legacy_origin as legacy_origin
from tests.retired_migration_producer import retained_candidate_result_fixture
from tests.test_shopify_sales import configuration as configuration


def test_derived_candidate_migration_roundtrip(
    monkeypatch: pytest.MonkeyPatch,
    configuration: Settings,
    tmp_path: Path,
    legacy_origin: Callable[[Engine], None],
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
        retained = retained_candidate_result_fixture(engine, tmp_path / "candidate-producer")
        with Session(engine) as db:
            assert db.scalar(select(CandidateResult.id)) == retained.result_id
            mandate_ids = set(db.scalars(select(ProviderExecutionMandate.id)))
            assert mandate_ids == set(retained.mandate_ids)
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
