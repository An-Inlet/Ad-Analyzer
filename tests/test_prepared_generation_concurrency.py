"""Prepared V6 generation: SQLite stale-ticket parity and PostgreSQL lock overlap."""

import hmac
import json
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event, Lock
from typing import Any

import pytest
from app.customers.access import SESSION_COOKIE
from app.main import app
from app.planning_documents import authority, repository
from app.planning_documents import service as service_module
from app.planning_documents.documents import PlanVersion
from app.planning_documents.models import PlanRequestRow, PlanRow, PlanVersionRow
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, select, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

from tests.contention_evidence import Evidence
from tests.creative_q07_fixture import planning_snapshot
from tests.test_creative_common_basis import financial_counts
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_customer_optimization_api import headers
from tests.test_owner_runtime_composition import actual_owner as actual_owner
from tests.test_prepared_generation_runtime import create
from tests.test_shopify_sales import configuration as configuration


@pytest.mark.parametrize("same_key", [False, True])
def test_prepared_generation_receipt_and_head_fence(
    actual_owner: Any,
    customer_engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
    same_key: bool,
    tmp_path: Path,
) -> None:
    with (
        Evidence(tmp_path / "contention-evidence.json") as evidence,
        monkeypatch.context() as patch,
    ):
        evidence.install(patch)
        _run_contention(actual_owner, customer_engine, patch, same_key, tmp_path, evidence)


def _run_contention(
    actual_owner: Any,
    customer_engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
    same_key: bool,
    tmp_path: Path,
    evidence: Evidence,
) -> None:
    alice, url = create(actual_owner)
    effects = financial_counts(customer_engine)
    providers = len(actual_owner[2]), len(actual_owner[0].calls)
    postgres = customer_engine.dialect.name == "postgresql"
    first_prepared, both_prepared, first_locked = Event(), Event(), Event()
    first_finished, loser_attempt = Event(), Event()
    mutex = Lock()
    preparations: list[Any] = []
    pids: dict[int, int] = {}
    blocked: list[bool] = []
    original_prepare = vars(service_module)["prepare_generation_checks"]
    original_save, original_lock = repository.save_generation, authority.lock

    def prepare(*args: Any) -> Any:
        with evidence.span("prepare"):
            result = original_prepare(*args)
        assert result is not None, "configured V6 preparation must be eligible"
        try:
            assert args[0].expected_version == 0
            with mutex:
                index = len(preparations)
                assert index < 2
                preparations.append(result)
            if index == 0:
                first_prepared.set()
                with evidence.span("prepare_peer_wait"):
                    assert both_prepared.wait(30), "second preparation did not arrive"
            else:
                both_prepared.set()
                # SQLite StaticPool has a single physical connection. Its complete
                # preparation and final transactions must remain sequential.
                ready = first_locked if postgres else first_finished
                with evidence.span("prepare_winner_wait"):
                    assert ready.wait(30), "first generation did not reach its boundary"
            evidence.preparation_complete()
            return result
        except BaseException:
            result.close()
            raise

    def saving(db: Session, **kwargs: Any) -> Any:
        index = next(i for i, value in enumerate(preparations) if value is kwargs["prepared"])
        db.info["prepared_race_index"] = index
        with evidence.span("save_setup", kwargs["fact"]):
            if postgres:
                db.execute(text("SET LOCAL lock_timeout = '4500ms'"))
                db.execute(text("SET LOCAL statement_timeout = '4500ms'"))
                pid = db.scalar(text("SELECT pg_backend_pid()"))
                assert type(pid) is int
                pids[index] = pid
        return original_save(db, **kwargs)

    def locked(db: Session, *args: Any, **kwargs: Any) -> Any:
        index = db.info.get("prepared_race_index")
        if index is None or db.info.get("prepared_race_lock_seen"):
            return original_lock(db, *args, **kwargs)
        db.info["prepared_race_lock_seen"] = True
        if index == 1 and postgres:
            loser_attempt.set()
        result = original_lock(db, *args, **kwargs)
        if index == 0 and postgres:
            with evidence.span("coordinator", args[2]):
                first_locked.set()
                with evidence.span("loser_attempt_wait", args[2]):
                    assert loser_attempt.wait(1), "second save did not attempt the final lock"
                # The coordinator stays unchanged; measure its full deadline cost.
                with evidence.span("observer_create", args[2]):
                    observer_engine = create_engine(
                        customer_engine.url,
                        poolclass=NullPool,
                        connect_args={"connect_timeout": 1, "options": "-cstatement_timeout=500"},
                    )
                try:
                    with evidence.span("observer_connect", args[2]):
                        observer = observer_engine.connect()
                    try:
                        with evidence.span("observer_query", args[2]):
                            deadline = time.monotonic() + 0.5
                            while True:
                                waiting = observer.scalar(
                                    text("SELECT :winner = ANY(pg_blocking_pids(:loser))"),
                                    {"winner": pids[0], "loser": pids[1]},
                                )
                                if waiting:
                                    blocked.append(True)
                                    evidence.database_blocking()
                                    break
                                assert time.monotonic() < deadline, (
                                    "database did not confirm lock overlap"
                                )
                                time.sleep(0.005)
                    finally:
                        with evidence.span("observer_disconnect", args[2]):
                            observer.close()
                finally:
                    with evidence.span("observer_dispose", args[2]):
                        observer_engine.dispose()
        return result

    monkeypatch.setattr(service_module, "prepare_generation_checks", prepare)
    monkeypatch.setattr(repository, "save_generation", saving)
    monkeypatch.setattr(authority, "lock", locked)

    def generate(index: int) -> Any:
        with evidence.worker(index):
            try:
                with TestClient(app, base_url=str(alice.base_url)) as client:
                    client.cookies.update(alice.cookies)
                    original_session = hmac.compare_digest(
                        client.cookies[SESSION_COOKIE], alice.cookies[SESSION_COOKIE]
                    )
                    assert original_session, "original authenticated session changed"
                    response = client.post(
                        url + "/generate",
                        headers=headers(client),
                        json=dict(
                            expected_input_revision=1,
                            expected_version=0,
                            request_key=f"prepared-race-{0 if same_key else index}",
                        ),
                    )
                    evidence.response(index, response)
                    return response
            finally:
                if index == 0:
                    first_finished.set()

    with ThreadPoolExecutor(max_workers=2) as pool:
        winner = pool.submit(generate, 0)
        assert first_prepared.wait(30), "first preparation did not arrive"
        loser = pool.submit(generate, 1)
        first, second = winner.result(timeout=45), loser.result(timeout=45)
    assert first.status_code == 200, "first response failed; see contention-evidence.json"
    if same_key:
        assert second.status_code == 200, "second response failed; see contention-evidence.json"
        same_response = second.json() == first.json()
        assert same_response, "idempotent response changed"
    else:
        assert second.status_code == 409, "second response failed; see contention-evidence.json"
        assert second.json() == {"detail": "generation input or version changed"}
    final_refresh_workers = [
        row["worker"]
        for row in evidence.records
        if row["event"] == "refreshed" and row["final_fact"]
    ]
    assert sorted(final_refresh_workers) == [0, 1], "one original final refresh per worker required"
    assert {row["worker"] for row in evidence.records if row["event"] == "guard_start"} == {0, 1}
    assert blocked == ([True] if postgres else [])
    assert len(preparations) == 2
    independent = preparations[0] is not preparations[1]
    assert independent, "each generation needs a distinct preparation"
    assert all(value.snapshots is None and value.db is None for value in preparations)
    document = PlanVersion.model_validate(first.json()["document"])
    with Session(customer_engine) as db:
        plan = db.scalars(select(PlanRow)).one()
        assert (plan.input_head, plan.version_head, plan.event_sequence) == (1, 1, 0)
        row = db.scalars(select(PlanVersionRow)).one()
        assert row.digest == document.digest()
        assert PlanVersion.model_validate_json(row.canonical_json) == document
        receipts = list(db.scalars(select(PlanRequestRow)))
        assert sorted(row.operation for row in receipts) == ["create", "generate"]
        generated = next(row for row in receipts if row.operation == "generate")
        assert (generated.plan_id, generated.version, generated.request_key) == (
            plan.id,
            1,
            "prepared-race-0",
        )
    retained = planning_snapshot(customer_engine)
    exported = alice.get(url + "/export?version=1")
    assert exported.status_code == 200, exported.text
    assert PlanVersion.model_validate(exported.json()["document"]) == document
    assert planning_snapshot(customer_engine) == retained
    assert financial_counts(customer_engine) == effects
    assert (len(actual_owner[2]), len(actual_owner[0].calls)) == providers
    (tmp_path / "prepared-generation-concurrency.json").write_text(
        json.dumps(
            dict(
                same_key=same_key,
                mode="postgres_blocked_lock" if postgres else "sqlite_sequential_stale_ticket",
                blocked=blocked,
                statuses=[first.status_code, second.status_code],
                distinct_preparations=independent,
                preparations_closed=all(value.snapshots is None for value in preparations),
                document_digest=document.digest(),
                export_digest=PlanVersion.model_validate(exported.json()["document"]).digest(),
                version_count=1,
                generation_receipt_count=1,
            ),
            indent=2,
        )
    )
