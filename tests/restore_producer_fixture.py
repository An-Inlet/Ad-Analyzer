"""Current-schema adapter for authentic historical restore rows, no guard overrides."""

from collections.abc import Iterator
from pathlib import Path
from uuid import uuid4

import pytest
from app.database.models import register_models
from scripts.inlet_restore_historical import _seed
from sqlalchemy import Engine, create_engine, event

from tests.test_customer_identity import customer_engine as customer_engine


@pytest.fixture
def seeded_restore_graph(customer_engine: Engine, tmp_path: Path) -> Iterator[Engine]:
    root = tmp_path / ("inlet_restore_fixture_" + uuid4().hex)
    root.mkdir()
    engine = customer_engine
    if engine.dialect.name == "sqlite":
        engine = create_engine("sqlite:///" + str(root / "current.sqlite"))
        event.listen(engine, "connect", lambda db, _: db.execute("PRAGMA foreign_keys=ON"))
        register_models().create_all(engine)
    try:
        _seed(engine, root / "producer", "fixture")
        yield engine
    finally:
        if engine is not customer_engine:
            engine.dispose()
