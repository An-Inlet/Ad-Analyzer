"""Genuine historical lineage in a current disposable schema; IDs cross the process seam."""

import json
import os
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from app.database.session import Base
from sqlalchemy import Engine, create_engine, event, text

from tests.retired_snapshot import PIN, extract, run_bounded


@dataclass(frozen=True)
class RetainedReviewIds:
    workspace_id: int
    preview_id: str
    review_id: str
    actor_id: str
    run_id: str
    attempt_id: str
    reservation_id: str
    provider_posts: int


@contextmanager
def retained_review_fixture(
    customer_engine: Engine, artifacts: Path,
) -> Iterator[tuple[Engine, RetainedReviewIds]]:
    artifacts.mkdir(parents=True, exist_ok=True)
    engine = customer_engine
    if engine.dialect.name == "sqlite":
        engine = create_engine(f"sqlite:///{artifacts / 'current.sqlite'}")
        event.listen(engine, "connect", lambda db, _: db.execute("PRAGMA foreign_keys=ON"))
        Base.metadata.create_all(engine)
        target = str(engine.url)
    else:
        with engine.connect() as connection:
            target = str(connection.scalar(text("select current_schema()")))
    try:
        root = Path(__file__).resolve().parents[1]
        snapshot = artifacts / "historical-source"
        extract(root, snapshot)
        output, log = artifacts / "producer-ids.json", artifacts / "producer.log"
        env = dict(os.environ, INLET_RETIRED_EXECUTION_CHILD=PIN, PYTHONPATH=str(snapshot))
        driver = root / "tests/fixtures/retired_execution/seed_driver.py"
        code = run_bounded(
            [sys.executable, str(driver), target, str(output)], snapshot, env, log, 180
        )
        assert code == 0, log.read_text()[-6000:]
        result = RetainedReviewIds(**json.loads(output.read_text()))
        assert result.provider_posts == 1
        yield engine, result
    finally:
        if engine is not customer_engine:
            engine.dispose()
