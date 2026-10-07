"""Actual portal/TLS/API/database progress, no browser fetch or service substitution."""

import asyncio
import json
import socket
import subprocess
import threading
import time
from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest
import uvicorn
from app.commerce.models import CommerceSnapshot, CommerceStore
from app.customers.identity import get_identity_provider
from app.database.session import Base, get_db
from app.main import app
from app.settings import Settings, settings
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, event, func, select
from sqlalchemy.orm import Session, sessionmaker
from starlette.responses import JSONResponse, Response
from starlette.types import Message, Receive, Scope, Send

from tests.goal_progress_fixture import ready
from tests.test_customer_browser_api_journey import localhost_certificate
from tests.test_customer_identity import ORIGIN, FakeProvider
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_portal import portal_executable
from tests.test_shopify_sales import configuration as configuration


def test_actual_goal_progress_portal(
    customer_engine: Engine, configuration: Settings, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = customer_engine
    if engine.dialect.name == "sqlite":
        engine = create_engine(f"sqlite:///{tmp_path / 'progress.sqlite'}",
                               connect_args={"check_same_thread": False, "timeout": 10})
        event.listen(
            engine, "connect",
            lambda connection, _: connection.execute("PRAGMA foreign_keys=ON"),
        )
        Base.metadata.create_all(engine)
    factory = sessionmaker(engine)
    provider = FakeProvider()

    def database() -> Generator[Session, None, None]:
        with factory() as db:
            yield db

    monkeypatch.setattr(app, "dependency_overrides", {
        get_db: database, get_identity_provider: lambda: provider,
    })
    monkeypatch.setattr(settings, "customer_app_origin", ORIGIN)
    client = TestClient(app, base_url=ORIGIN)
    _, _, _, _, _, store_id, _, now = ready(engine, configuration, (client, client, provider))
    with Session(engine) as db:
        snapshots = db.scalar(select(func.count()).select_from(CommerceSnapshot))
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    origin = f"https://127.0.0.1:{listener.getsockname()[1]}"
    monkeypatch.setattr(settings, "customer_app_origin", origin)
    completed = threading.Event()
    results: list[dict[str, Any]] = []
    holding = False
    entered, release = asyncio.Event(), asyncio.Event()

    async def harness(scope: Scope, receive: Receive, send: Send) -> None:
        nonlocal holding
        path = scope.get("path", "")
        if path == "/__fixture__/start":
            html = Path("app/portal/static/index.html").read_text().replace(
                '/app/assets/portal.mjs', '/__fixture__/driver.mjs')
            response = Response(html, media_type="text/html")
            for cookie in client.cookies.jar:
                assert cookie.value is not None
                response.set_cookie(cookie.name, cookie.value, secure=True, samesite="strict",
                                    httponly="csrf" not in cookie.name.lower())
            await response(scope, receive, send)
            return
        if path == "/__fixture__/driver.mjs":
            await Response(Path("tests/javascript/goal_progress_api_browser.mjs").read_text(),
                           media_type="text/javascript")(scope, receive, send)
            return
        if path in {"/__fixture__/importing", "/__fixture__/complete"}:
            with factory() as db:
                store = db.get(CommerceStore, store_id)
                assert store
                store.window_end = now if path.endswith("importing") else None
                db.commit()
            await JSONResponse({"ok": True})(scope, receive, send)
            return
        if path == "/__fixture__/hold":
            holding = True
            entered.clear()
            release.clear()
            await JSONResponse({"ok": True})(scope, receive, send)
            return
        if path == "/__fixture__/held":
            await asyncio.wait_for(entered.wait(), 15)
            await JSONResponse({"ok": True})(scope, receive, send)
            return
        if path == "/__fixture__/release":
            release.set()
            await JSONResponse({"ok": True})(scope, receive, send)
            return
        if path == "/__fixture__/result":
            body = bytearray()
            while True:
                incoming = await receive()
                body.extend(incoming.get("body", b""))
                if not incoming.get("more_body", False):
                    break
            results.append(json.loads(body))
            await JSONResponse({"ok": True})(scope, receive, send)
            completed.set()
            return
        if path.endswith("/progress") and holding:
            holding = False
            messages: list[Message] = []

            async def collect(message: Message) -> None:
                messages.append(message)

            await app(scope, receive, collect)
            entered.set()
            await asyncio.wait_for(release.wait(), 20)
            for message in messages:
                await send(message)
            return
        await app(scope, receive, send)

    cert, key = localhost_certificate(tmp_path)
    server = uvicorn.Server(uvicorn.Config(harness, log_level="critical", lifespan="off",
                                           ssl_certfile=str(cert), ssl_keyfile=str(key)))
    thread = threading.Thread(target=lambda: server.run(sockets=[listener]), daemon=True)
    thread.start()
    deadline = time.monotonic() + 10
    while not server.started and thread.is_alive() and time.monotonic() < deadline:
        time.sleep(0.01)
    assert server.started
    browser = subprocess.Popen([
        portal_executable("chromium", "chromium-browser", "google-chrome"),
        "--headless", "--no-sandbox", "--disable-gpu", "--disable-background-networking",
        "--no-first-run", "--disable-extensions", "--ignore-certificate-errors",
        "--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1",
        f"--user-data-dir={tmp_path / 'browser'}", origin + "/__fixture__/start",
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        assert completed.wait(90), "Actual progress browser did not finish"
        assert results and results[0]["status"] == "passed", results
        with factory() as db:
            assert db.scalar(select(func.count()).select_from(CommerceSnapshot)) == snapshots
    finally:
        browser.terminate()
        try:
            browser.wait(timeout=5)
        except subprocess.TimeoutExpired:
            browser.kill()
            browser.wait(timeout=5)
        server.should_exit = True
        thread.join(timeout=10)
        listener.close()
        client.close()
        if engine is not customer_engine:
            engine.dispose()
