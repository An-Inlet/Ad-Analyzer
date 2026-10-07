"""Populated 0075 graph tested on real Alembic PostgreSQL, separate disposable schema."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from app.ads.models import DailyMetric
from app.initial_planning.models import ObservationRow
from app.workspaces.models import Workspace
from sqlalchemy import Engine, delete, func, insert, select, text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session

from tests.migration_engine import migration_customer_engine as migration_customer_engine
from tests.test_customer_lifecycle import seed
from tests.test_initial_planning_lifecycle import MODELS, counts, graph


def test_populated_owned_graph_survives_schema_constraints_and_roundtrip(
    migration_customer_engine: Engine,
) -> None:
    engine = migration_customer_engine
    if engine.dialect.name != "postgresql":
        pytest.skip("actual Alembic populated roundtrip uses PostgreSQL")
    with Session(engine) as db:
        _, wid = seed(db)
        _, other = seed(db, "other")
        first = graph(db, wid, datetime.now(UTC))[0]
        second = graph(db, other, datetime.now(UTC))[0]
        original = {column.name: getattr(first, column.name) for column in first.__table__.columns}
        foreign = {
            **original,
            "id": uuid4().hex,
            "workspace_id": other,
            "account_id": second.account_id,
            "campaign_id": second.campaign_id,
        }
        metrics = db.scalar(select(func.count()).select_from(DailyMetric))
        db.rollback()
        with pytest.raises(IntegrityError):
            db.execute(insert(ObservationRow).values(**foreign))
        db.rollback()
        for model in MODELS:
            with pytest.raises(DBAPIError, match="immutable initial planning evidence"):
                db.execute(text(f"UPDATE {model.__tablename__} SET workspace_id=workspace_id"))
            db.rollback()
        db.execute(select(Workspace.id).where(Workspace.id == wid).with_for_update(key_share=True))
        db.execute(delete(ObservationRow).where(ObservationRow.workspace_id == wid))
        assert counts(db, wid) == [0, 0, 0, 0]
        assert counts(db, other) == [1, 1, 1, 1]
        db.rollback()
        assert counts(db, wid) == [1, 1, 1, 1]
    command.downgrade(Config("alembic.ini"), "20261006_0074")
    command.upgrade(Config("alembic.ini"), "20261006_0075")
    with Session(engine) as db:
        assert counts(db, wid) == [0, 0, 0, 0]
        assert db.scalar(select(func.count()).select_from(DailyMetric)) == metrics
        assert db.get(Workspace, wid) is not None and db.get(Workspace, other) is not None
