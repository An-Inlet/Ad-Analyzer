"""Actual configured owned discovery, authenticated HTTPS UI, and no execution."""

import json
import socket
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

import pytest
import uvicorn
from app.api.customer_campaign_review import router as campaign_router
from app.customers.models import CustomerSession
from app.publication.execution_models import (
    ProviderExecutionAttempt,
    ProviderExecutionReceipt,
    ProviderExecutionReview,
    ProviderExposureReservation,
)
from app.settings import Settings, settings
from fastapi.staticfiles import StaticFiles
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session
from starlette.responses import JSONResponse, Response
from starlette.types import Receive, Scope, Send

from tests.test_campaign_video import encoded as encoded
from tests.test_customer_browser_api_journey import localhost_certificate
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_customer_portal import portal_executable
from tests.test_shopify_sales import configuration as configuration
from tests.tiktok_discovery_fixture import configured_discovery_customer


def test_owned_tiktok_discovery_https(
    customer_engine: Engine,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    configuration: Settings,
    replicas: Any,
    encoded: Any,
) -> None:
    chromium = portal_executable("chromium", "chromium-browser", "google-chrome")
    alice, base, _, requests, control, native = configured_discovery_customer(
        customer_engine, configuration, tmp_path, monkeypatch, replicas, encoded()
    )
    alice.app.include_router(campaign_router)
    alice.app.mount("/app/assets", StaticFiles(directory="app/portal/static"))
    wid = int(base.split("/workspaces/")[1].split("/")[0])
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    origin = f"https://127.0.0.1:{listener.getsockname()[1]}"
    monkeypatch.setattr(settings, "customer_app_origin", origin)
    completed = threading.Event()
    result: list[dict[str, Any]] = []

    async def harness(scope: Scope, receive: Receive, send: Send) -> None:
        path = scope.get("path", "")
        if path == "/__fixture__/driver.mjs":
            script = (
                Path("tests/javascript/tiktok_discovery_browser.mjs")
                .read_text()
                .replace("__WORKSPACE__", str(wid))
            )
            await Response(script, media_type="text/javascript")(scope, receive, send)
            return
        if path == "/__fixture__/start":
            html = (
                Path("app/portal/static/execution.html")
                .read_text()
                .replace("/app/assets/execution.mjs", "/__fixture__/driver.mjs")
            )
            await Response(html, media_type="text/html")(scope, receive, send)
            return
        if path == "/__fixture__/missing":
            control["missing_events"] = True
            await JSONResponse({"ok": True})(scope, receive, send)
            return
        if path == "/__fixture__/revoke-next":

            def revoke() -> None:
                with Session(customer_engine) as db:
                    for session in db.scalars(select(CustomerSession)):
                        session.revoked_at = int(time.time())
                    db.commit()

            control["discovery_callback"] = revoke
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
        await alice.app(scope, receive, send)

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
        assert completed.wait(60), "Discovery browser did not report completion"
        assert result and result[0]["status"] == "passed", result
        # Two complete reads (three GETs each), then one revoked in-flight GET.
        # Business Center selection performs no HTTP.
        assert len(requests) == 7
        assert all(request.method == "GET" for request in requests)
        assert control["builds"] == 0
        assert control["opened"] == control["closed"]
        assert native.posts == native.activations == 0
        with Session(customer_engine) as db:
            for model in (
                ProviderExecutionReview,
                ProviderExecutionAttempt,
                ProviderExecutionReceipt,
                ProviderExposureReservation,
            ):
                assert db.scalar(select(func.count()).select_from(model)) == 0
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
