"""Actual TLS first-customer budget consent without prior production authority."""

import json
import socket
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

import pytest
import uvicorn
from app.settings import Settings, settings
from sqlalchemy import Engine
from sqlalchemy.orm import Session
from starlette.responses import JSONResponse, Response
from starlette.types import Receive, Scope, Send

from tests.budget_mandate_fixture import first_customer
from tests.test_customer_browser_api_journey import localhost_certificate
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_customer_portal import portal_executable
from tests.test_shopify_sales import configuration as configuration


@pytest.mark.parametrize("unavailable", [False, True])
def test_first_customer_budget_browser(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    replicas: Any,
    unavailable: bool,
) -> None:
    chromium = portal_executable("chromium", "chromium-browser", "google-chrome")
    alice, _, _, _, requests, _, _, native_server = first_customer(
        customer_engine, configuration, tmp_path, monkeypatch, replicas
    )
    from app.initial_planning.planning_consent_models import PlanningConsentRow
    from app.publication.execution_models import (
        ProviderExecutionAttempt,
        ProviderExecutionConsent,
        ProviderExecutionMandate,
        ProviderExposureReservation,
    )
    from sqlalchemy import func, select

    with Session(customer_engine) as db:
        for model in (
            ProviderExecutionMandate,
            ProviderExecutionConsent,
            ProviderExecutionAttempt,
            ProviderExposureReservation,
        ):
            assert db.scalar(select(func.count()).select_from(model)) == 0
    if unavailable:
        monkeypatch.setattr(settings, "budget_mandate_policy_path", None)
        monkeypatch.setattr(settings, "budget_mandate_policy_digest", None)
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    origin = f"https://127.0.0.1:{listener.getsockname()[1]}"
    monkeypatch.setattr(settings, "customer_app_origin", origin)
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
            response = Response(html, media_type="text/html")
            # Transfer the actual API-created original session into the browser;
            # no new session/approval is fabricated or substituted for the job.
            for cookie in alice.cookies.jar:
                response.set_cookie(
                    cookie.name,
                    cookie.value,
                    secure=True,
                    samesite="strict",
                    httponly="csrf" not in cookie.name.lower(),
                )
            await response(scope, receive, send)
            return
        if path == "/__fixture__/driver.mjs":
            script = Path("tests/javascript/initial_budget_mandate_browser.mjs").read_text()
            script = script.replace("__UNAVAILABLE__", str(unavailable).lower())
            await Response(script, media_type="text/javascript")(scope, receive, send)
            return
        if path.startswith("/app/assets/"):
            name = path.removeprefix("/app/assets/")
            if name in {
                "initial-planning.mjs",
                "initial-execution.mjs",
                "initial-automation.mjs",
                "session-context.mjs",
            }:
                await Response(
                    Path("app/portal/static", name).read_text(), media_type="text/javascript"
                )(scope, receive, send)
                return
        if path == "/__fixture__/result":
            body = bytearray()
            while True:
                event = await receive()
                body.extend(event.get("body", b""))
                if not event.get("more_body", False):
                    break
            results.append(json.loads(body))
            await JSONResponse({"ok": True})(scope, receive, send)
            completed.set()
            return
        await alice.app(scope, receive, send)

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
            "--window-size=1365,1100",
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
        assert completed.wait(90), "Browser did not report completion"
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
    with Session(customer_engine) as db:
        assert db.scalar(select(func.count()).select_from(ProviderExecutionConsent)) == 0
        assert db.scalar(select(func.count()).select_from(PlanningConsentRow)) == (
            0 if unavailable else 1
        )
        assert db.scalar(select(func.count()).select_from(ProviderExecutionAttempt)) == 0
        assert db.scalar(select(func.count()).select_from(ProviderExposureReservation)) == 0
    assert requests and all(request.method == "GET" for request in requests)
    assert not native_server.posts
