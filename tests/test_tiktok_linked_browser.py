"""Actual authenticated publication browser journeys on both databases."""

import json
import socket
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest
import uvicorn
from app.publication.execution_models import (
    ProviderExecutionAttempt,
    ProviderExecutionReceipt,
    ProviderExecutionReview,
    ProviderExposureReservation,
)
from app.settings import Settings, settings
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
from tests.tiktok_linked_runtime_fixture import configured_linked_customer


def historical_contract_actual_linked_tiktok_customer_browser(
    customer_engine: Engine,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    configuration: Settings,
    replicas: Any,
    encoded: Any,
) -> None:
    from app.api import customer_campaign_review
    from app.api.customer_campaign_review import router as campaign_router

    from tests.test_commerce_measurement import NOW

    class Clock:
        @classmethod
        def now(cls, tz: Any = None) -> datetime:
            return NOW if tz else NOW.replace(tzinfo=None)

    # Match the configured fixture's explicit October 5 execution clock.
    monkeypatch.setattr(customer_campaign_review, "datetime", Clock)
    from fastapi.staticfiles import StaticFiles

    chromium = portal_executable("chromium", "chromium-browser", "google-chrome")
    alice, base, policy, draft, _, server_http, requests, control = configured_linked_customer(
        customer_engine, configuration, tmp_path, monkeypatch, replicas, encoded()
    )
    alice.app.mount("/app/assets", StaticFiles(directory="app/portal/static"))
    alice.app.include_router(campaign_router)
    wid = int(base.split("/workspaces/")[1].split("/")[0])
    engine = customer_engine
    with Session(engine) as db:
        for model in (
            ProviderExecutionReview,
            ProviderExecutionAttempt,
            ProviderExecutionReceipt,
            ProviderExposureReservation,
        ):
            assert db.scalar(select(func.count()).select_from(model)) == 0
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    origin = f"https://127.0.0.1:{listener.getsockname()[1]}"
    monkeypatch.setattr(settings, "customer_app_origin", origin)
    completed = threading.Event()
    result: list[dict[str, Any]] = []
    failures: list[tuple[str, int]] = []

    async def harness(scope: Scope, receive: Receive, send: Send) -> None:
        path = scope.get("path", "")
        if path in {"/__fixture__/driver.mjs", "/__fixture__/execution.mjs"}:
            script = Path(
                "tests/javascript/tiktok_linked_actual.mjs"
                if path.endswith("driver.mjs")
                else "tests/javascript/tiktok_linked_run.mjs"
            ).read_text()
            script = (
                script.replace("__WORKSPACE__", str(wid))
                .replace("__POLICY__", json.dumps(policy))
                .replace("__DRAFT__", draft)
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
            html = (
                Path("app/portal/static/tiktok-linked.html")
                .read_text()
                .replace("/app/assets/tiktok-linked.mjs", "/__fixture__/driver.mjs")
            )
            await Response(html, media_type="text/html")(scope, receive, send)
            return
        if path == "/__fixture__/execution":
            html = (
                Path("app/portal/static/execution.html")
                .read_text()
                .replace("/app/assets/execution.mjs", "/__fixture__/execution.mjs")
            )
            await Response(html, media_type="text/html")(scope, receive, send)
            return

        async def traced_send(message: Any) -> None:
            if message["type"] == "http.response.start" and message["status"] >= 400:
                failures.append((path, message["status"]))
            await send(message)

        await alice.app(scope, receive, traced_send)

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
        assert completed.wait(120), "Execution browser did not report completion"
        assert result and result[0]["status"] == "passed", (result, failures)
        assert requests and control["opened"] == control["closed"]
        with Session(engine) as db:
            assert db.scalar(select(func.count()).select_from(ProviderExposureReservation)) == 1
            reservation = db.scalar(select(ProviderExposureReservation))
            assert reservation and reservation.state == "held"
            assert server_http.posts == 5 and server_http.activations == 3
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
