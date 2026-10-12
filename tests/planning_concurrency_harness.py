"""Bounded client scheduling and passive PostgreSQL observation; no request barriers."""

import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from threading import Barrier, Event, Lock, Thread
from typing import Any, Literal

from sqlalchemy import Connection, Engine, event, text

from tests.contention_evidence import _WORKER
from tests.planning_release_evidence import ReleaseEvidence

Pattern = Literal["same_key", "different_keys", "distinct_workspaces"]
Size = Literal["small", "large"]


@dataclass(frozen=True)
class Scenario:
    size: Size
    pattern: Pattern
    offset_ms: int

    @property
    def key(self) -> str:
        return f"{self.size}-{self.pattern}-{self.offset_ms}ms"

    @property
    def requires_overlap(self) -> bool:
        return self.offset_ms == 0 and self.pattern != "distinct_workspaces"


SIZES: tuple[Size, ...] = ("small", "large")
PATTERNS: tuple[Pattern, ...] = ("same_key", "different_keys", "distinct_workspaces")
SCENARIOS = tuple(
    Scenario(size, pattern, offset)
    for size in SIZES
    for pattern in PATTERNS
    for offset in (0, 50, 250)
)


def run_clients(
    first: Callable[[], Any],
    second: Callable[[], Any],
    *,
    offset_ms: int,
    evidence: ReleaseEvidence,
) -> tuple[Any, Any]:
    """Callbacks own already opened clients; scheduling ends before HTTP/authentication."""
    assert offset_ms in (0, 50, 250)
    ready = Barrier(3)
    first_arrived = Event()
    first_stamp: list[float] = []
    results: list[Any] = [None, None]
    errors: list[BaseException | None] = [None, None]

    def client(index: int, operation: Callable[[], Any]) -> None:
        with evidence.worker(index):
            with evidence.stage("client_ready"):
                ready.wait(timeout=10)
                if index == 1 and offset_ms:
                    assert first_arrived.wait(10), "first client did not arrive"
                    remaining = first_stamp[0] + offset_ms / 1000 - time.monotonic()
                    if remaining > 0:
                        Event().wait(remaining)
            with evidence.stage("client_arrival"):
                if index == 0:
                    first_stamp.append(time.monotonic())
                    first_arrived.set()
            try:
                response = operation()
                evidence.response(index, response)
                results[index] = response
            except BaseException as exc:
                errors[index] = exc
                raise

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(client, i, callback) for i, callback in enumerate((first, second))]
        ready.wait(timeout=10)
        # Read both outcomes, including when the first callback raises.
        for index, future in enumerate(futures):
            try:
                future.result(timeout=120)
            except BaseException as exc:
                if errors[index] is None:
                    errors[index] = exc
    for error in errors:
        if error is not None:
            raise error
    return results[0], results[1]


class PassiveBlockingObserver:
    """Preopened observer connection; no callback waits for database overlap."""

    def __init__(self, engine: Engine, observer: Connection, evidence: ReleaseEvidence) -> None:
        assert engine.dialect.name == observer.dialect.name == "postgresql"
        assert observer.get_isolation_level() == "READ COMMITTED"
        self.engine, self.observer, self.evidence = engine, observer, evidence
        self.mutex = Lock()
        self.pids: dict[int, tuple[int, tuple[int, int] | None]] = {}
        self.stop = Event()
        self.thread: Thread | None = None
        self.overlaps: set[tuple[int, int]] = set()
        self.incidental: set[tuple[int, int]] = set()
        self.listener_removed = False
        self.errors = 0
        self.samples = 0

    def _query_started(self, connection: Any, *args: Any) -> None:
        worker = _WORKER.get()
        if worker not in (0, 1):
            return
        assert worker is not None
        try:
            pid = connection.connection.driver_connection.info.backend_pid
            assert type(pid) is int and pid > 0
            scope = self.evidence.save_scopes().get(worker)
            with self.mutex:
                self.pids = {key: value for key, value in self.pids.items() if value[0] != pid}
                self.pids[worker] = (pid, scope)
        except BaseException:
            self.errors += 1

    def _sample(self) -> None:
        while not self.stop.wait(0.01):
            try:
                with self.mutex:
                    pair = dict(self.pids)
                if set(pair) != {0, 1}:
                    continue
                scopes = self.evidence.save_scopes()
                rows = self.observer.execute(
                    text(
                        "SELECT :a = ANY(pg_blocking_pids(:b)), "
                        ":b = ANY(pg_blocking_pids(:a))"
                    ),
                    {"a": pair[0][0], "b": pair[1][0]},
                ).one()
                self.samples += 1
                with self.mutex:
                    same_backends = self.pids == pair
                final_save = (
                    set(scopes) == {0, 1}
                    and scopes == self.evidence.save_scopes()
                    and same_backends
                    and all(pair[worker][1] == scopes[worker] for worker in (0, 1))
                )
                observed = self.overlaps if final_save else self.incidental
                for waiter, blocking in ((1, rows[0]), (0, rows[1])):
                    if blocking and (1 - waiter, waiter) not in observed:
                        observed.add((1 - waiter, waiter))
                        self.evidence._record(
                            "database_blocking", winner=1 - waiter, waiter=waiter,
                            scope="final_save" if final_save else "incidental",
                        )
            except BaseException:
                self.errors += 1
                return

    def _cleanup(self) -> bool:
        stopped = False
        try:
            self.stop.set()
        except BaseException:
            self.errors += 1
        try:
            if self.thread is not None:
                self.thread.join(timeout=2)
        except BaseException:
            self.errors += 1
        try:
            stopped = self.thread is None or not self.thread.is_alive()
        except BaseException:
            self.errors += 1
        try:
            event.remove(self.engine, "before_cursor_execute", self._query_started)
            self.listener_removed = True
        except BaseException:
            self.errors += 1
        try:
            self.evidence._record(
                "blocking_observer_closed", stopped=stopped, samples=self.samples,
                errors=self.errors, overlaps=len(self.overlaps),
                incidental_overlaps=len(self.incidental), listener_removed=self.listener_removed,
            )
        except BaseException:
            self.errors += 1
        clean = stopped and self.listener_removed and self.errors == 0
        if not clean:
            self.evidence.observer_errors += 1
        return clean

    def __enter__(self) -> "PassiveBlockingObserver":
        # Caller connects/configures the observer before any request is launched.
        try:
            event.listen(self.engine, "before_cursor_execute", self._query_started)
            self.thread = Thread(target=self._sample, name="release-lock-observer", daemon=True)
            self.thread.start()
        except BaseException:
            self.errors += 1
            self._cleanup()
            raise
        return self

    def __exit__(self, kind: Any, error: Any, trace: Any) -> None:
        clean = self._cleanup()
        if kind is None:
            assert clean, "blocking evidence incomplete"


def assert_response_contract(
    scenario: Scenario,
    responses: tuple[Any, Any],
    scopes: tuple[tuple[int, str], tuple[int, str]],
) -> None:
    """HTTP contract only; SQL/receipt/export/financial assertions are still required."""
    statuses = [response.status_code for response in responses]
    if scenario.pattern == "different_keys":
        assert sorted(statuses) == [200, 409], "expected one success and one head conflict"
        loser = responses[statuses.index(409)]
        expected_conflict = loser.json() == {"detail": "generation input or version changed"}
        assert expected_conflict, "unexpected refusal is not a head conflict"
    else:
        assert statuses == [200, 200], "both requests must succeed"
    if scenario.pattern == "same_key":
        same_response = responses[0].json() == responses[1].json()
        assert same_response, "idempotent response differs"
    if scenario.pattern == "distinct_workspaces":
        assert scopes[0][0] != scopes[1][0], "distinct owned workspaces required"
    else:
        assert scopes[0] == scopes[1], "one plan and workspace required"
    for response, (workspace, plan) in zip(responses, scopes, strict=True):
        if response.status_code == 200:
            inputs = response.json()["document"]["inputs"]
            isolated = (inputs["workspace_id"], inputs["plan_id"]) == (workspace, plan)
            assert isolated, "response crossed plan/workspace boundary"
