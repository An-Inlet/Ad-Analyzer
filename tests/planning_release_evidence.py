"""Opt-in release evidence from setup through teardown, without payload retention."""

import functools
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from hashlib import sha256
from pathlib import Path
from typing import Any

import pytest
from app.planning_documents import service as service_module
from fastapi.testclient import TestClient

from tests.contention_evidence import _WORKER, Evidence

_KEY: pytest.StashKey["ReleaseEvidence"] = pytest.StashKey()
_CURRENT: ContextVar["ReleaseEvidence | None"] = ContextVar("release_evidence", default=None)


class ReleaseEvidence(Evidence):
    """Fixed stage, client-arrival and pre-delay observations plus original guards."""

    def __init__(self, destination: Path) -> None:
        super().__init__(destination)
        self.active_saves: dict[int, tuple[int, int]] = {}
        self.save_sequence = 0

    def __enter__(self) -> "ReleaseEvidence":
        super().__enter__()
        return self

    case_phase = "setup"
    failed_report = False

    def __exit__(self, kind: Any, error: Any, trace: Any) -> None:
        super().__exit__(RuntimeError if self.failed_report else kind, error, trace)

    def _persist(self, failed: bool) -> None:
        super()._persist(failed or self.failed_report)

    def _record(self, event: str, **values: Any) -> None:
        worker = _WORKER.get()
        try:
            if worker in (0, 1) and values.get("phase") == "save":
                assert worker is not None
                with self.mutex:
                    if event == "start" and values.get("final_fact") is True:
                        self.save_sequence += 1
                        self.active_saves[worker] = (self.save_sequence, values["fact"])
                    elif event == "finish":
                        self.active_saves.pop(worker, None)
        except BaseException:
            self.observer_errors += 1
        super()._record(event, case_phase=self.case_phase, **values)

    def save_scopes(self) -> dict[int, tuple[int, int]]:
        with self.mutex:
            return dict(self.active_saves)

    @contextmanager
    def stage(self, name: str) -> Iterator[None]:
        assert name in {"setup", "call", "teardown", "client_ready", "client_arrival"}
        self._record("stage_start", stage=name)
        try:
            yield
        finally:
            self._record("stage_finish", stage=name, raised=sys.exception() is not None)

    def before_delay(self, fact: Any, phase: str, seconds: float) -> None:
        assert phase in {"pre_cas", "post_flush", "lock"}
        assert seconds == 6
        self._record("intentional_delay_start", phase=phase, seconds=seconds, **self._fact(fact))

    def install(self, patch: pytest.MonkeyPatch) -> None:
        super().install(patch)
        original = service_module.PlanningDocumentService.generate

        def generation(*args: Any, **kwargs: Any) -> Any:
            worker = _WORKER.get()
            assert worker is not None
            self.prepared.discard(worker)
            self.final_facts.pop(worker, None)
            self._record("generation_start")
            try:
                return original(*args, **kwargs)
            finally:
                self._record("generation_finish", raised=sys.exception() is not None)

        @functools.wraps(original)
        def generate(*args: Any, **kwargs: Any) -> Any:
            if _WORKER.get() in (0, 1):
                return generation(*args, **kwargs)
            with self.worker(0):
                return generation(*args, **kwargs)

        self.originals.append((service_module.PlanningDocumentService, "generate", original))
        patch.setattr(service_module.PlanningDocumentService, "generate", generate)
        prepare = vars(service_module)["prepare_generation_checks"]

        @functools.wraps(prepare)
        def preparing(*args: Any, **kwargs: Any) -> Any:
            with self.span("prepare"):
                result = prepare(*args, **kwargs)
            if _WORKER.get() in (0, 1):
                self.preparation_complete()
            return result

        self.originals.append((service_module, "prepare_generation_checks", prepare))
        patch.setattr(service_module, "prepare_generation_checks", preparing)
        original_request = TestClient.request

        @functools.wraps(original_request)
        def request(client: Any, method: Any, url: Any, **kwargs: Any) -> Any:
            category = "generate" if str(url).split("?", 1)[0].endswith("/generate") else "other"
            self._record("http_start", route=category)
            try:
                response = original_request(client, method, url, **kwargs)
                self._record("http_finish", route=category, status=response.status_code)
                return response
            except BaseException:
                self._record("http_exception", route=category)
                raise

        self.originals.append((TestClient, "request", original_request))
        patch.setattr(TestClient, "request", request)


def pytest_addoption(parser: Any) -> None:
    parser.addoption("--planning-release-evidence-dir", default=None)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_protocol(item: Any, nextitem: Any) -> Any:
    directory = item.config.getoption("--planning-release-evidence-dir")
    if directory is None:
        yield
        return
    root = Path(directory)
    root.mkdir(parents=True, exist_ok=True)
    destination = root / (sha256(item.nodeid.encode()).hexdigest() + ".json")
    with ReleaseEvidence(destination) as evidence, pytest.MonkeyPatch.context() as patch:
        item.stash[_KEY] = evidence
        evidence.install(patch)
        token = _CURRENT.set(evidence)
        try:
            yield
        finally:
            _CURRENT.reset(token)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item: Any, call: Any) -> Any:
    outcome = yield
    report = outcome.get_result()
    if _KEY in item.stash:
        evidence = item.stash[_KEY]
        evidence.failed_report |= report.failed
        evidence._record("pytest_report", stage=report.when, outcome=report.outcome)
        evidence.case_phase = {"setup": "call", "call": "teardown", "teardown": "teardown"}[
            report.when
        ]


def record_intentional_delay(fact: Any, phase: str, seconds: float) -> None:
    evidence = _CURRENT.get()
    if evidence is not None:
        evidence.before_delay(fact, phase, seconds)
