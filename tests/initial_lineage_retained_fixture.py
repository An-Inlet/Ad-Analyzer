"""Immutable genuine creation/activation history for current budget-lineage reads."""

import json
import os
import re
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import pytest
from app import advertising_capabilities
from app.database.session import Base
from scripts.inlet_producer_source_lifetime import SourceLifetime
from scripts.reset_disposable_postgres import validate_disposable_url
from sqlalchemy import Engine, create_engine, event, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from tests.financial_origin_retained_fixture import schema_snapshot
from tests.initial_lineage_validation import load_initial_lineage
from tests.retired_snapshot import PIN, extract, run_bounded
from tests.social_producer_retained_fixture import graph, owned_sqlite_target


@dataclass(frozen=True)
class InitialLineageIds:
    mode: str
    provider: str
    workspace_id: int
    account_id: int
    actor_id: str
    run_id: str
    review_id: str
    reservation_id: str
    parent_run_id: str | None
    parent_review_id: str | None
    native_id: str
    plan_digest: str
    review_digest: str
    creation_posts: int
    activation_posts: int


@dataclass(frozen=True)
class InitialLineageSource:
    engine: Engine
    ids: InitialLineageIds
    artifacts: Path


def decode_ids(output: Path, mode: str) -> InitialLineageIds:
    assert mode in {"creation", "activation"}
    assert output.is_file() and not output.is_symlink() and 0 < output.stat().st_size <= 4096
    raw = json.loads(output.read_text())
    assert type(raw) is dict and set(raw) == set(InitialLineageIds.__dataclass_fields__)
    assert raw["mode"] == mode and raw["provider"] == "meta_ads"
    for key in ("workspace_id", "account_id"):
        assert type(raw[key]) is int and raw[key] > 0
    for key in (
        "actor_id",
        "run_id",
        "review_id",
        "reservation_id",
        "plan_digest",
        "review_digest",
    ):
        assert type(raw[key]) is str and re.fullmatch(
            r"[a-f0-9]{64}" if key.endswith("digest") else r"[a-f0-9]{32}", raw[key]
        )
    for key in ("parent_run_id", "parent_review_id"):
        if mode == "creation":
            assert raw[key] is None
        else:
            assert type(raw[key]) is str and re.fullmatch(r"[a-f0-9]{32}", raw[key])
    assert type(raw["native_id"]) is str and re.fullmatch(r"[1-9][0-9]*", raw["native_id"])
    assert type(raw["creation_posts"]) is int and raw["creation_posts"] == 5
    assert type(raw["activation_posts"]) is int
    assert raw["activation_posts"] == (3 if mode == "activation" else 0)
    return InitialLineageIds(**raw)


def artifact_path(path: Path) -> None:
    assert path.is_absolute() and path.resolve() == path
    assert not path.is_symlink() and all(not p.is_symlink() for p in path.parents)


@contextmanager
def retained_initial_lineage(
    original: Engine, artifacts: Path, mode: Literal["creation", "activation"]
) -> Iterator[InitialLineageSource]:
    assert mode in {"creation", "activation"}
    assert not advertising_capabilities.advertising_writes_enabled()
    artifact_path(artifacts)
    artifacts.mkdir(parents=True)
    engine = original
    if original.dialect.name == "sqlite":
        database = artifacts / "current.sqlite"
        database.touch(exist_ok=False)
        target = owned_sqlite_target(f"sqlite:///{database}", database)
        engine = create_engine(target)
        event.listen(engine, "connect", lambda db, _: db.execute("PRAGMA foreign_keys=ON"))
        Base.metadata.create_all(engine)
    else:
        safe = make_url(validate_disposable_url())
        assert safe.host in {"localhost", "127.0.0.1", "::1"} and not safe.query
        assert engine.url == safe
        with engine.connect() as connection:
            target = str(connection.scalar(text("SELECT current_schema()")))
        assert re.fullmatch(r"inlet_test_[a-f0-9]{32}", target)
    try:
        with engine.connect() as connection:
            for name in set(inspect(engine).get_table_names()) - {"alembic_version"}:
                quoted = engine.dialect.identifier_preparer.quote(name)
                assert connection.scalar(text(f"SELECT count(*) FROM {quoted}")) == 0
        schema = schema_snapshot(engine)
        root = Path(__file__).resolve().parents[1]
        with SourceLifetime.open("initial_lineage", artifacts) as lifetime:
            extract(root, lifetime.source)
            lifetime.extracted()
            output, log = artifacts / "ids.json", artifacts / "producer.log"
            lifetime.child_started()
            code = run_bounded(
                [
                    sys.executable,
                    str(root / "tests/fixtures/retired_execution/initial_lineage_seed_driver.py"),
                    target,
                    str(output),
                    mode,
                ],
                lifetime.source,
                dict(
                    os.environ, INLET_RETIRED_EXECUTION_CHILD=PIN, PYTHONPATH=str(lifetime.source)
                ),
                log,
                180,
            )
            lifetime.after_reaped(code)
        assert code == 0, log.read_text()[-6000:]
        source = InitialLineageSource(engine, decode_ids(output, mode), artifacts)
        with Session(engine) as db:
            load_initial_lineage(db, source)
        assert schema_snapshot(engine) == schema
        before = graph(engine)
        try:
            yield source
        finally:
            assert not advertising_capabilities.advertising_writes_enabled()
            assert graph(engine) == before
            assert schema_snapshot(engine) == schema
    finally:
        if engine is not original:
            engine.dispose()


@pytest.fixture
def initial_lineage_source(
    customer_engine: Engine, tmp_path: Path, request: pytest.FixtureRequest
) -> Iterator[InitialLineageSource]:
    modes: dict[str, Literal["creation", "activation"]] = {
        "test_actual_creation_history_does_not_consume_budget_history_bound": "creation",
        "test_actual_activation_history_is_not_a_budget_decision": "activation",
    }
    assert request.node.originalname in modes
    with retained_initial_lineage(
        customer_engine, tmp_path / "initial-lineage", modes[request.node.originalname]
    ) as source:
        yield source
