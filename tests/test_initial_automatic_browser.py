"""Actual configured V2 handoff and separate approval through TLS customer pages."""

import json
import socket
import subprocess
import threading
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
import uvicorn
from app.api import customer_session_automation
from app.customers.access import SESSION_COOKIE, CustomerPrincipal, digest
from app.customers.models import CustomerSession, CustomerUser
from app.initial_planning.automatic_contracts import InitialReportedRulePolicyV1
from app.initial_planning.automatic_source import INITIAL_RULE_PRODUCER_FAMILY
from app.initial_planning.start_contracts import (
    INITIAL_AUTOMATIC_FAMILY,
    InitialRuleAutomaticPolicyV1,
)
from app.optimization_candidates.selection_contracts import CandidatePolicyRef
from app.production_runtime.reported_automation import configured_session_automation
from app.session_automation import worker
from app.session_automation.models import AutomaticDecisionAdmission, SessionAutomationRun
from app.settings import Settings, settings
from sqlalchemy import Engine
from sqlalchemy.orm import Session
from starlette.responses import JSONResponse, Response
from starlette.types import Receive, Scope, Send

from tests.initial_start_configuration import configure
from tests.test_customer_browser_api_journey import localhost_certificate
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_customer_optimization_api import headers
from tests.test_customer_portal import portal_executable
from tests.test_shopify_sales import configuration as configuration
from tests.v2_execution_fixture import ready


@pytest.mark.parametrize(
    "scenario", ["complete", "lost_start_response", "unknown_provider_response"]
)
def historical_contract_initial_automatic_browser(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    replicas: Any,
    scenario: str,
) -> None:
    from tests import budget_mandate_fixture
    from tests.test_planning_reporting_configuration import profile

    configured_profile = profile()
    configured_profile = configured_profile.model_copy(
        update={
            "native_read": configured_profile.native_read.model_copy(
                update={"observation_lifetime_seconds": 120}
            ),
            "initial": configured_profile.initial.model_copy(
                update={"preview_lifetime_seconds": 120}
            ),
        }
    )
    monkeypatch.setattr(budget_mandate_fixture, "profile", lambda: configured_profile)
    chromium = portal_executable("chromium", "chromium-browser", "google-chrome")
    alice, planning_root, execution_base, query, _, native_server, _, planning = ready(
        customer_engine, configuration, tmp_path, monkeypatch, replicas
    )
    if scenario == "unknown_provider_response":
        original_call = type(native_server).__call__
        native_server.timeout = True

        def unavailable_readback(server: Any, request: httpx.Request) -> httpx.Response:
            if server is native_server and server.posts and request.method == "GET":
                raise httpx.ReadTimeout("offline original readback unavailable")
            response = original_call(server, request)
            assert isinstance(response, httpx.Response)
            return response

        monkeypatch.setattr(type(native_server), "__call__", unavailable_readback)
    from app.publication.execution_models import (
        ProviderExecutionApproval,
        ProviderExecutionAttempt,
        ProviderExecutionReceipt,
        ProviderExecutionReview,
        ProviderExposureReservation,
    )
    from sqlalchemy import func, select

    with Session(customer_engine) as db:
        for model in (
            ProviderExecutionReview,
            ProviderExecutionReceipt,
            ProviderExecutionApproval,
            ProviderExecutionAttempt,
            ProviderExposureReservation,
        ):
            assert db.scalar(select(func.count()).select_from(model)) == 0
    base = execution_base + "/optimization"
    options = alice.post(base + "/target-options", json=query, headers=headers(alice))
    assert options.status_code == 200, options.text
    selection = {**query, "option_id": options.json()["options"][0]["id"]}
    draft = alice.post(
        base + "/budget-mandates",
        headers=headers(alice),
        json={
            "intent": {
                "selection": selection,
                "total_cap_micros": 50_000_000,
                "aggressiveness": "balanced",
            },
        },
    )
    assert draft.status_code == 201, draft.text
    mandate = draft.json()
    consent = alice.post(
        base + "/budget-mandates/" + mandate["mandate_id"] + "/consent",
        headers=headers(alice),
        json={
            "selection": selection,
            "expected_revision": mandate["revision"],
            "policy_digest": mandate["policy_digest"],
            "preparation_digest": mandate["preparation_digest"],
        },
    )
    assert consent.status_code == 200, consent.text
    wid = int(execution_base.split("/workspaces/")[1].split("/")[0])
    from datetime import UTC, datetime

    from app.commerce.models import CommerceStore
    from app.commerce.sync import CommerceSyncService

    from tests.test_commerce_measurement import FakeMeasurement

    with Session(customer_engine) as db:
        store = db.scalar(select(CommerceStore).where(CommerceStore.workspace_id == wid))
        assert store
        store.last_sync_at = None
        db.commit()
        assert (
            CommerceSyncService(
                db, configuration, FakeMeasurement(configuration, [([], None)])
            ).page(wid, now=datetime.now(UTC))["status"]
            == "complete"
        )
    numeric = InitialReportedRulePolicyV1(
        workspace_id=wid,
        environment="contract_test",
        policy_id="a" * 32,
        revision=1,
        policy_family="b" * 32,
        planning_profile_digest=configured_profile.digest(),
        initial=configured_profile.initial,
        allowed_operation="meta_budget_set_v1",
        maximum_candidate_age_seconds=120,
    )
    automatic = InitialRuleAutomaticPolicyV1(
        decision_basis="initial_reported_efficiency_rule",
        workspace_id=wid,
        environment="contract_test",
        policy_family=INITIAL_AUTOMATIC_FAMILY,
        policy_id="d" * 32,
        revision=1,
        candidate_policy=CandidatePolicyRef(policy_id=numeric.policy_id, revision=1),
        candidate_policy_digest=numeric.digest(),
        allowed_operations=("meta_budget_set_v1",),
        semantic_producer_families=(INITIAL_RULE_PRODUCER_FAMILY,),
        lifetime_seconds=120,
        cadence_seconds=60,
    )
    configure(SimpleNamespace(policy=numeric), automatic, tmp_path, monkeypatch)
    alice.app.include_router(customer_session_automation.router)
    token_digest = digest(alice.cookies[SESSION_COOKIE])
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    origin = f"https://127.0.0.1:{listener.getsockname()[1]}"
    monkeypatch.setattr(settings, "customer_app_origin", origin)
    completed = threading.Event()
    results = []
    start_requests = []
    original_attempts: list[tuple[str, str]] = []

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
            script = Path("tests/javascript/initial_automatic_browser.mjs").read_text()
            script = script.replace("__PLANNING_MANDATE__", planning["mandate_id"])
            script = script.replace(
                "__LOST_START__", str(scenario == "lost_start_response").lower()
            )
            await Response(script, media_type="text/javascript")(scope, receive, send)
            return
        if path == execution_base + "/automation/start":
            start_requests.append(path)
            if scenario == "lost_start_response":
                # Commit the actual customer request, then lose its successful response.
                messages: list[Any] = []

                async def capture(message: Any) -> None:
                    messages.append(message)

                await alice.app(scope, receive, capture)
                assert messages[0]["status"] == 200
                await JSONResponse({"detail": "fixture_response_unavailable"}, status_code=503)(
                    scope, receive, send
                )
                return
        if path == "/__fixture__/worker":

            def run_worker() -> str:
                with Session(customer_engine) as db:
                    session = db.get(CustomerSession, token_digest)
                    assert session
                    user = db.get(CustomerUser, session.user_id)
                    assert user
                    principal = CustomerPrincipal(user, session)
                    original = db.scalar(
                        select(SessionAutomationRun).where(SessionAutomationRun.workspace_id == wid)
                    )
                    assert original
                    run_id = original.id
                    db.commit()
                    with configured_session_automation(
                        db, principal, replicas[2], settings
                    ) as runtime:
                        assert runtime
                        outcome = worker.advance(customer_engine, wid, run_id, runtime)
                    attempt = db.scalar(select(ProviderExecutionAttempt))
                    assert attempt
                    original_attempts.append((attempt.id, attempt.fence))
                    return outcome

            from starlette.concurrency import run_in_threadpool

            result = await run_in_threadpool(run_worker)
            await JSONResponse({"result": result})(scope, receive, send)
            return
        if path.startswith("/app/assets/"):
            name = path.removeprefix("/app/assets/")
            if name in {
                "initial-planning.mjs",
                "initial-execution.mjs",
                "initial-automation.mjs",
                "session-context.mjs",
                "optimization.mjs",
                "optimization-budget.mjs",
                "session-automation.mjs",
                "candidate-read.mjs",
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
        assert db.scalar(select(func.count()).select_from(ProviderExecutionApproval)) == 0
        assert db.scalar(select(func.count()).select_from(ProviderExecutionAttempt)) == 1
        assert db.scalar(select(func.count()).select_from(AutomaticDecisionAdmission)) == 1
        assert db.scalar(select(func.count()).select_from(ProviderExposureReservation)) == 1
        assert db.scalar(select(SessionAutomationRun.state)) == "stopped"
        receipt = db.scalar(select(ProviderExecutionReceipt))
        expected = "unknown" if scenario == "unknown_provider_response" else "verified_target_state"
        assert receipt and receipt.receipt["outcome"] == expected
        attempt = db.scalar(select(ProviderExecutionAttempt))
        assert attempt and original_attempts == [(attempt.id, attempt.fence)]
        if scenario == "unknown_provider_response":
            from app.publication.optimization_contracts import MetaBudgetSetV1, OptimizationRequest

            request = OptimizationRequest.model_validate(attempt.request)
            assert isinstance(request.intent.action, MetaBudgetSetV1)
            assert int(native_server.meta_campaign["daily_budget"]) * 10_000 == (
                request.intent.action.amount_micros
            )
            assert db.scalar(select(ProviderExposureReservation.state)) == "held"
    assert len(native_server.posts) == 1
    assert len(start_requests) == 1
