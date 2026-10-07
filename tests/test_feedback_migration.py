"""Populated0064 PG upgrade/delete-trigger/downgrade preserves financial history."""

import os
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from app.commerce.models import CommerceMeasurementPublication
from app.optimization_candidates.models import CandidateJob
from app.outcome_feedback.models import ContributionSlot, V3Assessment, V3EvidenceDependency
from app.publication.execution_models import ProviderExecutionReceipt, ProviderExposureReservation
from app.settings import Settings, settings
from scripts.reset_disposable_postgres import validate_disposable_url
from sqlalchemy import create_engine, delete, inspect, make_url, select, text
from sqlalchemy.orm import Session

from tests.test_feedback_policy import make_assessment
from tests.test_feedback_storage import seed_graph
from tests.test_shopify_sales import configuration as configuration


def test_populated_feedback_migration_roundtrip(
    monkeypatch: pytest.MonkeyPatch,
    configuration: Settings,
    tmp_path: Path,
) -> None:
    if (
        not os.environ.get("AD_ANALYZER_TEST_POSTGRES_URL")
        or os.environ.get("AD_ANALYZER_CI_DISPOSABLE_POSTGRES") != "true"
    ):
        pytest.skip("explicit disposable PostgreSQL required")
    url = validate_disposable_url()
    schema = "inlet_feedback_" + uuid4().hex
    admin = create_engine(url)
    with admin.begin() as db:
        db.execute(text(f'CREATE SCHEMA "{schema}"'))
    scoped = make_url(url).update_query_dict({"options": f"-csearch_path={schema}"})
    engine = create_engine(scoped)
    monkeypatch.setattr(settings, "database_url", scoped.render_as_string(hide_password=False))
    config = Config("alembic.ini")
    try:
        # Current producer helpers require current authority/provenance columns.
        # Build the real owned receipt at head, then migrate its retained financial
        # graph to the historical predecessor before testing the 0064 upgrade.
        command.upgrade(config, "head")
        value = make_assessment(engine, configuration, tmp_path)
        with Session(engine) as db:
            receipts = set(db.scalars(select(ProviderExecutionReceipt.id)))
            reservations = set(db.scalars(select(ProviderExposureReservation.id)))
            assert receipts and reservations
        command.downgrade(config, "20261006_0062")
        command.upgrade(config, "20261006_0064")
        with Session(engine) as db:
            identifier, historical, job, slot = seed_graph(db, value, configuration)
            assert set(db.scalars(select(ProviderExecutionReceipt.id))) == receipts
            assert set(db.scalars(select(ProviderExposureReservation.id))) == reservations
            db.execute(
                delete(CommerceMeasurementPublication).where(
                    CommerceMeasurementPublication.id == historical
                )
            )
            db.commit()
            assert db.get(V3Assessment, identifier) is None and db.get(CandidateJob, job) is None
            assert db.get(ContributionSlot, slot) is None
            assert not list(db.scalars(select(V3EvidenceDependency.assessment_id)))
        command.downgrade(config, "20261006_0062")
        assert V3Assessment.__tablename__ not in inspect(engine).get_table_names()
        with Session(engine) as db:
            assert set(db.scalars(select(ProviderExecutionReceipt.id))) == receipts
            assert set(db.scalars(select(ProviderExposureReservation.id))) == reservations
        command.upgrade(config, "20261006_0064")
        with Session(engine) as db:
            assert db.scalar(select(V3Assessment.id)) is None
    finally:
        engine.dispose()
        with admin.begin() as db:
            db.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()
