"""Diagnostic-only replay of one failed concurrency case; no acceptance credit."""

import inspect
import json
import sys
import time
from pathlib import Path
from threading import Event as OriginalEvent
from threading import Lock, get_ident
from typing import Any

import pytest
from app.planning_documents import authority, owner_review_generation, repository
from app.planning_documents.documents import PlanVersion
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from tests import test_prepared_generation_concurrency as original_case
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_owner_runtime_composition import actual_owner as actual_owner
from tests.test_shopify_sales import configuration as configuration


def test_diagnostic_prepared_same_key(
    actual_owner: Any,
    customer_engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    records: list[tuple[int, dict[str, Any]]] = []
    workers: dict[int, int] = {}
    first_locks: set[int] = set()
    post_workers: dict[int, int] = {}
    dropped = 0
    event_count = 0
    record_lock = Lock()
    original_final, original_save, original_lock = (
        authority.final,
        repository.save_generation,
        authority.lock,
    )
    original_post = TestClient.post
    original_validation = inspect.getattr_static(PlanVersion, "model_validate")
    assert type(original_validation) is classmethod
    original_linked = vars(owner_review_generation)["_linked"]
    active: dict[int, tuple[int, authority.IdentityFact]] = {}
    age_samples: dict[tuple[int, str], dict[str, Any]] = {}
    pure_samples: dict[tuple[int, str], dict[str, Any]] = {}
    foreign_fact_samples = 0

    def resources() -> dict[str, Any]:
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
                content = (Path("/sys/fs/cgroup") / name).read_text()
                if len(content) > 8192:
                    raise ValueError("bounded numeric counters required")
                values = {}
                for line in content.splitlines():
                    key, value = line.split()
                    if key in allowed:
                        if not value.isascii() or not value.isdigit() or len(value) > 20:
                            raise ValueError("numeric resource counter required")
                        values[key] = int(value)
                result[name] = {"available": True, "values": values}
            except Exception:
                result[name] = {"available": False}
        return result

    before_resources = resources()

    def record(values: dict[str, Any]) -> None:
        nonlocal dropped
        with record_lock:
            if len(records) < 64:
                records.append((get_ident(), values))
            else:
                dropped += 1

    def timed(name: str, operation: Any, *args: Any, **kwargs: Any) -> Any:
        wall, cpu = time.monotonic(), time.thread_time()
        try:
            return operation(*args, **kwargs)
        finally:
            record(
                dict(
                    event=name,
                    wall_seconds=time.monotonic() - wall,
                    thread_cpu_seconds=time.thread_time() - cpu,
                    raised=sys.exception() is not None,
                )
            )

    class ObservedEvent(OriginalEvent):
        def __init__(self) -> None:
            nonlocal event_count
            super().__init__()
            labels = (
                "first_prepared",
                "both_prepared",
                "first_locked",
                "first_finished",
                "loser_attempt",
            )
            assert event_count < len(labels)
            self.label = labels[event_count]
            event_count += 1

        def wait(self, timeout: float | None = None) -> bool:
            result = timed("wait_" + self.label, super().wait, timeout)
            assert type(result) is bool
            return result

    def final(principal: Any, fact: Any, **kwargs: Any) -> None:
        nonlocal foreign_fact_samples
        scope = active.get(get_ident())
        if scope is None:
            return original_final(principal, fact, **kwargs)
        if fact is not scope[1]:
            foreign_fact_samples += 1
            return original_final(principal, fact, **kwargs)
        before = time.monotonic() - fact.completed_monotonic
        phase = kwargs.get("diagnostic_phase", "unspecified")
        if type(phase) is not str or phase not in {
            "unspecified",
            "lock",
            "pre_cas",
            "post_flush",
            "replay",
        }:
            phase = "other"
        try:
            original_final(principal, fact, **kwargs)
        except BaseException:
            record(
                dict(
                    event="authority_failure",
                    phase=phase,
                    age_before_seconds=before,
                    age_after_seconds=time.monotonic() - fact.completed_monotonic,
                )
            )
            raise
        finally:
            after = time.monotonic() - fact.completed_monotonic
            value = age_samples.setdefault(
                (scope[0], phase),
                dict(
                    count=0,
                    min_before=before,
                    max_before=before,
                    max_after=after,
                    failures=0,
                ),
            )
            value["count"] += 1
            value["min_before"] = min(value["min_before"], before)
            value["max_before"] = max(value["max_before"], before)
            value["max_after"] = max(value["max_after"], after)
            value["failures"] += int(sys.exception() is not None)

    def pure(name: str, operation: Any, *args: Any, **kwargs: Any) -> Any:
        scope = active.get(get_ident())
        if scope is None:
            return operation(*args, **kwargs)
        wall, cpu = time.monotonic(), time.thread_time()
        try:
            return operation(*args, **kwargs)
        finally:
            value = pure_samples.setdefault(
                (scope[0], name),
                dict(count=0, wall_seconds=0.0, thread_cpu_seconds=0.0, failures=0),
            )
            value["count"] += 1
            value["wall_seconds"] += time.monotonic() - wall
            value["thread_cpu_seconds"] += time.thread_time() - cpu
            value["failures"] += int(sys.exception() is not None)

    def validate(cls: Any, *args: Any, **kwargs: Any) -> Any:
        operation = original_validation.__get__(None, cls)
        return pure("PlanVersion.model_validate", operation, *args, **kwargs)

    def linked(*args: Any, **kwargs: Any) -> Any:
        return pure("owner_linked", original_linked, *args, **kwargs)

    def saving(db: Any, **kwargs: Any) -> Any:
        index = db.info["prepared_race_index"]
        assert index in (0, 1)
        workers[get_ident()] = index
        original_recheck = kwargs["recheck"]

        def recheck(*args: Any, **inner: Any) -> Any:
            return timed("source_recheck", original_recheck, *args, **inner)

        kwargs["recheck"] = recheck
        active[get_ident()] = (index, kwargs["fact"])
        try:
            return timed("save", original_save, db, **kwargs)
        finally:
            active.pop(get_ident(), None)

    def locked(db: Any, *args: Any, **kwargs: Any) -> Any:
        index = db.info.get("prepared_race_index")
        if index in (0, 1) and index not in first_locks:
            first_locks.add(index)
            return timed("first_lock", original_lock, db, *args, **kwargs)
        return original_lock(db, *args, **kwargs)

    def post(client: Any, url: Any, **kwargs: Any) -> Any:
        if not str(url).endswith("/generate"):
            return original_post(client, url, **kwargs)
        post_workers[get_ident()] = len(post_workers)
        response = original_post(client, url, **kwargs)
        category = "success" if response.status_code == 200 else "other_error"
        if response.status_code != 200:
            try:
                body = response.json()
                detail = body.get("detail") if type(body) is dict else None
                if type(body) is not dict or type(detail) is not str:
                    category = "observer_error"
                elif detail in {
                    "planning_authority_expired",
                    "generation input or version changed",
                }:
                    category = detail
            except Exception:
                category = "observer_error"
        record(dict(event="response", status=response.status_code, category=category))
        return response

    def inclusive(name: str, operation: Any) -> Any:
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            return timed(name, operation, *args, **kwargs)

        return wrapper

    try:
        with monkeypatch.context() as patch:
            patch.setattr(original_case, "Event", ObservedEvent)
            patch.setattr(authority, "final", final)
            patch.setattr(authority, "lock", locked)
            patch.setattr(repository, "save_generation", saving)
            patch.setattr(TestClient, "post", post)
            patch.setattr(PlanVersion, "model_validate", classmethod(validate))
            patch.setattr(owner_review_generation, "_linked", linked)
            for name in ("capture_retained_sources", "plan_version_storage_pair"):
                patch.setattr(repository, name, inclusive(name, vars(repository)[name]))
            original_case.test_prepared_generation_receipt_and_head_fence(
                actual_owner, customer_engine, patch, True, tmp_path
            )
    finally:
        active_error = sys.exception()
        try:
            events: list[dict[str, Any]] = []
            invalid_events = 0
            allowed: dict[str, set[Any]] = dict(
                event={"planning_authority_expired"},
                schema_version={1},
                route={"generate", "current", "history", "version", "unspecified"},
                phase={"lock", "replay", "pre_cas", "post_flush", "unspecified"},
                cause={"fact_age_outside_window", "session_expired"},
                session_predicate={"not_evaluated", "expired"},
                status={409},
            )
            entries = caplog.records
            for entry in entries[:256]:
                if entry.name != "inlet.planning.authority":
                    continue
                try:
                    message = entry.getMessage()
                    if type(message) is not str or len(message) > 1024:
                        raise ValueError("bounded authority event required")
                    value = json.loads(message)
                    if type(value) is not dict or value.keys() != allowed.keys():
                        raise ValueError("fixed authority event required")
                    for key, choices in allowed.items():
                        kind = int if key in {"schema_version", "status"} else str
                        if type(value[key]) is not kind or value[key] not in choices:
                            raise ValueError("fixed authority value required")
                    events.append(value)
                except Exception:
                    invalid_events += 1
            payload = dict(
                diagnostic_only=True,
                resources_before=before_resources,
                resources_after=resources(),
                authority_age_samples=[
                    dict(worker=worker, phase=phase, **value)
                    for (worker, phase), value in sorted(age_samples.items())
                ],
                pure_validation_samples=[
                    dict(worker=worker, operation=name, **value)
                    for (worker, name), value in sorted(pure_samples.items())
                ],
                foreign_fact_samples=foreign_fact_samples,
                active_scopes_closed=not active,
                records=[
                    dict(worker=workers.get(thread, post_workers.get(thread)), **values)
                    for thread, values in records
                ],
                authority_events=events,
                invalid_authority_events=invalid_events,
                authority_logs_truncated=len(entries) > 256,
                dropped_records=dropped,
                observer_restored=(
                    authority.final is original_final
                    and authority.lock is original_lock
                    and repository.save_generation is original_save
                    and TestClient.post is original_post
                    and inspect.getattr_static(PlanVersion, "model_validate") is original_validation
                    and vars(owner_review_generation)["_linked"] is original_linked
                ),
            )
            (tmp_path / "prepared-concurrency-diagnostic.json").write_text(
                json.dumps(payload, indent=2) + "\n"
            )
        except BaseException:
            if active_error is None:
                raise
