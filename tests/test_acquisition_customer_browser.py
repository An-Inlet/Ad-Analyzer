"""Real TLS page -> actual owned API -> worker -> newly produced independent publication."""

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
from app.api import customer_commerce, customer_goals
from app.commerce.acquisition_models import CommerceAcquisitionJob as Job
from app.commerce.models import CommerceMeasurementPublication
from app.commerce.publication_contracts import IndependentManifest
from app.customers.models import CustomerSession
from app.jobs import commerce_acquisition_worker as runner
from app.portal.router import STATIC
from app.portal.router import router as portal
from app.settings import Settings, settings
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session
from starlette.responses import JSONResponse, Response
from starlette.staticfiles import StaticFiles
from starlette.types import Message, Receive, Scope, Send

from tests.test_commerce_acquisition_jobs import configured
from tests.test_customer_browser_api_journey import localhost_certificate
from tests.test_customer_identity import FakeProvider
from tests.test_customer_portal import portal_executable
from tests.test_independent_publications import (
    configuration as configuration,
)
from tests.test_independent_publications import (
    customer_engine as customer_engine,
)
from tests.test_independent_publications import (
    replicas as replicas,
)


def test_actual_customer_window_request_recovery_worker_and_cancel(
    customer_engine: Engine,
    configuration: Settings,
    replicas: tuple[TestClient, TestClient, FakeProvider],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    owned, request, fixture, client, provider, _, _, _ = configured(
        customer_engine,
        configuration,
        replicas,
        monkeypatch,
        tmp_path,
    )
    app = client.app
    app.include_router(customer_commerce.router)
    app.include_router(customer_goals.router)
    app.include_router(portal)
    app.mount("/app/assets", StaticFiles(directory=STATIC))
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    origin = f"https://127.0.0.1:{listener.getsockname()[1]}"
    monkeypatch.setattr(settings, "customer_app_origin", origin)
    monkeypatch.setattr(configuration, "customer_app_origin", origin)
    done = threading.Event()
    results: list[dict[str, Any]] = []
    observed: list[IndependentManifest] = []
    holding = False
    entered, release = asyncio.Event(), asyncio.Event()

    async def harness(scope: Scope, receive: Receive, send: Send) -> None:
        nonlocal holding
        path = scope.get("path", "")
        if path == "/__fixture__/hold":
            holding = True
            entered.clear()
            release.clear()
            await JSONResponse({"ok": True})(scope, receive, send)
            return
        if path == "/__fixture__/held":
            await asyncio.wait_for(entered.wait(), 15)
            await JSONResponse({"ok": True})(scope, receive, send)
            return
        if path == "/__fixture__/release":
            release.set()
            await JSONResponse({"ok": True})(scope, receive, send)
            return
        if path in {"/__fixture__/disable", "/__fixture__/enable"}:
            configuration.customer_independent_acquisition_enabled = path.endswith("/enable")
            await JSONResponse({"ok": True})(scope, receive, send)
            return

        if path == "/__fixture__/start":
            html = (
                (STATIC / "measurement-history.html")
                .read_text()
                .replace("/app/assets/measurement-history.mjs", "/__fixture__/driver.mjs")
            )
            response = Response(html, media_type="text/html")
            for cookie in client.cookies.jar:
                assert cookie.value is not None
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
            await Response(
                Path("tests/javascript/acquisition_api_browser.mjs").read_text(),
                media_type="text/javascript",
            )(scope, receive, send)
            return
        if path == "/__fixture__/tick":
            await asyncio.to_thread(runner.tick, customer_engine, configuration, lambda: provider)
            await JSONResponse({"ok": True})(scope, receive, send)
            return
        if path == "/__fixture__/revoke":
            with Session(customer_engine) as db:
                jobs = list(
                    db.scalars(select(Job).where(Job.workspace_id == request.scope.workspace_id))
                )
                assert sorted(job.state for job in jobs) == ["cancelled", "completed", "pending"]
                completed = next(job for job in jobs if job.state == "completed")
                publication = db.get(CommerceMeasurementPublication, completed.publication_id)
                assert publication is not None
                observed.append(IndependentManifest.model_validate(publication.manifest))
                for session in db.scalars(select(CustomerSession)):
                    session.revoked_at = int(time.time())
                db.commit()
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
        if path.endswith("/commerce/acquisitions") and scope["method"] == "GET" and holding:
            holding = False
            messages: list[Message] = []

            async def collect(message: Message) -> None:
                messages.append(message)

            await app(scope, receive, collect)
            entered.set()
            await asyncio.wait_for(release.wait(), 20)
            for message in messages:
                await send(message)
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
        assert done.wait(90), "Acquisition browser did not finish"
        assert results and results[0]["status"] == "passed", json.dumps(results, indent=2)
        assert len(fixture.seen) == 5
        assert len(observed) == 1
        assert (
            observed[0].correction_status == "unresolved" and observed[0].maturity == "unqualified"
        )
        with Session(customer_engine) as db:
            assert list(db.scalars(select(Job))) == []  # Existing session-erasure lifecycle.
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
