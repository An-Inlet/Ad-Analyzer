"""Actual HTTPS comparison/apply with genuine mocked report and preview services."""

import json
import socket
import subprocess
import threading
import time
from collections.abc import Generator
from dataclasses import replace
from pathlib import Path

import pytest
import uvicorn
from app.api import customer as customer_api
from app.api.customer_initial_planning import get_initial_planning_runtime
from app.customers.access import CustomerPrincipal
from app.customers.identity import get_identity_provider
from app.customers.models import CustomerSession, CustomerUser
from app.database.session import Base, get_db
from app.main import app
from app.meta.sync import MetaSyncService
from app.reported_feedback.contracts import ReportedAcquisitionRequestV1
from app.reported_feedback.models import ReportedFeedbackJob
from app.reported_feedback.runtime import get_reported_feedback_runtime
from app.settings import Settings, settings
from sqlalchemy import Engine, create_engine, event, select
from sqlalchemy.orm import Session, sessionmaker
from starlette.responses import JSONResponse, Response
from starlette.types import Receive, Scope, Send

from tests.reported_feedback_journey_fixture import acquired, baseline
from tests.test_customer_browser_api_journey import localhost_certificate
from tests.test_customer_identity import FakeProvider
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_portal import portal_executable
from tests.test_reported_feedback_acquisition import acquisition_fixture
from tests.test_shopify_sales import configuration as configuration


def test_actual_acquisition_calibration_feedback_browser(
    customer_engine: Engine,
    configuration: Settings,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    chromium = portal_executable("chromium", "chromium-browser", "google-chrome")
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    origin = f"https://127.0.0.1:{listener.getsockname()[1]}"
    monkeypatch.setattr(settings, "customer_app_origin", origin)
    engine = customer_engine
    if engine.dialect.name == "sqlite":
        engine = create_engine(
            f"sqlite:///{tmp_path / 'planning.sqlite'}", connect_args={"check_same_thread": False}
        )
        event.listen(
            engine, "connect", lambda connection, _: connection.execute("PRAGMA foreign_keys=ON")
        )
        Base.metadata.create_all(engine)
    factory = sessionmaker(engine)
    provider = FakeProvider()
    # Login remains real; the long fixture lease spans the explicit future closed
    # reporting window without inventing a customer session row for the browser.
    monkeypatch.setattr(customer_api, "TTL_SECONDS", 60 * 86400)
    with factory() as db:
        data = acquisition_fixture(db, configuration, tmp_path, monkeypatch)
        wid, principal, runtime, _, _, _, clock, runner, _, _, _ = data
        user = db.get(CustomerUser, principal.user.id)
        assert user
        user.subject = "reported-browser"
        db.commit()
        original_runner_config = runner.settings
        source_type, source_id = type(data[5]), data[5].id
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
            for key, value in {"WORKSPACE": wid}.items():
                script = script.replace(f"__{key}__", str(value))
            await Response(script, media_type="text/javascript")(scope, receive, send)
            return
        if path == "/__fixture__/acquire":
            try:
                with factory() as db:
                    job = db.scalar(
                        select(ReportedFeedbackJob).where(
                            ReportedFeedbackJob.workspace_id == wid,
                            ReportedFeedbackJob.state.not_in(("blocked", "expired")),
                        )
                    )
                    assert job is not None
                    user = db.get(CustomerUser, job.original_actor_id)
                    session = db.get(CustomerSession, job.original_session_digest)
                    assert user and session
                    current = list(data)
                    current[1] = CustomerPrincipal(user, session)
                    current[2] = runtime_box[0]
                    current[3] = job
                    current[4] = ReportedAcquisitionRequestV1.model_validate(job.document)
                    current[5] = db.get(source_type, source_id)
                    current[7] = MetaSyncService(
                        db, original_runner_config, reported_feedback=runtime_box[0]
                    )
                    actual, updated, observation = acquired(
                        db, configuration, tmp_path, monkeypatch, data=tuple(current)
                    )
                    updated, value = baseline(db, actual, updated, observation)
                    runtime_box[0] = updated
                    assert value.after_budget_micros == 46_000_000
                    assert len(data[10].posts) == 1
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
        if engine is not customer_engine:
            engine.dispose()
