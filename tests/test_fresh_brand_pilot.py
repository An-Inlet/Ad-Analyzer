"""Fresh visible customer continuity; only provider HTTP/SDK and worker timing are mocked."""

import hashlib
import hmac
import html
import json
import socket
import subprocess
import threading
import time
from collections.abc import Generator
from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlencode, urlsplit
from urllib.request import Request, urlopen

import httpx
import pytest
import uvicorn
from app.api import (
    customer_account_diagnostics,
    customer_billing,
    customer_campaign_review,
    customer_goals,
    customer_google,
    customer_mandates,
    customer_plan_review,
    customer_shopify,
)
from app.billing.contracts import get_billing_transport
from app.billing.dispatcher import run as billing_run
from app.billing.entitlements import policy
from app.billing.models import WorkspaceBilling
from app.billing.scope import configured_scope
from app.billing.service import require_entitlement
from app.billing.stripe import StripeBilling
from app.collectors import account_diagnostics
from app.commerce import reporting
from app.commerce.ledger import MEASUREMENT_SCOPES
from app.commerce.models import CommerceEntry
from app.commerce.sync import CommerceSyncService
from app.customers.identity import get_identity_provider
from app.customers.models import CustomerMembership, CustomerSession, CustomerUser
from app.database.session import Base, get_db
from app.goals import service as goals
from app.goals.models import Goal
from app.google_connections.http import GoogleHTTPRead
from app.google_connections.models import GoogleCustomerConnection
from app.main import app
from app.publication.execution_models import ProviderExecutionApproval, ProviderExecutionAttempt
from app.session_automation.models import AutomaticDecisionAdmission
from app.settings import Settings, settings
from app.shopify import client as shopify_http
from app.shopify.models import ShopifyConnection
from app.workspaces.models import Workspace
from cryptography.fernet import Fernet
from fastapi import HTTPException
from pydantic import SecretStr
from sqlalchemy import Engine, create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker
from starlette.responses import Response
from starlette.types import Receive, Scope, Send

from tests.browser_targets import wait_for_page_target
from tests.test_billing_offers import PROFILE, TEST, StripeOfferFixture
from tests.test_commerce_measurement import NOW, agreement, source
from tests.test_customer_billing import SECRET, signature
from tests.test_customer_browser_api_journey import SDK, localhost_certificate
from tests.test_customer_identity import FakeProvider
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_portal import portal_executable
from tests.test_google_connections_browser import GoogleBrowser
from tests.test_google_native_inventory import key, payloads
from tests.test_inlet_customer_journey import JourneyClock
from tests.test_shopify_sales import SHOP
from tests.test_shopify_sales import configuration as configuration


class TestOfferHTTP(StripeOfferFixture):
    __test__ = False

    def __init__(self) -> None:
        super().__init__()
        self.return_url = ""
        self.paid = False

    def document(self, path: str) -> dict[str, Any]:
        value = super().document(path)

        def test_mode(item: Any) -> Any:
            if isinstance(item, dict):
                return {k: False if k == "livemode" else test_mode(v) for k, v in item.items()}
            if isinstance(item, list):
                return [test_mode(v) for v in item]
            return item

        value = test_mode(value)
        if "checkout/sessions" in path and "line_items" not in path and not self.paid:
            value.update(status="open", subscription=None)
        return dict(value)

    def respond(self, request: httpx.Request) -> httpx.Response:
        assert request.url.host == "api.stripe.com"
        if request.method == "POST" and request.url.path == "/v1/checkout/sessions":
            self.return_url = parse_qs(request.content.decode())["success_url"][0]
        return super().respond(request)


class FreshBrowser(GoogleBrowser):
    def __init__(self, url: str, origin: str, billing: TestOfferHTTP) -> None:
        super().__init__(url, origin)
        self.billing = billing

    def consent_document(self, url: str) -> str:
        host = urlsplit(url).hostname
        if host == "accounts.google.com":
            return super().consent_document(url)
        if host == SHOP:
            params = parse_qs(urlsplit(url).query)
            values = dict(
                shop=SHOP,
                state=params["state"][0],
                code="offline-consent-code",
                timestamp=str(int(NOW.timestamp())),
            )
            secret = settings.shopify_client_secret
            assert secret
            values["hmac"] = hmac.new(
                secret.get_secret_value().encode(),
                "&".join(f"{k}={v}" for k, v in sorted(values.items())).encode(),
                hashlib.sha256,
            ).hexdigest()
            callback = params["redirect_uri"][0] + "?" + urlencode(values)
            return (
                '<title>Offline Shopify Consent</title><a id="consent-approve" href="'
                + html.escape(callback)
                + '">Approve</a>'
            )
        assert host == "checkout.stripe.com"
        return (
            '<title>Offline Stripe Test</title><a id="provider-return" href="'
            + html.escape(self.billing.return_url)
            + '">Return To Inlet</a>'
        )

    def js(self, code: str) -> Any:
        return self.evaluate(code.replace("$(", "document.getElementById("))

    def ready(self, code: str) -> None:
        try:
            self.wait(code.replace("$(", "document.getElementById("))
        except AssertionError as exc:
            message = self.evaluate(
                "document.getElementById('result')?.textContent || document.getEl"
                "ementById('message')?.textContent || document.getElementById('st"
                "atus')?.textContent || document.getElementById('creation-status'"
                ")?.textContent || document.getElementById('review-status')?.textContent"
                " || location.pathname"
            )
            raise AssertionError(
                str(exc)
                + "; customer status="
                + str(message)
                + "; review="
                + str(self.evaluate("document.getElementById('review-status')?.textContent"))
            ) from None

    def navigate(self, path: str) -> None:
        self.call("Page.navigate", {"url": self.origin + path})

    def api(self, path: str, method: str = "GET", body: Any = None) -> Any:
        return self.js(
            (
                "(async()=>{const csrf=document.cookie.split(';').map(x=>x.trim()"
                ").find(x=>x.startsWith('__Host-inlet_csrf='))?.split('=')[1];con"
                "st r=await fetch("
            )
            + json.dumps(path)
            + ",{method:"
            + json.dumps(method)
            + ",headers:{'Content-Type':'application/json','X-CSRF-Token':csrf},body:"
            + ("undefined" if body is None else "JSON.stringify(" + json.dumps(body) + ")")
            + "});return {status:r.status,body:await r.json().catch(()=>null)};})()"
        )


def test_fresh_visible_brand_journey(
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
    profile = PROFILE.model_copy(update={"scope": TEST})
    values: dict[str, Any] = {
        "customer_app_origin": origin,
        "customer_auth_enabled": True,
        "customer_browser_auth_enabled": True,
        "customer_identity_project_id": "offline-browser",
        "customer_identity_web_api_key": "offline-public-browser-key-000000",
        "customer_identity_web_app_id": "1:123456:web:abcdef",
        "billing_provider_mode": "stripe_test",
        "billing_api_key": SecretStr("sk_test_offline"),
        "billing_api_version": profile.api_version,
        "billing_merchant_account_id": TEST.merchant_account_id,
        "billing_offer_profile": profile.model_dump_json(),
        "billing_webhook_secret": SecretStr(SECRET),
        "billing_required": True,
        "google_customer_runtime_mode": "google_read",
        "google_customer_client_id": "offline-client",
        "google_customer_client_secret": SecretStr("offline-secret"),
        "google_customer_developer_token": SecretStr("offline-developer"),
        "google_customer_api_version": "v25",
        "google_customer_encryption_key": SecretStr(Fernet.generate_key().decode()),
        "customer_native_diagnostics_enabled": True,
        "media_storage_mode": "local_dev",
        "media_local_directory": str(tmp_path / "private-media"),
    }
    for field in Settings.model_fields:
        if field.startswith("shopify_"):
            values[field] = getattr(configuration, field)
    values.update(shopify_customer_enabled=True, shopify_measurement_enabled=True)
    for field, value in values.items():
        monkeypatch.setattr(settings, field, value)
    for module in (
        customer_billing,
        customer_goals,
        customer_shopify,
        customer_google,
        customer_plan_review,
        customer_mandates,
        customer_campaign_review,
        goals,
        reporting,
    ):
        monkeypatch.setattr(module, "datetime", JourneyClock)
    monkeypatch.setattr(customer_account_diagnostics, "utc_now", lambda: NOW)
    engine = customer_engine
    if engine.dialect.name == "sqlite":
        engine = create_engine(
            f"sqlite:///{tmp_path / 'fresh.sqlite'}",
            connect_args={"check_same_thread": False, "timeout": 10},
        )
        Base.metadata.create_all(engine)
    factory = sessionmaker(engine)
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(CustomerUser)) == 0
        assert db.scalar(select(func.count()).select_from(Workspace)) == 0

    billing = TestOfferHTTP()
    stripe_init = StripeBilling.__init__

    def stripe_setup(self: StripeBilling, *args: Any, **kwargs: Any) -> None:
        kwargs["http_transport"] = httpx.MockTransport(billing.respond)
        kwargs["clock"] = lambda: NOW
        stripe_init(self, *args, **kwargs)

    monkeypatch.setattr(StripeBilling, "__init__", stripe_setup)
    native_calls: list[str] = []

    def google_wire(request: httpx.Request) -> httpx.Response:
        native_calls.append(
            "oauth" if request.url.host == "oauth2.googleapis.com" else "google_read"
        )
        if request.url.host == "oauth2.googleapis.com":
            return httpx.Response(
                200,
                json=dict(
                    access_token="offline-access",
                    refresh_token="offline-refresh",
                    expires_in=3600,
                    token_type="Bearer",
                ),
            )
        if request.method == "GET":
            return httpx.Response(200, json={"resourceNames": ["customers/1234567890"]})
        query = json.loads(request.content)["query"]
        data = payloads()
        data["customer"][0]["customer"].update(
            timeZone="UTC", manager=False, descriptiveName="Fresh Brand Ads"
        )
        return httpx.Response(200, json={"results": data[key(query)]})

    google_init = GoogleHTTPRead.__init__

    def google_setup(self: GoogleHTTPRead, *args: Any, **kwargs: Any) -> None:
        kwargs["transport"] = httpx.MockTransport(google_wire)
        google_init(self, *args, **kwargs)

    monkeypatch.setattr(GoogleHTTPRead, "__init__", google_setup)
    monkeypatch.setattr(
        account_diagnostics, "diagnostic_transport", lambda: httpx.MockTransport(google_wire)
    )
    shop_calls: list[str] = []

    class ShopifyHTTP:
        def open(self, request: Request, timeout: int) -> BytesIO:
            assert timeout == 15 and urlsplit(request.full_url).hostname == SHOP
            assert isinstance(request.data, bytes)
            body = json.loads(request.data)
            shop_calls.append(
                "token" if request.full_url.endswith("access_token") else "shopify_read"
            )
            if request.full_url.endswith("access_token"):
                result: dict[str, Any] = dict(
                    access_token="offline-shop",
                    refresh_token="offline-refresh",
                    expires_in=3600,
                    scope=",".join(sorted(MEASUREMENT_SCOPES)),
                )
            elif "AnalyzerShop" in body["query"]:
                result = {
                    "data": {
                        "shop": {
                            "id": "gid://shopify/Shop/123",
                            "name": "Fresh Brand Store",
                            "myshopifyDomain": SHOP,
                            "currencyCode": "USD",
                            "ianaTimezone": "UTC",
                        },
                        "currentAppInstallation": {
                            "accessScopes": [{"handle": s} for s in sorted(MEASUREMENT_SCOPES)]
                        },
                    }
                }
            elif "InletMeasurementOrders" in body["query"]:
                result = {
                    "data": {
                        "orders": {
                            "nodes": [source()],
                            "pageInfo": {"hasNextPage": False, "endCursor": None},
                        }
                    }
                }
            elif "InletAgreements" in body["query"]:
                fact = agreement()
                fact["sales"] = {
                    "nodes": fact["sales"],
                    "pageInfo": {"hasNextPage": False, "endCursor": None},
                }
                result = {
                    "data": {
                        "order": {
                            "agreements": {
                                "nodes": [fact],
                                "pageInfo": {"hasNextPage": False, "endCursor": None},
                            }
                        }
                    }
                }
            else:
                raise AssertionError("unexpected Shopify query")
            return BytesIO(json.dumps(result).encode())

    monkeypatch.setattr(shopify_http, "build_opener", lambda *_: ShopifyHTTP())

    def database() -> Generator[Session, None, None]:
        with factory() as db:
            yield db

    monkeypatch.setattr(
        app,
        "dependency_overrides",
        {get_db: database, get_identity_provider: lambda: FakeProvider()},
    )

    async def harness(scope: Scope, receive: Receive, send: Send) -> None:
        if scope.get("path") == "/app/assets/firebase-auth.mjs":
            await Response(SDK, media_type="text/javascript")(scope, receive, send)
        else:
            await app(scope, receive, send)

    cert, tls_key = localhost_certificate(tmp_path)
    server = uvicorn.Server(
        uvicorn.Config(
            harness,
            log_level="critical",
            lifespan="off",
            ssl_certfile=str(cert),
            ssl_keyfile=str(tls_key),
        )
    )
    thread = threading.Thread(target=lambda: server.run(sockets=[listener]), daemon=True)
    thread.start()
    deadline = time.monotonic() + 10
    while not server.started and time.monotonic() < deadline:
        time.sleep(0.02)
    assert server.started
    browser_profile = tmp_path / "chrome"
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
            f"--user-data-dir={browser_profile}",
            "about:blank",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    browser: FreshBrowser | None = None
    try:
        active = browser_profile / "DevToolsActivePort"
        deadline = time.monotonic() + 15
        while not active.exists() and time.monotonic() < deadline:
            time.sleep(0.03)
        port = active.read_text().splitlines()[0]

        def tabs() -> list[dict[str, Any]]:
            with urlopen(f"http://127.0.0.1:{port}/json", timeout=5) as response:
                return list(json.load(response))

        browser = FreshBrowser(wait_for_page_target(tabs), origin, billing)
        browser.call(
            "Fetch.enable",
            {
                "patterns": [
                    {"urlPattern": p, "requestStage": "Request"}
                    for p in [
                        "https://accounts.google.com/o/oauth2/v2/auth*",
                        f"https://{SHOP}/admin/oauth/authorize*",
                        "https://checkout.stripe.com/c/*",
                    ]
                ]
            },
        )
        browser.navigate("/app")
        browser.ready("$('signin') && !$('signin').disabled && !$('signin').hidden")
        browser.js("$('signin').click()")
        browser.ready("!$('application').hidden && !$('retry').disabled")
        browser.js(
            "$('provision').elements.namedItem('name').value='Fresh Brand';$("
            "'provision').elements.namedItem('slug').value='fresh-brand';$('p"
            "rovision').requestSubmit()"
        )
        browser.ready("!$('workspace-content').hidden && !$('retry').disabled")
        wid = int(browser.js("$('workspace').value"))
        root = f"/api/customer/v1/workspaces/{wid}"
        assert len(browser.api("/api/customer/v1/workspaces")["body"]) == 1
        browser.ready("!$('checkout').hidden && !$('checkout').disabled")
        billing.lost = True
        browser.js("$('checkout').click()")
        browser.ready("$('message').className === 'error' && !$('billing-refresh').disabled")
        assert len(billing.post_keys) == 1
        original_checkout_key = billing.post_keys[0]
        # The ordinary status GET exposes the original pending purchase without POST.
        # Explicit Resume retries only its exact original offer and idempotency key.
        billing.lost = False
        browser.js("$('billing-refresh').click()")
        browser.ready("$('checkout').textContent.includes('Resume') && !$('checkout').disabled")
        assert len(billing.post_keys) == 1
        assert len(set(billing.post_keys)) == 1
        browser.js("$('checkout').click()")
        browser.ready("$('provider-return') !== null")
        browser.js("$('provider-return').click()")
        browser.ready("$('billing') && !$('workspace-content').hidden && !$('retry').disabled")
        with factory() as db:
            with pytest.raises(HTTPException):
                require_entitlement(db, wid, policy(), NOW, scope=configured_scope())
            row = db.scalar(select(WorkspaceBilling).where(WorkspaceBilling.workspace_id == wid))
            assert row and row.environment == "test" and row.checkout_offer_binding_id
        billing.paid = True
        event = json.dumps(
            {
                "id": "evt_fresh_brand",
                "type": "customer.subscription.updated",
                "livemode": False,
                "data": {"object": {"id": "sub_fixture", "customer": "cus_fixture"}},
            }
        ).encode()
        assert (
            browser.js(
                (
                    "fetch('/api/billing/stripe/test/events',{method:'POST',headers:{"
                    "'Stripe-Signature':"
                )
                + json.dumps(signature(event))
                + "},body:"
                + json.dumps(event.decode())
                + "}).then(r=>r.status)"
            )
            == 200
        )
        assert billing_run(factory, policy(), get_billing_transport(), NOW)["events"] == 1
        browser.js("$('billing-refresh').click()")
        browser.ready("$('billing').textContent.startsWith('Active') && !$('retry').disabled")
        with factory() as db:
            require_entitlement(db, wid, policy(), NOW, scope=TEST)
            row = db.scalar(select(WorkspaceBilling).where(WorkspaceBilling.workspace_id == wid))
            assert row and row.subscription_offer_binding_id and row.qualification
        browser.ready("!$('google-authorize').hidden && !$('google-authorize').disabled")
        browser.js("$('google-authorize').click()")
        browser.ready("$('consent-approve') !== null")
        browser.js("$('consent-approve').click()")
        browser.ready("$('google-selection') && !$('google-selection').hidden")
        browser.js("$('google-select').click()")
        browser.ready(
            "$('google-disconnect') && !$('google-disconnect').hidden && !$('retry').disabled"
        )
        with factory() as db:
            connected = db.scalar(select(GoogleCustomerConnection))
            assert connected
            original_google_id = connected.id
        # Reauthorize the same selected account through the customer's OAuth UI.
        browser.js("$('google-authorize').click()")
        browser.ready("$('consent-approve') !== null")
        browser.js("$('consent-approve').click()")
        browser.ready("$('google-selection') && !$('google-selection').hidden")
        browser.js("$('google-select').click()")
        browser.ready(
            "$('google-disconnect') && !$('google-disconnect').hidden && !$('retry').disabled"
        )
        with factory() as db:
            assert db.scalar(select(func.count()).select_from(GoogleCustomerConnection)) == 1
            assert db.scalar(select(GoogleCustomerConnection.id)) == original_google_id
        browser.js(
            "$('shopify-domain').value="
            + json.dumps(SHOP)
            + ";$('shopify-connect').requestSubmit()"
        )
        browser.ready("$('consent-approve') !== null")
        browser.js("$('consent-approve').click()")
        browser.ready(
            "$('shopify-disconnect-open') && !$('shopify-disconnect-open').hi"
            "dden && !$('retry').disabled"
        )
        with factory() as db:
            assert CommerceSyncService(db, settings).page(wid, now=NOW) == {
                "status": "complete",
                "imported": 1,
            }
        browser.navigate("/app?workspace=" + str(wid))
        browser.ready("$('store')?.options.length === 1 && !$('retry').disabled")
        form = dict(
            target="10000",
            target_month="2026-11",
            baseline_month="2026-09",
            budget="100",
            budget_start="2026-11-01",
            budget_end="2026-12-01",
        )
        browser.js(
            "for(const [k,v] of Object.entries("
            + json.dumps(form)
            + ")) $('goal-form').elements.namedItem(k).value=v;$('goal-form').requestSubmit()"
        )
        browser.ready(
            "$('message').textContent.includes('Goal draft saved') && !$('retry').disabled"
        )
        original_goal = browser.api(root + "/goals")["body"][0]
        browser.js(
            "$('goal-form').elements.namedItem('target').value='12000';"
            "$('goal-form').elements.namedItem('target').dispatchEvent(new Event('input',"
            "{bubbles:true}));$('goal-form').requestSubmit()"
        )
        browser.ready(
            "$('message').textContent.includes('Goal draft saved') && !$('retry').disabled"
        )
        edited_goal = browser.api(root + "/goals")["body"][0]
        assert edited_goal["id"] == original_goal["id"]
        assert edited_goal["revision"] == original_goal["revision"] + 1
        assert edited_goal["definition"]["target_micros"] == 12_000_000_000
        browser.js("$('preview').click()")
        browser.ready("!$('review').hidden && !$('confirm').disabled")
        assert "90.00" in browser.js("$('review-data').textContent")
        browser.js("$('confirm').click()")
        browser.ready("$('message').textContent.includes('Goal confirmed') && !$('retry').disabled")
        goal_id = browser.api(root + "/goals")["body"][0]["id"]
        browser.navigate("/app/plan-review")
        browser.ready("!$('selection').hidden && !$('refresh').disabled")
        browser.js(
            f"$('workspace').value='{wid}';$('workspace').dispatchEvent(new Event('change'))"
        )
        browser.ready(
            "$('goal').options.length===2 && $('account').options.length===2 "
            "&& !$('refresh').disabled"
        )
        browser.js(
            "$('goal').selectedIndex=1;$('goal').dispatchEvent(new Event('cha"
            "nge'));$('account').selectedIndex=1;$('account').dispatchEvent(n"
            "ew Event('change'));$('context').click()"
        )
        browser.ready("!$('editor').hidden && !$('save').disabled")
        assert "USD 100.000000" in browser.js("$('goal-context').textContent")
        browser.js("$('planning-form').requestSubmit()")
        browser.ready("!$('review').hidden && !$('refresh').disabled")
        assert browser.js("$('approve').disabled")
        planning = browser.api(root + "/mandates")["body"][0]
        edited = browser.api(
            root + "/mandates/" + planning["id"],
            "PUT",
            dict(expected_revision=planning["revision"], definition=planning["definition"]),
        )
        assert edited["status"] == 200
        browser.js(
            "$('consent').checked=true;$('consent').dispatchEvent(new Event('change'));"
            "$('approve').click()"
        )
        browser.ready("$('status').textContent.includes('changed') && !$('refresh').disabled")
        assert browser.js("$('review').hidden && $('approve').disabled")
        browser.js("$('load').click()")
        browser.ready("!$('review').hidden && !$('refresh').disabled")
        browser.js(
            "$('consent').checked=true;$('consent').dispatchEvent(new Event('"
            "change'));$('approve').click()"
        )
        browser.ready("!$('approved').hidden && !$('refresh').disabled")
        browser.navigate("/app/campaign-review")
        browser.ready("$('review-workspace').options.length===2 && !$('review-reload').disabled")
        browser.js(
            f"$('review-workspace').value='{wid}';"
            "$('review-workspace').dispatchEvent(new Event('change'))"
        )
        browser.ready(
            "!$('draft-creation').hidden && $('create-mandate').options.lengt"
            "h===2 && !$('review-reload').disabled"
        )
        browser.js(
            "$('create-mandate').selectedIndex=1;$('create-mandate').dispatch"
            "Event(new Event('change'));$('create-account').value='0';$('crea"
            "te-account').dispatchEvent(new Event('change'))"
        )
        draft_fields = dict(
            name="Fresh Brand Search Plan",
            landing_page="https://example.invalid/products",
            budget="50",
            starts="2026-11-01T00:00",
            ends="2026-11-02T00:00",
            countries="US",
            languages="en",
            headlines="First Headline\nSecond Headline\nThird Headline",
            descriptions="First Description\nSecond Description",
            exact_keywords="supplied product",
        )
        browser.js(
            "for(const[k,v] of Object.entries("
            + json.dumps(draft_fields)
            + "))$('draft-create').elements.namedItem(k).value=v;$('draft-create').requestSubmit()"
        )
        browser.ready(
            "$('campaign-title').textContent==='Fresh Brand Search Plan' && !"
            "$('review-draft').disabled"
        )
        browser.js(
            "$('review-consent').checked=true;$('review-consent').dispatchEve"
            "nt(new Event('change'));$('approve-campaign').click()"
        )
        browser.ready("$('approval-status').textContent.includes('Approved For Offline Planning')")
        draft_id = browser.js("$('review-draft').value")
        browser.navigate("/app/account-diagnostics")
        browser.ready("!$('diagnostic-selection').hidden && !$('diagnostic-refresh').disabled")
        browser.js(
            f"$('diagnostic-workspace').value='{wid}';"
            "$('diagnostic-workspace').dispatchEvent(new Event('change'))"
        )
        browser.ready(
            "$('diagnostic-account').options.length===2 && !$('diagnostic-refresh').disabled"
        )
        browser.js(
            "$('diagnostic-account').selectedIndex=1;$('diagnostic-account').dispatchEvent(new Even"
            "t('change'));$('diagnostic-start').value='2026-10-01T00:00';$('diagnostic-end').value="
            "'2026-10-05T00:00';$('diagnostic-form').requestSubmit()"
        )
        browser.ready("!$('diagnostic-report').hidden && !$('diagnostic-refresh').disabled")
        assert "safe spending limit" in browser.js("$('diagnostic-reasons').textContent")
        browser.navigate("/app/optimization")
        browser.ready("$('opt-workspace').options.length===2")
        browser.js(
            f"$('opt-workspace').value='{wid}';"
            "$('opt-workspace').dispatchEvent(new Event('change'))"
        )
        browser.ready("$('opt-environment').textContent.includes('Not Configured')")
        capabilities = browser.api(root + "/execution/automation/capabilities")
        assert capabilities["status"] == 200 and capabilities["body"]["available"] is False
        assert not capabilities["body"]["policies"]
        browser.navigate("/app?workspace=" + str(wid))
        browser.ready("!$('workspace-content').hidden && !$('retry').disabled")
        browser.js("$('logout').click()")
        browser.ready("$('application').hidden && !$('retry').disabled")
        browser.js("globalThis.__fixtureIdentity='browser-b';$('signin').click()")
        browser.ready("!$('application').hidden && !$('retry').disabled")
        assert browser.js(
            "$('workspace-content').hidden && $('goal-detail').textContent==="
            "'' && $('billing').textContent===''"
        )
        before = len(native_calls)
        assert browser.api(root + "/goals/" + goal_id)["status"] == 404
        assert browser.api(root + "/campaign-drafts/" + draft_id + "/preview")["status"] == 404
        with factory() as db:
            account_id = db.scalar(
                select(GoogleCustomerConnection.account_id).where(
                    GoogleCustomerConnection.workspace_id == wid
                )
            )
        assert browser.api(
            root + "/execution/diagnostics",
            "POST",
            dict(
                account_id=account_id,
                starts_at="2026-10-01T00:00:00Z",
                ends_at="2026-10-05T00:00:00Z",
            ),
        )["status"] in {403, 404}
        assert len(native_calls) == before
        browser.js(
            "$('provision').elements.namedItem('name').value='Other Brand';$("
            "'provision').elements.namedItem('slug').value='other-brand';$('p"
            "rovision').requestSubmit()"
        )
        browser.ready("!$('workspace-content').hidden && !$('retry').disabled")
        assert int(browser.js("$('workspace').value")) != wid
        browser.js("$('logout').click()")
        browser.ready("$('application').hidden && !$('retry').disabled")
        browser.js("globalThis.__fixtureIdentity='browser-a';$('signin').click()")
        browser.ready("!$('application').hidden && !$('retry').disabled")
        browser.js(
            f"$('workspace').value='{wid}';$('workspace').dispatchEvent(new Event('change'))"
        )
        browser.ready("!$('workspace-content').hidden && !$('retry').disabled")
        assert browser.api(root + "/goals/" + goal_id)["body"]["confirmation_recorded"]
        assert browser.api(root + "/campaign-drafts/" + draft_id + "/preview")["status"] == 200
        assert browser.api(root + "/billing")["body"]["status"] == "active"

        with factory() as db:
            assert db.scalar(select(func.count()).select_from(CustomerUser)) == 2
            assert db.scalar(select(func.count()).select_from(CustomerMembership)) == 2
            assert db.scalar(select(func.count()).select_from(GoogleCustomerConnection)) == 1
            assert db.scalar(select(func.count()).select_from(ShopifyConnection)) == 1
            assert (db.scalar(select(func.count()).select_from(CommerceEntry)) or 0) > 0
            saved_goal = db.get(Goal, goal_id)
            assert saved_goal and saved_goal.workspace_id == wid
            assert db.scalar(select(func.count()).select_from(ProviderExecutionApproval)) == 0
            assert db.scalar(select(func.count()).select_from(ProviderExecutionAttempt)) == 0
            assert db.scalar(select(func.count()).select_from(AutomaticDecisionAdmission)) == 0
        assert len(billing.post_keys) == 2
        assert set(billing.post_keys) == {original_checkout_key}
        # A future target period is observable but cannot invent zero sales or success.
        browser.js(
            "$('goal').value=" + json.dumps(goal_id)
            + ";$('goal').dispatchEvent(new Event('change'))"
        )
        browser.ready("!$('goal-progress').hidden && !$('goal-progress-refresh').disabled")
        progress_path = root + "/goals/" + goal_id + "/progress?expected_revision=" + str(
            edited_goal["revision"]
        )
        progress = browser.api(progress_path)
        assert progress["status"] == 200
        assert progress["body"]["status"] == "not_started"
        assert progress["body"]["net_sales_micros"] is None
        assert progress["body"]["spending_authorized"] is False
        browser.navigate("/app?workspace=" + str(wid))
        browser.ready("!$('workspace-content').hidden && !$('retry').disabled")
        browser.js(
            "$('goal').value=" + json.dumps(goal_id)
            + ";$('goal').dispatchEvent(new Event('change'))"
        )
        browser.ready("!$('goal-progress').hidden && !$('goal-progress-refresh').disabled")
        assert browser.api(progress_path)["body"]["definition_digest"] == progress["body"][
            "definition_digest"
        ]
        # Operational revocation is an adverse control, never fixture provisioning.
        with factory() as db:
            for session in db.scalars(select(CustomerSession)):
                session.revoked_at = int(time.time())
            db.commit()
        before = len(native_calls)
        browser.js("$('goal-progress-refresh').click()")
        browser.ready("$('application').hidden")
        assert browser.api(progress_path)["status"] == 401
        assert browser.js("$('goal-progress').hidden && $('goal-progress-data').textContent === ''")
        assert len(native_calls) == before
    finally:
        if browser:
            browser.context.close()
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
        server.should_exit = True
        thread.join(timeout=5)
        listener.close()
        if engine is not customer_engine:
            engine.dispose()
