"""Owned current read fixtures from exact historical approved source records."""

import json
import os
import re
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from app import advertising_capabilities
from app.customers.models import CustomerMembership, CustomerUser
from app.database.session import Base
from app.goals import service as goals
from app.goals.models import Goal
from app.goals.schemas import GoalDefinition
from app.publication.customer_intents import account
from scripts.inlet_producer_source_lifetime import SourceLifetime
from scripts.reset_disposable_postgres import validate_disposable_url
from sqlalchemy import Engine, create_engine, event, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from tests.retired_snapshot import PIN, extract, run_bounded
from tests.test_commerce_measurement import NOW


@dataclass(frozen=True)
class OptimizationSourceIds:
    workspace_id: int
    actor_id: str
    account_id: int
    goal_id: str
    goal_revision: int
    policy_digest: str
    provider_posts: int


def no_effects(engine: Engine) -> None:
    assert not advertising_capabilities.advertising_writes_enabled()
    with engine.connect() as connection:
        for table in (
            "provider_execution_attempts",
            "provider_execution_receipts",
            "provider_execution_reviews",
            "provider_execution_runs",
            "provider_exposure_reservations",
            "provider_execution_responses",
            "provider_execution_consents",
            "provider_execution_mandates",
        ):
            assert connection.scalar(text(f"SELECT count(*) FROM {table}")) == 0


@contextmanager
def retained_optimization_source_fixture(
    customer_engine: Engine,
    artifacts: Path,
) -> Iterator[tuple[Engine, OptimizationSourceIds, Path]]:
    artifacts.mkdir(parents=True)
    engine = customer_engine
    if engine.dialect.name == "sqlite":
        engine = create_engine(f"sqlite:///{artifacts / 'current.sqlite'}")
        event.listen(engine, "connect", lambda db, _: db.execute("PRAGMA foreign_keys=ON"))
        Base.metadata.create_all(engine)
        target = str(engine.url)
    else:
        assert os.environ["AD_ANALYZER_CI_DISPOSABLE_POSTGRES"] == "true"
        url = make_url(validate_disposable_url())
        assert url.drivername == "postgresql+psycopg"
        assert url.host in {"127.0.0.1", "localhost", "::1"} and not url.query
        assert url.database and re.fullmatch(r"inlet_[a-z0-9_]+_ci", url.database)
        assert engine.url == url
        with engine.connect() as connection:
            target = str(connection.scalar(text("SELECT current_schema()")))
        assert re.fullmatch(r"inlet_test_[a-f0-9]{32}", target)
    try:
        no_effects(engine)
        tables = set(inspect(engine).get_table_names())
        with engine.connect() as connection:
            for table in tables - {"alembic_version"}:
                quoted = engine.dialect.identifier_preparer.quote(table)
                assert connection.scalar(text(f"SELECT count(*) FROM {quoted}")) == 0
        root = Path(__file__).resolve().parents[1]
        with SourceLifetime.open("optimization_source", artifacts) as lifetime:
            snapshot = lifetime.source
            extract(root, snapshot)
            lifetime.extracted()
            output, log = artifacts / "ids.json", artifacts / "producer.log"
            env = dict(os.environ, INLET_RETIRED_EXECUTION_CHILD=PIN, PYTHONPATH=str(snapshot))
            driver = root / "tests/fixtures/retired_execution/optimization_source_seed_driver.py"
            lifetime.child_started()
            code = run_bounded(
                [sys.executable, str(driver), target, str(output)], snapshot, env, log, 180
            )
            lifetime.after_reaped(code)
        assert code == 0, log.read_text()[-6000:]
        assert output.stat().st_size <= 4096
        raw = json.loads(output.read_text())
        assert type(raw) is dict
        assert set(raw) == set(OptimizationSourceIds.__dataclass_fields__)
        for name in ("workspace_id", "account_id", "goal_revision"):
            assert type(raw[name]) is int and raw[name] > 0
        for name in ("actor_id", "goal_id"):
            assert type(raw[name]) is str and re.fullmatch("[a-f0-9]{32}", raw[name])
        assert type(raw["policy_digest"]) is str
        assert re.fullmatch("[a-f0-9]{64}", raw["policy_digest"])
        assert type(raw["provider_posts"]) is int and raw["provider_posts"] == 0
        ids = OptimizationSourceIds(**raw)
        media = artifacts / "media"
        with Session(engine) as db:
            user = db.get(CustomerUser, ids.actor_id)
            membership = db.get(CustomerMembership, (ids.actor_id, ids.workspace_id))
            assert user and user.status == "active"
            assert membership and membership.role == "owner" and membership.status == "active"
            goal = db.get(Goal, ids.goal_id)
            assert goal and goal.workspace_id == ids.workspace_id
            assert goal.revision == ids.goal_revision
            assert goals.assessment(db, goal, NOW) == "confirmed"
            definition = GoalDefinition.model_validate(goals.current(db, goal).definition)
            assert definition.budget_start == NOW.date()
            scope = account(db, ids.workspace_id, ids.account_id)
            assert scope.account.platform == "google_ads"
        assert set(inspect(engine).get_table_names()) == tables
        no_effects(engine)
        try:
            yield engine, ids, media
        finally:
            no_effects(engine)
    finally:
        if engine is not customer_engine:
            engine.dispose()
