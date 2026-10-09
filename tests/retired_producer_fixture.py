"""Genuine historical lineage in a current disposable schema; IDs cross the process seam."""

import json
import os
import re
import sys
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from app.database.session import Base
from sqlalchemy import Engine, create_engine, event, inspect, text

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


@dataclass(frozen=True)
class RetainedInitialRuleIds:
    workspace_id: int
    preview_id: str
    mandate_id: str
    session_run_id: str
    candidate_job_id: str
    provider_posts: int


NativeDiagnosticProvider = Literal["google_ads", "meta_ads", "tiktok_ads"]


@dataclass(frozen=True)
class RetainedNativeDiagnosticIds:
    workspace_id: int
    actor_id: str
    account_id: int
    mandate_id: str
    revision: int
    consent_id: str
    policy_digest: str
    ledger_id: str
    environment: str
    provider_posts: int


@contextmanager
def retained_native_diagnostic_fixture(
    customer_engine: Engine,
    artifacts: Path,
    provider: NativeDiagnosticProvider,
) -> Iterator[tuple[Engine, RetainedNativeDiagnosticIds]]:
    if provider not in {"google_ads", "meta_ads", "tiktok_ads"}:
        raise AssertionError("Only closed native diagnostic providers")
    with _retained_fixture(
        customer_engine, artifacts, "native_diagnostic", None, provider=provider
    ) as (engine, raw):
        result = RetainedNativeDiagnosticIds(**raw)
        assert result.provider_posts == 0
        yield engine, result


@contextmanager
def retained_review_fixture(
    customer_engine: Engine,
    artifacts: Path,
    *,
    prepare_schema: Callable[[Engine], None] | None = None,
) -> Iterator[tuple[Engine, RetainedReviewIds]]:
    with _retained_fixture(customer_engine, artifacts, "review", prepare_schema) as (engine, raw):
        result = RetainedReviewIds(**raw)
        assert result.provider_posts == 1
        yield engine, result


@contextmanager
def retained_initial_rule_fixture(
    customer_engine: Engine,
    artifacts: Path,
) -> Iterator[tuple[Engine, RetainedInitialRuleIds]]:
    with _retained_fixture(customer_engine, artifacts, "initial_rule", None) as (engine, raw):
        result = RetainedInitialRuleIds(**raw)
        assert result.provider_posts == 0
        yield engine, result


@contextmanager
def _retained_fixture(
    customer_engine: Engine,
    artifacts: Path,
    mode: Literal["review", "initial_rule", "native_diagnostic"],
    prepare_schema: Callable[[Engine], None] | None,
    *,
    provider: NativeDiagnosticProvider | None = None,
) -> Iterator[tuple[Engine, dict[str, Any]]]:
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
        if prepare_schema is not None:
            prepare_schema(engine)
        root = Path(__file__).resolve().parents[1]
        snapshot = artifacts / "historical-source"
        extract(root, snapshot)
        output, log = artifacts / "producer-ids.json", artifacts / "producer.log"
        env = dict(os.environ, INLET_RETIRED_EXECUTION_CHILD=PIN, PYTHONPATH=str(snapshot))
        driver = root / "tests/fixtures/retired_execution/seed_driver.py"
        arguments = [sys.executable, str(driver), target, str(output), mode]
        if mode == "native_diagnostic":
            assert provider in {"google_ads", "meta_ads", "tiktok_ads"}
            arguments.append(provider)
        else:
            assert provider is None
        code = run_bounded(
            arguments, snapshot, env, log, 180
        )
        assert code == 0, log.read_text()[-6000:]
        yield engine, json.loads(output.read_text())
    finally:
        if engine is not customer_engine:
            engine.dispose()


@dataclass(frozen=True)
class RetainedCommercePublicationIds:
    workspace_id: int
    store_id: str
    publication_id: str
    order_count: int
    publication_count: int
    evidence_state_count: int


def retained_commerce_publication_fixture(
    engine: Engine, artifacts: Path,
) -> RetainedCommercePublicationIds:
    """Single closed producer at actual 0053; caller owns all schema DDL."""
    assert engine.dialect.name == "postgresql"
    assert os.environ.get("AD_ANALYZER_CI_DISPOSABLE_POSTGRES") == "true"
    with engine.connect() as db:
        target = str(db.scalar(text("SELECT current_schema()")))
        assert re.fullmatch(r"inlet_publication_[a-f0-9]{32}", target)
        revision = set(db.scalars(text("SELECT version_num FROM alembic_version")))
        assert revision == {"20261006_0051", "20261006_0053"}
        for table in ("commerce_orders", "commerce_measurement_publications",
                      "commerce_evidence_states"):
            assert db.scalar(text(f"SELECT count(*) FROM {table}")) == 0
    tables = set(inspect(engine).get_table_names())
    assert {"workspaces", "commerce_orders", "commerce_measurement_publications",
            "commerce_evidence_states"} <= tables
    assert not {"meta_presence_stage_contexts", "planning_input_revisions",
                "campaign_performance_completions"} & tables
    artifacts.mkdir(parents=True, exist_ok=True)
    root = Path(__file__).resolve().parents[1]
    snapshot = artifacts / "historical-source"
    extract(root, snapshot)
    output, log = artifacts / "producer-ids.json", artifacts / "producer.log"
    assert not output.exists()
    env = dict(os.environ, INLET_RETIRED_EXECUTION_CHILD=PIN, PYTHONPATH=str(snapshot))
    code = run_bounded(
        [sys.executable, str(root / "tests/fixtures/retired_execution/seed_driver.py"),
         target, str(output), "commerce_publication_0053"], snapshot, env, log, 180,
    )
    assert code == 0, log.read_text()[-6000:]
    raw = json.loads(output.read_text())
    assert set(raw) == set(RetainedCommercePublicationIds.__dataclass_fields__)
    assert type(raw["workspace_id"]) is int and raw["workspace_id"] > 0
    for key in ("store_id", "publication_id"):
        assert type(raw[key]) is str and 0 < len(raw[key]) <= 128
    for key in ("order_count", "publication_count", "evidence_state_count"):
        assert type(raw[key]) is int and raw[key] == 1
    result = RetainedCommercePublicationIds(**raw)
    assert set(inspect(engine).get_table_names()) == tables
    with engine.connect() as db:
        assert set(db.scalars(text("SELECT version_num FROM alembic_version"))) == revision
        assert db.execute(text(
            "SELECT workspace_id,store_id FROM commerce_measurement_publications WHERE id=:id"
        ), {"id": result.publication_id}).one() == (result.workspace_id, result.store_id)
        assert db.scalar(text("SELECT store_id FROM commerce_evidence_states")) == result.store_id
        for table in ("commerce_orders", "commerce_measurement_publications",
                      "commerce_evidence_states"):
            assert db.scalar(text(f"SELECT count(*) FROM {table}")) == 1
    return result
