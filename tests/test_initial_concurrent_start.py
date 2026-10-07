"""Two actual Start requests meet outside locks and converge after catalog reads."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from threading import Barrier, local
from typing import Any

import pytest
from app.initial_planning.automatic_models import InitialRuleOpportunity
from app.initial_planning.start_models import InitialRuleSessionStart
from app.optimization_candidates.models import CandidateJob
from app.optimization_candidates.review_bridge import original
from app.publication.execution_models import ProviderExecutionAttempt
from app.session_automation import service
from app.session_automation.models import SessionAutomationRun
from app.settings import Settings
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_initial_rule_acceptance import initial_start_case
from tests.test_shopify_sales import configuration as configuration


def test_concurrent_exact_initial_start(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    replicas: Any,
) -> None:
    if customer_engine.dialect.name != "postgresql":
        pytest.skip("independent Start transactions require PostgreSQL row locks")
    with initial_start_case(customer_engine, configuration, tmp_path, monkeypatch, replicas) as (
        c,
        runtime,
        intent,
        wid,
    ):
        actor, token = c.principal.user.id, c.principal.session.digest
        c.db.commit()
        barrier, turns = Barrier(2), local()
        catalog = runtime.selection.catalog

        def synchronized_catalog(request: Any, now: Any) -> Any:
            value = catalog(request, now)
            if not getattr(turns, "passed", False):
                turns.passed = True
                # Both callers have observed no existing Start and committed before IO.
                barrier.wait(timeout=30)
            return value

        runtime = replace(
            runtime, selection=replace(runtime.selection, catalog=synchronized_catalog)
        )

        def start() -> str:
            with Session(customer_engine) as db:
                principal = original(db, actor, token)
                return service.start(db, principal, wid, intent, runtime).id

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(start) for _ in range(2)]
            identifiers = [future.result(timeout=90) for future in futures]
        assert identifiers[0] == identifiers[1]
        with Session(customer_engine) as db:
            for model in (
                SessionAutomationRun,
                InitialRuleSessionStart,
                CandidateJob,
                InitialRuleOpportunity,
            ):
                assert db.scalar(select(func.count()).select_from(model)) == 1
            assert db.scalar(select(func.count()).select_from(ProviderExecutionAttempt)) == 0
        assert not c.server.posts
