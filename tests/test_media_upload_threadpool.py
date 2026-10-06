"""Upload body receipt stays async; authorization and persistence run serially off-loop."""

import asyncio
import threading
from types import SimpleNamespace
from typing import Any

import pytest
from app.api import customer_campaign_review as api
from app.campaign_review import service
from fastapi import Request, Response


def test_upload_worker_keeps_event_loop_responsive(monkeypatch: pytest.MonkeyPatch) -> None:
    loop_thread = threading.get_ident()
    entered, release = threading.Event(), threading.Event()
    events: list[tuple[str, int]] = []
    db, provider, store = object(), object(), object()
    principal: Any = SimpleNamespace(user=SimpleNamespace(id="synthetic-owner"))

    def guard(actual_db: Any, actual_principal: Any, wid: int, actual_provider: Any) -> None:
        assert (actual_db, actual_principal, wid, actual_provider) == (db, principal, 12, provider)
        assert threading.get_ident() != loop_thread
        events.append(("guard", threading.get_ident()))

    class Row:
        sha256, mime, width, height, size = "a" * 64, "video/mp4", 64, 64, 9

        @property
        def id(self) -> str:
            events.append(("serialize", threading.get_ident()))
            return "synthetic-media"

    def persist(*args: Any) -> Row:
        assert args[:5] == (db, 12, "synthetic-owner", b"synthetic", store)
        assert threading.get_ident() != loop_thread
        events.append(("persist", threading.get_ident()))
        entered.set()
        assert release.wait(2), "event loop did not advance while decoder/storage was blocked"
        return Row()

    monkeypatch.setattr(api, "access", lambda *args: None)
    monkeypatch.setattr(api, "lock_customer_mutation", guard)
    monkeypatch.setattr(service, "upload", persist)

    async def run() -> None:
        async def receive() -> dict[str, Any]:
            return {"type": "http.request", "body": b"synthetic", "more_body": False}

        request = Request({"type": "http"}, receive)
        # Only service dependencies are stand-ins; the actual async route and
        # Starlette worker boundary execute, including response serialization.
        dependencies: Any = (12, request, principal, provider, db, store, Response())
        task = asyncio.create_task(api.upload(*dependencies))
        try:
            for _ in range(100):
                if entered.is_set():
                    break
                await asyncio.sleep(0.01)
            assert entered.is_set()
            assert not task.done()
            release.set()
            result = await asyncio.wait_for(task, 3)
            assert result["media_id"] == "synthetic-media"
        finally:
            release.set()
            if not task.done():
                await task

    asyncio.run(run())
    assert [name for name, _ in events] == ["guard", "persist", "serialize"]
    assert len({thread for _, thread in events}) == 1
    assert events[0][1] != loop_thread
