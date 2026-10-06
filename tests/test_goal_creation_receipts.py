"""Atomic scoped creation retries on SQLite and disposable PostgreSQL."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

import pytest
from app.database.session import Base
from app.goals import service
from app.goals.models import Goal, GoalCreation, GoalRevision
from app.settings import Settings
from fastapi import HTTPException
from sqlalchemy import Engine, create_engine, func, select
from sqlalchemy.orm import Session

from tests.test_commerce_measurement import NOW
from tests.test_customer_goals import definition, seed
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_shopify_sales import configuration as configuration


def test_creation_receipt_scope_binding_and_rollback(
    customer_engine: Engine, configuration: Settings
) -> None:
    with Session(customer_engine) as db:
        original = seed(db, configuration)
        other = seed(db, configuration, "other")
        wid = original.workspace_id
        first = service.create(db, wid, "actor-a", "same-request", None, NOW)
        gid = first.id
        db.commit()
        assert service.create(db, wid, "actor-a", "same-request", None, NOW).id == gid
        other_actor = service.create(db, wid, "actor-b", "same-request", None, NOW)
        other_workspace = service.create(
            db, other.workspace_id, "actor-a", "same-request", None, NOW
        )
        assert len({gid, other_actor.id, other_workspace.id}) == 3
        db.commit()
        original_definition = service.current(db, original).definition
        assert original_definition is not None
        d = definition(original_definition["store_id"])
        with pytest.raises(HTTPException, match="different input"):
            service.create(db, wid, "actor-a", "same-request", d, NOW)
        db.rollback()
        count = db.scalar(select(func.count()).select_from(Goal))
        with pytest.raises(HTTPException, match="measurement source"):
            service.create(
                db,
                wid,
                "actor-a",
                "invalid-source",
                d.model_copy(update={"store_id": "z" * 32}),
                NOW,
            )
        db.rollback()
        assert db.scalar(select(func.count()).select_from(Goal)) == count
        assert db.get(GoalCreation, (wid, "actor-a", "invalid-source")) is None
        assert db.scalar(select(func.count()).select_from(GoalRevision)) == count
        service.create(db, wid, "actor-a", "rolled-back", None, NOW)
        db.rollback()
        assert db.get(GoalCreation, (wid, "actor-a", "rolled-back")) is None
        assert db.scalar(select(func.count()).select_from(Goal)) == count


def test_concurrent_same_goal_creation(customer_engine: Engine, configuration: Settings) -> None:
    if customer_engine.dialect.name != "postgresql":
        return
    concurrent_creation(customer_engine, configuration)


def concurrent_creation(customer_engine: Engine, configuration: Settings) -> None:
    with Session(customer_engine) as db:
        wid = seed(db, configuration).workspace_id
    barrier = Barrier(2)

    def submit() -> str:
        with Session(customer_engine) as db:
            barrier.wait(timeout=10)
            goal = service.create(db, wid, "actor-a", "concurrent-request", None, NOW)
            result = goal.id
            db.commit()
            return result

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(submit) for _ in range(2)]
        assert len({f.result(timeout=20) for f in futures}) == 1
    with Session(customer_engine) as db:
        assert db.scalar(select(func.count()).select_from(Goal)) == 2
        assert db.scalar(select(func.count()).select_from(GoalRevision)) == 2
        assert db.scalar(select(func.count()).select_from(GoalCreation)) == 1


def test_sqlite_file_concurrent_creation(tmp_path: Path, configuration: Settings) -> None:
    engine = create_engine(
        f"sqlite:///{tmp_path / 'concurrent.sqlite'}",
        connect_args={"check_same_thread": False, "timeout": 10},
    )
    Base.metadata.create_all(engine)
    try:
        concurrent_creation(engine, configuration)
    finally:
        engine.dispose()
