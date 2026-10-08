"""Ordinary configured optimization APIs, actual TLS browser and MockHTTP adapters."""

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

from tests.configured_optimization_fixture import configured
from tests.test_customer_browser_api_journey import localhost_certificate
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_customer_portal import portal_executable
from tests.test_shopify_sales import configuration as configuration


@pytest.mark.parametrize("platform", ["google_ads", "meta_ads"])
@pytest.mark.parametrize("scenario", ["complete", "unknown", "revoked"])
def historical_contract_configured_optimization_browser(
    customer_engine: Engine,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    configuration: Settings,
    replicas: Any,
    scenario: str,
    platform: str,
) -> None:
    from app.api.customer_goals import router as goal_router
    from fastapi.staticfiles import StaticFiles

    chromium = portal_executable("chromium", "chromium-browser", "google-chrome")
    alice, base, query, wire, control = configured(
        customer_engine, configuration, tmp_path, monkeypatch, replicas, platform
    )
    alice.app.mount("/app/assets", StaticFiles(directory="app/portal/static"))
    alice.app.include_router(goal_router)
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

    async def harness(scope: Scope, receive: Receive, send: Send) -> None:
        path = scope.get("path", "")
        if path == "/__fixture__/driver.mjs":
            script = Path("tests/javascript/configured_optimization.mjs").read_text()
            script = (
                script.replace("__WORKSPACE__", str(wid))
                .replace("__PLATFORM__", platform)
                .replace("__SCENARIO__", scenario)
                .replace("__GOAL__", query["goal_id"])
                .replace("__ACCOUNT__", str(query["account_id"]))
            )
            await Response(script, media_type="text/javascript")(scope, receive, send)
            return
        if path == "/__fixture__/unknown":
            native = wire.google if platform == "google_ads" else wire.meta
            native.ignore = native.timeout = True
            await JSONResponse({"ok": True})(scope, receive, send)
            return
        if path == "/__fixture__/recover":
            (wire.google if platform == "google_ads" else wire.meta).timeout = False
            await JSONResponse({"ok": True})(scope, receive, send)
            return
        if path == "/__fixture__/revoke-next":

            def revoke() -> None:
                from app.customers.models import CustomerSession

                with Session(engine) as db:
                    for session in db.scalars(select(CustomerSession)):
                        session.revoked_at = int(time.time())
                    db.commit()

            control["callback"] = revoke
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
                Path("app/portal/static/optimization.html")
                .read_text()
                .replace("/app/assets/optimization.mjs", "/__fixture__/driver.mjs")
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
        assert control["opened"] > 0 and control["opened"] == control["closed"]
        with Session(engine) as db:
            if scenario == "revoked":
                assert db.scalar(select(func.count()).select_from(ProviderExecutionReview)) == 0
                assert db.scalar(select(func.count()).select_from(ProviderExposureReservation)) == 0
            else:
                assert db.scalar(select(func.count()).select_from(ProviderExposureReservation)) == 1
                reservation = db.scalar(select(ProviderExposureReservation))
                assert reservation and reservation.state == "held"
                assert db.scalar(select(func.count()).select_from(ProviderExecutionAttempt)) == 1
            writes = wire.google.writes if platform == "google_ads" else wire.meta.posts
            assert len(writes) == (0 if scenario == "revoked" else 1)
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
