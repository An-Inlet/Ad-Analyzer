"""Actual HTTPS comparison/apply with genuine mocked report and preview services."""

import json
import socket
import subprocess
import threading
import time
from collections.abc import Generator
from dataclasses import replace
from datetime import timedelta
from pathlib import Path

import pytest
import uvicorn
from app.api.customer_initial_planning import get_initial_planning_runtime
from app.customers.access import TTL_SECONDS, CustomerPrincipal
from app.customers.identity import get_identity_provider
from app.customers.models import CustomerSession, CustomerUser
from app.database.session import get_db
from app.main import app
from app.meta.security import utc
from app.meta.sync import MetaSyncService
from app.reported_feedback.contracts import ReportedAcquisitionRequestV1
from app.reported_feedback.models import ReportedFeedbackJob
from app.reported_feedback.runtime import get_reported_feedback_runtime
from app.settings import Settings, settings
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session, sessionmaker
from starlette.responses import JSONResponse, Response
from starlette.types import Receive, Scope, Send

from tests.reported_feedback_journey_fixture import acquired
from tests.reported_original_fixture import customer_engine as customer_engine
from tests.reported_original_fixture import prepare_reported_read
from tests.reported_planning_journey_fixture import PlanningOrigin, baseline_current
from tests.reported_planning_journey_fixture import planning_origin as planning_origin
from tests.reported_read_acquisition_fixture import prepare_reported_acquisition
from tests.test_customer_browser_api_journey import localhost_certificate
from tests.test_customer_identity import FakeProvider
from tests.test_customer_identity import customer_engine as base_customer_engine  # noqa: F401
from tests.test_customer_portal import portal_executable
from tests.test_shopify_sales import configuration as configuration


def test_actual_acquisition_calibration_feedback_browser(
    customer_engine: Engine,
    configuration: Settings,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    planning_origin: PlanningOrigin,
) -> None:
    chromium = portal_executable("chromium", "chromium-browser", "google-chrome")
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    origin = f"https://127.0.0.1:{listener.getsockname()[1]}"
    monkeypatch.setattr(settings, "customer_app_origin", origin)
    engine = customer_engine
    factory = sessionmaker(engine)
    provider = FakeProvider()
    with factory() as db:
        prepared = prepare_reported_read(db, planning_origin.ids)
        data = prepare_reported_acquisition(db, configuration, prepared, monkeypatch)
        wid, principal, runtime, bootstrap, _, _, clock, runner, _, _, _ = data
        original_runner_config = runner.settings
        source_type, source_id = type(data.source), data.source.id
        bootstrap_id = bootstrap.id
        before_sessions = set(db.scalars(select(CustomerSession.digest)))
    runtime_box = [replace(runtime, initial=replace(runtime.initial, session_factory=factory))]

    def database() -> Generator[Session, None, None]:
        with factory() as db:
            yield db

    monkeypatch.setattr(
        app,
        "dependency_overrides",
        {
            get_db: database,
            get_identity_provider: lambda: provider,
            get_reported_feedback_runtime: lambda: runtime_box[0],
            get_initial_planning_runtime: lambda: runtime_box[0].initial,
        },
    )
    completed = threading.Event()
    results = []

    async def harness(scope: Scope, receive: Receive, send: Send) -> None:
        path = scope.get("path", "")
        if path == "/__fixture__/start":
            html = (
                Path("app/portal/static/reported-comparison.html")
                .read_text()
                .replace("/app/assets/reported-comparison.mjs", "/__fixture__/driver.mjs")
            )
            await Response(html, media_type="text/html")(scope, receive, send)
            return
        if path == "/__fixture__/driver.mjs":
            script = Path("tests/javascript/reported_feedback_actual_browser.mjs").read_text()
            for key, replacement in {"WORKSPACE": wid}.items():
                script = script.replace(f"__{key}__", str(replacement))
            for suffix in ("actual", "rotated"):
                literal = "'reported-browser:" + suffix + "'"
                assert script.count(literal) == 1
                script = script.replace(
                    literal, json.dumps(planning_origin.ids.actor_id + ":" + suffix)
                )
            await Response(script, media_type="text/javascript")(scope, receive, send)
            return
        if path == "/__fixture__/acquire":
            try:
                with factory() as db:
                    jobs = list(db.scalars(
                        select(ReportedFeedbackJob).where(
                            ReportedFeedbackJob.workspace_id == wid,
                            ReportedFeedbackJob.state.not_in(("blocked", "expired")),
                        )
                    ))
                    assert len(jobs) == 1
                    job = jobs[0]
                    assert job.id != bootstrap_id
                    assert (
                        job.original_actor_id, job.original_attempt_id, job.account_id,
                        job.campaign_id, job.source_connection_id,
                    ) == (
                        planning_origin.ids.actor_id, planning_origin.ids.attempt_id,
                        planning_origin.ids.account_id, planning_origin.ids.campaign_id,
                        planning_origin.ids.source_id,
                    )
                    user = db.get(CustomerUser, job.original_actor_id)
                    session = db.get(CustomerSession, job.original_session_digest)
                    source = db.get(source_type, source_id)
                    assert user and session and source
                    assert session.user_id == user.id
                    assert session.digest not in before_sessions
                    assert source.generation == job.source_generation
                    request = ReportedAcquisitionRequestV1.model_validate(job.document)
                    assert (request.before, request.after) == (
                        data.request.before, data.request.after
                    )
                    assert job.next_due_at is not None
                    prior_clock = clock[0]
                    clock[0] = max(clock[0], utc(job.next_due_at) + timedelta(seconds=1))
                    (tmp_path / "job-due-clock.json").write_text(json.dumps({
                        "prior_clock": prior_clock.isoformat(),
                        "actual_job_due": utc(job.next_due_at).isoformat(),
                        "acquisition_clock": clock[0].isoformat(),
                        "advance_seconds": (clock[0] - prior_clock).total_seconds(),
                    }, indent=2))
                    current = data._replace(
                        principal=CustomerPrincipal(user, session),
                        runtime=runtime_box[0], job=job, request=request, source=source,
                        runner=MetaSyncService(
                            db, original_runner_config, reported_feedback=runtime_box[0]
                        ),
                    )
                    actual, updated, observation = acquired(
                        db, configuration, tmp_path, monkeypatch, data=current
                    )
                    assert actual is current
                    updated, value, reads = baseline_current(
                        db, current, updated, observation, planning_origin, tmp_path, monkeypatch
                    )
                    runtime_box[0] = updated
                    assert value.after_budget_micros == 46_000_000
                    assert planning_origin.ids.original_post_count == 1 and reads.server.posts == []
                await JSONResponse({"ok": True})(scope, receive, send)
            except Exception as exc:
                import traceback

                traceback.print_exc()
                await JSONResponse({"error": str(exc)}, status_code=500)(scope, receive, send)
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
        with factory() as db:
            added = list(db.scalars(select(CustomerSession).where(
                CustomerSession.digest.not_in(before_sessions)
            )))
            assert len(added) == 2
            assert all(row.user_id == planning_origin.ids.actor_id for row in added)
            assert all(row.expires_at - row.created_at == TTL_SECONDS for row in added)
            browser_jobs = list(db.scalars(select(ReportedFeedbackJob).where(
                ReportedFeedbackJob.original_session_digest.in_([row.digest for row in added])
            )))
            assert len(browser_jobs) == 1
            rotated = [
                row for row in added if row.digest != browser_jobs[0].original_session_digest
            ]
            assert len(rotated) == 1 and rotated[0].revoked_at is not None
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
