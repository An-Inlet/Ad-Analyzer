"""Actual HTTPS browser→customer API→owned planning service; native IO uses MockHTTP."""

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
from app.planning_documents.models import PlanEventRow, PlanRow, PlanVersionRow
from app.publication.execution_models import ProviderExecutionAttempt
from app.settings import Settings, settings
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session
from starlette.responses import JSONResponse, Response
from starlette.types import Receive, Scope, Send

from tests import test_customer_identity
from tests.test_customer_browser_api_journey import localhost_certificate
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_customer_portal import portal_executable
from tests.test_planning_evidence_adapter import setup_evidence
from tests.test_shopify_sales import configuration as configuration

pytestmark = pytest.mark.planning_boundary


@pytest.mark.parametrize(
    ("journey", "platform"),
    [("documents", "google_ads"), ("targets", "google_ads"),
     ("targets", "meta_ads"), ("targets", "tiktok_ads")],
)
def test_actual_planning_browser_lost_response_recovery_and_versions(
    journey: str,
    platform: str,
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    origin = f"https://127.0.0.1:{listener.getsockname()[1]}"
    # Fixtures and the browser use the same real HTTPS origin and synthetic identity.
    monkeypatch.setattr(test_customer_identity, "ORIGIN", origin)
    monkeypatch.setattr(settings, "customer_app_origin", origin)
    for client in replicas[:2]:
        client.base_url = origin
    _, ticket, _, calls = setup_evidence(
        customer_engine, configuration, replicas, monkeypatch, platform
    )
    provider = replicas[2]

    def database() -> Generator[Session, None, None]:
        with Session(customer_engine) as db:
            yield db

    monkeypatch.setattr(
        app,
        "dependency_overrides",
        {
            get_db: database,
            get_identity_provider: lambda: provider,
        },
    )
    complete = threading.Event()
    results: list[dict[str, Any]] = []

    async def harness(scope: Scope, receive: Receive, send: Send) -> None:
        path = scope.get("path", "")
        if path == "/__fixture__/start":
            html = (
                Path("app/portal/static/planning.html")
                .read_text()
                .replace("/app/assets/planning.mjs", "/__fixture__/driver.mjs")
            )
            await Response(html, media_type="text/html")(scope, receive, send)
            return
        if path == "/__fixture__/driver.mjs":
            script = Path(f"tests/javascript/planning_{journey}_browser.mjs").read_text()
            script = script.replace("__INPUTS__", ticket.inputs.model_dump_json())
            await Response(script, media_type="text/javascript")(scope, receive, send)
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
            portal_executable("chromium", "chromium-browser", "google-chrome"),
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
        assert complete.wait(55), "Browser did not report completion"
        assert results and results[0]["status"] == "passed", results
        assert calls
        with Session(customer_engine) as db:
            assert db.scalar(select(func.count()).select_from(PlanRow)) == 1
            assert db.scalar(select(func.count()).select_from(PlanVersionRow)) == 2
            assert db.scalar(select(func.count()).select_from(PlanEventRow)) == (
                3 if journey == "documents" else 0
            )
            assert db.scalar(select(func.count()).select_from(ProviderExecutionAttempt)) == 0
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
