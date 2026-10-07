"""Actual disposable PostgreSQL migration, including bounded table constraints."""

# ruff: noqa: F811
import pytest
from alembic import command
from alembic.config import Config
from app.operations.models import OperationalObservationRecord as Record
from app.operations.observations import DatabaseObservationSink
from sqlalchemy import Engine, inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from tests.migration_engine import migration_customer_engine  # noqa: F401
from tests.test_operational_observations import media_event


def test_real_migration_roundtrip(migration_customer_engine: Engine) -> None:
    engine = migration_customer_engine
    if engine.dialect.name != "postgresql":
        pytest.skip("production migration requires disposable PostgreSQL")
    config = Config("alembic.ini")
    DatabaseObservationSink(engine).record(media_event())
    with Session(engine) as db:
        assert len(db.scalars(select(Record)).all()) == 1
        event = media_event().model_dump()
        event["component"] = "arbitrary_private_payload"
        db.add(Record(**event, occurrence_count=1))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
    command.downgrade(config, "20261006_0070-1")
    assert "operational_observations" not in inspect(engine).get_table_names()
    command.upgrade(config, "20261006_0070")
    DatabaseObservationSink(engine).record(media_event())
    with Session(engine) as db:
        assert len(db.scalars(select(Record)).all()) == 1
