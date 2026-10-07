"""Deterministic reproduction of hosted Chrome's empty initial target response."""

import time
from typing import Any
from urllib.error import URLError

import pytest

from tests import browser_targets as discovery


def test_initial_empty_and_incomplete_targets_wait_for_page(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    page = {
        "id": "ready",
        "type": "page",
        "webSocketDebuggerUrl": "ws://127.0.0.1/devtools/page/ready",
    }
    replies: list[list[dict[str, Any]]] = [
        [],
        [{"type": "service_worker", "webSocketDebuggerUrl": "worker"}],
        [{"type": "page", "id": "ready"}],
        [page],
    ]
    # This is the exact hosted failure before the fix: server exists, no page yet.
    with pytest.raises(IndexError):
        replies[0][0]
    sleeps: list[float] = []
    monkeypatch.setattr(time, "sleep", sleeps.append)
    assert discovery.wait_for_page_target(lambda: replies.pop(0)) == page["webSocketDebuggerUrl"]
    assert sleeps == [0.03] * 3 and replies == []


def test_target_id_and_transient_connection_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = 0

    def targets() -> list[dict[str, Any]]:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise URLError("not ready")
        return [
            {"type": "page", "id": "old", "webSocketDebuggerUrl": "old"},
            {"type": "page", "id": "new", "webSocketDebuggerUrl": "new"},
        ]

    monkeypatch.setattr(time, "sleep", lambda _: None)
    assert discovery.wait_for_page_target(targets, target_id="new") == "new"
    assert calls == 2


def test_no_target_fails_with_bounded_readiness_diagnostic(monkeypatch: pytest.MonkeyPatch) -> None:
    clock = iter([0.0, 0.0, 0.5, 1.1])
    monkeypatch.setattr(time, "monotonic", lambda: next(clock))
    monkeypatch.setattr(time, "sleep", lambda _: None)
    with pytest.raises(AssertionError, match="ready page target before the deadline"):
        discovery.wait_for_page_target(lambda: [], timeout=1)
