"""TLS browser consumes the real configured v2 producer and feedback API."""

import json
import socket
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

import pytest
import uvicorn
from app.customers.access import TTL_SECONDS
from app.customers.models import CustomerSession
from app.settings import Settings, settings
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session
from starlette.responses import JSONResponse, Response
from starlette.types import Receive, Scope, Send

from tests.configured_planning_read_fixture import configured_journey
from tests.reported_original_fixture import customer_engine as customer_engine
from tests.reported_planning_journey_fixture import PlanningOrigin
from tests.reported_planning_journey_fixture import planning_origin as planning_origin
from tests.test_customer_browser_api_journey import localhost_certificate
from tests.test_customer_identity import customer_engine as base_customer_engine  # noqa: F401
from tests.test_customer_identity import replicas as replicas
from tests.test_customer_portal import portal_executable
from tests.test_shopify_sales import configuration as configuration


def test_configured_v2_browser(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    replicas: Any,
    planning_origin: PlanningOrigin,
) -> None:
    chromium = portal_executable("chromium", "chromium-browser", "google-chrome")
    with Session(customer_engine) as db:
        alice, _, wid, _, _, _, _, _, _, _ = configured_journey(
            db, customer_engine, configuration, tmp_path, monkeypatch, replicas,
            origin=planning_origin,
        )
        before_sessions = set(db.scalars(select(CustomerSession.digest)))
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    origin = f"https://127.0.0.1:{listener.getsockname()[1]}"
    monkeypatch.setattr(settings, "customer_app_origin", origin)
    completed = threading.Event()
    results = []

    async def harness(scope: Scope, receive: Receive, send: Send) -> None:
        path = scope.get("path", "")
        if path == "/__fixture__/start":
            html = Path("app/portal/static/reported-comparison.html").read_text().replace(
                "/app/assets/reported-comparison.mjs", "/__fixture__/driver.mjs"
            )
            response = Response(html, media_type="text/html")
            # Transfer the actual API-created original session into the browser;
            # no new session/approval is fabricated or substituted for the job.
            for cookie in alice.cookies.jar:
                assert cookie.value is not None
                response.set_cookie(
                    cookie.name, cookie.value, secure=True, samesite="strict",
                    httponly="csrf" not in cookie.name.lower(),
                )
            await response(scope, receive, send)
            return
        if path == "/__fixture__/driver.mjs":
            script = Path("tests/javascript/reported_feedback_actual_browser.mjs").read_text()
            start = script.index("assert((await fetch('/api/customer/v1/session'")
            end = script.index("$('refresh').click();", start)
            script = (
                script[:start] + "await import('/app/assets/reported-comparison.mjs');\n"
                + script[end:]
            )
            script = script.replace("__WORKSPACE__", str(wid))
            script = script.replace("USD 47", "USD 45.75").replace(
                "computed47 from46 baseline", "configured policy adjusts46 to45.75"
            )
            rotation = "'reported-browser:rotated'"
            assert script.count(rotation) == 1
            script = script.replace(rotation, json.dumps(planning_origin.ids.actor_id + ":rotated"))
            await Response(script, media_type="text/javascript")(scope, receive, send)
            return
        if path.startswith("/app/assets/"):
            name = path.removeprefix("/app/assets/")
            if name in {"reported-comparison.mjs", "session-context.mjs"}:
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
        (tmp_path / "browser-result.json").write_text(json.dumps(results, indent=2))
        assert results and results[0]["status"] == "passed", results
        with Session(customer_engine) as db:
            added = list(db.scalars(select(CustomerSession).where(
                CustomerSession.digest.not_in(before_sessions)
            )))
            assert len(added) == 1
            assert added[0].user_id == planning_origin.ids.actor_id
            assert added[0].expires_at - added[0].created_at == TTL_SECONDS
            assert added[0].revoked_at is not None
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
