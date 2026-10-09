"""Genuine historical lineage in a current disposable schema; IDs cross the process seam."""

import json
import os
import sys
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

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
