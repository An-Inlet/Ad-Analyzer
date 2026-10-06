"""Real portal/navigation/GET bridge; consent HTTP is intercepted before any network."""

import asyncio
import base64
import hashlib
import hmac
import html
import json
import socket
import subprocess
import threading
import time
from collections.abc import Generator
from contextlib import ExitStack
from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlencode, urlsplit
from urllib.request import Request, urlopen
from uuid import uuid4

import pytest
import uvicorn
from app.customers.identity import get_identity_provider
from app.customers.models import CustomerMembership, CustomerUser
from app.database.session import Base, get_db
from app.main import app
from app.settings import Settings, settings
from app.shopify import client as shopify_http
from app.shopify.models import ShopifyConnection, ShopifyOAuthState
from sqlalchemy import Engine, create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker
from starlette.types import Receive, Scope, Send
from websockets.sync.client import connect

from tests.test_customer_browser_api_journey import localhost_certificate
from tests.test_customer_identity import ISSUER, FakeProvider
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_portal import portal_executable
from tests.test_google_customer_connections import setup
from tests.test_shopify_sales import SHOP
from tests.test_shopify_sales import configuration as configuration


class Browser:
    def __init__(self, url: str, origin: str) -> None:
        self.context = ExitStack()
        self.socket = self.context.enter_context(connect(url, open_timeout=5))
        self.sequence = 0
        self.origin = origin
        self.callbacks: list[str] = []

    def consent_document(self, url: str) -> str:
        parsed = urlsplit(url)
        assert parsed.scheme == "https" and parsed.hostname == SHOP
        assert parsed.path == "/admin/oauth/authorize"
        params_in = parse_qs(parsed.query)
        assert params_in["redirect_uri"] == [self.origin + "/api/customer/v1/shopify/callback"]
        state = params_in["state"][0]
        values = {
            "shop": SHOP,
            "state": state,
            "code": "offline-consent-code",
            "timestamp": str(int(time.time())),
        }
        secret = settings.shopify_client_secret
        assert secret is not None
        values["hmac"] = hmac.new(
            secret.get_secret_value().encode(),
            "&".join(f"{key}={value}" for key, value in sorted(values.items())).encode(),
            hashlib.sha256,
        ).hexdigest()
        callback = params_in["redirect_uri"][0] + "?" + urlencode(values)
        self.callbacks.append(callback)
        cancel = (
            params_in["redirect_uri"][0]
            + "?"
            + urlencode({"error": "access_denied", "state": state})
        )
        body = (
            "<!doctype html><title>Offline Shopify Consent</title>"
            "<h1>Review Store Permissions</h1>"
            f'<a id="consent-approve" href="{html.escape(callback)}">Approve</a>'
            f'<a id="consent-cancel" href="{html.escape(cancel)}">Cancel</a>'
        )
        return body

    def call(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        self.sequence += 1
        request_id = self.sequence
        self.socket.send(json.dumps({"id": request_id, "method": method, "params": params or {}}))
        while True:
            reply = json.loads(self.socket.recv(timeout=15))
            if reply.get("method") == "Fetch.requestPaused":
                event = reply["params"]
                body = self.consent_document(event["request"]["url"])
                self.sequence += 1
                self.socket.send(
                    json.dumps(
                        {
                            "id": self.sequence,
                            "method": "Fetch.fulfillRequest",
                            "params": {
                                "requestId": event["requestId"],
                                "responseCode": 200,
                                "responseHeaders": [
                                    {"name": "Content-Type", "value": "text/html"},
                                    {"name": "Cache-Control", "value": "no-store"},
                                ],
                                "body": base64.b64encode(body.encode()).decode(),
                            },
                        }
                    )
                )
            if reply.get("id") == request_id:
                assert "error" not in reply, "Browser command failed"
                return dict(reply.get("result", {}))

    def evaluate(self, expression: str) -> Any:
        result = self.call(
            "Runtime.evaluate",
            {"expression": expression, "awaitPromise": True, "returnByValue": True},
        )
        if "exceptionDetails" in result:
            raise AssertionError("Browser expression failed")
        return result.get("result", {}).get("value")

    def wait(self, expression: str) -> None:
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            try:
                if self.evaluate(expression):
                    return
            except AssertionError:
                pass  # A document may be replaced during navigation.
            time.sleep(0.03)
        raise AssertionError("Browser condition did not settle: " + expression)


def test_portal_shopify_consent_cancel_back_retry_and_session_change(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chromium = portal_executable(
        "chromium", "chromium-browser", "google-chrome", "google-chrome-stable"
    )
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    origin = f"https://127.0.0.1:{listener.getsockname()[1]}"
    for name in Settings.model_fields:
        if name.startswith("shopify_"):
            monkeypatch.setattr(settings, name, getattr(configuration, name))
    monkeypatch.setattr(settings, "shopify_customer_enabled", True)
    monkeypatch.setattr(settings, "customer_app_origin", origin)
    provider_calls: list[str] = []

    class ProviderHTTP:
        def open(self, request: Request, timeout: int) -> BytesIO:
            assert timeout == 15
            parsed = urlsplit(request.full_url)
            assert parsed.scheme == "https" and parsed.hostname == SHOP
            if parsed.path == "/admin/oauth/access_token":
                provider_calls.append("token")
                value: dict[str, Any] = {
                    "access_token": "offline-consent-grant",
                    "refresh_token": "offline-refresh",
                    "expires_in": 3600,
                    "refresh_token_expires_in": 86400,
                    "scope": "read_orders,read_products",
                }
            else:
                assert parsed.path.endswith("/graphql.json")
                provider_calls.append("metadata")
                value = {
                    "data": {
                        "shop": {
                            "id": "gid://shopify/Shop/123",
                            "name": "Consent Store",
                            "myshopifyDomain": SHOP,
                            "currencyCode": "USD",
                            "ianaTimezone": "UTC",
                        },
                        "currentAppInstallation": {
                            "accessScopes": [{"handle": "read_orders"}, {"handle": "read_products"}]
                        },
                    }
                }
            return BytesIO(json.dumps(value).encode())

    monkeypatch.setattr(shopify_http, "build_opener", lambda *_: ProviderHTTP())
    engine = customer_engine
    if engine.dialect.name == "sqlite":
        engine = create_engine(
            f"sqlite:///{tmp_path / 'consent.sqlite'}", connect_args={"check_same_thread": False}
        )
        Base.metadata.create_all(engine)
    factory = sessionmaker(engine)
    actor = uuid4().hex
    with factory() as db:
        wid, _ = setup(db, "consent")
        db.add(
            CustomerUser(
                id=actor, issuer=ISSUER, subject="consent-owner", email="owner@example.invalid"
            )
        )
        db.flush()
        db.add(CustomerMembership(user_id=actor, workspace_id=wid, role="owner"))
        db.commit()

    def database() -> Generator[Session, None, None]:
        with factory() as db:
            yield db

    monkeypatch.setattr(
        app,
        "dependency_overrides",
        {get_db: database, get_identity_provider: lambda: FakeProvider()},
    )
    initial_probe, release_probe = threading.Event(), threading.Event()

    async def delayed_initial_session(scope: Scope, receive: Receive, send: Send) -> None:
        # Reproduce login finishing while the portal's startup probe still disables Retry.
        if (
            scope["type"] == "http"
            and scope["method"] == "GET"
            and scope["path"] == "/api/customer/v1/session"
            and not initial_probe.is_set()
        ):
            initial_probe.set()
            assert await asyncio.to_thread(release_probe.wait, 15)
        await app(scope, receive, send)

    cert, key = localhost_certificate(tmp_path)
    server = uvicorn.Server(
        uvicorn.Config(
            delayed_initial_session,
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
    profile = tmp_path / "browser"
    process = subprocess.Popen(
        [
            chromium,
            "--headless",
            "--no-sandbox",
            "--disable-gpu",
            "--disable-background-networking",
            "--no-first-run",
            "--disable-extensions",
            "--ignore-certificate-errors",
            "--remote-debugging-port=0",
            "--remote-debugging-address=127.0.0.1",
            "--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1",
            f"--user-data-dir={profile}",
            "about:blank",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    browser: Browser | None = None
    second: Browser | None = None
    try:
        active = profile / "DevToolsActivePort"
        deadline = time.monotonic() + 10
        while not active.exists() and time.monotonic() < deadline:
            time.sleep(0.03)
        port = active.read_text().splitlines()[0]

        def tabs() -> list[dict[str, Any]]:
            with urlopen(f"http://127.0.0.1:{port}/json", timeout=5) as response:
                return list(json.load(response))

        browser = Browser(tabs()[0]["webSocketDebuggerUrl"], origin)
        browser.call(
            "Fetch.enable",
            {
                "patterns": [
                    {
                        "urlPattern": f"https://{SHOP}/admin/oauth/authorize*",
                        "requestStage": "Request",
                    }
                ]
            },
        )
        browser.call("Page.navigate", {"url": origin + "/app"})
        browser.wait("document.getElementById('retry') !== null")
        assert initial_probe.wait(10)
        assert browser.evaluate("document.getElementById('retry').disabled")

        def login(current: Browser, token: str) -> None:
            assert (
                current.evaluate(
                    "fetch('/api/customer/v1/session',{method:'POST',headers:{'Content-Type':'application/json','X-Inlet-Request':'1'},body:JSON.stringify({id_token:"
                    + json.dumps(token)
                    + "})}).then(r=>r.status)"
                )
                == 200
            )

        login(browser, "consent-owner:first")
        release_probe.set()
        browser.wait(
            "typeof document.getElementById('retry').onclick === 'function' && "
            "!document.getElementById('retry').disabled"
        )
        browser.evaluate("document.getElementById('retry').click()")

        def workspace(current: Browser) -> None:
            current.wait(
                "document.getElementById('workspace')?.options.length === 2 && "
                "!document.getElementById('workspace').disabled"
            )
            current.evaluate(
                f"document.getElementById('workspace').value='{wid}';"
                "document.getElementById('workspace').dispatchEvent(new Event('change'))"
            )
            current.wait(
                "!document.getElementById('shopify-connect').hidden && "
                "!document.getElementById('shopify-authorize').disabled && "
                "!document.getElementById('workspace-content').hidden"
            )

        def begin(current: Browser) -> None:
            current.evaluate(
                "document.getElementById('shopify-domain').value="
                + json.dumps(SHOP)
                + ";document.getElementById('shopify-connect').requestSubmit()"
            )
            current.wait("document.getElementById('consent-cancel') !== null")

        workspace(browser)
        begin(browser)
        browser.evaluate("document.getElementById('consent-cancel').click()")
        browser.wait("document.getElementById('result')?.textContent.includes('not completed')")
        assert browser.evaluate("location.search") == ""
        with factory() as db:
            assert db.scalar(select(func.count()).select_from(ShopifyOAuthState)) == 1
        assert provider_calls == []
        browser.evaluate("document.getElementById('cancel-attempt').click()")
        browser.wait("document.getElementById('result').textContent.includes('attempt canceled')")
        with factory() as db:
            assert db.scalar(select(func.count()).select_from(ShopifyOAuthState)) == 0
        browser.evaluate("document.getElementById('return-workspace').click()")
        browser.wait(
            "document.getElementById('shopify-domain') !== null && "
            "!document.getElementById('workspace-content').hidden"
        )
        begin(browser)
        old_callback = browser.callbacks[-1]
        browser.evaluate("history.back()")
        browser.wait("document.getElementById('workspace') !== null")
        workspace(browser)
        begin(browser)
        browser.call("Page.navigate", {"url": old_callback})
        browser.wait("document.getElementById('result')?.textContent.includes('start again')")
        assert provider_calls == []
        browser.evaluate("document.getElementById('return-workspace').click()")
        workspace(browser)
        begin(browser)
        # A second tab changes the real customer session while consent is pending.
        target = browser.call("Target.createTarget", {"url": origin + "/app"})["targetId"]
        second = Browser(
            next(tab["webSocketDebuggerUrl"] for tab in tabs() if tab["id"] == target), origin
        )
        second.wait("document.getElementById('retry') !== null")
        login(second, "consent-stranger:second")
        browser.evaluate("document.getElementById('consent-approve').click()")
        browser.wait("document.getElementById('result')?.textContent.includes('start again')")
        assert provider_calls == []
        login(second, "consent-owner:third")
        browser.evaluate("document.getElementById('return-workspace').click()")
        workspace(browser)
        begin(browser)
        browser.evaluate("document.getElementById('consent-approve').click()")
        browser.wait(
            "document.getElementById('shopify-current')?.textContent.includes('Connected')"
        )
        assert browser.evaluate("document.getElementById('workspace').value") == str(wid)
        assert browser.evaluate("location.search") == ""
        assert provider_calls == ["token", "metadata"]
        with factory() as db:
            row = db.scalar(select(ShopifyConnection))
            assert row is not None and row.workspace_id == wid and row.shop_domain == SHOP
        history = browser.call("Page.getNavigationHistory")
        assert all(
            "code=" not in entry["url"] and "hmac=" not in entry["url"]
            for entry in history["entries"]
        )
    finally:
        release_probe.set()
        if browser:
            browser.context.close()
        if second:
            second.context.close()
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
        server.should_exit = True
        thread.join(timeout=10)
        listener.close()
        if engine is not customer_engine:
            engine.dispose()
