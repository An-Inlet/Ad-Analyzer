"""Actual authenticated publication browser journeys on both databases."""

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
from app.api import customer_descriptive
from app.commerce import evidence as commerce_evidence
from app.customers.identity import get_identity_provider
from app.customers.models import CustomerMembership, CustomerUser
from app.database.session import Base, get_db
from app.main import app
from app.outcomes import descriptive
from app.settings import Settings, settings
from app.shopify.privacy import process_event
from app.workspaces.models import Workspace
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker
from starlette.responses import JSONResponse, Response
from starlette.types import Receive, Scope, Send

from tests.test_commerce_measurement import NOW
from tests.test_customer_browser_api_journey import localhost_certificate
from tests.test_customer_identity import ISSUER, FakeProvider
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_portal import portal_executable
from tests.test_owned_outcomes import evidence
from tests.test_shopify_sales import SHOP
from tests.test_shopify_sales import configuration as configuration


def test_measurement_real_browser(
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
        wid, actor, body, _, _ = evidence(db, configuration, tmp_path)
        user = db.get(CustomerUser, actor)
        assert user is not None
        user.issuer, user.subject = ISSUER, "measurement-owner"
        workspace = db.get(Workspace, wid)
        assert workspace is not None
        workspace.name = "<img src=x>"
        db.commit()

    def database() -> Generator[Session, None, None]:
        with factory() as db:
            yield db

    monkeypatch.setattr(
        app,
        "dependency_overrides",
        {get_db: database, get_identity_provider: lambda: FakeProvider()},
    )
    original_read = commerce_evidence.read_publication

    def read_at_fixture_time(*args: Any, **kwargs: Any) -> Any:
        return original_read(*args, **kwargs, now=NOW)

    monkeypatch.setattr(commerce_evidence, "read_publication", read_at_fixture_time)
    original_compare = descriptive.compare

    def compare_at_fixture_time(db: Any, wid: int, body: Any, authorize: Any) -> Any:
        return original_compare(db, wid, body, authorize, clock=lambda: NOW)

    monkeypatch.setattr(customer_descriptive, "compare", compare_at_fixture_time)
    completed = threading.Event()
    result: list[dict[str, Any]] = []

    async def harness(scope: Scope, receive: Receive, send: Send) -> None:
        path = scope.get("path", "")
        if path == "/__fixture__/driver.mjs":
            script = (
                Path("tests/javascript/measurement_history_browser.mjs")
                .read_text()
                .replace("__WORKSPACE__", str(wid))
            )
            await Response(script, media_type="text/javascript")(scope, receive, send)
            return
        if path == "/__fixture__/viewer":
            with factory() as db:
                membership = db.get(CustomerMembership, (actor, wid))
                assert membership
                membership.role = "viewer"
                db.commit()
            await JSONResponse({"ok": True})(scope, receive, send)
            return
        if path == "/__fixture__/erase":
            with factory() as db:
                process_event(db, configuration, "orders/delete", SHOP, {"id": 1}, NOW)
                db.commit()
            await JSONResponse({"ok": True})(scope, receive, send)
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
                Path("app/portal/static/measurement-history.html")
                .read_text()
                .replace("/app/assets/measurement-history.mjs", "/__fixture__/driver.mjs")
            )
            await Response(html, media_type="text/html")(scope, receive, send)
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
        assert completed.wait(60), "Measurement browser did not report completion"
        assert result and result[0]["status"] == "passed", result
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
