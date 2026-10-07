"""Actual authenticated publication browser journeys on both databases."""

import json
import socket
import subprocess
import threading
import time
from collections.abc import Generator
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
import uvicorn
from app.api.customer_execution import get_execution_media_factory
from app.campaign_review.storage import get_media_store
from app.customers.identity import get_identity_provider
from app.customers.models import CustomerUser
from app.database.session import Base, get_db
from app.main import app
from app.publication import execution_mandates
from app.publication.customer_runtime import get_customer_execution_runtime
from app.publication.execution_authorization import owner_authorizer
from app.publication.execution_models import (
    ProviderExecutionAttempt,
    ProviderExecutionMandate,
    ProviderExecutionReceipt,
    ProviderExecutionReview,
    ProviderExposureReservation,
)
from app.publication.social_customer_producer import catalog_request
from app.publication.social_review_runtime import get_social_review_runtime
from app.publication.social_review_service import confirm, prepare
from app.publication.social_selection import ReviewIntent, resolve
from app.settings import Settings, settings
from app.workspaces.models import Workspace
from sqlalchemy import Engine, create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker
from starlette.responses import JSONResponse, Response
from starlette.types import Receive, Scope, Send

from tests.test_campaign_video import encoded as encoded
from tests.test_commerce_measurement import NOW
from tests.test_customer_browser_api_journey import localhost_certificate
from tests.test_customer_identity import ISSUER, FakeProvider
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_portal import portal_executable
from tests.test_customer_social_execution import setup_social
from tests.test_shopify_sales import configuration as configuration


@pytest.mark.parametrize(
    "platform,scenario",
    [
        ("meta_ads", "journey"),
        ("meta_ads", "media_session"),
        ("meta_ads", "media_integrity"),
        ("tiktok_ads", "journey"),
        ("meta_ads", "context_race"),
        *(
            ("meta_ads", "context_" + transition)
            for transition in (
                "aba",
                "body",
                "draft",
                "workspace",
                "logout",
                "session",
                "policy",
                "run",
                "failure",
                "lost",
            )
        ),
        ("meta_ads", "clarity"),
        ("tiktok_ads", "clarity"),
    ],
)
def test_social_execution_real_browser(
    customer_engine: Engine,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    configuration: Settings,
    encoded: Any,
    platform: str,
    scenario: str,
) -> None:
    chromium = portal_executable(
        "chromium", "chromium-browser", "google-chrome", "google-chrome-stable"
    )
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    origin = f"https://127.0.0.1:{listener.getsockname()[1]}"
    monkeypatch.setattr(settings, "customer_app_origin", origin)
    engine = customer_engine
    if engine.dialect.name == "sqlite":
        engine = create_engine(
            f"sqlite:///{tmp_path / 'closure.sqlite'}", connect_args={"check_same_thread": False}
        )
        Base.metadata.create_all(engine)
    factory = sessionmaker(engine)
    with factory() as db:
        original, account, actor, media, cover, runtime, mandate_id, server_http = setup_social(
            db,
            configuration,
            tmp_path,
            platform,
            encoded() if platform == "tiktok_ads" else None,
            monkeypatch,
        )
        wid = account.workspace_id
        discovery = runtime.social_review
        assert discovery is not None
        catalog = discovery.catalog(catalog_request(original.review.source, account), NOW)
        current = resolve(
            db,
            wid,
            actor,
            ReviewIntent.model_validate(
                {
                    "draft_id": original.review.source.draft_id,
                    "draft_revision": original.review.source.revision,
                    "option_id": catalog.options[0].identifier(catalog.request),
                    "answer": {"kind": "meta_no_dsa", "special_category_answer": "none_applicable"}
                    if platform == "meta_ads"
                    else {"kind": "tiktok_cover", "reviewed_pair": True},
                    "cover_media_id": cover,
                }
            ),
            media,
            discovery,
            owner_authorizer,
        )
        row = prepare(db, wid, actor, current, lambda: NOW, owner_authorizer)
        confirm(db, wid, row.id, row.digest, actor, current, lambda: NOW, owner_authorizer)
        if scenario.startswith("context_") or scenario == "clarity":
            second_cover = cover
            second = catalog.options[0].model_copy(
                update={"page_id": "987654321", "label": "Other Page / Pixel"}
            )
            if platform == "tiktok_ads":
                import io

                from app.campaign_review import service as media_service
                from PIL import Image

                raw = io.BytesIO()
                Image.new("RGB", (1200, 1200), "blue").save(raw, format="PNG")
                second_cover = media_service.upload(db, wid, actor, raw.getvalue(), media, NOW).id
                second = catalog.options[0]
            catalog = catalog.model_copy(
                update={
                    "options": [catalog.options[0]]
                    if platform == "tiktok_ads"
                    else [catalog.options[0], second]
                }
            )
            discovery = replace(discovery, catalog=lambda request, now: catalog)
            runtime = replace(runtime, social_review=discovery)
            second_document = resolve(
                db,
                wid,
                actor,
                ReviewIntent(
                    draft_id=original.review.source.draft_id,
                    draft_revision=original.review.source.revision,
                    option_id=second.identifier(catalog.request),
                    answer=current.answer,
                    cover_media_id=second_cover,
                ),
                media,
                discovery,
                owner_authorizer,
            )
            second_row = prepare(db, wid, actor, second_document, lambda: NOW, owner_authorizer)
            confirm(
                db,
                wid,
                second_row.id,
                second_row.digest,
                actor,
                second_document,
                lambda: NOW,
                owner_authorizer,
            )
        mandate = db.get(ProviderExecutionMandate, mandate_id)
        assert mandate is not None
        policy = execution_mandates.policy(db, mandate).model_dump(mode="json")
        user = db.get(CustomerUser, actor)
        assert user is not None
        user.issuer, user.subject = ISSUER, "social-execution-owner"
        workspace = db.get(Workspace, wid)
        assert workspace is not None
        workspace.name = "<img src=x>"
        db.commit()

    def database() -> Generator[Session, None, None]:
        with factory() as db:
            yield db

    monkeypatch.setattr(
        app,
        "dependency_overrides",
        {
            get_db: database,
            get_identity_provider: lambda: FakeProvider(),
            get_customer_execution_runtime: lambda: runtime,
            get_social_review_runtime: lambda: runtime.social_review,
            get_media_store: lambda: media,
            get_execution_media_factory: lambda: lambda: media,
        },
    )
    models = (
        ProviderExecutionReview,
        ProviderExecutionAttempt,
        ProviderExecutionReceipt,
        ProviderExposureReservation,
    )
    with factory() as db:
        prior_financial = tuple(
            db.scalar(select(func.count()).select_from(model)) for model in models
        )
    completed = threading.Event()
    result: list[dict[str, Any]] = []

    async def harness(scope: Scope, receive: Receive, send: Send) -> None:
        path = scope.get("path", "")
        if path == "/__fixture__/driver.mjs":
            script = (
                Path(
                    "tests/javascript/tiktok_legacy_execution_denial.mjs"
                    if platform == "tiktok_ads"
                    else "tests/javascript/execution_media_context.mjs"
                    if scenario.startswith("media_")
                    else "tests/javascript/execution_clarity.mjs"
                    if scenario == "clarity"
                    else "tests/javascript/execution_context_race.mjs"
                    if scenario.startswith("context_")
                    else "tests/javascript/social_execution_browser.mjs"
                )
                .read_text()
                .replace("__SCENARIO__", scenario)
                .replace("__WORKSPACE__", str(wid))
                .replace("__TRANSITION__", scenario.removeprefix("context_"))
                .replace("__DRAFT__", original.review.source.draft_id)
                .replace("__POLICY__", json.dumps(policy))
            )
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
            # Preserve the actual application URL so receipt recovery is exercised.
            html = (
                Path("app/portal/static/execution.html")
                .read_text()
                .replace("/app/assets/execution.mjs", "/__fixture__/driver.mjs")
            )
            await Response(html, media_type="text/html")(scope, receive, send)
            return
        await app(scope, receive, send)

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
        assert completed.wait(60), "Execution browser did not report completion"
        assert result and result[0]["status"] == "passed", result
        if platform == "tiktok_ads":
            assert server_http.posts == server_http.activations == 0
            with factory() as db:
                assert (
                    tuple(db.scalar(select(func.count()).select_from(model)) for model in models)
                    == prior_financial
                )
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
