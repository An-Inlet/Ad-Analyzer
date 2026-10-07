"""Actual HTTPS customer ownership and truthful default-off reporting UI."""

import json
import socket
import subprocess
import threading
import time
from collections.abc import Generator
from pathlib import Path
from uuid import uuid4

import pytest
import uvicorn
from app.customers.identity import get_identity_provider
from app.customers.models import CustomerMembership, CustomerUser
from app.database.session import Base, get_db
from app.main import app
from app.settings import settings
from app.workspaces.models import Workspace
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from starlette.responses import JSONResponse, Response
from starlette.types import Receive, Scope, Send

from tests.test_customer_browser_api_journey import localhost_certificate
from tests.test_customer_identity import ISSUER, FakeProvider
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_portal import portal_executable


@pytest.mark.parametrize("scenario", ["unavailable", "controlled"])
def test_actual_reported_feedback_unavailable_browser(
    scenario: str,
    customer_engine: Engine,
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
    with factory() as db:
        user = CustomerUser(
            id=uuid4().hex,
            issuer=ISSUER,
            subject="reported-browser",
            email="owner@example.test",
            status="active",
        )
        db.add(user)
        db.commit()
        space = Workspace(
            slug="reported-browser", name="Alpha", client_name="Alpha", status="active"
        )
        db.add(space)
        db.flush()
        wid = space.id
        db.add(CustomerMembership(user_id=user.id, workspace_id=wid, role="owner"))
        db.commit()

    def database() -> Generator[Session, None, None]:
        with factory() as db:
            yield db

    monkeypatch.setattr(
        app,
        "dependency_overrides",
        {
            get_db: database,
            get_identity_provider: lambda: provider,
        },
    )
    completed = threading.Event()
    results = []

    async def harness(scope: Scope, receive: Receive, send: Send) -> None:
        path = scope.get("path", "")
        if path == "/__fixture__/start":
            html = (
                Path("app/portal/static/reported-comparison.html")
                .read_text()
                .replace("/app/assets/reported-comparison.mjs", "/__fixture__/driver.mjs")
            )
            await Response(html, media_type="text/html")(scope, receive, send)
            return
        if path == "/__fixture__/driver.mjs":
            script = Path(f"tests/javascript/reported_feedback_{scenario}_browser.mjs").read_text()
            for key, value in {"WORKSPACE": wid}.items():
                script = script.replace(f"__{key}__", str(value))
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
