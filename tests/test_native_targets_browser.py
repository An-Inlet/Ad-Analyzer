"""Real HTTPS UI/API/vault/native collectors; no replaced diagnostic service."""

import asyncio
import json
import socket
import subprocess
import threading
import time
from collections.abc import Generator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest
import uvicorn
from app.ads.models import AdvertisingAccount
from app.api import customer_planning_target_catalog as api
from app.collectors import account_diagnostics
from app.customers.identity import get_identity_provider
from app.customers.models import CustomerMembership, CustomerUser
from app.database.session import Base, get_db
from app.main import app
from app.publication import execution_mandates
from app.settings import Settings, settings
from cryptography.fernet import Fernet
from pydantic import SecretStr
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker
from starlette.responses import JSONResponse, Response
from starlette.types import Receive, Scope, Send

from tests import test_planning_target_catalog_api as source_fixture
from tests.test_customer_browser_api_journey import localhost_certificate
from tests.test_customer_identity import ISSUER, FakeProvider
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_portal import portal_executable
from tests.test_google_native_inventory import key, payloads
from tests.test_meta_native_inventory import PRIVATE
from tests.test_meta_native_inventory import Server as MetaServer
from tests.test_planning_target_catalog_api import seed
from tests.test_shopify_sales import configuration as configuration
from tests.test_tiktok_native_inventory import Server as TikTokServer


@pytest.mark.parametrize("provider", ["google_ads", "meta_ads", "tiktok_ads"])
def test_actual_native_targets_browser(
    customer_engine: Engine,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    configuration: Settings,
    provider: str,
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
            f"sqlite:///{tmp_path / 'diagnostics.sqlite'}",
            connect_args={"check_same_thread": False},
        )
        Base.metadata.create_all(engine)
    factory = sessionmaker(engine)
    for attr in (
        "google_customer_encryption_key",
        "meta_token_encryption_key",
        "source_token_encryption_key",
    ):
        monkeypatch.setattr(settings, attr, SecretStr(Fernet.generate_key().decode()))
    monkeypatch.setattr(settings, "google_customer_client_id", "synthetic-client")
    monkeypatch.setattr(settings, "google_customer_client_secret", SecretStr("synthetic-secret"))
    monkeypatch.setattr(settings, "meta_client_secret", SecretStr("synthetic-app-secret"))
    monkeypatch.setattr(settings, "customer_native_diagnostics_enabled", True)
    monkeypatch.setattr(source_fixture, "NOW", datetime.now(UTC))
    request = seed(engine, configuration, tmp_path, provider)
    wid, actor = request.workspace_id, request.actor
    with factory() as db:
        user = db.get(CustomerUser, actor)
        assert user
        user.issuer, user.subject = ISSUER, "diagnostics-browser"
        account = db.get(AdvertisingAccount, request.account_id)
        assert account
        account.name = "Brand <img src=x>"
        db.commit()
    monkeypatch.setattr(api, "utc_now", lambda: datetime.now(UTC))

    def no_mandate(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("account reads must not require a spending mandate")

    monkeypatch.setattr(execution_mandates, "checked", no_mandate)
    calls: list[str] = []
    made: list[bool] = []
    closed: list[bool] = []
    native_server = MetaServer() if provider == "meta_ads" else TikTokServer()

    def wire(req: httpx.Request) -> httpx.Response:
        rows: list[dict[str, Any]]
        calls.append(str(req.url.host))
        if req.url.host == "oauth2.googleapis.com":
            return httpx.Response(
                200, json=dict(access_token=PRIVATE, token_type="Bearer", expires_in=3600)
            )
        if provider == "google_ads":
            query = json.loads(req.content)["query"]
            data = payloads()
            data["customer"][0]["customer"]["timeZone"] = "UTC"
            if "FROM ad_group" in query:
                rows = [
                    {
                        "adGroup": dict(
                            resourceName="customers/1234567890/adGroups/7",
                            campaign="customers/1234567890/campaigns/1",
                            name="Child <img src=x>",
                            status="ENABLED",
                            type="SEARCH_STANDARD",
                        )
                    }
                ]
            else:
                rows = data[key(query)]
                if ".name" in query:
                    rows[0]["campaign"]["name"] = None
            return httpx.Response(200, json={"results": rows})
        fields = req.url.params.get("fields", "")
        metadata = (
            "name" in fields.split(",") or "campaign_name" in fields or "adgroup_name" in fields
        )
        if metadata and isinstance(native_server, MetaServer):
            rows = json.loads(
                json.dumps(
                    native_server.adsets
                    if req.url.path.endswith("adsets")
                    else native_server.campaigns
                )
            )
            response = httpx.Response(200, json={"data": rows})
        else:
            response = native_server(req)
        if metadata:
            data = response.json()
            rows = data["data"] if provider == "meta_ads" else data["data"]["list"]
            for row in rows:
                field = (
                    "name"
                    if provider == "meta_ads"
                    else "adgroup_name"
                    if "adgroup/get" in req.url.path
                    else "campaign_name"
                )
                row[field] = (
                    "Native <img src=x>"
                    if "adsets" in req.url.path or "adgroup/get" in req.url.path
                    else (None if provider == "meta_ads" else "x" * 161)
                )
            return httpx.Response(200, json=data)
        return response

    class Transport(httpx.MockTransport):
        def close(self) -> None:
            closed.append(True)
            super().close()

    def transport() -> httpx.BaseTransport:
        made.append(True)
        return Transport(wire)

    monkeypatch.setattr(account_diagnostics, "diagnostic_transport", transport)

    def database() -> Generator[Session, None, None]:
        with factory() as db:
            yield db

    monkeypatch.setattr(
        app,
        "dependency_overrides",
        {get_db: database, get_identity_provider: lambda: FakeProvider()},
    )
    hold, entered, release, completed = (threading.Event() for _ in range(4))
    result: list[dict[str, Any]] = []
    disabled_calls: list[int] = []

    async def harness(scope: Scope, receive: Receive, send: Send) -> None:
        path = scope.get("path", "")
        if path == "/__fixture__/driver.mjs":
            script = (
                Path("tests/javascript/native_targets_api_browser.mjs")
                .read_text()
                .replace("__WORKSPACE__", str(wid))
                .replace("__ACCOUNT__", str(request.account_id))
            )
            await Response(script, media_type="text/javascript")(scope, receive, send)
            return
        if path == "/__fixture__/start":
            html = (
                Path("app/portal/static/account-diagnostics.html")
                .read_text()
                .replace("/app/assets/account-diagnostics.mjs", "/__fixture__/driver.mjs")
            )
            await Response(html, media_type="text/html")(scope, receive, send)
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
        if path == "/__fixture__/hold":
            entered.clear()
            release.clear()
            hold.set()
            await JSONResponse({"ok": True})(scope, receive, send)
            return
        if path == "/__fixture__/entered":
            await JSONResponse({"entered": entered.is_set()})(scope, receive, send)
            return
        if path == "/__fixture__/release":
            release.set()
            await JSONResponse({"ok": True})(scope, receive, send)
            return
        if path in {"/__fixture__/disabled", "/__fixture__/enabled"}:
            disabled = path.endswith("disabled")
            if disabled:
                disabled_calls.append(len(calls))
            else:
                assert len(calls) == disabled_calls[-1], "disabled factory made native requests"
            monkeypatch.setattr(settings, "customer_native_diagnostics_enabled", not disabled)
            await JSONResponse({"ok": True})(scope, receive, send)
            return
        if path == "/__fixture__/viewer":
            with factory() as db:
                membership = db.get(CustomerMembership, (actor, wid))
                assert membership
                membership.role = "viewer"
                db.commit()
            await JSONResponse({"ok": True})(scope, receive, send)
            return
        if path.endswith("/planning/target-catalog-v2") and hold.is_set():
            hold.clear()
            messages: list[Any] = []

            async def capture(message: Any) -> None:
                messages.append(message)

            await app(scope, receive, capture)
            entered.set()
            assert await asyncio.to_thread(release.wait, 15), "held response was not released"
            for message in messages:
                await send(message)
            return
        await app(scope, receive, send)

    certificate, tls_key = localhost_certificate(tmp_path)
    server = uvicorn.Server(
        uvicorn.Config(
            harness,
            log_level="critical",
            lifespan="off",
            ssl_certfile=str(certificate),
            ssl_keyfile=str(tls_key),
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
        assert completed.wait(60), "Actual diagnostics browser did not report completion"
        assert result and result[0]["status"] == "passed", result
        assert len(made) == 7 and len(closed) == len(made), (
            "seven explicit native target reads; all transports closed"
        )
    finally:
        release.set()
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
