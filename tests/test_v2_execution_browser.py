"""Actual configured V2 handoff and separate approval through TLS customer pages."""

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

from tests.test_customer_browser_api_journey import localhost_certificate
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_customer_optimization_api import headers
from tests.test_customer_portal import portal_executable
from tests.test_shopify_sales import configuration as configuration
from tests.v2_execution_fixture import ready


@pytest.mark.parametrize("unavailable", [False, True])
def test_v2_execution_review_browser(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    replicas: Any,
    unavailable: bool,
) -> None:
    chromium = portal_executable("chromium", "chromium-browser", "google-chrome")
    alice, planning_root, execution_base, query, _, native_server, _, planning = ready(
        customer_engine, configuration, tmp_path, monkeypatch, replicas
    )
    from app.publication.execution_models import (
        ProviderExecutionApproval,
        ProviderExecutionAttempt,
        ProviderExecutionReview,
        ProviderExposureReservation,
        ProviderPeriodLedger,
    )
    from sqlalchemy import func, select

    with Session(customer_engine) as db:
        for model in (ProviderExecutionReview, ProviderExecutionApproval,
                      ProviderExecutionAttempt, ProviderExposureReservation):
            assert db.scalar(select(func.count()).select_from(model)) == 0
    if not unavailable:
        base = execution_base + "/optimization"
        options = alice.post(base + "/target-options", json=query, headers=headers(alice))
        assert options.status_code == 200, options.text
        selection = {**query, "option_id": options.json()["options"][0]["id"]}
        draft = alice.post(base + "/budget-mandates", headers=headers(alice), json={
            "intent": {"selection": selection, "total_cap_micros": 50_000_000,
                       "aggressiveness": "balanced"},
        })
        assert draft.status_code == 201, draft.text
        mandate = draft.json()
        consent = alice.post(base + "/budget-mandates/" + mandate["mandate_id"] + "/consent",
            headers=headers(alice), json={"selection": selection,
                "expected_revision": mandate["revision"], "policy_digest": mandate["policy_digest"],
                "preparation_digest": mandate["preparation_digest"]})
        assert consent.status_code == 200, consent.text
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    origin = f"https://127.0.0.1:{listener.getsockname()[1]}"
    monkeypatch.setattr(settings, "customer_app_origin", origin)
    completed = threading.Event()
    results = []

    async def harness(scope: Scope, receive: Receive, send: Send) -> None:
        path = scope.get("path", "")
        if path == "/__fixture__/start":
            html = Path("app/portal/static/initial-planning.html").read_text().replace(
                "/app/assets/initial-planning.mjs", "/__fixture__/driver.mjs"
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
            script = Path("tests/javascript/v2_execution_browser.mjs").read_text()
            script = script.replace("__UNAVAILABLE__", str(unavailable).lower()).replace(
                "__PLANNING_MANDATE__", planning["mandate_id"]
            )
            await Response(script, media_type="text/javascript")(scope, receive, send)
            return
        if path == "/app/optimization":
            html = Path("app/portal/static/optimization.html").read_text().replace(
                "/app/assets/optimization.mjs", "/__fixture__/approval.mjs"
            )
            await Response(html, media_type="text/html")(scope, receive, send)
            return
        if path == "/__fixture__/approval.mjs":
            script = Path("tests/javascript/v2_execution_approval.mjs").read_text()
            await Response(script, media_type="text/javascript")(scope, receive, send)
            return
        if path.startswith("/app/assets/"):
            name = path.removeprefix("/app/assets/")
            if name in {"initial-planning.mjs", "initial-execution.mjs", "session-context.mjs",
                        "optimization.mjs", "optimization-budget.mjs", "session-automation.mjs",
                        "candidate-read.mjs"}:
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
        assert db.scalar(select(func.count()).select_from(ProviderExecutionReview)) == (
            0 if unavailable else 1
        )
        assert db.scalar(select(func.count()).select_from(ProviderExecutionApproval)) == (
            0 if unavailable else 1
        )
        assert db.scalar(select(func.count()).select_from(ProviderExecutionAttempt)) == 0
        assert db.scalar(select(func.count()).select_from(ProviderExposureReservation)) == 0
        if not unavailable:
            from app.initial_planning.models import PreviewRow
            from app.initial_planning.review_v2_models import InitialPreviewExecutionProofRow

            review = db.scalar(select(ProviderExecutionReview))
            assert review and review.initial_preview_provenance_required
            proof = db.get(InitialPreviewExecutionProofRow, (review.id, review.workspace_id))
            assert proof
            preview = db.get(PreviewRow, proof.document["preview_id"])
            assert preview
            assert preview.document["schema_version"] == "inlet.initial-efficiency-preview.v2"
            assert review.document["plan"]["intent"]["action"]["amount_micros"] == (
                preview.document["after_budget_micros"]
            )
            assert proof.document["planning_mandate"]["mandate_id"] != (
                proof.document["execution_mandate"]["mandate_id"]
            )
            assert db.scalar(select(func.count()).select_from(ProviderPeriodLedger)) == 1
    assert not native_server.posts
