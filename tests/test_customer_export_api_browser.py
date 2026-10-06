"""Actual Chromium -> localhost HTTPS -> production APIs -> SQLite/PostgreSQL export."""

import socket
import subprocess
import threading
import time
from collections.abc import Generator
from pathlib import Path

import pytest
import uvicorn
from app.customers.identity import get_identity_provider
from app.customers.models import CustomerSession
from app.database.session import get_db
from app.lifecycle.models import LifecycleRequest, LifecycleStep
from app.main import app
from app.settings import settings
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session
from starlette.responses import Response
from starlette.types import Receive, Scope, Send

from tests.test_customer_browser_api_journey import localhost_certificate
from tests.test_customer_exports import export_engine as export_engine
from tests.test_customer_identity import FakeProvider
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_portal import portal_executable


def test_real_export_browser_api_database(
    export_engine: Engine, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    chromium = portal_executable(
        "chromium", "chromium-browser", "google-chrome", "google-chrome-stable"
    )
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    origin = f"https://127.0.0.1:{listener.getsockname()[1]}"
    monkeypatch.setattr(settings, "customer_app_origin", origin)
    finished, outcome = threading.Event(), []
    html = (
        Path("app/portal/static/workspace-export.html")
        .read_text()
        .replace("/app/assets/workspace-export.mjs", "/__export_script__")
    )

    async def harness(scope: Scope, receive: Receive, send: Send) -> None:
        path = scope.get("path")
        if path == "/__export_page__":
            await Response(html, media_type="text/html")(scope, receive, send)
        elif path == "/__export_script__":
            await Response(
                Path("tests/javascript/customer_export_api_browser.mjs").read_text(),
                media_type="text/javascript",
            )(scope, receive, send)
        elif path == "/__export_result__":
            body = bytearray()
            while True:
                message = await receive()
                body.extend(message.get("body", b""))
                if not message.get("more_body"):
                    break
            outcome.append(body.decode())
            await Response("ok")(scope, receive, send)
            finished.set()
        else:
            await app(scope, receive, send)

    def database() -> Generator[Session, None, None]:
        with Session(export_engine) as db:
            yield db

    previous = dict(app.dependency_overrides)
    app.dependency_overrides[get_db] = database
    app.dependency_overrides[get_identity_provider] = FakeProvider
    cert, key = localhost_certificate(tmp_path)
    server = uvicorn.Server(
        uvicorn.Config(harness, ssl_certfile=str(cert), ssl_keyfile=str(key), log_level="error")
    )
    thread = threading.Thread(target=lambda: server.run(sockets=[listener]), daemon=True)
    browser = None
    try:
        thread.start()
        deadline = time.monotonic() + 10
        while not server.started and time.monotonic() < deadline:
            time.sleep(0.02)
        assert server.started
        browser = subprocess.Popen(
            [
                chromium,
                "--headless",
                "--no-sandbox",
                "--disable-gpu",
                "--ignore-certificate-errors",
                "--disable-background-networking",
                "--no-first-run",
                "--disable-extensions",
                "--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1",
                f"--user-data-dir={tmp_path / 'browser'}",
                f"{origin}/__export_page__",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        assert finished.wait(60), "Actual export browser did not complete"
        assert outcome == ["passed"], outcome
        with Session(export_engine) as db:
            receipt = db.scalar(
                select(LifecycleRequest).where(LifecycleRequest.operation == "export")
            )
            assert (
                receipt is not None and receipt.state == "archive_built" and receipt.revision == 2
            )
            assert receipt.blockers[0]["media_archive_complete"] is True
            step = db.get(LifecycleStep, (receipt.id, "export_build"))
            assert step is not None and step.state == "complete" and step.evidence_digest
            session = db.scalar(select(CustomerSession))
            assert session is not None and session.revoked_at is not None
    finally:
        if browser is not None:
            browser.terminate()
            try:
                browser.wait(timeout=5)
            except subprocess.TimeoutExpired:
                browser.kill()
                browser.wait(timeout=5)
        server.should_exit = True
        thread.join(timeout=10)
        listener.close()
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)
