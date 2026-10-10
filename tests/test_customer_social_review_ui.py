"""Retained shell with current social review component/API; not a current product page."""

import hashlib
import json
import socket
import subprocess
import threading
import time
import traceback
from collections.abc import Generator
from datetime import UTC, datetime, timedelta, tzinfo
from pathlib import Path
from typing import Any

import pytest
import uvicorn
from app.api import customer_campaign_review
from app.campaign_review.storage import get_media_store
from app.customers.identity import get_identity_provider
from app.customers.models import CustomerUser
from app.database.session import get_db
from app.main import app
from app.publication.social_review_contracts import SocialRequirements
from app.publication.social_review_runtime import SocialReviewRuntime, get_social_review_runtime
from app.settings import Settings, settings
from app.workspaces.models import Workspace
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker
from starlette.responses import JSONResponse, Response
from starlette.types import Receive, Scope, Send

from tests.social_producer_retained_fixture import SocialProducerSource, load_source
from tests.social_review_ui_current_fixture import assert_ui_copy_denials
from tests.social_review_ui_current_fixture import social_ui_source as social_ui_source
from tests.test_campaign_video import encoded as encoded
from tests.test_commerce_measurement import NOW
from tests.test_customer_browser_api_journey import localhost_certificate
from tests.test_customer_identity import FakeProvider
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_portal import portal_executable
from tests.test_shopify_sales import configuration as configuration


@pytest.mark.parametrize("platform", ["meta_ads", "tiktok_ads"])
def test_social_review_real_browser(
    customer_engine: Engine,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    configuration: Settings,
    encoded: Any,
    platform: str,
    social_ui_source: SocialProducerSource,
) -> None:
    chromium = portal_executable(
        "chromium", "chromium-browser", "google-chrome", "google-chrome-stable"
    )
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    origin = f"https://127.0.0.1:{listener.getsockname()[1]}"
    monkeypatch.setattr(settings, "customer_app_origin", origin)
    clock = [NOW]

    class ReviewClock(datetime):
        @classmethod
        def now(cls, tz: tzinfo | None = None) -> "ReviewClock":
            return cls.fromtimestamp(clock[0].timestamp(), tz)

    # Discovery and the actual preview route must observe the same fixture period.
    monkeypatch.setattr(customer_campaign_review, "datetime", ReviewClock)
    engine = social_ui_source.engine
    factory = sessionmaker(engine)
    with factory() as db:
        original, account, catalog, producer, actor, media, cover, _ = load_source(
            db, social_ui_source
        )
        wid = account.workspace_id
        profile = next(iter(producer.profiles.values()))
        if platform == "meta_ads":
            profile = profile.model_copy(update={"dsa_required": False})
        option = catalog.options[0].model_copy(update={"profile_digest": profile.digest()})
        catalog = catalog.model_copy(update={"options": [option]})
        runtime = SocialReviewRuntime(
            environment="contract_test",
            catalog=lambda request, now: catalog,
            profiles=(profile,),
            requirements={
                profile.digest(): SocialRequirements(
                    profile_digest=profile.digest(),
                    requirements_digest="a" * 64,
                    wording_version="browser-test-v1",
                    verified=True,
                    dsa_required=False,
                    wording="Offline Test: Review This No-DSA Profile And Its Exact Media.",
                )
            },
            clock=lambda: clock[0],
        )
        user = db.get(CustomerUser, actor)
        assert user is not None
        assert user.issuer == "mock" and user.subject == actor
        provider = FakeProvider()
        provider.issuer, provider.email = user.issuer, user.email
        workspace = db.get(Workspace, wid)
        assert workspace is not None
        name_started = datetime.now(UTC)
        workspace.name = "<img src=x>"
        db.commit()
        name_ended = datetime.now(UTC)
    assert social_ui_source.ui_evidence is not None
    social_ui_source.ui_evidence.record_workspace_name_change(
        social_ui_source, name_started, name_ended,
    )

    def database() -> Generator[Session, None, None]:
        with factory() as db:
            yield db

    monkeypatch.setattr(
        app,
        "dependency_overrides",
        {
            get_db: database,
            get_identity_provider: lambda: provider,
            get_social_review_runtime: lambda: runtime,
            get_media_store: lambda: media,
        },
    )
    completed = threading.Event()
    result: list[dict[str, Any]] = []
    responses: list[tuple[str, int]] = []

    async def harness(scope: Scope, receive: Receive, send: Send) -> None:
        request_started = int(time.time())
        path = scope.get("path", "")
        if path == "/__fixture__/expire" and scope["method"] == "POST":
            clock[0] = NOW + timedelta(days=2)
            await JSONResponse({"ok": True})(scope, receive, send)
            return
        if path == "/__fixture__/driver.mjs":
            script = (
                Path("tests/javascript/social_configuration_browser.mjs")
                .read_text()
                .replace("__WORKSPACE__", str(wid))
                .replace("__DRAFT__", original.review.source.draft_id)
                .replace("__PLATFORM__", platform)
            )
            literal = "'social-owner:browser'"
            assert script.count(literal) == 1
            script = script.replace(literal, json.dumps(actor + ":browser"))
            await Response(script, media_type="text/javascript")(scope, receive, send)
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
            # Exact retained HTML only; modules and APIs remain current.
            raw = Path("tests/fixtures/retained-social-configuration.html").read_bytes()
            assert hashlib.sha256(raw).hexdigest() == (
                "a2806c2269712abc778295b9cc2c6dbb65cb61f3e270d306542691051799e0de"
            )
            html = raw.decode("utf-8")
            assert html.count("/app/assets/social-configuration.mjs") == 1
            html = html.replace(
                "/app/assets/social-configuration.mjs", "/__fixture__/driver.mjs"
            )
            await Response(html, media_type="text/html")(scope, receive, send)
            return

        async def record(message: Any) -> None:
            if message["type"] == "http.response.start":
                assert social_ui_source.ui_evidence is not None
                if path == "/api/customer/v1/session":
                    if scope["method"] == "POST" and message["status"] == 200:
                        social_ui_source.ui_evidence.record_login(
                            social_ui_source, message["headers"], request_started, int(time.time())
                        )
                    elif scope["method"] == "DELETE" and message["status"] == 204:
                        social_ui_source.ui_evidence.record_logout(
                            request_started, int(time.time())
                        )
                if path.endswith("/preview"):
                    responses.append(("campaign_preview", message["status"]))
                elif path.endswith("/options"):
                    responses.append(("social_options", message["status"]))
            await send(message)

        try:
            await app(scope, receive, record)
        except Exception:
            (tmp_path / "harness-error.txt").write_text(traceback.format_exc())
            raise

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
        assert completed.wait(60), "Social review browser did not report completion"
        (tmp_path / "browser-result.json").write_text(json.dumps(result, indent=2))
        (tmp_path / "http-statuses.json").write_text(json.dumps(responses, indent=2))
        assert result and result[0]["status"] == "passed", (result, responses)
        assert_ui_copy_denials(social_ui_source)
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
