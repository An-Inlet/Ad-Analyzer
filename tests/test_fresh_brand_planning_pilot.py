"""Fresh visible customer continuity; only provider HTTP/SDK and worker timing are mocked."""

import json
import socket
import subprocess
import threading
import time
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

import httpx
import pytest
import uvicorn
from app.billing.contracts import get_billing_transport
from app.billing.dispatcher import run as billing_run
from app.billing.entitlements import policy
from app.billing.models import WorkspaceBilling
from app.billing.scope import configured_scope
from app.billing.service import require_entitlement
from app.billing.stripe import StripeBilling
from app.campaign_performance.models import CurrentPerformance, PerformanceCompletion
from app.collectors import account_diagnostics
from app.commerce.ledger import MEASUREMENT_SCOPES
from app.commerce.models import CommerceStore
from app.commerce.sync import CommerceSyncService
from app.customers.access import SESSION_COOKIE, digest
from app.customers.identity import get_identity_provider
from app.customers.models import CustomerSession, CustomerUser
from app.database.session import Base, get_db
from app.google_connections import service as google_service
from app.google_connections.contracts import get_transport
from app.google_connections.http import GoogleHTTPRead
from app.google_connections.models import GoogleCustomerConnection
from app.lifecycle.privacy import workspace_export_revision
from app.main import app
from app.planning_documents.models import PlanRow, PlanVersionRow
from app.publication.execution_models import (
    ProviderExecutionApproval,
    ProviderExecutionAttempt,
    ProviderExposureReservation,
)
from app.session_automation.models import AutomaticDecisionAdmission
from app.settings import Settings, settings
from app.shopify import client as shopify_http
from app.workspaces.models import Workspace
from cryptography.fernet import Fernet
from fastapi import HTTPException
from pydantic import SecretStr
from sqlalchemy import Engine, create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker
from starlette.responses import Response
from starlette.types import Message, Receive, Scope, Send

from tests import test_billing_offers as billing_helpers
from tests import test_fresh_brand_pilot as legacy_helpers
from tests.browser_targets import wait_for_page_target
from tests.test_billing_offers import PROFILE, TEST
from tests.test_commerce_measurement import agreement, source
from tests.test_customer_billing import SECRET, signature
from tests.test_customer_browser_api_journey import SDK, localhost_certificate
from tests.test_customer_identity import FakeProvider
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_portal import portal_executable
from tests.test_fresh_brand_pilot import FreshBrowser, TestOfferHTTP
from tests.test_google_native_inventory import key, payloads
from tests.test_shopify_sales import SHOP
from tests.test_shopify_sales import configuration as configuration


class PlanningBrowser(FreshBrowser):
    def ready(self, code: str) -> None:
        try:
            super().ready(code)
        except AssertionError as error:
            raise AssertionError(
                str(error) + "; planning=" + str(self.js("$('planning-message')?.textContent"))
            ) from None


def test_fresh_visible_planning_brand_journey(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = datetime.now(UTC)
    monkeypatch.setattr(legacy_helpers, "NOW", now)
    monkeypatch.setattr(billing_helpers, "NOW", now)
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
        kwargs["clock"] = lambda: datetime.now(UTC)
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
        if query.startswith("SELECT campaign.id, campaign.name, campaign.status,"):
            return httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "campaign": {
                                "id": "1",
                                "name": "Fresh Brand Search",
                                "status": "ENABLED",
                                "advertisingChannelType": "SEARCH",
                            }
                        }
                    ]
                },
            )
        if query.startswith("SELECT campaign.id, segments.date, metrics.impressions,"):
            import re
            from datetime import date

            dates = re.findall(r"'(\d{4}-\d{2}-\d{2})'", query)
            first, last = (date.fromisoformat(value) for value in dates)
            return httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "campaign": {"id": "1"},
                            "segments": {"date": (first + timedelta(days=i)).isoformat()},
                            "metrics": {
                                "impressions": "100",
                                "clicks": "10",
                                "costMicros": "1000000",
                                "conversions": "2",
                                "conversionsValue": "20",
                            },
                        }
                        for i in range((last - first).days + 1)
                    ]
                },
            )
        if "FROM ad_group" in query:
            return httpx.Response(200, json={"results": []})
        data = payloads()
        if "campaign.name" in query:
            for row in data["campaign"]:
                row["campaign"]["name"] = "Fresh Brand Search"

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
                            "nodes": [source(updated=now)],
                            "pageInfo": {"hasNextPage": False, "endCursor": None},
                        }
                    }
                }
            elif "InletAgreements" in body["query"]:
                fact = agreement(when=now.replace(day=1) - timedelta(days=1))
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

    generation_errors: list[str] = []

    async def harness(scope: Scope, receive: Receive, send: Send) -> None:
        if scope.get("path") == "/app/assets/firebase-auth.mjs":
            await Response(SDK, media_type="text/javascript")(scope, receive, send)
        else:
            response_status = 200

            async def capture(message: Message) -> None:
                nonlocal response_status
                if message["type"] == "http.response.start":
                    response_status = message["status"]
                if (
                    scope.get("path", "").endswith("/generate")
                    and response_status >= 400
                    and message["type"] == "http.response.body"
                ):
                    generation_errors.append(message.get("body", b"").decode())
                await send(message)

            try:
                await app(scope, receive, capture)
            except Exception as error:
                import traceback

                generation_errors.append(
                    type(error).__name__
                    + ": "
                    + str(error)
                    + "\n"
                    + "".join(traceback.format_tb(error.__traceback__))
                )
                raise

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

        browser = PlanningBrowser(wait_for_page_target(tabs), origin, billing)
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
        assert billing.post_keys[0] == original_checkout_key
        browser.js("$('checkout').click()")
        browser.ready("$('provider-return') !== null")
        browser.js("$('provider-return').click()")
        browser.ready("$('billing') && !$('workspace-content').hidden && !$('retry').disabled")
        with factory() as db:
            with pytest.raises(HTTPException):
                require_entitlement(db, wid, policy(), now, scope=configured_scope())
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
                + json.dumps(signature(event, datetime.now(UTC)))
                + "},body:"
                + json.dumps(event.decode())
                + "}).then(r=>r.status)"
            )
            == 200
        )
        assert billing_run(factory, policy(), get_billing_transport(), now)["events"] == 1
        browser.js("$('billing-refresh').click()")
        browser.ready("$('billing').textContent.startsWith('Active') && !$('retry').disabled")
        with factory() as db:
            require_entitlement(db, wid, policy(), now, scope=TEST)
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
            assert CommerceSyncService(db, settings).page(wid, now=now) == {
                "status": "complete",
                "imported": 1,
            }
        with factory() as db:
            connection = db.scalar(select(GoogleCustomerConnection))
            assert connection is not None
            for _ in range(2):
                google_service.tick(
                    db,
                    wid,
                    connection.id,
                    connection.generation,
                    get_transport(),
                    datetime.now(UTC),
                )
                db.commit()
        browser.navigate("/app?workspace=" + str(wid))
        browser.ready("$('store')?.options.length === 1 && !$('retry').disabled")
        target_start = (now.replace(day=28) + timedelta(days=4)).replace(day=1)
        target_end = (target_start.replace(day=28) + timedelta(days=4)).replace(day=1)
        baseline = now.replace(day=1) - timedelta(days=1)
        form = dict(
            target="10000",
            target_month=target_start.strftime("%Y-%m"),
            baseline_month=baseline.strftime("%Y-%m"),
            budget="100",
            aggressiveness="balanced",
            budget_start=target_start.date().isoformat(),
            budget_end=target_end.date().isoformat(),
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
        browser.navigate("/app/planning")
        browser.ready(
            "$('planning-workspace').options.length===2 && !$('planning-refresh').disabled"
        )
        browser.js(
            f"$('planning-workspace').value='{wid}';$('planning-workspace').dispatchEve"
            f"nt(new Event('change'))"
        )
        browser.ready("!$('planning-new').hidden && !$('planning-new').disabled")
        browser.js("$('planning-new').click()")
        browser.ready("!$('planning-editor').hidden && !$('planning-save').disabled")
        browser.js(
            "$('planning-goal').value="
            + json.dumps(goal_id)
            + ";$('planning-goal').dispatchEvent(new Event('change'));"
            "const account=$('planning-accounts').querySelector('input');account.check"
            "ed=true;account.dispatchEvent(new Event('change'));"
        )
        end = now.replace(hour=0, minute=0, second=0, microsecond=0)
        fields = {
            "milestone": "Grow fresh brand merchandise sales",
            "product": "Reusable bottle",
            "start": (end - timedelta(days=1)).isoformat()[:16],
            "end": end.isoformat()[:16],
        }
        browser.js(
            "globalThis.__planPosts=0;globalThis.__realFetch=fetch.bind(window);"
            "window.fetch=async(...args)=>{const r=await __realFetch(...args);"
            "if(String(args[0]).endsWith('/planning/plans')&&args[1]?.method==='POST'){"
            "__planPosts++;throw Error('Synthetic response lost after commit');}return r;};"
        )
        browser.js(
            "for(const [key,value] of Object.entries("
            + json.dumps(fields)
            + ")) $('planning-'+key).value=value;"
            "$('planning-form').requestSubmit()"
        )
        browser.ready("!$('planning-pending').hidden && !$('planning-recover').disabled")
        assert browser.js("__planPosts") == 1
        browser.js("$('planning-recover').click()")
        browser.ready(
            "$('planning-pending').hidden && !$('planning-current').hidden && !$('plan"
            "ning-generate').disabled"
        )
        assert browser.js("__planPosts") == 1
        browser.js("window.fetch=__realFetch")
        with factory() as db:
            publication = db.scalar(
                select(PerformanceCompletion).join(
                    CurrentPerformance, CurrentPerformance.completion_id == PerformanceCompletion.id
                )
            )
            assert publication is not None
            connected = db.scalar(select(GoogleCustomerConnection))
            assert connected is not None
            assert (publication.source_connection_ref, publication.generation) == (
                connected.id,
                connected.generation,
            )
            assert publication.row_count == 7
            (tmp_path / "source-proof.json").write_text(
                json.dumps(
                    {
                        "completion_id": publication.id,
                        "manifest_digest": publication.manifest_digest,
                        "generation": publication.generation,
                        "source_connection_ref": publication.source_connection_ref,
                        "privacy_revision": publication.privacy_revision,
                        "workspace_privacy_revision": workspace_export_revision(db, wid),
                        "starts_on": str(publication.starts_on),
                        "ends_on": str(publication.ends_on),
                        "completed_at": str(publication.completed_at),
                        "row_count": publication.row_count,
                        "saved_inputs": browser.api(root + "/planning/plans")["body"],
                    },
                    indent=2,
                )
            )
            assert publication.privacy_revision == workspace_export_revision(db, wid), (
                "completion privacy changed after actual imports"
            )
        browser.js("$('planning-generate').click()")
        browser.ready("!$('planning-read').disabled")
        assert not browser.js("$('planning-document').hidden"), browser.js(
            "$('planning-message').textContent"
        ) + str(generation_errors)
        plans = browser.api(root + "/planning/plans")
        assert plans["status"] == 200 and len(plans["body"]["items"]) == 1
        plan_id = plans["body"]["items"][0]["plan_id"]
        current = browser.api(root + "/planning/plans/" + plan_id)
        assert current["status"] == 200, current
        assert current["body"]["advertising_writes_enabled"] is False
        assert current["body"]["spending_authority"] == "none"
        assert "Plan Version 1" in browser.js("$('planning-document').textContent")
        assert current["body"]["inputs"]["goal"]["goal_id"] == goal_id
        assert current["body"]["inputs"]["goal"]["definition"]["budget_micros"] == 100_000_000
        assert current["body"]["inputs"]["goal"]["definition"]["aggressiveness"] == "balanced"
        assert "100.00" in browser.js("$('planning-document').textContent")
        for kind, statement in (
            ("accepted_for_manual_application", "I reviewed this exact plan."),
            ("customer_reports_applied", "I applied this myself outside Inlet."),
        ):
            browser.js(
                "$('planning-action').selectedIndex=1;$('planning-action').dispatchEve"
                "nt(new Event('change'));"
                "$('planning-record-type').value="
                + json.dumps(kind)
                + ";$('planning-record-type').dispatchEvent(new Event('change'));"
                "$('planning-statement').value=" + json.dumps(statement) + ";"
                "$('planning-applied').value=new Date().toISOString().slice(0,16);"
                "$('planning-confirm-review').checked=true;$('planning-confirm-review'"
                ").dispatchEvent(new Event('change'));"
                "$('planning-record').click()"
            )
            browser.ready(
                "!$('planning-list-refresh').disabled && $('planning-message').textCon"
                "tent.includes('customer record was saved')"
            )
        assert "Not Independently Verified" in browser.js("$('planning-events').textContent")
        browser.js("$('planning-edit').click()")
        browser.ready("!$('planning-editor').hidden && !$('planning-save').disabled")
        browser.js(
            "$('planning-constraints').value='Keep customer service capacity unchanged"
            "';$('planning-form').requestSubmit()"
        )
        browser.ready("$('planning-editor').hidden && !$('planning-generate').disabled")
        assert browser.js("!$('planning-confirm-review').checked")
        browser.js("$('planning-generate').click()")
        browser.ready(
            "$('planning-document').textContent.includes('Plan Version 2') && !$('plan"
            "ning-read').disabled"
        )
        updated = browser.api(root + "/planning/plans/" + plan_id)["body"]
        assert updated["version"] == 2 and updated["input_revision"] == 2
        assert updated["document_digest"] != current["body"]["document_digest"]

        browser.js("$('planning-progress-read').click()")
        browser.ready("!$('planning-progress').hidden && !$('planning-read').disabled")
        progress = browser.api(root + "/planning/plans/" + plan_id + "/progress?version=2")
        assert progress["status"] == 200, progress
        assert progress["body"]["advertising_writes_enabled"] is False
        body = progress["body"]
        assert (body["plan_id"], body["version"], body["document_digest"]) == (
            plan_id,
            2,
            updated["document_digest"],
        )
        assert body["binding_status"] == "matched" and body["binding_reason"] is None
        assert body["manual_application"] == "not_assessed" and body["attribution"] == "unavailable"
        sales = body["sales"]
        assert sales["metric"] == "shopify_merchandise_net_sales_v1"
        assert (sales["workspace_id"], sales["goal_id"], sales["revision"]) == (
            wid,
            goal_id,
            edited_goal["revision"],
        )
        assert sales["target_micros"] == 12_000_000_000
        assert sales["currency"] == "USD" and sales["time_zone"] == "UTC"
        assert sales["status"] == "not_started" and sales["reasons"] == ["no_closed_days"]
        assert sales["coverage"] is None and sales["net_sales_micros"] is None
        assert sales["spending_authorized"] is False and sales["attribution"] == "unavailable"
        with factory() as db:
            store = db.scalar(select(CommerceStore).where(CommerceStore.workspace_id == wid))
            assert store is not None and store.last_sync_at is not None
            assert sales["store_id"] == store.id and sales["source_revision"] == store.revision
            assert datetime.fromisoformat(sales["source_watermark"].replace("Z", "+00:00")).replace(
                tzinfo=None
            ) == store.last_sync_at.replace(tzinfo=None)
            assert sales["import_in_progress"] is False
        ordinary = browser.api(
            root
            + "/goals/"
            + goal_id
            + "/progress?expected_revision="
            + str(edited_goal["revision"])
        )
        assert ordinary["status"] == 200
        assert {key: value for key, value in ordinary["body"].items() if key != "as_of"} == {
            key: value for key, value in sales.items() if key != "as_of"
        }

        # Ordinary current API must enforce CSRF even for local customer records.
        assert (
            browser.js(
                "fetch("
                + json.dumps(root + "/planning/plans")
                + ",{method:'POST',headers:{'Content-Type':'application/json'},"
                "body:'{}'}).then(r=>r.status)"
            )
            == 403
        )
        browser.js("$('planning-logout').click()")
        browser.ready("$('planning-selection').hidden && $('planning-document').hidden")
        assert browser.js("$('planning-document').textContent") == ""
        browser.navigate("/app")
        browser.ready("!$('signin').hidden && !$('signin').disabled")
        browser.js("globalThis.__fixtureIdentity='browser-b';$('signin').click()")
        browser.ready("!$('application').hidden && !$('retry').disabled")
        assert browser.api("/api/customer/v1/workspaces")["body"] == []
        before_reads = len(native_calls)
        for path in (
            "/goals/" + goal_id,
            "/planning/accounts",
            "/planning/plans/" + plan_id,
            "/planning/plans/" + plan_id + "/versions/1",
            "/planning/plans/" + plan_id + "/events",
            "/planning/plans/" + plan_id + "/export?version=1",
            "/planning/plans/" + plan_id + "/progress?version=2",
        ):
            assert browser.api(root + path)["status"] == 404, path
        assert len(native_calls) == before_reads
        browser.js(
            "$('provision').elements.namedItem('name').value='Other Brand';$('provisio"
            "n').elements.namedItem('slug').value='other-brand';$('provision').request"
            "Submit()"
        )
        browser.ready("!$('workspace-content').hidden && !$('retry').disabled")
        assert int(browser.js("$('workspace').value")) != wid
        browser.js("$('logout').click()")
        browser.ready("$('application').hidden && !$('signin').disabled")
        browser.js("globalThis.__fixtureIdentity='browser-a';$('signin').click()")
        browser.ready("!$('application').hidden && !$('retry').disabled")
        browser.navigate("/app/planning")
        browser.ready(
            "$('planning-workspace').options.length===2 && !$('planning-refresh').disabled"
        )
        browser.js(
            f"$('planning-workspace').value='{wid}';$('planning-workspace').dispatchEve"
            f"nt(new Event('change'))"
        )
        browser.ready(
            "$('planning-plans').querySelector('button') && !$('planning-list-refresh').disabled"
        )
        browser.js("$('planning-plans').querySelector('button').click()")
        browser.ready("!$('planning-document').hidden && !$('planning-read').disabled")
        browser.js("$('planning-events-refresh').click()")
        browser.ready(
            "$('planning-events').textContent.includes('Not Independently Verified') &"
            "& !$('planning-read').disabled"
        )
        assert browser.api(root + "/billing")["body"]["status"] == "active"
        # Keep an independent, ordinarily authenticated Brand B session active.
        with httpx.Client(base_url=origin, verify=False, trust_env=False) as other_browser:
            other_login = other_browser.post(
                "/api/customer/v1/session",
                headers={"Origin": origin, "X-Inlet-Request": "1"},
                json={"id_token": "browser-b:parallel-" + str(time.time_ns())},
            )
            assert other_login.status_code == 200
            cookies = browser.call("Network.getCookies", {"urls": [origin]})["cookies"]
            browser_digest = digest(
                next(c["value"] for c in cookies if c["name"] == SESSION_COOKIE)
            )
            with factory() as db:
                selected_session = db.get(CustomerSession, browser_digest)
                assert selected_session is not None and selected_session.revoked_at is None
                assert (
                    selected_session.user_id
                    == browser.api("/api/customer/v1/session")["body"]["user_id"]
                )
                unchanged = {
                    row.digest: row.revoked_at
                    for row in db.scalars(select(CustomerSession))
                    if row.digest != browser_digest
                }
                selected_session.revoked_at = int(time.time())
                db.commit()
            before_reads = len(native_calls)
            browser.js("$('planning-progress-read').click()")
            browser.ready("$('planning-selection').hidden && $('planning-document').hidden")
            assert browser.js("$('planning-document').textContent") == ""
            assert browser.api(root + "/planning/plans/" + plan_id)["status"] == 401
            assert len(native_calls) == before_reads
            assert other_browser.get("/api/customer/v1/session").status_code == 200
            assert other_browser.get(root + "/planning/plans/" + plan_id).status_code == 404
            with factory() as db:
                assert unchanged == {
                    row.digest: row.revoked_at
                    for row in db.scalars(select(CustomerSession))
                    if row.digest != browser_digest
                }
        with factory() as db:
            assert db.scalar(select(func.count()).select_from(CustomerUser)) == 2
            assert db.scalar(select(func.count()).select_from(PlanRow)) == 1
            assert db.scalar(select(func.count()).select_from(PlanVersionRow)) == 2
            assert db.scalar(select(func.count()).select_from(ProviderExecutionApproval)) == 0
            assert db.scalar(select(func.count()).select_from(ProviderExecutionAttempt)) == 0
            assert db.scalar(select(func.count()).select_from(AutomaticDecisionAdmission)) == 0
            assert db.scalar(select(func.count()).select_from(ProviderExposureReservation)) == 0
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
