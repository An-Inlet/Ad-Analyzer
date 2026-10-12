"""Real PostgreSQL waiting preserves original authority and current revocation."""

import json
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event
from typing import Any

import pytest
from app.customers.access import SESSION_COOKIE, digest
from app.customers.models import CustomerSession, CustomerUser
from app.planning_documents import authority, repository
from app.planning_documents import service as service_module
from app.planning_documents.models import PlanRow
from app.workspaces.models import Workspace
from sqlalchemy import Engine, create_engine, select, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

from tests.creative_q07_fixture import planning_snapshot
from tests.test_creative_common_basis import financial_counts
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_customer_optimization_api import headers
from tests.test_owner_runtime_composition import actual_owner as actual_owner
from tests.test_planning_authority_diagnostics import events
from tests.test_prepared_generation_runtime import create
from tests.test_shopify_sales import configuration as configuration


@pytest.mark.parametrize("customer_engine", ["postgres"], indirect=True)
@pytest.mark.parametrize("revoked", [False, True])
def test_blocked_final_save_preserves_authority(
    actual_owner: Any,
    customer_engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
    revoked: bool,
) -> None:
    alice, url = create(actual_owner)
    before = planning_snapshot(customer_engine)
    financial = financial_counts(customer_engine)
    providers = len(actual_owner[2]), len(actual_owner[0].calls)
    prepared_ready, release_preparation, save_ready = Event(), Event(), Event()
    preparations: list[Any] = []
    final_facts: list[authority.IdentityFact] = []
    saved_facts: list[authority.IdentityFact] = []
    lock_facts: list[authority.IdentityFact] = []
    pids: list[int] = []
    original_prepare = vars(service_module)["prepare_generation_checks"]
    original_refresh, original_save, original_lock = (
        authority.refresh,
        repository.save_generation,
        authority.lock,
    )

    def prepare(*args: Any) -> Any:
        result = original_prepare(*args)
        assert result is not None
        preparations.append(result)
        prepared_ready.set()
        try:
            assert release_preparation.wait(30), "blocker was not ready"
            return result
        except BaseException:
            result.close()
            raise

    def refresh(*args: Any) -> authority.IdentityFact:
        result = original_refresh(*args)
        if prepared_ready.is_set():
            final_facts.append(result)
        return result

    def saving(db: Session, **kwargs: Any) -> Any:
        db.execute(text("SET LOCAL lock_timeout = '12000ms'"))
        db.execute(text("SET LOCAL statement_timeout = '12000ms'"))
        pid = db.scalar(text("SELECT pg_backend_pid()"))
        assert type(pid) is int
        pids.append(pid)
        saved_facts.append(kwargs["fact"])
        db.info["controlled_final_save"] = True
        save_ready.set()
        return original_save(db, **kwargs)

    def locked(db: Session, principal: Any, workspace_id: int, fact: Any, **kwargs: Any) -> Any:
        if db.info.get("controlled_final_save"):
            lock_facts.append(fact)
        return original_lock(db, principal, workspace_id, fact, **kwargs)

    monkeypatch.setattr(service_module, "prepare_generation_checks", prepare)
    monkeypatch.setattr(authority, "refresh", refresh)
    monkeypatch.setattr(repository, "save_generation", saving)
    monkeypatch.setattr(authority, "lock", locked)

    def generate() -> Any:
        return alice.post(
            url + "/generate",
            headers=headers(alice),
            json=dict(expected_input_revision=1, expected_version=0, request_key="lock-age"),
        )

    blocked = False
    release_age = 0.0
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(generate)
        try:
            assert prepared_ready.wait(30), "final preparation did not arrive"
            with Session(customer_engine) as blocker, blocker.begin():
                blocker.execute(text("SET LOCAL statement_timeout = '12000ms'"))
                plan = blocker.scalars(select(PlanRow)).one()
                blocker.scalar(
                    select(Workspace).where(Workspace.id == plan.workspace_id).with_for_update()
                )
                blocker_pid = blocker.scalar(text("SELECT pg_backend_pid()"))
                if revoked:
                    session_digest = digest(alice.cookies[SESSION_COOKIE])
                    user_id = blocker.scalar(
                        select(CustomerSession.user_id).where(
                            CustomerSession.digest == session_digest
                        )
                    )
                    blocker.scalar(
                        select(CustomerUser).where(CustomerUser.id == user_id).with_for_update()
                    )
                    session = blocker.scalars(
                        select(CustomerSession)
                        .where(CustomerSession.digest == session_digest)
                        .with_for_update()
                    ).one()
                    session.revoked_at = int(time.time())
                    blocker.flush()
                release_preparation.set()
                assert save_ready.wait(10), "final save did not arrive"
                # Separate connection, bounded SQL, exact blocker relation.
                observer_engine = create_engine(
                    customer_engine.url,
                    poolclass=NullPool,
                    connect_args={"connect_timeout": 1, "options": "-cstatement_timeout=500"},
                )
                try:
                    with observer_engine.connect() as observer:
                        deadline = time.monotonic() + 1
                        while True:
                            blocked = bool(
                                observer.scalar(
                                    text("SELECT :blocker = ANY(pg_blocking_pids(:worker))"),
                                    dict(blocker=blocker_pid, worker=pids[0]),
                                )
                            )
                            if blocked:
                                break
                            assert time.monotonic() < deadline, "workspace wait not observed"
                            time.sleep(0.005)
                finally:
                    observer_engine.dispose()
                one_final_refresh = len(final_facts) == 1
                assert one_final_refresh, "final refresh count changed"
                fact = final_facts[0]
                while time.monotonic() - fact.completed_monotonic < 6:
                    time.sleep(0.02)
                release_age = time.monotonic() - fact.completed_monotonic
                # Commit unlocks workspace and publishes revocation together.
        finally:
            release_preparation.set()
        response = future.result(timeout=20)

    assert response.status_code == (401 if revoked else 409), response.text
    assert response.json() == {
        "detail": "customer authentication required" if revoked else "planning_authority_expired"
    }
    observed = events(caplog)
    if revoked:
        assert observed == []
    else:
        assert observed == [
            dict(
                event="planning_authority_expired",
                schema_version=1,
                route="generate",
                phase="lock",
                cause="fact_age_outside_window",
                session_predicate="not_evaluated",
                status=409,
            )
        ]
    one_fact_each = len(final_facts) == len(saved_facts) == len(lock_facts) == 1
    assert one_fact_each, "original authority call counts changed"
    original_fact = final_facts[0] is saved_facts[0] is lock_facts[0]
    assert original_fact, "original authority fact changed"
    assert blocked and release_age >= 6
    assert len(preparations) == 1
    assert preparations[0].snapshots is None and preparations[0].db is None
    assert planning_snapshot(customer_engine) == before
    assert financial_counts(customer_engine) == financial
    assert (len(actual_owner[2]), len(actual_owner[0].calls)) == providers
    (tmp_path / "lock-expiry.json").write_text(
        json.dumps(
            dict(
                revoked=revoked,
                blocked=blocked,
                release_age_seconds=release_age,
                status=response.status_code,
                final_refreshes=1,
                same_original_fact=True,
                preparation_closed=True,
                planning_unchanged=True,
                financial_unchanged=True,
                authority_events=observed,
            ),
            indent=2,
        )
        + "\n"
    )
