"""Actual authenticated publication browser journeys on both databases."""

import json
import socket
import subprocess
import threading
import time
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

from tests.google_runtime_fixture import configured_customer
from tests.test_customer_browser_api_journey import localhost_certificate
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_customer_portal import portal_executable
from tests.test_shopify_sales import configuration as configuration


@pytest.mark.parametrize("scenario", ["complete", "unknown", "revoked"])
def historical_contract_configured_google_execution_browser(
    customer_engine: Engine,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    configuration: Settings,
    replicas: Any,
    scenario: str,
) -> None:
    from app.api.customer_campaign_review import router as campaign_router
    from fastapi.staticfiles import StaticFiles

    chromium = portal_executable("chromium", "chromium-browser", "google-chrome")
    alice, base, policy, _, _, server_http, requests, control = configured_customer(
        customer_engine, configuration, tmp_path, monkeypatch, replicas
    )
    alice.app.mount("/app/assets", StaticFiles(directory="app/portal/static"))
    alice.app.include_router(campaign_router)
    wid = int(base.split("/workspaces/")[1].split("/")[0])
    engine = customer_engine
    with Session(engine) as db:
        for model in (ProviderExecutionReview, ProviderExecutionAttempt,
                      ProviderExecutionReceipt, ProviderExposureReservation):
            assert db.scalar(select(func.count()).select_from(model)) == 0
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    origin = f"https://127.0.0.1:{listener.getsockname()[1]}"
    monkeypatch.setattr(settings, "customer_app_origin", origin)
    completed = threading.Event()
    result: list[dict[str, Any]] = []

    async def harness(scope: Scope, receive: Receive, send: Send) -> None:
        path = scope.get("path", "")
        if path == "/__fixture__/driver.mjs":
            script = Path("tests/javascript/configured_google_execution.mjs").read_text()
            script = script.replace("__WORKSPACE__", str(wid)).replace(
                "__POLICY__", json.dumps(policy)
            ).replace("__SCENARIO__", scenario)
            await Response(script, media_type="text/javascript")(scope, receive, send)
            return
        if path == "/__fixture__/unknown":
            server_http.timeout = True
            await JSONResponse({"ok": True})(scope, receive, send)
            return
        if path == "/__fixture__/recover":
            server_http.timeout = False
            await JSONResponse({"ok": True})(scope, receive, send)
            return
        if path == "/__fixture__/revoke-next":
            def revoke() -> None:
                from app.customers.models import CustomerSession
                with Session(engine) as db:
                    for session in db.scalars(select(CustomerSession)):
                        session.revoked_at = int(time.time())
                    db.commit()
            control["qualification_callback"] = revoke
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
        assert completed.wait(60), "Execution browser did not report completion"
        assert result and result[0]["status"] == "passed", result
        assert requests and control["transports_opened"] == control["transports_closed"]
        with Session(engine) as db:
            assert db.scalar(select(func.count()).select_from(ProviderExposureReservation)) == 1
            reservation = db.scalar(select(ProviderExposureReservation))
            assert reservation and reservation.state == "held"
            if scenario == "unknown":
                assert db.scalar(select(func.count()).select_from(ProviderExecutionAttempt)) == 1
                assert server_http.posts == 1 and server_http.activations == 0
            elif scenario == "revoked":
                assert server_http.activations == 0
            else:
                assert server_http.activations > 0
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
