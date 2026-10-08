"""Actual HTTPS reported-rule consumer with configured worker and MockHTTP only."""

import asyncio
import json
import socket
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

import pytest
import uvicorn
from app.api.customer_goals import router as goal_router
from app.customers.access import SESSION_COOKIE, digest
from app.customers.models import CustomerSession
from app.jobs.customer_runtime import run_customer_tick
from app.publication.execution_models import ProviderExecutionApproval, ProviderExposureReservation
from app.reported_feedback.models import ReportedWindowCapsule
from app.settings import Settings, settings
from fastapi.staticfiles import StaticFiles
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session
from starlette.responses import JSONResponse, Response
from starlette.types import Receive, Scope, Send

from tests.configured_reported_rule_fixture import configured_reported_customer
from tests.test_customer_browser_api_journey import localhost_certificate
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_customer_portal import portal_executable
from tests.test_shopify_sales import configuration as configuration


@pytest.mark.parametrize("change", ["none", "lost_start", "erasure", "revoked"])
def historical_contract_configured_reported_rule_browser(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    replicas: Any,
    change: str,
) -> None:
    chromium = portal_executable("chromium", "chromium-browser", "google-chrome")
    alice, base, wire, clock, _, _, _, _, _ = configured_reported_customer(
        customer_engine, configuration, tmp_path, monkeypatch, replicas
    )
    wid = int(base.split("/workspaces/")[1].split("/")[0])
    alice.app.include_router(goal_router)
    alice.app.mount("/app/assets", StaticFiles(directory="app/portal/static"))
    with Session(customer_engine) as db:
        approvals = db.scalar(select(func.count()).select_from(ProviderExecutionApproval))
    assert len(wire.meta.posts) == 1
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    origin = f"https://127.0.0.1:{listener.getsockname()[1]}"
    monkeypatch.setattr(settings, "customer_app_origin", origin)
    completed = threading.Event()
    results = []
    failures = []
    ticks = 0

    async def harness(scope: Scope, receive: Receive, send: Send) -> None:
        nonlocal ticks
        path = scope.get("path", "")
        if path == "/__fixture__/start":
            html = Path("app/portal/static/optimization.html").read_text().replace(
                "/app/assets/optimization.mjs", "/__fixture__/driver.mjs"
            )
            response = Response(html, media_type="text/html")
            # Transfer the actual API-created original session into the browser;
            # no new session/approval is fabricated or substituted for the job.
            for cookie in alice.cookies.jar:
                response.set_cookie(
                    cookie.name, cookie.value, secure=True, samesite="strict",
                    httponly="csrf" not in cookie.name.lower(),
                )
            await response(scope, receive, send)
            return
        if path == "/__fixture__/driver.mjs":
            script = Path("tests/javascript/reported_rule_actual.mjs").read_text()
            script = script.replace("__WORKSPACE__", str(wid)).replace("__CHANGE__", change)
            await Response(script, media_type="text/javascript")(scope, receive, send)
            return
        if path == "/__fixture__/tick":
            from datetime import timedelta

            ticks += 1
            if ticks > 1 and change in {"erasure", "revoked"}:
                with Session(customer_engine) as db:
                    if change == "erasure":
                        capsule = db.scalar(select(ReportedWindowCapsule))
                        if capsule is not None:
                            db.delete(capsule)
                    else:
                        original = db.get(CustomerSession, digest(alice.cookies[SESSION_COOKIE]))
                        assert original
                        original.revoked_at = int(clock[0].timestamp())
                    db.commit()
            result = await asyncio.to_thread(
                run_customer_tick, customer_engine, configuration=settings, now=clock[0]
            )
            clock[0] += timedelta(seconds=31)
            await JSONResponse(result)(scope, receive, send)
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
        async def traced_send(message: Any) -> None:
            if message["type"] == "http.response.start" and message["status"] >= 400:
                failures.append((path, message["status"]))
            await send(message)

        await alice.app(scope, receive, traced_send)
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
        assert completed.wait(90), "Browser did not report completion"
        assert results and results[0]["status"] == "passed", (results, failures)
        assert len(wire.meta.posts) == (1 if change in {"erasure", "revoked"} else 2)
        with Session(customer_engine) as db:
            assert (
                db.scalar(select(func.count()).select_from(ProviderExecutionApproval)) == approvals
            )
            assert db.scalar(
                select(func.count()).select_from(ProviderExposureReservation).where(
                    ProviderExposureReservation.state == "held"
                )
            ) == 1
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
