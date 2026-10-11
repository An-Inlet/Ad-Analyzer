"""Actual private-v5 HTTPS portal; real services/SQL and read-only provider MockHTTP."""

import json
import os
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
from app.campaign_review.models import MediaObject
from app.campaign_review.storage import get_media_store
from app.customers.identity import get_identity_provider
from app.customers.models import CustomerMembership
from app.database.session import get_db
from app.main import app
from app.planning_documents.documents import PlanVersion
from app.planning_documents.models import PlanInputRow, PlanRow, PlanVersionRow
from app.settings import Settings, settings
from app.workspaces.models import Workspace
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session
from starlette.responses import JSONResponse, Response
from starlette.types import Message, Receive, Scope, Send

from tests import test_customer_identity, test_customer_optimization_api, test_selected_customer_api
from tests.creative_browser_capture import capture_saved_basis
from tests.creative_browser_observer import fixed_detail, route_class
from tests.creative_common_basis_fixture import Platform, prepare_creative_common_basis
from tests.creative_q08_fixture import prepare_creative_q08_basis
from tests.q16_fixture import IMAGE
from tests.test_creative_common_basis import financial_counts
from tests.test_customer_browser_api_journey import localhost_certificate
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import login
from tests.test_customer_identity import replicas as replicas
from tests.test_customer_portal import portal_executable
from tests.test_shopify_sales import configuration as configuration

pytestmark = pytest.mark.planning_boundary


@pytest.mark.parametrize(
    "journey,platform",
    [
        ("google", "google_ads"),
        ("meta", "meta_ads"),
        ("tiktok", "tiktok_ads"),
        ("safety", "google_ads"),
        ("q08", "meta_ads"),
    ],
)
def test_actual_creative_planning_browser(
    customer_engine: Engine,
    request: pytest.FixtureRequest,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    journey: str,
    platform: Platform,
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
    if journey == "q08":
        fixture = prepare_creative_q08_basis(
            customer_engine, configuration, replicas, monkeypatch, tmp_path / "media"
        )
    else:
        fixture = prepare_creative_common_basis(
            customer_engine,
            configuration,
            replicas,
            monkeypatch,
            tmp_path / "media",
            platform=platform,
            selected_value="10" if platform == "google_ads" else None,
        )
    basis = fixture.basis
    # Only workspace ownership fixture rows; never seed plans, proofs or execution.
    bob = login(replicas[1], "creative-foreign-owner:initial")
    with Session(customer_engine) as db:
        foreign = Workspace(
            slug="creative-foreign", name="Foreign", client_name="Foreign", status="active"
        )
        db.add(foreign)
        db.flush()
        db.add(CustomerMembership(user_id=bob, workspace_id=foreign.id, role="owner"))
        db.commit()
        foreign_id = foreign.id
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
    complete = threading.Event()
    results: list[dict[str, Any]] = []
    mutation_requests: list[str] = []
    generation_outcomes: list[dict[str, Any]] = []
    capture_enabled = os.environ.get("INLET_CREATIVE_BROWSER_CAPTURE") == "1"
    if capture_enabled:
        assert journey == "google" and customer_engine.dialect.name == "sqlite"
    browser_config = dict(
        capture_enabled=capture_enabled,
        workspace_id=basis.workspace_id,
        foreign_workspace_id=foreign_id,
        account_id=basis.account_id,
        body=fixture.body,
        journey=journey,
        media_id=basis.media_id,
        media_sha256=basis.media_sha256,
    )

    async def harness(scope: Scope, receive: Receive, send: Send) -> None:
        path = scope.get("path", "")
        if path == "/__fixture__/capture" and capture_enabled:
            capture_saved_basis(tmp_path / "browser", tmp_path / "saved-creative-basis.png")
            await JSONResponse({"ok": True})(scope, receive, send)
            return
        if path == "/__fixture__/start":
            messages: list[Message] = []

            async def capture(message: Message) -> None:
                messages.append(message)

            # Retain the actual page's headers/CSP; replace only its test entry module.
            page_scope = dict(scope, path="/app/planning", raw_path=b"/app/planning")
            await app(page_scope, receive, capture)
            head = next(message for message in messages if message["type"] == "http.response.start")
            assert head["status"] == 200
            html = b"".join(message.get("body", b"") for message in messages)
            assert b"/app/assets/planning.mjs" in html
            page_headers = {
                key.decode("latin-1"): value.decode("latin-1")
                for key, value in head["headers"]
                if key.lower() != b"content-length"
            }
            assert "img-src 'self' blob:" in page_headers["content-security-policy"]
            await Response(
                html.replace(b"/app/assets/planning.mjs", b"/__fixture__/driver.mjs"),
                headers=page_headers,
            )(scope, receive, send)
            return
        if path == "/__fixture__/driver.mjs":
            script = Path("tests/javascript/planning_creative_browser.mjs").read_text()
            await Response(
                script.replace("__CONFIG__", json.dumps(browser_config)),
                media_type="text/javascript",
            )(
                scope,
                receive,
                send,
            )
            return
        if path == "/__fixture__/mug.png":
            await Response(IMAGE.read_bytes(), media_type="image/png")(scope, receive, send)
            return
        if path == "/__fixture__/remove-bytes" and scope.get("method") == "POST":
            # Metadata remains intact. This must not imply refreshed byte availability.
            (fixture.store.root / str(basis.workspace_id) / basis.media_sha256).unlink()
            await JSONResponse({"ok": True})(scope, receive, send)
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
        if scope.get("method") == "POST" and path.endswith(
            ("/media", "/generate", "/planning/plans")
        ):
            mutation_requests.append(path)
        observed_route = route_class(path, scope.get("method", ""))
        if observed_route is not None:
            status = 0
            error_body = bytearray()

            async def observed_send(message: Message) -> None:
                nonlocal status
                if message["type"] == "http.response.start":
                    status = message["status"]
                elif message["type"] == "http.response.body" and status >= 400:
                    error_body.extend(message.get("body", b"")[: max(0, 8192 - len(error_body))])
                await send(message)

            started = time.monotonic()
            await app(scope, receive, observed_send)
            elapsed = time.monotonic() - started
            try:
                detail = json.loads(error_body).get("detail") if error_body else None
            except (ValueError, AttributeError):
                detail = "unlisted_server_detail"
            if len(generation_outcomes) < 100:
                generation_outcomes.append(
                    {
                        "ordinal": len(generation_outcomes) + 1,
                        "route": observed_route,
                        "status": status,
                        "detail": fixed_detail(detail),
                        "elapsed_seconds": round(elapsed, 6),
                    }
                )
        else:
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
            *(
                [
                    "--remote-debugging-port=0",
                    "--remote-debugging-address=127.0.0.1",
                    "--window-size=1440,1100",
                ]
                if capture_enabled
                else []
            ),
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
        assert complete.wait(120), "Creative browser did not report completion"
        assert results and results[0]["status"] == "passed", (results, generation_outcomes)
        assert financial_counts(customer_engine) == counts
        assert fixture.calls and all(":mutate" not in call for call in fixture.calls)
        with Session(customer_engine) as db:
            assert db.scalar(select(func.count()).select_from(MediaObject)) == 1
            expected = 0 if journey == "safety" else 2 if journey == "google" else 1
            assert db.scalar(select(func.count()).select_from(PlanVersionRow)) == expected
            assert db.scalar(select(func.count()).select_from(PlanInputRow)) == expected
            for row in db.scalars(select(PlanVersionRow)):
                doc = PlanVersion.model_validate_json(row.canonical_json)
                assert doc.creative_proof is not None
                assert len(doc.creative_proof.basis.images) == 1
                assert doc.creative_proof.basis.images[0].sha256 == basis.media_sha256
                assert doc.inputs.creative is not None and doc.inputs.creative.product is not None
                assert doc.inputs.creative.product.name == "Reusable travel mug"
                assert doc.inputs.creative.product.list_price is not None
                assert doc.inputs.creative.product.list_price.micros == 25_000_000
                if journey == "q08":
                    assert doc.inputs.total_ceiling_micros == 0
                    assert doc.inputs.goal.revision == basis.goal_revision
                    assert doc.inputs.goal.confirmation_reference == basis.confirmation_id
                    assert doc.creative_composition is not None
                    assert len(doc.creative_composition.proposals) == 1
                    proposal = doc.creative_composition.proposals[0]
                    assert proposal.target_basis == "observed_empty_account"
                    assert proposal.empty_catalog_witness is not None
                    assert proposal.empty_catalog_witness.catalog_evidence.catalog.targets == ()
                    assert all(s.ceiling_micros == s.unallocated_micros == 0 for s in doc.scenarios)
                    assert all(not s.allocations and s.forecast is None for s in doc.scenarios)
        (tmp_path / "creative-browser-result.json").write_text(
            json.dumps(
                {
                    "browser": results[0],
                    "journey": journey,
                    "database": customer_engine.dialect.name,
                    "planning_mutation_requests": mutation_requests,
                    "financial_counts": counts,
                },
                indent=2,
            )
        )
    finally:
        original_failure = sys.exception() is not None
        try:
            browser.terminate()
            try:
                browser.wait(timeout=5)
            except subprocess.TimeoutExpired:
                browser.kill()
                browser.wait(timeout=5)
        finally:
            try:
                server.should_exit = True
                thread.join(timeout=10)
            finally:
                listener.close()
                request.node.user_properties.append(
                    ("route_observer_shutdown_complete", not thread.is_alive())
                )
                try:
                    (tmp_path / "generation-outcomes.json").write_text(
                        json.dumps(tuple(generation_outcomes)[:100], indent=2)
                    )
                except OSError:
                    request.node.user_properties.append(("route_observer_persistence", "failed"))
                    if not original_failure:
                        raise AssertionError(
                            "Bounded route observations were not persisted"
                        ) from None
