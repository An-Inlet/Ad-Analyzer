"""Scoped-factory scheduling regression; lower-level service fixtures, not API acceptance."""

from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest
from app.optimization_candidates import service
from app.settings import Settings
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from tests.candidate_current_fixture import current_candidate_read as current_candidate_read
from tests.candidate_worker_fixture import (
    current_dual_candidate_read as current_dual_candidate_read,
)
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_shopify_sales import configuration as configuration


@pytest.mark.parametrize("batch_limit", [1, 10])
@pytest.mark.parametrize("failure", ["raise", "none"])
@pytest.mark.planning_boundary
def test_distinct_scoped_lifetimes_survive_first_admission_failure(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    batch_limit: int,
    failure: str,
    current_dual_candidate_read: tuple[Engine, dict[str, Any]],
) -> None:
    from tests.candidate_read_retained_fixture import load_candidate_read_fixture

    customer_engine, ids = current_dual_candidate_read
    runtimes = {}
    originals = {}
    for name in ("first", "second"):
        with Session(customer_engine) as db:
            principal, work, _, _, runtime, _ = load_candidate_read_fixture(db, ids[name])
            job = service.enqueue(db, principal, work, runtime)
            runtimes[job.workspace_id] = runtime
            originals[job.workspace_id] = (job.actor_id, job.auth_session_digest)
    entered, closed = [], []

    @contextmanager
    def scoped(engine: Engine, wid: int, job_id: str) -> Any:
        assert engine is customer_engine
        entered.append(wid)
        try:
            with Session(engine) as db:
                row = service.load(db, wid, job_id)
                assert (row.actor_id, row.auth_session_digest) == originals[wid]
            if len(entered) == 1:
                if failure == "raise":
                    raise RuntimeError("controlled admission failure")
                yield None
                return
            yield runtimes[wid]
        finally:
            closed.append(wid)

    def forbidden() -> Any:
        raise AssertionError("global runtime factory must not run")

    first = next(iter(runtimes.values()))

    def tick() -> dict[str, int]:
        return service.run_candidate_reads(
            customer_engine,
            forbidden,
            scoped_provider=scoped,
            environment=first.environment,
            clock=first.clock,
            limit=batch_limit,
        )

    if batch_limit == 1:
        assert tick() == {"unavailable": 1}
        assert tick() == {"completed": 1}
    else:
        assert tick() == {"unavailable": 1, "completed": 1}
    assert len(entered) == 2 and len(set(entered)) == 2
    assert entered == closed
    assert len(set(originals.values())) == 2


@pytest.mark.planning_boundary
def test_revoked_first_job_yields_to_same_workspace_next_tick(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    current_candidate_read: tuple[Engine, Any],
) -> None:
    from dataclasses import replace
    from datetime import timedelta

    from app.customers.access import CustomerPrincipal, lock_customer_mutation
    from app.customers.models import CustomerSession
    from app.optimization_candidates.models import CandidateJob

    from tests.candidate_read_retained_fixture import load_candidate_read_fixture
    from tests.test_execution_session_authorizer import guard

    customer_engine, ids = current_candidate_read
    with Session(customer_engine) as db:
        first, work, _, _, runtime, _ = load_candidate_read_fixture(db, ids)
        first_job = service.enqueue(db, first, work, runtime)
        first_id = first_job.id
        first_job.due_at = runtime.clock() - timedelta(seconds=1)
        db.commit()
        _, token = guard(db, first.user.id)
        second_session = db.get(CustomerSession, token)
        assert second_session
        second = CustomerPrincipal(first.user, second_session)
        second_policy = work.policy.model_copy(update={"revision": 2})
        policies = {1: work.policy, 2: second_policy}
        runtime = replace(runtime, policy_reader=lambda db, wid, pid, rev: policies[rev])
        second_work = work.model_copy(update={"policy": second_policy})
        second_id = service.enqueue(db, second, second_work, runtime).id
        first_session = db.get(CustomerSession, first.session.digest)
        assert first_session
        first_session.revoked_at = int(runtime.clock().timestamp())
        db.commit()

    seen = []

    @contextmanager
    def scoped(engine: Engine, workspace: int, identifier: str) -> Any:
        seen.append(identifier)
        with Session(engine) as db:
            job = service.load(db, workspace, identifier)
            principal = service.principal_for(db, job)
            lock_customer_mutation(db, principal, workspace, runtime.identity)
        yield runtime

    def tick() -> dict[str, int]:
        return service.run_candidate_reads(
            customer_engine,
            scoped_provider=scoped,
            environment=runtime.environment,
            clock=runtime.clock,
            limit=1,
        )

    assert tick() == {"unavailable": 1}
    assert tick() == {"completed": 1}
    assert seen == [first_id, second_id]
    with Session(customer_engine) as db:
        first_row = db.get(CandidateJob, first_id)
        assert first_row and first_row.state == "pending"
        assert first_row.fence is None and first_row.attempts == 0
        assert first_row.error_code == "candidate_runtime_unavailable"
