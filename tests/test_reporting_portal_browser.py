"""Real local TLS customer UI/API/SQL; only provider transport and response loss are injected."""

import json
import socket
import subprocess
import threading
import time
from dataclasses import replace
from pathlib import Path
from typing import Any, cast

import httpx
import pytest
import uvicorn
from app.api.customer_planning_catalog import router as account_router
from app.api.customer_reporting import get_selected_customer_runtime
from app.api.customer_reporting_capture import router as capture_router
from app.campaign_performance.range_receipt_models import RangeReceiptRow
from app.campaign_performance.selected_models import SelectedCaptureRow
from app.portal.router import STATIC
from app.portal.router import router as portal_router
from app.settings import settings
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from starlette.responses import JSONResponse, Response
from starlette.types import Receive, Scope, Send

from tests.test_customer_browser_api_journey import localhost_certificate
from tests.test_customer_portal import portal_executable
from tests.test_google_range_publication_api import range_customer as range_customer
from tests.test_selected_customer_api import CustomerFixture
from tests.test_selected_customer_api import configured as configured
from tests.test_selected_customer_api import customer as customer
from tests.test_selected_customer_api import customer_engine as customer_engine
from tests.test_selected_customer_api import replicas as replicas


def test_actual_reporting_portal(
    range_customer: CustomerFixture, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    f = range_customer
    application = cast(FastAPI, f.alice.app)
    application.include_router(account_router)
    application.include_router(capture_router)
    application.include_router(portal_router)
    application.mount("/app/assets", StaticFiles(directory=STATIC))
    old_transport = f.runtime.transport
    f.label = "Purchase <img src=x onerror=alert(1)>"

    def wire(req: httpx.Request) -> httpx.Response:
        query = json.loads(req.content)["query"]
        if "FROM conversion_action" in query:
            if "conversion_action.name" not in query:
                return httpx.Response(
                    200,
                    json={
                        "results": [
                            {
                                "conversionAction": {
                                    "resourceName": "customers/1234567890/conversionActions/123",
                                    "ownerCustomer": "customers/1234567890",
                                }
                            }
                        ]
                    },
                )
            return f.handle(req)
        if "segments.conversion_action" in query:
            f.calls.append("selected-search")
            return httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "campaign": {
                                "id": "1",
                                "resourceName": "customers/1234567890/campaigns/1",
                            },
                            "segments": {
                                "date": "2026-09-30",
                                "conversionAction": "customers/1234567890/conversionActions/123",
                            },
                            "metrics": {"conversions": "10", "conversionsValue": "100"},
                        }
                    ]
                },
            )
        with old_transport() as transport:
            return transport.handle_request(req)

    f.runtime = replace(f.runtime, transport=lambda: httpx.MockTransport(wire))
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    origin = f"https://127.0.0.1:{listener.getsockname()[1]}"
    monkeypatch.setattr(settings, "customer_app_origin", origin)
    done = threading.Event()
    results: list[dict[str, Any]] = []
    requests: list[dict[str, Any]] = []
    observed_captures: list[str] = []

    async def harness(scope: Scope, receive: Receive, send: Send) -> None:
        path = scope.get("path", "")
        if path == "/__fixture__/start":
            html = (
                (STATIC / "reporting.html")
                .read_text()
                .replace("/app/assets/reporting.mjs", "/__fixture__/driver.mjs")
            )
            await Response(html, media_type="text/html")(scope, receive, send)
            return
        if path == "/__fixture__/driver.mjs":
            script = (
                Path("tests/javascript/reporting_api_browser.mjs")
                .read_text()
                .replace("__WORKSPACE__", str(f.wid))
                .replace("__ACCOUNT__", str(f.aid))
            )
            await Response(script, media_type="text/javascript")(scope, receive, send)
            return
        if path in {"/__fixture__/disabled", "/__fixture__/enabled"}:
            disabled = path.endswith("disabled")
            application.dependency_overrides[get_selected_customer_runtime] = (
                (lambda: None) if disabled else (lambda: f.runtime)
            )
            with Session(f.engine) as db:
                assert db.scalar(select(func.count()).select_from(RangeReceiptRow)) == 0
            await JSONResponse({"ok": True})(scope, receive, send)
            return
        if path == "/__fixture__/capture-checkpoint":
            with Session(f.engine) as db:
                rows = list(db.scalars(select(SelectedCaptureRow)))
                assert len(rows) == 1
                observed_captures.append(rows[0].id)
            await JSONResponse({"ok": True})(scope, receive, send)
            return
        if path == "/__fixture__/result":
            body = bytearray()
            while True:
                message = await receive()
                body.extend(message.get("body", b""))
                if not message.get("more_body", False):
                    break
            results.append(json.loads(body))
            await JSONResponse({"ok": True})(scope, receive, send)
            done.set()
            return
        if path.endswith("/aggregate-range"):
            chunks: list[dict[str, Any]] = []
            while True:
                message = await receive()
                chunks.append(dict(message))
                if not message.get("more_body", False):
                    break
            requests.append(json.loads(b"".join(m.get("body", b"") for m in chunks)))

            async def replay() -> Any:
                if chunks:
                    return chunks.pop(0)
                return await receive()

            await application(scope, replay, send)
            return
        await application(scope, receive, send)

    cert, key = localhost_certificate(tmp_path)
    server = uvicorn.Server(
        uvicorn.Config(
            harness,
            lifespan="off",
            log_level="critical",
            ssl_certfile=str(cert),
            ssl_keyfile=str(key),
        )
    )
    thread = threading.Thread(target=lambda: server.run(sockets=[listener]), daemon=True)
    thread.start()
    deadline = time.monotonic() + 10
    while not server.started and time.monotonic() < deadline:
        time.sleep(0.01)
    assert server.started
    browser = subprocess.Popen(
        [
            portal_executable(
                "chromium", "chromium-browser", "google-chrome", "google-chrome-stable"
            ),
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
        assert done.wait(60), "Reporting browser did not finish"
        assert results and results[0]["status"] == "passed", results
        assert len(requests) == 4 and requests[1] == requests[2]
        assert requests[3]["request_id"] != requests[1]["request_id"]
        with Session(f.engine) as db:
            assert db.scalar(select(func.count()).select_from(RangeReceiptRow)) == 2
            assert db.scalar(select(func.count()).select_from(SelectedCaptureRow)) == 0
            assert observed_captures == [results[0]["capture"]]
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
