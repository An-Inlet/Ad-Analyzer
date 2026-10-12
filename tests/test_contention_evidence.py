"""Verify diagnostic failure paths before the next application contention attempt."""

import json
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier
from typing import Any

import pytest
from app.planning_documents import authority, repository
from app.planning_documents.authority_diagnostics import PlanningDiagnosticRoute
from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.testclient import TestClient

from tests.contention_evidence import _WORKER, Evidence


def fact() -> authority.IdentityFact:
    return authority.IdentityFact(
        "PRIVATE-USER", "PRIVATE-ISSUER", "PRIVATE-SUBJECT", "PRIVATE-SESSION", 1, time.monotonic()
    )


@pytest.mark.parametrize("failure", ["first_request", "second_request", "assertion", "none"])
def test_both_asgi_outcomes_and_original_failure_are_persisted(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure: str,
) -> None:
    app = FastAPI()
    barrier = Barrier(2)
    sentinel = RuntimeError("PRIVATE-EXCEPTION")
    seen: list[int] = []
    original_fact = fact()

    def final(principal: Any, received: Any, **kwargs: Any) -> None:
        same_fact = received is original_fact
        assert same_fact, "fact substituted"
        seen.append(1)

    monkeypatch.setattr(authority, "final", final)

    @app.get("/{index}")
    def endpoint(index: int) -> dict[str, bool]:
        barrier.wait(timeout=5)
        vars(authority)["final"](None, original_fact, diagnostic_phase="pre_cas")
        if failure == ("first_request" if index == 0 else "second_request"):
            raise sentinel
        if index == 1:
            raise HTTPException(409, "planning_authority_expired")
        return {"PRIVATE-PAYLOAD": True}

    destination = tmp_path / "evidence.json"
    evidence = Evidence(destination)

    def run() -> None:
        with evidence, monkeypatch.context() as patch:
            evidence.install(patch)

            def request(index: int) -> None:
                try:
                    with evidence.worker(index), TestClient(app) as client:
                        response = client.get(f"/{index}")
                        evidence.response(index, response)
                finally:
                    assert _WORKER.get() is None, "client worker context was not reset"

            with ThreadPoolExecutor(max_workers=2) as pool:
                futures = [pool.submit(request, i) for i in (0, 1)]
                for future in futures:
                    future.result(timeout=10)
            if failure == "assertion":
                raise sentinel

    if failure == "none":
        run()
    else:
        with pytest.raises(RuntimeError) as error:
            run()
        original_exception = error.value is sentinel
        assert original_exception, "observer replaced original exception"
    raw = destination.read_text()
    data = json.loads(raw)
    assert "PRIVATE" not in raw
    assert data["body_failed"] is (failure != "none")
    assert [o["state"] for o in data["outcomes"]] == [
        "exception" if failure == "first_request" else "response",
        "exception" if failure == "second_request" else "response",
    ]
    assert seen == [1, 1]
    guards = [r for r in data["records"] if r["event"] == "guard_finish"]
    assert {g["worker"] for g in guards} == {0, 1}
    assert all(g["phase"] == "pre_cas" and g["age"] >= 0 and not g["raised"] for g in guards)
    assert data["workers_finished"] and data["sampler_stopped"] and data["observers_restored"]
    assert data["observer_errors"] == data["dropped"] == data["unbound_fact_samples"] == 0
    assert data["evidence_complete"]
    assert len(data["resources"]) >= 2
    assert vars(authority)["final"] is final
    with evidence.span("request"):
        pass
    assert evidence.records[-1]["worker"] is None  # Context is reset in the caller.


def test_original_dispatch_returns_and_guard_exception_are_preserved(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sentinel = HTTPException(409, "PRIVATE-ERROR")
    original_fact = fact()
    returned = object()
    calls: list[str] = []

    def refresh(*args: Any) -> Any:
        calls.append("refresh")
        return original_fact

    def lock(*args: Any, **kwargs: Any) -> Any:
        calls.append("lock")
        return returned

    def final(*args: Any, **kwargs: Any) -> None:
        calls.append("final")
        raise sentinel

    def save(*args: Any, **kwargs: Any) -> Any:
        calls.append("save")
        kwargs["recheck"]()
        return returned

    def recheck() -> None:
        calls.append("recheck")

    monkeypatch.setattr(authority, "refresh", refresh)
    monkeypatch.setattr(authority, "lock", lock)
    monkeypatch.setattr(authority, "final", final)
    monkeypatch.setattr(repository, "save_generation", save)
    for name in ("capture_retained_sources", "plan_version_storage_pair", "version"):

        def retained(*args: Any, _name: str = name, **kwargs: Any) -> Any:
            calls.append(_name)
            return returned

        monkeypatch.setattr(repository, name, retained)
    e = Evidence(tmp_path / "dispatch.json")
    with pytest.raises(HTTPException) as error, e, monkeypatch.context() as patch:
        e.install(patch)
        with e.worker(0):
            e.preparation_complete()
            refreshed = vars(authority)["refresh"](None, None)
            same = refreshed is original_fact
            assert same
            result = vars(authority)["lock"](None, None, 1, refreshed)
            same = result is returned
            assert same
            result = vars(repository)["save_generation"](None, fact=refreshed, recheck=recheck)
            same = result is returned
            assert same
            for name in ("capture_retained_sources", "plan_version_storage_pair", "version"):
                result = vars(repository)[name]()
                same = result is returned
                assert same
            vars(authority)["final"](None, refreshed, diagnostic_phase="post_flush")
    same = error.value is sentinel
    assert same
    assert calls == [
        "refresh",
        "lock",
        "save",
        "recheck",
        "capture_retained_sources",
        "plan_version_storage_pair",
        "version",
        "final",
    ]
    raw = (tmp_path / "dispatch.json").read_text()
    assert "PRIVATE" not in raw
    data = json.loads(raw)
    guards = [r for r in data["records"] if r["event"] == "guard_finish"]
    assert len(guards) == 1 and guards[0]["raised"] and guards[0]["final_fact"]
    assert data["outcomes"][1]["state"] == "not_started"


def test_persistence_failure_never_replaces_original_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    e = Evidence(tmp_path / "broken.json")
    sentinel = RuntimeError("PRIVATE-ORIGINAL")

    def broken(*args: Any) -> None:
        raise OSError("PRIVATE-WRITER")

    monkeypatch.setattr(e, "_persist", broken)
    with pytest.raises(RuntimeError) as error, e:
        raise sentinel
    same = error.value is sentinel
    assert same
    output = capsys.readouterr()
    assert output.err == "CONTENTION_EVIDENCE_WRITE_OR_CLEANUP_FAILED\n"
    assert e.sampler is not None and not e.sampler.is_alive()


def test_bounded_output_and_unknown_response_redaction(tmp_path: Path) -> None:
    e = Evidence(tmp_path / "bounded.json")
    app = FastAPI()

    @app.get("/")
    def endpoint() -> None:
        raise HTTPException(400, "PRIVATE-DETAIL")

    with (
        pytest.raises(AssertionError, match="incomplete evidence"),
        e,
        e.worker(0),
        TestClient(app) as client,
    ):
        e.response(0, client.get("/"))
        for _ in range(2050):
            with e.span("request"):
                pass
    raw = e.destination.read_text()
    data = json.loads(raw)
    assert "PRIVATE" not in raw
    assert len(data["records"]) == 4096 and data["dropped"] > 0
    assert data["outcomes"][0]["category"] == "other_error"
    assert not data["evidence_complete"] and not data["body_failed"]
    assert data["workers_finished"] and data["sampler_stopped"]


def test_actual_expiry_event_is_attributed_and_persisted(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from dataclasses import replace

    from tests.test_planning_authority_diagnostics import identity

    principal, original_fact = identity()
    original_fact = replace(original_fact, completed_monotonic=time.monotonic() - 6)
    e = Evidence(tmp_path / "expiry.json")
    with pytest.raises(HTTPException) as error, e, monkeypatch.context() as patch:
        e.install(patch)
        with e.worker(1):
            authority.final(principal, original_fact, diagnostic_phase="pre_cas")
    assert (error.value.status_code, error.value.detail) == (409, "planning_authority_expired")
    raw = e.destination.read_text()
    assert "PRIVATE" not in raw
    data = json.loads(raw)
    recorded = [r for r in data["records"] if r["event"] == "authority_expiry"]
    assert len(recorded) == 1 and recorded[0]["worker"] == 1
    assert recorded[0]["diagnostic"] == dict(
        event="planning_authority_expired",
        schema_version=1,
        route="unspecified",
        phase="pre_cas",
        cause="fact_age_outside_window",
        session_predicate="not_evaluated",
        status=409,
    )
    assert data["observers_restored"] and data["sampler_stopped"]


@pytest.mark.parametrize("target", ["_sample_fact", "_sample_clocks"])
def test_observation_failure_cannot_prevent_or_replace_original_call(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    target: str,
) -> None:
    e = Evidence(tmp_path / "sampling-failure.json")
    sentinel = HTTPException(409, "PRIVATE-ORIGINAL")
    calls: list[bool] = []

    def original(*args: Any, **kwargs: Any) -> None:
        calls.append(True)
        raise sentinel

    def broken(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("PRIVATE-OBSERVER")

    monkeypatch.setattr(authority, "final", original)
    monkeypatch.setattr(e, target, broken)
    with pytest.raises(HTTPException) as error, e, monkeypatch.context() as patch:
        e.install(patch)
        with e.worker(0):
            vars(authority)["final"](None, fact(), diagnostic_phase="pre_cas")
    same = error.value is sentinel
    assert same, "observer masked original exception"
    assert calls == [True]
    raw = e.destination.read_text()
    assert "PRIVATE" not in raw
    data = json.loads(raw)
    assert data["body_failed"] and not data["evidence_complete"]
    assert data["observer_errors"] > 0
    assert data["observers_restored"] and data["sampler_stopped"] and data["workers_finished"]


def test_actual_route_conflict_is_a_complete_fixed_event(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = FastAPI()
    router = APIRouter(route_class=PlanningDiagnosticRoute)

    @router.get("/")
    def generate_plan() -> None:
        raise HTTPException(409, "generation input or version changed")

    app.include_router(router)
    e = Evidence(tmp_path / "route-conflict.json")
    with e, monkeypatch.context() as patch:
        e.install(patch)
        with e.worker(1), TestClient(app) as client:
            response = client.get("/")
            e.response(1, response)
    data = json.loads(e.destination.read_text())
    assert data["evidence_complete"] and not data["body_failed"]
    assert data["outcomes"][1]["status"] == 409
    records = [r for r in data["records"] if r["event"] == "route_conflict"]
    assert len(records) == 1 and records[0]["worker"] == 1
    assert records[0]["diagnostic"] == dict(
        event="planning_route_conflict",
        schema_version=1,
        route="generate",
        reason="other_conflict",
        status=409,
    )
    assert not any(r["event"] == "authority_expiry" for r in data["records"])


@pytest.mark.parametrize("kind", ["expiry", "route_conflict"])
def test_native_event_extra_fields_are_rejected_without_payloads(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    kind: str,
) -> None:
    import logging

    data: dict[str, Any] = dict(schema_version=1, route="generate", status=409)
    if kind == "expiry":
        data.update(
            event="planning_authority_expired",
            phase="lock",
            cause="fact_age_outside_window",
            session_predicate="not_evaluated",
        )
    else:
        data.update(event="planning_route_conflict", reason="other_conflict")
    data["PRIVATE-PAYLOAD"] = "PRIVATE-VALUE"
    e = Evidence(tmp_path / "rejected-event.json")
    with (
        pytest.raises(AssertionError, match="incomplete evidence"),
        e,
        monkeypatch.context() as patch,
    ):
        e.install(patch)
        with e.worker(0):
            logging.getLogger("inlet.planning.authority").warning(json.dumps(data))
    raw = e.destination.read_text()
    assert "PRIVATE" not in raw
    result = json.loads(raw)
    assert result["observer_errors"] == 1 and not result["evidence_complete"]
    assert not any(r["event"] in {"route_conflict", "authority_expiry"} for r in result["records"])
