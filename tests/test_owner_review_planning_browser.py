"""Actual private V6 portal with owned receipt discovery and no advertising writes."""

import hashlib
import hmac
import json
import socket
import subprocess
import sys
import threading
import time
from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest
import uvicorn
from app.campaign_review.storage import get_media_store
from app.customers.access import CSRF_COOKIE, SESSION_COOKIE, digest
from app.customers.identity import get_identity_provider
from app.customers.models import CustomerSession
from app.database.session import get_db
from app.main import app
from app.planning_catalog.contracts import GoogleSettingsV1
from app.planning_catalog.metadata_contracts import TargetCatalogV2
from app.planning_documents.documents import PlanVersion
from app.planning_documents.models import PlanInputRow, PlanRow, PlanVersionRow
from app.settings import Settings, settings
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import Message, Receive, Scope, Send

from tests import test_customer_identity, test_customer_optimization_api, test_selected_customer_api
from tests.creative_browser_observer import fixed_detail, route_class
from tests.creative_q07_fixture import planning_snapshot
from tests.google_budget_owner_discovery_fixture import OwnerCatalogResponseControl
from tests.owner_review_runtime_fixture import configured_owner_review
from tests.test_creative_common_basis import financial_counts
from tests.test_customer_browser_api_journey import localhost_certificate
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_customer_portal import portal_executable
from tests.test_shopify_sales import configuration as configuration

pytestmark = pytest.mark.planning_boundary


@pytest.mark.parametrize(
    "journey",
    ["positive", "partial", "complete_to_partial", "literal_text", "duplicate_names"],
)
def test_actual_owner_review_planning_browser(
    customer_engine: Engine,
    request: pytest.FixtureRequest,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    journey: str,
) -> None:
    listener = socket.socket()
    request.addfinalizer(listener.close)
    listener.bind(("127.0.0.1", 0))
    origin = f"https://127.0.0.1:{listener.getsockname()[1]}"
    monkeypatch.setattr(test_customer_identity, "ORIGIN", origin)
    monkeypatch.setattr(test_selected_customer_api, "ORIGIN", origin)
    monkeypatch.setattr(test_customer_optimization_api, "ORIGIN", origin)
    monkeypatch.setattr(settings, "customer_app_origin", origin)
    for client in replicas[:2]:
        client.base_url = origin
    literal: dict[str, Any] | None = (
        {
            "names": {
                "1": 'Mug <img src=x onerror="window.q15Injected=true"> A',
                "2": 'Mug <svg onload="window.q15Injected=true"> B',
            },
            "milestone": 'Review <script>window.q15Injected=true</script> sales',
            "scenario": '=HYPERLINK("inert", "Customer Alternative")',
            "restriction": 'No <img src=x onerror="window.q15Injected=true"> claims',
        }
        if journey == "literal_text" else None
    )
    response_control = OwnerCatalogResponseControl() if journey == "complete_to_partial" else None
    fixture, body, calls, _ = configured_owner_review(
        customer_engine,
        configuration,
        replicas,
        monkeypatch,
        tmp_path,
        partial=journey == "partial",
        response_control=response_control,
        native_names=(
            {"1": "Mug Campaign", "2": "Mug Campaign", "3": "Mug Campaign"}
            if journey == "duplicate_names" else literal["names"] if literal else None
        ),
    )
    basis = fixture.basis
    original_cookie = replicas[0].cookies[SESSION_COOKIE]
    original_csrf = replicas[0].cookies[CSRF_COOKIE]
    session_digest = digest(original_cookie)
    with Session(customer_engine) as db:
        original_session = db.get(CustomerSession, session_digest)
        assert original_session is not None
        session_state = (
            original_session.user_id,
            original_session.authenticated_at,
            original_session.expires_at,
            original_session.revoked_at,
        )
    session_posts = 0
    counts = financial_counts(customer_engine)
    assert counts == (0,) * 6
    with Session(customer_engine) as db:
        assert db.scalar(select(func.count()).select_from(PlanRow)) == 0
    provider = replicas[2]

    def database() -> Generator[Session, None, None]:
        with Session(customer_engine) as db:
            yield db

    monkeypatch.setattr(
        app,
        "dependency_overrides",
        {
            get_db: database,
            get_identity_provider: lambda: provider,
            get_media_store: lambda: fixture.store,
        },
    )
    # Only form values, never the fixture's prepared scenario/owner request body.
    form = {
        key: body["inputs"][key]
        for key in (
            "goal_id",
            "milestone",
            "product_offer",
            "reporting_window",
            "comparison_window",
            "selected_reporting",
        )
    }
    config = dict(
        workspace_id=basis.workspace_id,
        account_id=basis.account_id,
        media_id=basis.media_id,
        media_sha256=basis.media_sha256,
        form=form,
        journey=journey,
        literal=literal,
        duplicate_names=journey == "duplicate_names",
    )
    complete = threading.Event()
    results: list[dict[str, Any]] = []
    observations: list[dict[str, Any]] = []
    artifacts: list[dict[str, Any]] = []
    truncated = False
    active_requests = 0
    input_posts = 0
    switched_snapshot: tuple[tuple[str, ...], ...] | None = None
    blocked_save_verified = False

    async def forward(scope: Scope, receive: Receive, send: Send) -> None:
        nonlocal active_requests
        active_requests += 1
        try:
            await app(scope, receive, send)
        finally:
            active_requests -= 1

    async def harness(scope: Scope, receive: Receive, send: Send) -> None:
        nonlocal truncated, session_posts, switched_snapshot, input_posts, blocked_save_verified
        path = scope.get("path", "")
        if path == "/api/customer/v1/session" and scope.get("method") == "POST":
            session_posts += 1
        if path.startswith("/api/customer/"):
            incoming = Request(scope).cookies.get(SESSION_COOKIE, "")
            if not hmac.compare_digest(incoming, original_cookie):
                raise AssertionError("Original authenticated session changed")
        if path == "/__fixture__/make-partial":
            checkpoint = Request(scope)
            if (
                response_control is None
                or scope.get("method") != "POST"
                or checkpoint.headers.get("origin") != origin
                or not hmac.compare_digest(
                    checkpoint.cookies.get(SESSION_COOKIE, ""), original_cookie
                )
                or not hmac.compare_digest(
                    checkpoint.headers.get("x-csrf-token", ""), original_csrf
                )
            ):
                raise AssertionError("Invalid native-response checkpoint")
            assert active_requests == 0 and switched_snapshot is None and input_posts == 0
            message = await receive()
            assert not message.get("body", b"") and not message.get("more_body", False)
            switched_snapshot = planning_snapshot(customer_engine)
            assert financial_counts(customer_engine) == counts
            response_control.make_partial()
            await JSONResponse({"ok": True}, headers={"Cache-Control": "no-store"})(
                scope, receive, send
            )
            return
        if path.endswith("/inputs") and scope.get("method") == "POST":
            if response_control is not None:
                assert switched_snapshot is not None and input_posts == 0
                assert response_control.partial_responses > 0
                assert planning_snapshot(customer_engine) == switched_snapshot
                assert financial_counts(customer_engine) == counts
                blocked_save_verified = True
            input_posts += 1
        if path == "/__fixture__/start":
            messages: list[Message] = []

            async def capture(message: Message) -> None:
                messages.append(message)

            await app(
                dict(scope, path="/app/planning", raw_path=b"/app/planning"), receive, capture
            )
            head = next(m for m in messages if m["type"] == "http.response.start")
            assert head["status"] == 200
            html = b"".join(m.get("body", b"") for m in messages)
            assert b"/app/assets/planning.mjs" in html
            page_headers = {
                k.decode("latin-1"): v.decode("latin-1")
                for k, v in head["headers"]
                if k.lower() != b"content-length"
            }
            assert "img-src 'self' blob:" in page_headers["content-security-policy"]
            response = Response(
                html.replace(b"/app/assets/planning.mjs", b"/__fixture__/driver.mjs"),
                headers=page_headers,
            )
            response.headers["Cache-Control"] = "no-store"
            # Transport already-issued credentials, never mint or renew a session.
            # Values exist only in the TLS cookies, never JS configuration/evidence.
            for name, value, http_only in (
                (SESSION_COOKIE, original_cookie, True),
                (CSRF_COOKIE, original_csrf, False),
            ):
                response.set_cookie(
                    name, value, secure=True, httponly=http_only, samesite="strict", path="/"
                )
            await response(scope, receive, send)
            return
        if path == "/__fixture__/driver.mjs":
            source = Path("tests/javascript/planning_owner_review_browser.mjs").read_text()
            await Response(
                source.replace("__CONFIG__", json.dumps(config)), media_type="text/javascript"
            )(scope, receive, send)
            return
        if path == "/__fixture__/result":
            data = bytearray()
            while True:
                message = await receive()
                data.extend(message.get("body", b""))
                assert len(data) <= 64 * 1024 * 1024
                if not message.get("more_body", False):
                    break
            results.append(json.loads(data))
            await JSONResponse({"ok": True})(scope, receive, send)
            complete.set()
            return
        label = route_class(path, scope.get("method", ""))
        if label is None:
            await forward(scope, receive, send)
            return
        status = 0
        error_body = bytearray()
        before = len(calls), len(fixture.calls)

        async def observed_send(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
            elif message["type"] == "http.response.body" and status >= 400:
                error_body.extend(message.get("body", b"")[: max(0, 8192 - len(error_body))])
            await send(message)

        started = time.monotonic()
        completed = False
        try:
            await forward(scope, receive, observed_send)
            completed = True
        finally:
            try:
                detail = json.loads(error_body).get("detail") if error_body else None
            except (ValueError, AttributeError):
                detail = "unlisted_server_detail"
            if len(observations) < 100:
                observations.append(
                    dict(
                        ordinal=len(observations) + 1,
                        route=label,
                        status=status,
                        detail=fixed_detail(detail),
                        completed=completed,
                        elapsed_seconds=round(time.monotonic() - started, 6),
                    )
                )
            else:
                truncated = True
        # Target collection is deliberately outside these receipt/read-only routes.
        assert before == (len(calls), len(fixture.calls))

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

    def stop_server() -> None:
        server.should_exit = True
        thread.join(timeout=10)

    request.addfinalizer(stop_server)
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
        assert complete.wait(120), "Owner browser did not report completion"
        assert results and results[0]["status"] == "passed", (results, observations)
        assert not truncated
        assert session_posts == 0
        assert financial_counts(customer_engine) == counts
        result = results[0]
        document = PlanVersion.model_validate(result["document"])
        exported = result["export"]
        assert PlanVersion.model_validate(exported["document"]).digest() == document.digest()
        assert document.policy_version == "inlet.descriptive-review.v6"
        assert document.google_budget_owner_review is not None
        reviews = document.google_budget_owner_review.reviews
        assert len(reviews) == (0 if journey == "partial" else 1)
        if reviews:
            review = reviews[0]
            assert review.intent.requested_amount_micros == 5_000_000
            assert review.disposition == "investigate_only" and review.application == "unavailable"
            assert review.period_spending_compatibility == "not_assessed"
            assert {m.provider_reference.entity_id for m in review.witness.affected_campaigns} == {
                "1",
                "2",
            }
        if journey == "duplicate_names":
            assert result["duplicate_checks"] is True
            selected_reference = (
                document.inputs.scenario_intents[0].allocations[0].target.provider_reference
            )
            assert selected_reference is not None
            assert selected_reference.entity_id == "2"
            assert len(document.inputs.excluded_entity_keys) == 1
            assert document.inputs.excluded_entity_keys == tuple(result["excluded_keys"])
            assert [m.display_name for m in reviews[0].witness.affected_campaigns] == [
                "Mug Campaign", "Mug Campaign"
            ]
        if literal:
            assert result["literal_checks"] is True
            assert document.inputs.milestone == literal["milestone"]
            assert document.inputs.scenario_intents[0].title == literal["scenario"]
            assert document.inputs.creative is not None
            assert document.inputs.creative.product is not None
            assert document.inputs.creative.product.restrictions == (literal["restriction"],)
            assert {
                m.provider_reference.entity_id: m.display_name
                for m in reviews[0].witness.affected_campaigns
            } == literal["names"]
        assert document.inputs.total_ceiling_micros == 1_000_000_000
        assert document.inputs.scenario_intents[0].allocations[0].amount_micros == 100_000_000
        assert document.inputs.scenario_intents[0].unallocated_micros == 900_000_000
        with Session(customer_engine) as db:
            current_session = db.get(CustomerSession, session_digest)
            assert current_session is not None
            if (
                current_session.user_id,
                current_session.authenticated_at,
                current_session.expires_at,
                current_session.revoked_at,
            ) != session_state:
                raise AssertionError("Original session lifetime or identity changed")
            assert db.scalar(select(func.count()).select_from(PlanVersionRow)) == 1
            assert db.scalar(select(func.count()).select_from(PlanInputRow)) == (
                2 if journey in {"positive", "complete_to_partial"} else 1
            )
        if response_control is not None:
            assert blocked_save_verified and input_posts == 1
            assert response_control.partial_responses > 0
            transition = result["transition"]
            before_catalog = TargetCatalogV2.model_validate(transition["complete_catalog"])
            after_catalog = TargetCatalogV2.model_validate(transition["partial_catalog"])
            assert before_catalog.composite_digest != after_catalog.composite_digest
            for catalog, expected_count in ((before_catalog, 2), (after_catalog, 3)):
                native = catalog.native_observation
                member_rows = [
                    row
                    for row in native.targets
                    if row.kind == "campaign"
                    and row.budget_owner_key == reviews[0].witness.owner_key
                ]
                assert len(member_rows) == 2
                assert all(
                    isinstance(row.settings, GoogleSettingsV1)
                    and row.settings.budget_reference_count == expected_count
                    for row in member_rows
                )
                coverage = [
                    row for row in catalog.metadata_observation.coverage if row.kind == "campaign"
                ]
                assert len(coverage) == 1
                assert (coverage[0].status, coverage[0].scope, coverage[0].count) == (
                    "complete",
                    "provider_campaigns",
                    3,
                )
            before_discovery = transition["complete_discovery"]
            after_discovery = transition["partial_discovery"]
            assert (
                before_discovery["status"] == "available" and len(before_discovery["owners"]) == 1
            )
            assert after_discovery["status"] == "unavailable" and after_discovery["owners"] == []
            assert after_discovery["reason"] == "google_budget_owner_unavailable"
            assert transition["blocked_input_posts"] == 0
            assert transition["final_input_posts"] == 1
            assert transition["historical"]["document"] == result["document"]
            assert transition["historical_export"]["document"] == result["document"]
            assert transition["historical"]["document_digest"] == document.digest()
            assert transition["historical_export"]["document_digest"] == document.digest()
            for name in (
                "complete_catalog",
                "complete_discovery",
                "partial_catalog",
                "partial_discovery",
                "historical",
                "historical_export",
            ):
                path = tmp_path / (name + ".json")
                path.write_text(json.dumps(transition[name], sort_keys=True, indent=2) + "\n")
                artifacts.append(
                    dict(name=name, sha256=hashlib.sha256(path.read_bytes()).hexdigest())
                )
        for name, value in (("document", result["document"]), ("export", exported)):
            path = tmp_path / (name + ".json")
            path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")
            artifacts.append(dict(name=name, sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
        (tmp_path / "artifacts.json").write_text(json.dumps(artifacts, indent=2) + "\n")
    finally:
        failed = sys.exception() is not None
        try:
            browser.terminate()
            try:
                browser.wait(timeout=5)
            except subprocess.TimeoutExpired:
                browser.kill()
                browser.wait(timeout=5)
        finally:
            stop_server()
            listener.close()
            request.node.user_properties.append(
                ("route_observer_shutdown_complete", not thread.is_alive())
            )
            try:
                (tmp_path / "route-observations.json").write_text(
                    json.dumps(
                        dict(
                            observations=observations,
                            truncated=truncated,
                            shutdown_complete=not thread.is_alive(),
                        ),
                        indent=2,
                    )
                    + "\n"
                )
            except OSError:
                request.node.user_properties.append(("route_observer_persistence", "failed"))
                if not failed:
                    raise AssertionError("Bounded route observations were not persisted") from None
