"""Explicit October2026 Q16 browser experiment; not default pytest collection."""

import asyncio
import json
import socket
import subprocess
import threading
import time
from collections.abc import Generator
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Literal

import pytest
import uvicorn
from app.api import customer as customer_api
from app.api import customer_planning_documents as api
from app.customers.identity import get_identity_provider, verified_identity
from app.database.session import get_db
from app.lifecycle.privacy import bump_workspace_export_revision
from app.main import app
from app.planning_documents.models import PlanEventRow, PlanVersionRow
from app.publication.execution_models import ProviderExecutionAttempt
from app.settings import Settings, settings
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session
from starlette.responses import JSONResponse, Response
from starlette.types import Message, Receive, Scope, Send

from tests import test_customer_identity, test_customer_optimization_api
from tests.q16_clock_feasibility_probe import NOV3, paid
from tests.q16_exact_acceptance import retained_counts
from tests.q16_fixture import import_progress_stage, prepare_q16_case
from tests.test_customer_browser_api_journey import localhost_certificate
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_customer_portal import portal_executable
from tests.test_shopify_sales import configuration as configuration

pytestmark = pytest.mark.planning_boundary


@pytest.mark.parametrize("generation_stage", ["nov3", "october"])
@pytest.mark.parametrize("branch", ["progress", "privacy"])
def test_dated_q16_browser(
    customer_engine: Engine, configuration: Settings, replicas: Any,
    generation_stage: Literal["nov3", "october"],
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, branch: Literal["progress", "privacy"],
) -> None:
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    origin = f"https://127.0.0.1:{listener.getsockname()[1]}"
    monkeypatch.setattr(test_customer_identity, "ORIGIN", origin)
    monkeypatch.setattr(test_customer_optimization_api, "ORIGIN", origin)
    monkeypatch.setattr(settings, "customer_app_origin", origin)
    for client in replicas[:2]:
        client.base_url = origin
    calls: list[str] = []
    ids = prepare_q16_case(customer_engine, configuration, replicas, monkeypatch, tmp_path,
                           branch=branch, native_calls=calls, generation_stage=generation_stage)
    alice, _, provider = replicas
    base = f"/api/customer/v1/workspaces/{ids.workspace_id}/planning/plans/{ids.plan_id}"
    original = alice.get(base + "/export", params={"version": 1})
    assert original.status_code == 200, original.text
    expected = original.json()
    (tmp_path / "original-artifact.json").write_text(json.dumps(expected, indent=2))
    (tmp_path / "fixture-ids.json").write_text(json.dumps(asdict(ids), indent=2))
    original_document_bytes = json.dumps(
        expected["document"], separators=(",", ":"), ensure_ascii=False
    )
    initial_counts = retained_counts(customer_engine)
    native_count = len(calls)
    now = NOV3 if generation_stage == "nov3" else datetime.now(UTC)
    fixed_stage = generation_stage == "nov3"
    issued = 0
    state: dict[str, Any] = {"hold": False, "held": False, "release": None, "reads": []}
    complete = threading.Event()
    results: list[dict[str, Any]] = []

    def database() -> Generator[Session, None, None]:
        with Session(customer_engine) as db:
            yield db

    monkeypatch.setattr(app, "dependency_overrides", {
        get_db: database, get_identity_provider: lambda: provider,
    })

    async def harness(scope: Scope, receive: Receive, send: Send) -> None:
        nonlocal now, issued, fixed_stage
        path = scope.get("path", "")
        if path == "/__fixture__/start":
            html = Path("app/portal/static/planning.html").read_text().replace(
                "/app/assets/planning.mjs", "/__fixture__/driver.mjs"
            )
            await Response(html, media_type="text/html")(scope, receive, send)
            return
        if path == "/__fixture__/driver.mjs":
            source = Path("tests/javascript/q16_browser.mjs").read_text()
            browser_data = dict(ids=asdict(ids), branch=branch, expected=expected,
                                generation_stage=generation_stage)
            await Response(source.replace("__CASE__", json.dumps(browser_data)),
                           media_type="text/javascript")(scope, receive, send)
            return
        if path == "/api/customer/v1/session" and scope["method"] == "POST":
            # Same narrow issuance seam as issue_at, but this is the actual browser HTTPS POST.
            issued += 1
            stamp = int((now if fixed_stage else datetime.now(UTC)).timestamp())
            project = provider.issuer.rsplit("/", 1)[1]
            real_time = time.time

            def verify(token: str) -> Any:
                assert token == f"q16-browser-{issued}"
                provider.check_active("q16-owner", stamp)
                return verified_identity(dict(
                    iss=provider.issuer, aud=project, sub="q16-owner", email="same@example.test",
                    email_verified=True, auth_time=stamp, iat=stamp, exp=stamp + 3600,
                ), project, stamp)

            with pytest.MonkeyPatch.context() as issue:
                issue.setattr(customer_api, "time", SimpleNamespace(time=lambda: stamp))
                issue.setattr(provider, "verify", verify)
                await app(scope, receive, send)
                assert time.time is real_time
            assert vars(customer_api)["time"] is time
            return
        if path in {"/__fixture__/initial_day", "/__fixture__/later_day",
                    "/__fixture__/refund_correction"}:
            stage: Literal["initial_day", "later_day", "refund_correction"] = (
                "initial_day" if path.endswith("initial_day") else
                "later_day" if path.endswith("later_day") else "refund_correction"
            )
            fixed_stage = True
            now = import_progress_stage(customer_engine, configuration, ids, stage=stage)
            paid(customer_engine, ids.workspace_id, now, monkeypatch, initial=False)
            monkeypatch.setattr(api, "utc_now", lambda: now)
            await JSONResponse({"ok": True, "as_of": now.isoformat()})(scope, receive, send)
            return
        if path == "/__fixture__/hold":
            state["hold"] = True
            await JSONResponse({"ok": True})(scope, receive, send)
            return
        if path == "/__fixture__/held":
            await JSONResponse({"held": state["held"]})(scope, receive, send)
            return
        if path == "/__fixture__/erase":
            with Session(customer_engine) as db:
                bump_workspace_export_revision(db, ids.workspace_id)
                db.commit()
            await JSONResponse({"ok": True})(scope, receive, send)
            return
        if path == "/__fixture__/release":
            assert state["release"] is not None
            state["release"].set()
            await JSONResponse({"ok": True})(scope, receive, send)
            return
        if path == base + "/progress":
            before = retained_counts(customer_engine)
            messages: list[Message] = []

            async def capture(message: Message) -> None:
                messages.append(message)

            await app(scope, receive, capture)
            assert retained_counts(customer_engine) == before
            raw = b"".join(message.get("body", b"") for message in messages)
            status = messages[0]["status"]
            state["reads"].append(dict(status=status, body=json.loads(raw)))
            if state["hold"]:
                assert status == 200
                state["hold"] = False
                release = asyncio.Event()
                state["release"], state["held"] = release, True
                await asyncio.wait_for(release.wait(), 30)
            for message in messages:
                await send(message)
            return
        if path == "/__fixture__/result":
            data = bytearray()
            while True:
                message = await receive()
                data.extend(message.get("body", b""))
                if not message.get("more_body", False):
                    break
            results.append(json.loads(data))
            await JSONResponse({"ok": True})(scope, receive, send)
            complete.set()
            return
        await app(scope, receive, send)

    cert, key = localhost_certificate(tmp_path)
    server = uvicorn.Server(uvicorn.Config(harness, lifespan="off", log_level="critical",
                                          ssl_certfile=str(cert), ssl_keyfile=str(key)))
    thread = threading.Thread(target=lambda: server.run(sockets=[listener]), daemon=True)
    thread.start()
    deadline = time.monotonic() + 10
    while not server.started and thread.is_alive() and time.monotonic() < deadline:
        time.sleep(.01)
    assert server.started
    browser = subprocess.Popen([
        portal_executable("chromium", "chromium-browser", "google-chrome"),
        "--headless", "--no-sandbox", "--disable-gpu", "--ignore-certificate-errors",
        "--disable-background-networking", "--no-first-run", "--disable-extensions",
        "--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1",
        f"--user-data-dir={tmp_path / 'browser'}", origin + "/__fixture__/start",
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        assert complete.wait(150), "Dated Q16 browser did not finish"
        (tmp_path / "browser-result.json").write_text(json.dumps(results, indent=2))
        (tmp_path / "progress-responses.json").write_text(json.dumps(state["reads"], indent=2))
        assert results and results[0]["status"] == "passed", results
        assert len(calls) == native_count
        successes = [r["body"] for r in state["reads"] if r["status"] == 200]
        assert successes and all(r["goal"] == successes[0]["goal"] for r in successes)
        assert all(r["document_digest"] == ids.document_digest for r in successes)
        assert successes[0]["sales"]["coverage"]["starts_at"] == "2026-11-01T04:00:00Z"
        assert successes[0]["sales"]["coverage"]["ends_at_exclusive"] == "2026-11-03T05:00:00Z"
        if branch == "progress":
            assert [r["net_sales_micros_exact"] for r in successes] == ["0", "25000000", "20000000"]
            assert [r["sales"]["coverage"]["closed_day_count"] for r in successes] == [2, 3, 3]
            assert successes[-1]["sales"]["coverage"]["ends_at_exclusive"] == "2026-11-04T05:00:00Z"
            expected_events = 2 if generation_stage == "october" else 0
            assert retained_counts(customer_engine)[:7] == (
                initial_counts[0], initial_counts[1],
                int(initial_counts[2] or 0) + expected_events, expected_events,
                *initial_counts[4:7],
            )
            assert results[0]["document_bytes"] == original_document_bytes
        with Session(customer_engine) as db:
            assert db.scalar(select(func.count()).select_from(PlanVersionRow)) == (
                1 if branch == "progress" else 0
            )
            assert db.scalar(select(func.count()).select_from(PlanEventRow)) == (
                2 if generation_stage == "october" and branch == "progress" else 0
            )
            assert db.scalar(select(func.count()).select_from(ProviderExecutionAttempt)) == 0
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
