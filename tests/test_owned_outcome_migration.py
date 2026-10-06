"""Populated0056→0057→0056→0057 in an explicitly disposable PostgreSQL schema."""

import os
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from app.commerce.models import CommerceMeasurementPublication
from app.outcomes import owned
from app.outcomes.models import ActionOutcomeAssessment
from app.settings import Settings, settings
from scripts.reset_disposable_postgres import validate_disposable_url
from sqlalchemy import create_engine, inspect, make_url, select, text
from sqlalchemy.orm import Session

from tests.test_commerce_measurement import NOW
from tests.test_owned_outcomes import evidence
from tests.test_shopify_sales import configuration as configuration


def test_owned_assessment_populated_roundtrip(
    monkeypatch: pytest.MonkeyPatch, configuration: Settings, tmp_path: Path
) -> None:
    if (
        not os.environ.get("AD_ANALYZER_TEST_POSTGRES_URL")
        or os.environ.get("AD_ANALYZER_CI_DISPOSABLE_POSTGRES") != "true"
    ):
        pytest.skip("explicit disposable PostgreSQL required")
    url = validate_disposable_url()
    schema = "inlet_outcome_" + uuid4().hex
    admin = create_engine(url)
    with admin.begin() as db:
        db.execute(text(f'CREATE SCHEMA "{schema}"'))
    scoped = make_url(url).update_query_dict({"options": f"-csearch_path={schema}"})
    engine = create_engine(scoped)
    monkeypatch.setattr(settings, "database_url", scoped.render_as_string(hide_password=False))
    config = Config("alembic.ini")
    try:
        command.upgrade(config, "20261006_0056")
        from tests.candidate_historical_schema import without_candidates

        without_candidates(monkeypatch, engine)
        with Session(engine) as db:
            wid, actor, body, _, _ = evidence(db, configuration, tmp_path)
            db.commit()
        command.upgrade(config, "20261006_0057")
        with Session(engine) as db:
            row = owned.create(db, wid, actor, body, lambda: None, lambda: NOW)
            identifier = row.id
            db.commit()
            assert db.get(ActionOutcomeAssessment, identifier) is not None
        command.downgrade(config, "20261006_0056")
        assert "action_outcome_assessments" not in inspect(engine).get_table_names()
        with Session(engine) as db:
            assert db.get(CommerceMeasurementPublication, body.publication_id) is not None
        command.upgrade(config, "20261006_0057")
        with Session(engine) as db:
            assert db.scalar(select(ActionOutcomeAssessment.id)) is None
            row = owned.create(db, wid, actor, body, lambda: None, lambda: NOW)
            assert row.assessment["status"] == "insufficient"
            db.commit()
    finally:
        engine.dispose()
        with admin.begin() as db:
            db.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()
