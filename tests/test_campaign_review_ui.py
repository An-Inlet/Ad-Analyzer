"""Rendered review uses real HTTPS customer APIs; provider identity stays offline."""

import json
import socket
import subprocess
import threading
import time
from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest
import uvicorn
from app.api import customer_campaign_review
from app.campaign_review import service
from app.campaign_review.contracts import RevisionInput
from app.campaign_review.models import CampaignRevision
from app.campaign_review.storage import get_media_store
from app.customers.identity import get_identity_provider
from app.customers.models import CustomerMembership, CustomerUser
from app.database.session import get_db
from app.main import app
from app.mandates import service as mandates
from app.settings import Settings, settings
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session, sessionmaker
from starlette.responses import JSONResponse, Response
from starlette.types import Receive, Scope, Send

from tests.campaign_review_ui_retained_fixture import CampaignUiSource, binding
from tests.campaign_review_ui_retained_fixture import campaign_ui_source as campaign_ui_source
from tests.test_campaign_review import definition, png
from tests.test_campaign_video import encoded as encoded
from tests.test_commerce_measurement import NOW
from tests.test_customer_browser_api_journey import localhost_certificate
from tests.test_customer_identity import FakeProvider
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_portal import portal_executable
from tests.test_inlet_customer_journey import JourneyClock
from tests.test_shopify_sales import configuration as configuration


def test_review_shell_and_assets() -> None:
    with TestClient(app) as client:
        response = client.get("/app/campaign-review")
        assert response.status_code == 200
        assert "Publication Blocked" in response.text
        assert "Approve This Offline Plan" in response.text
        assert "unsafe-inline" not in response.headers["content-security-policy"]
        assert "media-src 'self' blob:" in response.headers["content-security-policy"]
        assert response.headers["cache-control"] == "no-store"
        assert client.get("/app/assets/campaign-review.mjs").status_code == 200
        assert client.get("/app/assets/campaign-review.css").status_code == 200
        assert "Open Campaign Review" in client.get("/app").text


def test_review_browser_real_api(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    encoded: Any,
    campaign_ui_source: CampaignUiSource,
) -> None:
    chromium = portal_executable(
        "chromium", "chromium-browser", "google-chrome", "google-chrome-stable"
    )
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    origin = f"https://127.0.0.1:{listener.getsockname()[1]}"
    monkeypatch.setattr(settings, "customer_app_origin", origin)
    monkeypatch.setattr(customer_campaign_review, "datetime", JourneyClock)
    source = campaign_ui_source
    engine, store, actor = source.engine, source.store, source.ids.actor_id
    factory = sessionmaker(engine)
    video_bytes = encoded()
    with factory() as db:
        mandate, account = binding(db, source.ids)
        policy = mandates.policy(db, mandate)
        user = db.get(CustomerUser, actor)
        assert user and user.subject == "review-owner"
        provider = FakeProvider()
        provider.issuer, provider.email = user.issuer, user.email
        image = service.upload(db, mandate.workspace_id, actor, png(), store, NOW)
        image_definition = definition(db, mandate, account).model_dump(mode="json")
        image_definition["account"] = policy.accounts[1].model_dump()
        image_definition["content"] = {
            "kind": "meta_website_sales_image_v1",
            "objective": "website_sales",
            "name": "Supplied Image",
            "landing_page": "https://example.invalid/shop",
            "audience": {"countries": ["US"], "languages": ["en"]},
            "headline": "Supplied Headline",
            "text": "Image Copy",
            "call_to_action": "SHOP_NOW",
            "media": {"media_id": image.id, "sha256": image.sha256},
        }
        image_row = service.revise(
            db,
            mandate.workspace_id,
            RevisionInput.model_validate(image_definition),
            actor,
            store,
            NOW,
        )
        image_draft_id = image_row.draft_id
        row = service.revise(
            db, mandate.workspace_id, definition(db, mandate, account), actor, store, NOW
        )
        wid, draft_id = mandate.workspace_id, row.draft_id
        image_media_id = image.id

    source.evidence.bind_setup(source, draft_id, image_draft_id, image_media_id, video_bytes)

    def database() -> Generator[Session, None, None]:
        with factory() as db:
            yield db

    monkeypatch.setattr(
        app,
        "dependency_overrides",
        {
            get_db: database,
            get_identity_provider: lambda: provider,
            get_media_store: lambda: store,
        },
    )
    completed = threading.Event()
    result: list[dict[str, Any]] = []

    media_denied = False

    async def harness(scope: Scope, receive: Receive, send: Send) -> None:
        nonlocal media_denied
        request_started = int(time.time())
        path = scope.get("path", "")
        if path == "/__fixture__/driver.mjs":
            script = (
                Path("tests/javascript/campaign_review_browser.mjs")
                .read_text()
                .replace("__WORKSPACE__", str(wid))
                .replace("__DRAFT__", draft_id)
                .replace("__IMAGE_DRAFT__", image_draft_id)
            )
            await Response(script, media_type="text/javascript")(scope, receive, send)
            return
        if path == "/__fixture__/video":
            await Response(video_bytes, media_type="video/mp4")(scope, receive, send)
            return
        if path == "/__fixture__/media-denied":
            media_denied = not media_denied
            await JSONResponse({"ok": True})(scope, receive, send)
            return
        if media_denied and "/media/" in path:
            await JSONResponse({"detail": "fixture media unavailable"}, status_code=503)(
                scope, receive, send
            )
            return
        if path == "/__fixture__/viewer":
            with factory() as db:
                membership = db.get(CustomerMembership, (actor, wid))
                assert membership is not None
                membership.role = "viewer"
                db.commit()
            await JSONResponse({"ok": True})(scope, receive, send)
            return
        if path == "/__fixture__/result":
            data = bytearray()
            while True:
                message = await receive()
                data.extend(message.get("body", b""))
                if not message.get("more_body", False):
                    break
            result.append(json.loads(data))
            await JSONResponse({"ok": True})(scope, receive, send)
            completed.set()
            return
        if path == "/__fixture__/start":
            html = (
                Path("app/portal/static/campaign-review.html")
                .read_text()
                .replace("/app/assets/campaign-review.mjs", "/__fixture__/driver.mjs")
            )
            await Response(html, media_type="text/html")(scope, receive, send)
            return
        async def record(message: Any) -> None:
            if (path == "/api/customer/v1/session" and scope["method"] == "POST"
                    and message["type"] == "http.response.start" and message["status"] == 200):
                source.evidence.bind_login(source, message["headers"], request_started,
                                           int(time.time()))
            await send(message)

        await app(scope, receive, record)

    certificate, key = localhost_certificate(tmp_path)
    server = uvicorn.Server(
        uvicorn.Config(
            harness,
            log_level="critical",
            lifespan="off",
            ssl_certfile=str(certificate),
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
        assert completed.wait(60), "Campaign review browser did not report completion"
        (tmp_path / "browser-result.json").write_text(json.dumps(result, indent=2))
        assert result and result[0]["status"] == "passed", result
        with factory() as db:
            revisions = list(
                db.scalars(
                    select(CampaignRevision)
                    .where(CampaignRevision.draft_id == draft_id)
                    .order_by(CampaignRevision.revision)
                )
            )
            assert len(revisions) == 3
            assert revisions[0].approved_by == actor and revisions[1].approved_by is None
            assert revisions[2].approved_by is None
        source.evidence.negatives(source)
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
