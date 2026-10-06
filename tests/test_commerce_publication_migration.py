"""0051 populated roundtrip strictly inside an explicitly disposable PG schema."""

import os
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from app.commerce.models import CommerceEvidenceState, CommerceMeasurementPublication
from app.settings import Settings, settings
from scripts.reset_disposable_postgres import validate_disposable_url
from sqlalchemy import create_engine, inspect, make_url, select, text
from sqlalchemy.orm import Session

from tests.test_commerce_measurement import NOW
from tests.test_commerce_publications import complete
from tests.test_shopify_sales import configuration as configuration


def test_publication_migration_roundtrip(
    monkeypatch: pytest.MonkeyPatch, configuration: Settings
) -> None:
    if (
        not os.environ.get("AD_ANALYZER_TEST_POSTGRES_URL")
        or os.environ.get("AD_ANALYZER_CI_DISPOSABLE_POSTGRES") != "true"
    ):
        pytest.skip("explicit disposable PostgreSQL required")
    url = validate_disposable_url()
    schema = "inlet_publication_" + uuid4().hex
    admin = create_engine(url)
    with admin.begin() as db:
        db.execute(text(f'CREATE SCHEMA "{schema}"'))
    scoped = make_url(url).update_query_dict({"options": f"-csearch_path={schema}"})
    engine = create_engine(scoped)
    monkeypatch.setattr(settings, "database_url", scoped.render_as_string(hide_password=False))
    config = Config("alembic.ini")
    try:
        command.upgrade(config, "20261006_0047")
        with engine.begin() as db:
            db.execute(
                text(
                    "INSERT INTO workspaces "
                    "(slug,name,client_name,status,is_default,created_at,updated_at) "
                    "VALUES ('preserved','Preserved','Preserved','active',false,:now,:now)"
                ),
                {"now": NOW},
            )
            original = db.execute(
                text("SELECT id,slug FROM workspaces WHERE slug='preserved'")
            ).one()
        command.upgrade(config, "20261006_0051")
        command.upgrade(config, "20261006_0053")
        with Session(engine) as db:
            complete(db, configuration)
            assert db.scalar(select(CommerceMeasurementPublication.id)) is not None
            assert db.scalar(select(CommerceEvidenceState.store_id)) is not None
        command.downgrade(config, "20261006_0047")
        assert "commerce_measurement_publications" not in inspect(engine).get_table_names()
        assert "commerce_evidence_states" not in inspect(engine).get_table_names()
        with engine.connect() as db:
            assert (
                db.execute(text("SELECT id,slug FROM workspaces WHERE slug='preserved'")).one()
                == original
            )
            assert db.execute(text("SELECT count(*) FROM commerce_orders")).scalar_one() == 1
        command.upgrade(config, "20261006_0051")
        command.upgrade(config, "20261006_0053")
        with Session(engine) as db:
            assert db.scalar(select(CommerceMeasurementPublication.id)) is None
            assert db.scalar(select(CommerceEvidenceState.store_id)) is None
    finally:
        engine.dispose()
        with admin.begin() as db:
            db.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()
