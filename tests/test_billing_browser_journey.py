"""Visible Stripe test navigation; real portal/API/DB, intercepted provider boundaries."""

import asyncio
import base64
import html
import json
import socket
import subprocess
import threading
import time
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit
from urllib.request import urlopen
from uuid import uuid4

import httpx
import pytest
import uvicorn
from app.billing.contracts import get_billing_transport
from app.billing.dispatcher import run
from app.billing.models import WorkspaceBilling
from app.billing.stripe import StripeBilling
from app.customers.identity import get_identity_provider
from app.customers.models import CustomerMembership, CustomerSession, CustomerUser
from app.database.session import Base, get_db
from app.main import app
from app.settings import settings
from pydantic import SecretStr
from sqlalchemy import Engine, create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from starlette.types import Receive, Scope, Send

from tests.test_customer_billing import POLICY, SECRET, payload, signature
from tests.test_customer_browser_api_journey import localhost_certificate
from tests.test_customer_identity import ISSUER, FakeProvider
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_portal import portal_executable
from tests.test_google_customer_connections import setup
from tests.test_shopify_consent_browser import Browser


class BillingBrowser(Browser):
    def evaluate(self, expression: str) -> Any:
        return super().evaluate(expression.replace("$(", "document.getElementById("))

    def call(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        self.sequence += 1
        request_id = self.sequence
        self.socket.send(json.dumps({"id": request_id, "method": method, "params": params or {}}))
        while True:
            reply = json.loads(self.socket.recv(timeout=20))
            if reply.get("method") == "Fetch.requestPaused":
                event = reply["params"]
                parsed = urlsplit(event["request"]["url"])
                assert parsed.scheme == "https" and parsed.hostname in {
                    "checkout.stripe.com",
                    "billing.stripe.com",
                }
                self.callbacks.append(event["request"]["url"])
                target = self.origin  # Set to the actual server-generated return URL by the test.
                body = (
                    "<!doctype html><title>Offline Stripe Test</title>"
                    "<h1>Offline Test Billing</h1>"
                    f'<a id="provider-return" href="{html.escape(target)}">Return</a>'
                    f'<a id="provider-cancel" href="{html.escape(target)}">Cancel</a>'
                )
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
                assert "error" not in reply
                return dict(reply.get("result", {}))


class BillingHTTP:
    def __init__(self) -> None:
        self.calls: list[httpx.Request] = []
        self.return_url = ""
        self.lose_first = True
        self.cancel = False
        self.on_portal: Any = None

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.calls.append(request)
        assert request.url.host == "api.stripe.com"
        data = parse_qs(request.content.decode())
        now = datetime.now(UTC)
        value: dict[str, Any] = {"livemode": False}
        if request.url.path == "/v1/customers":
            value.update(id="cus_fixture")
        elif request.url.path == "/v1/checkout/sessions":
            assert data["line_items[0][price]"] == [POLICY.price_id]
            assert data["success_url"] == data["cancel_url"]
            self.return_url = data["success_url"][0]
            value.update(
                id="cs_fixture",
                customer="cus_fixture",
                mode="subscription",
                url="https://checkout.stripe.com/c/pay/cs_test_fixture",
                expires_at=int((now + timedelta(hours=1)).timestamp()),
            )
            if self.lose_first:
                self.lose_first = False
                raise httpx.ReadTimeout("synthetic lost response after provider acceptance")
        elif request.url.path == "/v1/checkout/sessions/cs_fixture":
            value.update(
                id="cs_fixture",
                customer="cus_fixture",
                mode="subscription",
                status="open",
                subscription=None,
            )
        elif request.url.path == "/v1/subscriptions/sub_fixture":
            value.update(
                id="sub_fixture",
                customer="cus_fixture",
                status="active",
                cancel_at_period_end=self.cancel,
                items={
                    "has_more": False,
                    "data": [
                        {
                            "quantity": 1,
                            "price": {"id": POLICY.price_id},
                            "current_period_end": int((now + timedelta(days=30)).timestamp()),
                        }
                    ],
                },
            )
        elif request.url.path == "/v1/billing_portal/sessions":
            self.return_url = data["return_url"][0]
            if self.on_portal:
                self.on_portal()
            value.update(
                customer="cus_fixture",
                configuration="bpc_fixture",
                url="https://billing.stripe.com/p/session/test_fixture",
            )
        else:
            raise AssertionError("Unexpected billing HTTP endpoint")
        return httpx.Response(200, json=value)


def test_visible_checkout_return_recovery_management_and_revocation(
    customer_engine: Engine, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    chromium = portal_executable(
        "chromium", "chromium-browser", "google-chrome", "google-chrome-stable"
    )
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    origin = f"https://127.0.0.1:{listener.getsockname()[1]}"
    for name, value in {
        "customer_app_origin": origin,
        "billing_price_id": POLICY.price_id,
        "billing_max_accounts": POLICY.max_accounts,
        "billing_portal_configuration": "bpc_fixture",
        "billing_webhook_secret": SecretStr(SECRET),
    }.items():
        monkeypatch.setattr(settings, name, value)
    engine = customer_engine
    if engine.dialect.name == "sqlite":
        engine = create_engine(
            f"sqlite:///{tmp_path / 'billing.sqlite'}", connect_args={"check_same_thread": False}
        )
        Base.metadata.create_all(engine)
    factory = sessionmaker(engine)
    actor = uuid4().hex
    with factory() as db:
        wid, _ = setup(db, "billing-browser")
        other_wid, _ = setup(db, "billing-other")
        db.add(
            CustomerUser(
                id=actor, issuer=ISSUER, subject="billing-owner", email="owner@example.invalid"
            )
        )
        db.flush()
        db.add(CustomerMembership(user_id=actor, workspace_id=wid, role="owner"))
        db.add(CustomerMembership(user_id=actor, workspace_id=other_wid, role="owner"))
        db.commit()
    io = BillingHTTP()
    transport = StripeBilling(
        SecretStr("sk_test_offline_fixture"),
        "2025-03-31.basil",
        http_transport=httpx.MockTransport(io),
    )

    def database() -> Generator[Session, None, None]:
        with factory() as db:
            yield db

    monkeypatch.setattr(
        app,
        "dependency_overrides",
        {
            get_db: database,
            get_identity_provider: lambda: FakeProvider(),
            get_billing_transport: lambda: transport,
        },
    )
    initial_probe, release_probe = threading.Event(), threading.Event()

    async def delayed_initial_session(scope: Scope, receive: Receive, send: Send) -> None:
        # Force the startup probe to overlap login, as it can under full-suite load.
        # The captured unauthenticated request must finish before Retry is clickable.
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
    while not server.started and time.monotonic() < deadline:
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
    browser: BillingBrowser | None = None
    try:
        active = profile / "DevToolsActivePort"
        deadline = time.monotonic() + 10
        while not active.exists() and time.monotonic() < deadline:
            time.sleep(0.03)
        port = active.read_text().splitlines()[0]
        with urlopen(f"http://127.0.0.1:{port}/json", timeout=5) as response:
            tabs = json.load(response)
        browser = BillingBrowser(tabs[0]["webSocketDebuggerUrl"], origin)
        browser.call(
            "Fetch.enable",
            {
                "patterns": [
                    {"urlPattern": "https://checkout.stripe.com/*"},
                    {"urlPattern": "https://billing.stripe.com/*"},
                ]
            },
        )
        browser.call("Page.navigate", {"url": origin + "/app"})
        browser.wait("$('retry') !== null")
        assert initial_probe.wait(10)
        assert browser.evaluate("$('retry').disabled")
        assert (
            browser.evaluate(
                "fetch('/api/customer/v1/session',{method:'POST',headers:{'Content-Type':'application/json','X-Inlet-Request':'1'},body:JSON.stringify({id_token:'billing-owner:first'})}).then(r=>r.status)"
            )
            == 200
        )
        release_probe.set()
        browser.wait("typeof $('retry').onclick === 'function' && !$('retry').disabled")
        browser.evaluate("$('retry').click()")
        browser.wait("$('workspace').options.length === 3 && !$('workspace').disabled")
        browser.evaluate(
            f"$('workspace').value='{wid}';$('workspace').dispatchEvent(new Event('change'))"
        )
        browser.wait("!$('checkout').hidden && !$('checkout').disabled")
        browser.evaluate("$('checkout').click()")
        browser.wait("$('message').className === 'error' && !$('billing-refresh').disabled")
        browser.evaluate("$('billing-refresh').click()")
        browser.wait("$('checkout').textContent.includes('Resume') && !$('checkout').disabled")
        expected_return = origin + f"/app/settings?workspace={wid}&billing_return=1"
        assert io.return_url == expected_return
        browser.origin = expected_return
        browser.evaluate("$('checkout').click()")
        browser.wait("$('provider-cancel') !== null")
        assert browser.evaluate("location.hostname") == "checkout.stripe.com"
        browser.evaluate("$('provider-cancel').click()")
        browser.wait("$('checkout')?.textContent.includes('Resume') && !$('checkout').disabled")
        assert browser.evaluate("location.search") == ""
        assert browser.evaluate("$('workspace').value") == str(wid)
        browser.evaluate("$('checkout').click()")
        browser.wait("$('provider-return') !== null")
        browser.evaluate("$('provider-return').click()")
        browser.wait(
            "$('billing-detail')?.textContent.includes('Checkout is pending') && "
            "!$('billing-refresh').disabled"
        )
        posts = [
            r for r in io.calls if r.method == "POST" and r.url.path == "/v1/checkout/sessions"
        ]
        assert len(posts) == 2 and len({r.headers["Idempotency-Key"] for r in posts}) == 1
        with factory() as db:
            row = db.get(WorkspaceBilling, wid)
            assert row and row.subscription_id is None and row.status == "unconfigured"

        def deliver(event: str) -> None:
            body = payload(event)
            with httpx.Client(verify=False) as client:
                result = client.post(
                    origin + "/api/billing/stripe/events",
                    content=body,
                    headers={"Stripe-Signature": signature(body, datetime.now(UTC))},
                )
                assert result.status_code == 200
            run(factory, POLICY, transport, datetime.now(UTC))

        deliver("evt_browser_active")
        browser.evaluate("$('billing-refresh').click()")
        browser.wait("$('billing').textContent.startsWith('Active') && !$('management').disabled")
        assert browser.evaluate("$('checkout').hidden")
        browser.evaluate("$('management').click()")
        browser.wait("$('provider-return') !== null")
        assert browser.evaluate("location.hostname") == "billing.stripe.com"
        io.cancel = True
        browser.evaluate("$('provider-return').click()")
        browser.wait(
            "$('billing')?.textContent.startsWith('Active') && !$('billing-refresh').disabled"
        )
        assert not browser.evaluate(
            "$('billing-detail').textContent.includes('Cancellation is scheduled')"
        )
        deliver("evt_browser_cancel")
        browser.evaluate("$('billing-refresh').click()")
        browser.wait("$('billing-detail').textContent.includes('Cancellation is scheduled')")

        # A delayed response from the previous workspace must never navigate.
        entered, release = threading.Event(), threading.Event()

        def pause() -> None:
            entered.set()
            assert release.wait(15)

        io.on_portal = pause
        count = len(browser.callbacks)
        browser.evaluate("$('management').click()")
        assert entered.wait(10)
        try:
            browser.evaluate(
                f"$('workspace').value='{other_wid}';"
                "$('workspace').dispatchEvent(new Event('change'))"
            )
            browser.wait("$('billing').textContent.startsWith('Not Configured')")
        finally:
            release.set()
        browser.wait("!$('management').disabled")
        assert len(browser.callbacks) == count
        browser.call("Page.navigate", {"url": expected_return})
        browser.wait("!$('management')?.hidden && !$('management').disabled")

        # Downgrade during the provider wait: response must not release a portal URL.
        def demote() -> None:
            with factory() as db:
                member = db.get(CustomerMembership, (actor, wid))
                assert member
                member.role = "viewer"
                db.commit()

        io.on_portal = demote
        count = len(browser.callbacks)
        browser.evaluate("$('management').click()")
        browser.wait("$('message').className === 'error' && $('management').hidden")
        assert len(browser.callbacks) == count
        browser.evaluate("$('billing-refresh').click()")
        browser.wait(
            "$('billing').textContent.startsWith('Active') && !$('billing-refresh').disabled"
        )
        assert browser.evaluate("$('checkout').hidden && $('management').hidden")
        # Restore owner, then revoke the session while obtaining a management URL.
        with factory() as db:
            member = db.get(CustomerMembership, (actor, wid))
            assert member
            member.role = "owner"
            db.commit()
        browser.call("Page.navigate", {"url": expected_return})
        browser.wait("!$('management')?.hidden && !$('management').disabled")

        def revoke() -> None:
            with factory() as db:
                for session in db.scalars(
                    select(CustomerSession).where(CustomerSession.user_id == actor)
                ):
                    session.revoked_at = int(time.time())
                db.commit()

        io.on_portal = revoke
        browser.evaluate("$('management').click()")
        browser.wait("!$('signed-out').hidden")
        assert len(browser.callbacks) == count
        assert browser.evaluate(
            "$('billing').textContent === '' && $('billing-detail').textContent === ''"
        )
    finally:
        release_probe.set()
        if browser:
            browser.context.close()
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
