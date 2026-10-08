"""Real HTTPS optimization browser, actual APIs/DB and mocked provider adapters."""

import asyncio
import json
import socket
import subprocess
import threading
import time
from collections.abc import Generator
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
import uvicorn
from app.customers.identity import get_identity_provider
from app.customers.models import CustomerMembership, CustomerUser
from app.database.session import Base, get_db
from app.main import app
from app.publication.customer_optimization_contracts import get_customer_optimization_runtime
from app.settings import Settings, settings
from app.workspaces.models import Workspace
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker
from starlette.responses import JSONResponse, Response
from starlette.types import Receive, Scope, Send

from tests.test_customer_browser_api_journey import localhost_certificate
from tests.test_customer_identity import ISSUER, FakeProvider
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_optimization_api import setup
from tests.test_customer_portal import portal_executable
from tests.test_shopify_sales import configuration as configuration


@pytest.mark.parametrize("scenario", ["manual", "automation_contract"])
def historical_contract_optimization_real_browser(
    scenario: str,
    customer_engine: Engine,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    configuration: Settings,
) -> None:
    chromium = portal_executable(
        "chromium", "chromium-browser", "google-chrome", "google-chrome-stable"
    )
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    origin = f"https://127.0.0.1:{listener.getsockname()[1]}"
    monkeypatch.setattr(settings, "customer_app_origin", origin)
    engine = customer_engine
    if engine.dialect.name == "sqlite":
        engine = create_engine(
            f"sqlite:///{tmp_path / 'closure.sqlite'}", connect_args={"check_same_thread": False}
        )
        Base.metadata.create_all(engine)
    factory = sessionmaker(engine)
    with factory() as db:
        wid, actor, p, runtime, server_http = setup(db, configuration, tmp_path, "google_ads")
        policy = p.model_dump(mode="json")
        qualify = runtime.execution.qualification_reader

        def qualify_both(*args: Any) -> Any:
            result = qualify(*args)
            return result.model_copy(
                update={"allowed_operations": ["google_budget_set_v1", "google_status_set_v1"]}
            )

        runtime = replace(
            runtime, execution=replace(runtime.execution, qualification_reader=qualify_both)
        )
        user = db.get(CustomerUser, actor)
        assert user is not None
        user.issuer, user.subject = ISSUER, "optimization-owner"
        workspace = db.get(Workspace, wid)
        assert workspace is not None
        workspace.name = "<img src=x>"
        db.commit()

    def database() -> Generator[Session, None, None]:
        with factory() as db:
            yield db

    active_runtime: list[Any] = [runtime]
    monkeypatch.setattr(
        app,
        "dependency_overrides",
        {
            get_db: database,
            get_identity_provider: lambda: FakeProvider(),
            get_customer_optimization_runtime: lambda: active_runtime[0],
        },
    )
    hold, entered, release = threading.Event(), threading.Event(), threading.Event()
    completed = threading.Event()
    result: list[dict[str, Any]] = []

    async def harness(scope: Scope, receive: Receive, send: Send) -> None:
        path = scope.get("path", "")
        if path == "/__fixture__/driver.mjs":
            script = (
                Path(
                    "tests/javascript/optimization_browser.mjs"
                    if scenario == "manual"
                    else "tests/javascript/session_automation_browser.mjs"
                )
                .read_text()
                .replace("__WORKSPACE__", str(wid))
                .replace("__POLICY__", json.dumps(policy))
            )
            await Response(script, media_type="text/javascript")(scope, receive, send)
            return
        if path == "/__fixture__/result":
            data = bytearray()
            while True:
                message = await receive()
                data.extend(message.get("body", b""))
                if not message.get("more_body", False):
                    break
            result.append(json.loads(data))
            await JSONResponse({"ok": True})(scope, receive, send)
            completed.set()
            return
        if path == "/__fixture__/start":
            # Preserve the actual application URL so receipt recovery is exercised.
            html = (
                Path("app/portal/static/optimization.html")
                .read_text()
                .replace("/app/assets/optimization.mjs", "/__fixture__/driver.mjs")
            )
            await Response(html, media_type="text/html")(scope, receive, send)
            return
        if path == "/__fixture__/disabled":
            active_runtime[0] = None
            await JSONResponse({"ok": True})(scope, receive, send)
            return
        if path == "/__fixture__/hold":
            entered.clear()
            release.clear()
            hold.set()
            await JSONResponse({"ok": True})(scope, receive, send)
            return
        if path == "/__fixture__/entered":
            await JSONResponse({"entered": entered.is_set()})(scope, receive, send)
            return
        if path == "/__fixture__/release":
            release.set()
            await JSONResponse({"ok": True})(scope, receive, send)
            return
        if path in {"/__fixture__/viewer", "/__fixture__/owner"}:
            with factory() as db:
                membership = db.get(CustomerMembership, (actor, wid))
                assert membership is not None
                membership.role = "viewer" if path.endswith("viewer") else "owner"
                db.commit()
            await JSONResponse({"ok": True})(scope, receive, send)
            return
        if path.endswith("/optimization/target-options") and hold.is_set():
            hold.clear()
            messages: list[Any] = []

            async def capture(message: Any) -> None:
                messages.append(message)

            await app(scope, receive, capture)
            entered.set()
            assert await asyncio.to_thread(release.wait, 15), "test response hold was not released"
            for message in messages:
                await send(message)
            return
        await app(scope, receive, send)

    certificate, key = localhost_certificate(tmp_path)
    server = uvicorn.Server(
        uvicorn.Config(
            harness,
            log_level="critical",
            lifespan="off",
            ssl_certfile=str(certificate),
            ssl_keyfile=str(key),
        )
    )
    thread = threading.Thread(target=lambda: server.run(sockets=[listener]), daemon=True)
    thread.start()
    deadline = time.monotonic() + 10
    while not server.started and thread.is_alive() and time.monotonic() < deadline:
        time.sleep(0.01)
    assert server.started
    browser = subprocess.Popen(
        [
            chromium,
            "--headless",
            "--no-sandbox",
            "--disable-gpu",
            "--disable-background-networking",
            "--no-first-run",
            "--disable-extensions",
            "--ignore-certificate-errors",
            "--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1",
            f"--user-data-dir={tmp_path / 'browser'}",
            origin + "/__fixture__/start",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        assert completed.wait(60), "Optimization browser did not report completion"
        assert result and result[0]["status"] == "passed", result
        assert len(server_http.writes) == (3 if scenario == "manual" else 0), (
            "initial, repeat, pause only; no replay after lost response"
        )
    finally:
        release.set()
        browser.terminate()
        try:
            browser.wait(timeout=5)
        except subprocess.TimeoutExpired:
            browser.kill()
            browser.wait(timeout=5)
        server.should_exit = True
        thread.join(timeout=10)
        listener.close()
        if engine is not customer_engine:
            engine.dispose()
