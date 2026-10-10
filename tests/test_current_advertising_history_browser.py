"""Current unpatched history-only pages, independently of pinned retired action UI."""

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
from app.customers.identity import get_identity_provider
from app.database.session import get_db
from app.main import app
from app.publication.execution_models import ProviderExecutionAttempt, ProviderExecutionRun
from app.settings import settings
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session
from starlette.responses import JSONResponse, Response
from starlette.types import Receive, Scope, Send

from tests import test_customer_identity
from tests.test_customer_browser_api_journey import localhost_certificate
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import login
from tests.test_customer_identity import replicas as replicas
from tests.test_customer_portal import portal_executable
from tests.test_planning_customer_boundary import owned_workspace

pytestmark = pytest.mark.planning_boundary


@pytest.mark.parametrize(
    "page", ["execution", "optimization", "social-configuration", "tiktok-linked"]
)
def test_current_history_pages_preserve_scope_and_have_no_action_controls(
    customer_engine: Engine, replicas: Any, monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path, page: str,
) -> None:
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    origin = f"https://127.0.0.1:{listener.getsockname()[1]}"
    monkeypatch.setattr(test_customer_identity, "ORIGIN", origin)
    monkeypatch.setattr(settings, "customer_app_origin", origin)
    for client in replicas[:2]:
        client.base_url = origin
    actor = login(replicas[0], "history-owner:fixture")
    with Session(customer_engine) as db:
        wid = owned_workspace(db, actor)

    def database() -> Generator[Session, None, None]:
        with Session(customer_engine) as db:
            yield db

    monkeypatch.setattr(app, "dependency_overrides", {
        get_db: database, get_identity_provider: lambda: replicas[2],
    })
    complete = threading.Event()
    results: list[dict[str, Any]] = []

    async def harness(scope: Scope, receive: Receive, send: Send) -> None:
        path = scope.get("path")
        if page in {"social-configuration", "tiktok-linked"} and path == f"/app/{page}":
            messages: list[Any] = []

            async def capture(message: Any) -> None:
                messages.append(message)

            await app(scope, receive, capture)
            start = next(m for m in messages if m["type"] == "http.response.start")
            assert start["status"] == 200
            assert b"text/html" in dict(start["headers"])[b"content-type"]
            raw = b"".join(m.get("body", b"") for m in messages
                           if m["type"] == "http.response.body")
            assert raw == Path("app/portal/static/advertising-history.html").read_bytes()
            html = raw.decode("utf-8")
            assert html.count("/app/assets/advertising-history.mjs") == 1
            html = html.replace("/app/assets/advertising-history.mjs", "/__fixture__/driver.mjs")
            body = html.encode("utf-8")
            assert sum(k.lower() == b"content-length" for k, _ in start["headers"]) == 1
            headers = [(k, str(len(body)).encode("ascii") if k.lower() == b"content-length" else v)
                       for k, v in start["headers"]]
            assert [(k, v) for k, v in headers if k.lower() != b"content-length"] == [
                (k, v) for k, v in start["headers"] if k.lower() != b"content-length"
            ]
            await send({**start, "headers": headers})
            await send({"type": "http.response.body", "body": body})
            return
        if path == "/__fixture__/start":
            html = Path(f"app/portal/static/{page}.html").read_text().replace(
                "/app/assets/advertising-history.mjs", "/__fixture__/driver.mjs"
            )
            await Response(html, media_type="text/html")(scope, receive, send)
            return
        if path == "/__fixture__/driver.mjs":
            source = Path("tests/javascript/current_advertising_history_browser.mjs").read_text()
            await Response(source.replace("__WORKSPACE__", str(wid)),
                           media_type="text/javascript")(scope, receive, send)
            return
        if path == "/__fixture__/result":
            data = bytearray()
            while True:
                message = await receive()
                data.extend(message.get("body", b""))
                if not message.get("more_body", False):
                    break
            results.append(json.loads(data))
            await JSONResponse({"ok": True})(scope, receive, send)
            complete.set()
            return
        await app(scope, receive, send)

    cert, key = localhost_certificate(tmp_path)
    server = uvicorn.Server(uvicorn.Config(
        harness, lifespan="off", log_level="critical",
        ssl_certfile=str(cert), ssl_keyfile=str(key),
    ))
    thread = threading.Thread(target=lambda: server.run(sockets=[listener]), daemon=True)
    thread.start()
    deadline = time.monotonic() + 10
    while not server.started and thread.is_alive() and time.monotonic() < deadline:
        time.sleep(.01)
    assert server.started
    browser = subprocess.Popen([
        portal_executable("chromium", "chromium-browser", "google-chrome"),
        "--headless", "--no-sandbox", "--disable-gpu", "--ignore-certificate-errors",
        "--disable-background-networking", "--no-first-run", "--disable-extensions",
        "--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1",
        f"--user-data-dir={tmp_path / 'browser'}",
        origin + (f"/app/{page}" if page in {"social-configuration", "tiktok-linked"}
                  else "/__fixture__/start"),
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        assert complete.wait(40), "Current history browser did not finish"
        assert results and results[0]["status"] == "passed", results
        with Session(customer_engine) as db:
            assert db.scalar(select(func.count()).select_from(ProviderExecutionAttempt)) == 0
            assert db.scalar(select(func.count()).select_from(ProviderExecutionRun)) == 0
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
