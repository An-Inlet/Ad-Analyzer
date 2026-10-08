"""Actual TLS page -> owned run -> vault/native diagnostic HTTP; no observation writes."""

import json
import socket
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

import httpx
import pytest
import uvicorn
from app.collectors import account_diagnostics
from app.publication.execution_models import ProviderExecutionAttempt, ProviderExposureReservation
from app.settings import Settings, settings
from fastapi.staticfiles import StaticFiles
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session
from starlette.responses import JSONResponse, Response
from starlette.types import Receive, Scope, Send

from tests.test_customer_browser_api_journey import localhost_certificate
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_customer_portal import portal_executable
from tests.test_google_total_envelope_api import created
from tests.test_shopify_sales import configuration as configuration


def historical_contract_actual_envelope_browser(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    replicas: Any,
) -> None:
    chromium = portal_executable("chromium", "chromium-browser", "google-chrome")
    alice, base, run, native = created(
        customer_engine, configuration, tmp_path, monkeypatch, replicas
    )
    engine = customer_engine
    wid = int(base.split("/workspaces/")[1].split("/")[0])
    alice.app.mount("/app/assets", StaticFiles(directory="app/portal/static"))
    monkeypatch.setattr(settings, "customer_native_diagnostics_enabled", True)
    with Session(engine) as db:
        attempt = db.scalar(
            select(ProviderExecutionAttempt).where(ProviderExecutionAttempt.step_id == "campaign")
        )
        assert attempt
        request = attempt.request
        before = [
            (r.id, r.state, r.amount_micros)
            for r in db.scalars(select(ProviderExposureReservation))
        ]
    campaign = next(k for k in native.rows if "/campaigns/" in k)
    budget = request["resources"]["budget"]
    advertiser = request["scope"]["external_advertiser_id"]
    operation = request["step"]["operation"]
    controls = {"lower": False}
    calls = []
    writes = native.posts

    def wire(req: httpx.Request) -> httpx.Response:
        calls.append(req.url.path)
        if req.url.host == "oauth2.googleapis.com":
            return httpx.Response(
                200,
                json={"access_token": "offline-read", "expires_in": 3600, "token_type": "Bearer"},
            )
        query = json.loads(req.content)["query"]
        if "FROM customer" in query:
            rows = [
                {
                    "customer": {
                        "id": advertiser,
                        "resourceName": f"customers/{advertiser}",
                        "currencyCode": "USD",
                        "timeZone": "Pacific/Pago_Pago",
                        "status": "ENABLED",
                    }
                }
            ]
        elif "FROM campaign_budget" in query:
            rows = [
                {
                    "campaignBudget": {
                        "resourceName": budget,
                        "totalAmountMicros": "20" if controls["lower"] else "30",
                        "referenceCount": "1",
                        "period": "CUSTOM_PERIOD",
                        "status": "ENABLED",
                        "type": "STANDARD",
                    }
                }
            ]
        elif "metrics.cost_micros" in query:
            rows = []
        elif "FROM campaign " in query:
            rows = [
                {
                    "campaign": {
                        "resourceName": campaign,
                        "campaignBudget": budget,
                        "status": "PAUSED",
                        "advertisingChannelType": "SEARCH",
                        "biddingStrategyType": "MANUAL_CPC",
                        "startDateTime": operation["starts_local"],
                        "endDateTime": operation["ends_local"],
                    }
                }
            ]
        else:
            rows = []
        return httpx.Response(200, json={"results": rows})

    monkeypatch.setattr(
        account_diagnostics, "diagnostic_transport", lambda: httpx.MockTransport(wire)
    )
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
                Path("tests/javascript/envelope_actual.mjs")
                .read_text()
                .replace("__WID__", str(wid))
                .replace("__RUN__", run["id"])
            )
            await Response(script, media_type="text/javascript")(scope, receive, send)
            return
        if path in {"/__fixture__/lower", "/__fixture__/disable"}:
            if path.endswith("lower"):
                controls["lower"] = True
            else:
                settings.customer_native_diagnostics_enabled = False
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
            html = (
                Path("app/portal/static/execution.html")
                .read_text()
                .replace("/app/assets/execution.mjs", "/__fixture__/driver.mjs")
            )
            await Response(html, media_type="text/html")(scope, receive, send)
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
        assert completed.wait(60), "Envelope browser did not complete"
        assert result and result[0]["status"] == "passed", result
        assert len(calls) == 14  # Two explicit reads; disabled read and page load emit none.
        assert native.posts == writes
        with Session(engine) as db:
            assert [
                (r.id, r.state, r.amount_micros)
                for r in db.scalars(select(ProviderExposureReservation))
            ] == before
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
