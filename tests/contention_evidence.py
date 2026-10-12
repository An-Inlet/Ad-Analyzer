"""Bounded test-only observations; never authority, payloads or exception text."""

import json
import logging
import math
import os
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from threading import Event, Lock, Thread
from typing import Any

import pytest
from app.planning_documents import authority, repository

_WORKER: ContextVar[int | None] = ContextVar("contention_worker", default=None)
PHASES = frozenset(
    {
        "request",
        "prepare",
        "prepare_peer_wait",
        "prepare_winner_wait",
        "refresh",
        "save",
        "save_setup",
        "source_recheck",
        "retained",
        "storage",
        "version_read",
        "lock",
        "coordinator",
        "loser_attempt_wait",
        "observer_create",
        "observer_connect",
        "observer_query",
        "observer_disconnect",
        "observer_dispose",
    }
)
GUARDS = frozenset({"lock", "replay", "pre_cas", "post_flush", "unspecified"})
DETAILS = frozenset(
    {
        "planning_authority_expired",
        "generation input or version changed",
        "customer authentication required",
    }
)


def resource_sample() -> dict[str, Any]:
    result: dict[str, Any] = {"scope": "shared_cgroup"}
    for name, allowed in (
        (
            "cpu.stat",
            {
                "usage_usec",
                "user_usec",
                "system_usec",
                "nr_periods",
                "nr_throttled",
                "throttled_usec",
            },
        ),
        ("memory.events", {"low", "high", "max", "oom", "oom_kill", "oom_group_kill"}),
    ):
        try:
            with (Path("/sys/fs/cgroup") / name).open() as source:
                contents = source.read(8193)
            if len(contents) > 8192:
                raise ValueError("bounded counters required")
            values = {}
            for line in contents.splitlines():
                key, value = line.split()
                if key in allowed:
                    if not value.isascii() or not value.isdigit() or len(value) > 20:
                        raise ValueError("numeric counter required")
                    values[key] = int(value)
            result[name] = values
        except Exception:
            result[name] = None
    for name in ("memory.current", "memory.max"):
        try:
            with (Path("/sys/fs/cgroup") / name).open() as source:
                value = source.read(32).strip()
            result[name] = int(value) if value.isascii() and value.isdigit() else None
        except Exception:
            result[name] = None
    return result


class Evidence:
    """Original calls run once; fixed observations are persisted after all workers."""

    def __init__(self, destination: Path) -> None:
        self.destination = destination
        self.started = time.monotonic()
        self.records: list[dict[str, Any]] = []
        self.resources: list[dict[str, Any]] = []
        self.outcomes = [
            dict(worker=i, state="not_started", status=None, category=None) for i in (0, 1)
        ]
        self.mutex = Lock()
        self.stop = Event()
        self.sampler: Thread | None = None
        self.dropped = 0
        self.observer_errors = 0
        self.unbound = 0
        self.active_workers = 0
        self.facts: dict[int, list[object]] = {0: [], 1: []}
        self.final_facts: dict[int, object] = {}
        self.prepared: set[int] = set()
        self.originals: list[tuple[Any, str, Any]] = []
        self.handler: logging.Handler | None = None

    def _record(self, event: str, **values: Any) -> None:
        try:
            with self.mutex:
                if len(self.records) < 4096:
                    self.records.append(
                        dict(
                            event=event,
                            at=time.monotonic() - self.started,
                            worker=_WORKER.get(),
                            **values,
                        )
                    )
                else:
                    self.dropped += 1
        except BaseException:
            self.observer_errors += 1

    def _resources(self) -> None:
        try:
            before = time.monotonic()
            sample = resource_sample()
            after = time.monotonic()
            with self.mutex:
                if len(self.resources) < 512:
                    self.resources.append(
                        dict(at=before - self.started, sampling_seconds=after - before, **sample)
                    )
                else:
                    self.dropped += 1
        except BaseException:
            self.observer_errors += 1

    def _sampling(self) -> None:
        while not self.stop.wait(0.25):
            self._resources()

    def _fact(self, fact: Any) -> dict[str, Any]:
        try:
            return self._sample_fact(fact)
        except BaseException:
            self.observer_errors += 1
            return dict(fact=None, final_fact=False, age=None)

    def _sample_clocks(self) -> tuple[float, float]:
        return time.monotonic(), time.thread_time()

    def _clocks(self) -> tuple[float | None, float | None]:
        try:
            return self._sample_clocks()
        except BaseException:
            self.observer_errors += 1
            return None, None

    def _sample_fact(self, fact: Any) -> dict[str, Any]:
        worker = _WORKER.get()
        if worker not in (0, 1):
            self.unbound += 1
            return dict(fact=None, final_fact=False, age=None)
        assert worker is not None
        facts = self.facts[worker]
        index = next((i for i, item in enumerate(facts) if item is fact), None)
        if index is None:
            if len(facts) >= 64:
                self.dropped += 1
            else:
                index = len(facts)
                facts.append(fact)
        completed = fact.completed_monotonic if type(fact) is authority.IdentityFact else None
        if completed is None or type(completed) not in (int, float):
            self.observer_errors += 1
            age = None
        else:
            elapsed = time.monotonic() - completed
            age = elapsed if math.isfinite(elapsed) else None
        return dict(fact=index, final_fact=self.final_facts.get(worker) is fact, age=age)

    @contextmanager
    def span(self, phase: str, fact: Any = None) -> Iterator[None]:
        assert phase in PHASES
        before, cpu = self._clocks()
        self._record("start", phase=phase, **(self._fact(fact) if fact is not None else {}))
        try:
            yield
        finally:
            after, cpu_after = self._clocks()
            self._record(
                "finish",
                phase=phase,
                seconds=after - before if after is not None and before is not None else None,
                thread_cpu_seconds=(
                    cpu_after - cpu if cpu_after is not None and cpu is not None else None
                ),
                raised=sys.exception() is not None,
                **(self._fact(fact) if fact is not None else {}),
            )

    @contextmanager
    def worker(self, index: int) -> Iterator[None]:
        assert type(index) is int and index in (0, 1)
        token = _WORKER.set(index)
        with self.mutex:
            self.active_workers += 1
            self.outcomes[index]["state"] = "running"
        try:
            with self.span("request"):
                yield
        finally:
            with self.mutex:
                if self.outcomes[index]["state"] == "running":
                    self.outcomes[index]["state"] = (
                        "exception" if sys.exception() else "no_response"
                    )
                self.active_workers -= 1
            _WORKER.reset(token)

    def response(self, index: int, response: Any) -> None:
        category = "other_error"
        status = response.status_code
        assert type(status) is int and 100 <= status <= 599
        if status == 200:
            category = "success"
        else:
            try:
                body = response.json()
                detail = body.get("detail") if type(body) is dict else None
                if type(detail) is str and detail in DETAILS:
                    category = detail
            except Exception:
                pass
        with self.mutex:
            self.outcomes[index].update(state="response", status=status, category=category)
        self._record("response", status=status, category=category)

    def database_blocking(self) -> None:
        self._record("database_blocking", winner=0, waiter=1)

    def preparation_complete(self) -> None:
        worker = _WORKER.get()
        assert worker in (0, 1), "request context missing at preparation"
        assert worker is not None
        self.prepared.add(worker)

    def install(self, patch: pytest.MonkeyPatch) -> None:
        def replace(module: Any, name: str, replacement: Any) -> Any:
            original = getattr(module, name)
            self.originals.append((module, name, original))
            patch.setattr(module, name, replacement)
            return original

        original_refresh = authority.refresh

        def refresh(*args: Any, **kwargs: Any) -> Any:
            if _WORKER.get() not in (0, 1):
                return original_refresh(*args, **kwargs)
            with self.span("refresh"):
                fact = original_refresh(*args, **kwargs)
            worker = _WORKER.get()
            if worker in self.prepared:
                assert worker is not None
                self.final_facts[worker] = fact
            self._record("refreshed", **self._fact(fact))
            return fact

        replace(authority, "refresh", refresh)
        original_final = authority.final

        def final(principal: Any, fact: Any, **kwargs: Any) -> None:
            if _WORKER.get() not in (0, 1):
                return original_final(principal, fact, **kwargs)
            phase = kwargs.get("diagnostic_phase", "unspecified")
            phase = phase if type(phase) is str and phase in GUARDS else "unspecified"
            self._record("guard_start", phase=phase, **self._fact(fact))
            try:
                original_final(principal, fact, **kwargs)
            finally:
                self._record(
                    "guard_finish",
                    phase=phase,
                    raised=sys.exception() is not None,
                    **self._fact(fact),
                )

        replace(authority, "final", final)
        original_lock = authority.lock

        def locked(db: Any, principal: Any, workspace_id: Any, fact: Any, **kwargs: Any) -> Any:
            if _WORKER.get() not in (0, 1):
                return original_lock(db, principal, workspace_id, fact, **kwargs)
            with self.span("lock", fact):
                return original_lock(db, principal, workspace_id, fact, **kwargs)

        replace(authority, "lock", locked)
        original_save = repository.save_generation

        def save(db: Any, **kwargs: Any) -> Any:
            if _WORKER.get() not in (0, 1):
                return original_save(db, **kwargs)
            original_recheck = kwargs["recheck"]

            def recheck(*args: Any, **inner: Any) -> Any:
                with self.span("source_recheck", kwargs["fact"]):
                    return original_recheck(*args, **inner)

            kwargs["recheck"] = recheck
            with self.span("save", kwargs["fact"]):
                return original_save(db, **kwargs)

        replace(repository, "save_generation", save)
        for name, phase in (
            ("capture_retained_sources", "retained"),
            ("plan_version_storage_pair", "storage"),
            ("version", "version_read"),
        ):
            original = getattr(repository, name)

            def observed(
                *args: Any, _phase: str = phase, _original: Any = original, **kwargs: Any
            ) -> Any:
                if _WORKER.get() not in (0, 1):
                    return _original(*args, **kwargs)
                with self.span(_phase):
                    return _original(*args, **kwargs)

            replace(repository, name, observed)

        evidence = self

        class FixedExpiry(logging.Handler):
            def emit(self, record: logging.LogRecord) -> None:
                try:
                    message = record.getMessage()
                    if len(message) > 1024:
                        raise ValueError("bounded event required")
                    data = json.loads(message)
                    allowed: dict[str, set[Any] | frozenset[str]] = dict(
                        event={"planning_authority_expired"},
                        schema_version={1},
                        route={"generate", "current", "history", "version", "unspecified"},
                        phase=GUARDS,
                        cause={"fact_age_outside_window", "session_expired"},
                        session_predicate={"not_evaluated", "expired"},
                        status={409},
                    )
                    recorded_event = "authority_expiry"
                    if type(data) is dict and data.get("event") == "planning_route_conflict":
                        allowed = dict(
                            event={"planning_route_conflict"},
                            schema_version={1},
                            route={"generate", "current", "history", "version", "unspecified"},
                            reason={"other_conflict"},
                            status={409},
                        )
                        recorded_event = "route_conflict"
                    if type(data) is not dict or data.keys() != allowed.keys():
                        raise ValueError("fixed fields required")
                    for key, choices in allowed.items():
                        kind = int if key in {"schema_version", "status"} else str
                        if type(data[key]) is not kind or data[key] not in choices:
                            raise ValueError("fixed value required")
                    evidence._record(recorded_event, diagnostic=data)
                except BaseException:
                    evidence.observer_errors += 1

        self.handler = FixedExpiry()
        logging.getLogger("inlet.planning.authority").addHandler(self.handler)

    def _persist(self, failed: bool) -> None:
        restored = all(getattr(module, name) is value for module, name, value in self.originals)
        data = dict(
            schema_version=1,
            body_failed=failed,
            evidence_complete=(
                self.active_workers == 0
                and (self.sampler is None or not self.sampler.is_alive())
                and restored
                and self.observer_errors == self.unbound == self.dropped == 0
            ),
            outcomes=self.outcomes,
            records=self.records,
            resources=self.resources,
            dropped=self.dropped,
            observer_errors=self.observer_errors,
            unbound_fact_samples=self.unbound,
            workers_finished=self.active_workers == 0,
            sampler_stopped=self.sampler is None or not self.sampler.is_alive(),
            observers_restored=restored,
        )
        with self.destination.open("x") as target:
            json.dump(data, target, indent=2, allow_nan=False)
            target.write("\n")
            target.flush()
            os.fsync(target.fileno())

    def __enter__(self) -> "Evidence":
        self._resources()
        self.sampler = Thread(
            target=self._sampling, name="contention-resource-sampler", daemon=True
        )
        self.sampler.start()
        return self

    def __exit__(self, kind: Any, error: Any, trace: Any) -> None:
        try:
            self.stop.set()
            if self.sampler is not None:
                self.sampler.join(timeout=2)
            self._resources()
            if self.handler is not None:
                logging.getLogger("inlet.planning.authority").removeHandler(self.handler)
                self.handler.close()
            self._persist(kind is not None)
            if kind is None:
                assert self.active_workers == 0, "evidence persisted before workers finished"
                assert self.sampler is not None and not self.sampler.is_alive(), (
                    "sampler not stopped"
                )
                assert self.observer_errors == self.unbound == self.dropped == 0, (
                    "incomplete evidence"
                )
                assert all(getattr(m, n) is v for m, n, v in self.originals), (
                    "observers not restored"
                )
        except BaseException:
            if kind is None:
                raise
            # Never replace the original request/assertion failure with an observer failure.
            print("CONTENTION_EVIDENCE_WRITE_OR_CLEANUP_FAILED", file=sys.stderr)
