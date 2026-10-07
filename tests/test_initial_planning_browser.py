"""Actual HTTPS page→session/CSRF→owned report comparison and persisted preview."""

import json
import socket
import subprocess
import threading
import time
from collections.abc import Generator
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
import uvicorn
from app.api import customer_initial_planning as api
from app.api.customer import router as customer_router
from app.customers.access import CustomerPrincipal
from app.customers.identity import get_identity_provider
from app.customers.models import CustomerSession, CustomerUser
from app.database.session import Base, get_db
from app.main import app
from app.publication.customer_optimization_contracts import get_customer_optimization_runtime
from app.settings import Settings, settings
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from starlette.responses import JSONResponse, Response
from starlette.types import Receive, Scope, Send

from tests.test_customer_browser_api_journey import localhost_certificate
from tests.test_customer_identity import ISSUER, FakeProvider
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_portal import portal_executable
from tests.test_execution_session_authorizer import guard
from tests.test_initial_planning_api import ready_history
from tests.test_shopify_sales import configuration as configuration


@pytest.mark.parametrize("scenario", ["unavailable", "review"])
def test_actual_initial_planning_browser(
    scenario: str,
    customer_engine: Engine,
    configuration: Settings,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    chromium = portal_executable("chromium", "chromium-browser", "google-chrome")
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    origin = f"https://127.0.0.1:{listener.getsockname()[1]}"
    monkeypatch.setattr(settings, "customer_app_origin", origin)
    engine = customer_engine
    if engine.dialect.name == "sqlite":
        engine = create_engine(
            f"sqlite:///{tmp_path / 'planning.sqlite'}", connect_args={"check_same_thread": False}
        )
        event.listen(
            engine, "connect", lambda connection, _: connection.execute("PRAGMA foreign_keys=ON")
        )
        Base.metadata.create_all(engine)
    factory = sessionmaker(engine)
    provider = FakeProvider()

    def database() -> Generator[Session, None, None]:
        with factory() as db:
            yield db

    server_http = None
    if scenario == "review":
        from tests import test_customer_identity, test_customer_optimization_api
        from tests.test_initial_preview_review import ready

        monkeypatch.setattr(test_customer_identity, "ORIGIN", origin)
        monkeypatch.setattr(test_customer_optimization_api, "ORIGIN", origin)

        local = FastAPI()
        local.include_router(customer_router)
        local.dependency_overrides[get_db] = database
        local.dependency_overrides[get_identity_provider] = lambda: provider
        client = TestClient(local, base_url=origin)
        wid, document, _, _, bridge, server_http, _ = ready(
            engine, configuration, monkeypatch, (client, client, provider)
        )
        native = replace(bridge.optimization, clock=lambda: datetime.now(UTC))
        runtime = replace(bridge.planning, native=native)
        goal_id = document.objective.goal_id
        cid = document.objective.cohort.campaign_id
    else:
        with factory() as db:
            user = CustomerUser(
                id=uuid4().hex,
                issuer=ISSUER,
                subject="planning-browser",
                email="owner@example.test",
                status="active",
            )
            db.add(user)
            db.commit()
            _, token = guard(db, user.id)
            session = db.get(CustomerSession, token)
            assert session
            wid, goal_id, _, cid, runtime, _ = ready_history(
                engine, configuration, monkeypatch, CustomerPrincipal(user, session), provider
            )

    monkeypatch.setattr(
        app,
        "dependency_overrides",
        {
            get_db: database,
            get_identity_provider: lambda: provider,
            api.get_initial_planning_runtime: lambda: runtime,
            get_customer_optimization_runtime: lambda: runtime.native,
        },
    )
    completed = threading.Event()
    results = []

    async def harness(scope: Scope, receive: Receive, send: Send) -> None:
        path = scope.get("path", "")
        if path == "/__fixture__/start":
            html = (
                Path("app/portal/static/initial-planning.html")
                .read_text()
                .replace("/app/assets/initial-planning.mjs", "/__fixture__/driver.mjs")
            )
            await Response(html, media_type="text/html")(scope, receive, send)
            return
        if path == "/__fixture__/driver.mjs":
            script = Path("tests/javascript/initial_planning_browser.mjs").read_text()
            if scenario == "review":
                script = Path("tests/javascript/initial_preview_review_browser.mjs").read_text()
            for key, value in {"WORKSPACE": wid, "GOAL": goal_id, "CAMPAIGN": cid}.items():
                script = script.replace(f"__{key}__", str(value))
            await Response(script, media_type="text/javascript")(scope, receive, send)
            return
        if scenario == "review" and path == "/app/optimization":
            html = Path("app/portal/static/optimization.html").read_text().replace(
                "/app/assets/optimization.mjs", "/__fixture__/review-driver.mjs"
            )
            await Response(html, media_type="text/html")(scope, receive, send)
            return
        if scenario == "review" and path == "/__fixture__/review-driver.mjs":
            script = Path(
                "tests/javascript/initial_preview_review_approval_browser.mjs"
            ).read_text()
            await Response(script, media_type="text/javascript")(scope, receive, send)
            return
        if path == "/__fixture__/result":
            data = bytearray()
            while True:
                event = await receive()
                data.extend(event.get("body", b""))
                if not event.get("more_body", False):
                    break
            results.append(json.loads(data))
            await JSONResponse({"ok": True})(scope, receive, send)
            completed.set()
            return
        await app(scope, receive, send)

    cert, key = localhost_certificate(tmp_path)
    server = uvicorn.Server(
        uvicorn.Config(
            harness,
            log_level="critical",
            lifespan="off",
            ssl_certfile=str(cert),
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
        assert completed.wait(60), "Browser did not report completion"
        assert results and results[0]["status"] == "passed", results
        if server_http is not None:
            assert not server_http.posts
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
        if engine is not customer_engine:
            engine.dispose()
