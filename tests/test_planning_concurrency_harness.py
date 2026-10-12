"""Scheduling and failure evidence microchecks; no product release acceptance."""

import json
import time
from pathlib import Path
from threading import Event, Lock
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from app.planning_documents import authority
from sqlalchemy import event

from tests import planning_concurrency_harness as harness
from tests.contention_evidence import _WORKER
from tests.planning_concurrency_harness import SCENARIOS, PassiveBlockingObserver, run_clients
from tests.planning_release_evidence import (
    _CURRENT,
    _KEY,
    ReleaseEvidence,
    pytest_runtest_makereport,
    pytest_runtest_protocol,
    record_intentional_delay,
)


def test_matrix_has_exactly_eighteen_declared_scenarios() -> None:
    assert len(SCENARIOS) == len({s.key for s in SCENARIOS}) == 18
    assert sum(s.requires_overlap for s in SCENARIOS) == 4


@pytest.mark.parametrize("offset", [0, 50, 250])
@pytest.mark.parametrize("failure", [False, True])
def test_arrivals_do_not_wait_inside_requests_and_both_outcomes_survive(
    tmp_path: Path, offset: int, failure: bool
) -> None:
    destination = tmp_path / "evidence.json"
    arrivals: list[float] = [0, 0]
    lock = Lock()
    second_arrived = Event()
    sentinel = RuntimeError("PRIVATE_FAILURE")

    def first() -> Any:
        with lock:
            arrivals[0] = time.monotonic()
        # Synthetic operation only: checks that client2 can arrive while client1 runs.
        assert second_arrived.wait(2)
        if failure:
            raise sentinel
        return httpx.Response(200, json={"PRIVATE_BODY": True})

    def second() -> Any:
        with lock:
            arrivals[1] = time.monotonic()
        second_arrived.set()
        return httpx.Response(409, json={"detail": "generation input or version changed"})

    if failure:
        with pytest.raises(RuntimeError) as actual, ReleaseEvidence(destination) as evidence:
            run_clients(first, second, offset_ms=offset, evidence=evidence)
        assert actual.value is sentinel
    else:
        with ReleaseEvidence(destination) as evidence:
            result = run_clients(first, second, offset_ms=offset, evidence=evidence)
        assert [r.status_code for r in result] == [200, 409]
    raw = destination.read_text()
    assert "PRIVATE" not in raw
    data = json.loads(raw)
    assert data["outcomes"][0]["state"] == ("exception" if failure else "response")
    assert data["outcomes"][1]["state"] == "response"
    assert data["evidence_complete"] and data["sampler_stopped"]
    starts = [r for r in data["records"] if r["event"] == "stage_start"]
    assert {r["stage"] for r in starts} == {"client_ready", "client_arrival"}
    if offset:
        assert arrivals[1] - arrivals[0] >= offset / 1000 - 0.01


@pytest.mark.parametrize("phase", ["setup", "call", "teardown"])
def test_first_failure_report_is_preserved_in_protocol(
    tmp_path: Path, phase: str
) -> None:
    item = SimpleNamespace(
        nodeid="synthetic::case",
        stash={},
        config=SimpleNamespace(getoption=lambda _: str(tmp_path)),
    )
    protocol = pytest_runtest_protocol(item, None)
    next(protocol)
    evidence = item.stash[_KEY]
    report = pytest_runtest_makereport(item, None)
    next(report)
    with pytest.raises(StopIteration):
        report.send(SimpleNamespace(get_result=lambda: SimpleNamespace(
            when=phase, outcome="failed", failed=True
        )))
    with pytest.raises(StopIteration):
        next(protocol)
    assert _CURRENT.get() is None
    paths = list(tmp_path.glob("*.json"))
    assert len(paths) == 1
    data = json.loads(paths[0].read_text())
    assert data["body_failed"] and data["evidence_complete"]
    assert any(r["event"] == "pytest_report" and r["stage"] == phase for r in data["records"])
    assert evidence.failed_report


def test_authority_age_and_phase_recorded_before_intentional_delay(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fact = authority.IdentityFact("PRIVATE", "PRIVATE", "PRIVATE", "PRIVATE", 1, time.monotonic())
    seen: list[Any] = []
    monkeypatch.setattr(authority, "final", lambda principal, value, **kw: seen.append(value))
    path = tmp_path / "delay.json"
    with ReleaseEvidence(path) as evidence, monkeypatch.context() as patch:
        evidence.install(patch)
        token = _CURRENT.set(evidence)
        try:
            with evidence.worker(0):
                record_intentional_delay(fact, "post_flush", 6)
                vars(authority)["final"](None, fact, diagnostic_phase="post_flush")
        finally:
            _CURRENT.reset(token)
    data = json.loads(path.read_text())
    delay = next(r for r in data["records"] if r["event"] == "intentional_delay_start")
    guard = next(r for r in data["records"] if r["event"] == "guard_start")
    assert delay["phase"] == guard["phase"] == "post_flush"
    assert 0 <= delay["age"] <= guard["age"] and delay["at"] <= guard["at"]
    assert seen == [fact] and data["evidence_complete"]
    assert "PRIVATE" not in path.read_text()


@pytest.mark.parametrize(
    "failure", ["body", "listen", "start", "remove", "join", "timeout", "record"]
)
def test_observer_lifecycle_never_masks_original_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    sentinel = RuntimeError("PRIVATE_ORIGINAL")
    steps: list[str] = []
    evidence = ReleaseEvidence(tmp_path / "observer.json")
    engine: Any = SimpleNamespace(dialect=SimpleNamespace(name="postgresql"))
    connection: Any = SimpleNamespace(
        dialect=engine.dialect, get_isolation_level=lambda: "READ COMMITTED"
    )

    def listen(*args: Any) -> None:
        steps.append("listen")
        if failure == "listen":
            raise sentinel

    def remove(*args: Any) -> None:
        steps.append("remove")
        if failure == "remove":
            raise RuntimeError("cleanup failed")

    class Worker:
        def __init__(self, **kwargs: Any) -> None:
            pass

        def start(self) -> None:
            steps.append("start")
            if failure == "start":
                raise sentinel

        def join(self, **kwargs: Any) -> None:
            steps.append("join")
            if failure == "join":
                raise RuntimeError("cleanup failed")

        def is_alive(self) -> bool:
            return failure == "timeout"

    monkeypatch.setattr(event, "listen", listen)
    monkeypatch.setattr(event, "remove", remove)
    monkeypatch.setattr(harness, "Thread", Worker)
    if failure == "record":
        def broken_record(*args: Any, **kwargs: Any) -> None:
            raise RuntimeError("record failed")
        monkeypatch.setattr(evidence, "_record", broken_record)
    observer = PassiveBlockingObserver(engine, connection, evidence)
    with pytest.raises(RuntimeError) as actual, observer:
        raise sentinel
    assert actual.value is sentinel
    assert "remove" in steps
    assert (evidence.observer_errors == 0) is (failure == "body")
    assert observer.listener_removed is (failure != "remove")


@pytest.mark.parametrize(
    "scope", ["final_save", "incidental", "ended_during_sample", "stale_pid", "replaced_pid"]
)
def test_only_stable_final_save_overlap_counts(tmp_path: Path, scope: str) -> None:
    evidence = ReleaseEvidence(tmp_path / "observer.json")
    engine: Any = SimpleNamespace(dialect=SimpleNamespace(name="postgresql"))
    if scope != "incidental":
        evidence.active_saves = {0: (1, 1), 1: (2, 1)}

    def query(*args: Any) -> Any:
        if scope == "ended_during_sample":
            evidence.active_saves.pop(1)
        elif scope == "replaced_pid":
            observer.pids[1] = (33, (2, 1))
        return SimpleNamespace(one=lambda: (True, False))

    connection: Any = SimpleNamespace(
        dialect=engine.dialect, get_isolation_level=lambda: "READ COMMITTED", execute=query
    )
    observer = PassiveBlockingObserver(engine, connection, evidence)
    observer.pids = {0: (11, (1, 1)), 1: (22, (2, 1))}
    if scope == "stale_pid":
        observer.pids[1] = (22, None)

    class OneSample(Event):
        calls = 0

        def wait(self, timeout: float | None = None) -> bool:
            self.calls += 1
            return self.calls > 1

    observer.stop = OneSample()
    observer._sample()
    assert observer.samples == 1 and observer.errors == 0
    assert observer.overlaps == ({(0, 1)} if scope == "final_save" else set())
    assert observer.incidental == (set() if scope == "final_save" else {(0, 1)})
    assert evidence.records[-1]["scope"] == (
        "final_save" if scope == "final_save" else "incidental"
    )


@pytest.mark.parametrize("pattern", ["same_key", "different_keys", "distinct_workspaces"])
def test_response_contract_rejects_expiry_and_cross_workspace(pattern: Any) -> None:
    scenario = harness.Scenario("small", pattern, 0)
    scopes = ((1, "a"), (2, "b") if pattern == "distinct_workspaces" else (1, "a"))

    def response(scope: tuple[int, str]) -> httpx.Response:
        return httpx.Response(
            200, json={"document": {"inputs": {"workspace_id": scope[0], "plan_id": scope[1]}}}
        )

    valid = (response(scopes[0]), response(scopes[1]))
    if pattern == "different_keys":
        valid = (
            valid[0], httpx.Response(409, json={"detail": "generation input or version changed"})
        )
    harness.assert_response_contract(scenario, valid, scopes)
    expired = httpx.Response(409, json={"detail": "planning_authority_expired"})
    with pytest.raises(AssertionError):
        harness.assert_response_contract(scenario, (valid[0], expired), scopes)
    with pytest.raises(AssertionError):
        harness.assert_response_contract(scenario, (response((99, "foreign")), valid[1]), scopes)


def test_backend_binding_captures_the_current_save_epoch(tmp_path: Path) -> None:
    evidence = ReleaseEvidence(tmp_path / "observer.json")
    engine: Any = SimpleNamespace(dialect=SimpleNamespace(name="postgresql"))
    connection: Any = SimpleNamespace(
        dialect=engine.dialect, get_isolation_level=lambda: "READ COMMITTED"
    )
    observer = PassiveBlockingObserver(engine, connection, evidence)
    sql_connection = SimpleNamespace(connection=SimpleNamespace(
        driver_connection=SimpleNamespace(info=SimpleNamespace(backend_pid=11))
    ))
    token = _WORKER.set(0)
    try:
        observer._query_started(sql_connection)
        assert observer.pids == {0: (11, None)}
        evidence.active_saves[0] = (1, 2)
        observer._query_started(sql_connection)
        assert observer.pids == {0: (11, (1, 2))}
    finally:
        _WORKER.reset(token)
