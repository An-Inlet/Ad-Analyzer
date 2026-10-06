"""Production portal DOM against real HTTPS APIs/database, with offline provider seams.

Only provider responses are fixtures. Shopify authorization, callback, import and
disconnect run through real customer APIs and services. Browser fetch is not replaced.
TLS material is generated temporarily for this localhost-only test.
"""

import hashlib
import hmac
import ipaddress
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
from urllib.parse import parse_qs, urlsplit
from urllib.request import Request

import pytest
import uvicorn
from app.api import customer_billing, customer_goals, customer_shopify
from app.billing.contracts import get_billing_transport
from app.billing.dispatcher import run as billing_run
from app.billing.models import BillingEvent, WorkspaceBilling
from app.commerce import reporting
from app.commerce.ledger import MEASUREMENT_SCOPES
from app.commerce.models import CommerceEntry, CommerceOrder, CommerceSnapshot, CommerceStore
from app.commerce.sync import CommerceSyncService
from app.customers.identity import get_identity_provider
from app.customers.models import CustomerMembership, CustomerSession, CustomerUser
from app.database.session import Base, get_db
from app.goals import service as goals
from app.goals.models import Goal, GoalCreation
from app.main import app
from app.settings import Settings, settings
from app.shopify import client as shopify_http
from app.shopify.models import ShopifyConnection, ShopifyOAuthState
from app.workspaces.models import Workspace
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID
from pydantic import SecretStr
from sqlalchemy import Engine, create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker
from starlette.responses import JSONResponse, Response
from starlette.types import Message, Receive, Scope, Send

from tests.test_commerce_measurement import NOW, agreement, source
from tests.test_customer_billing import POLICY, SECRET, FixtureBilling, payload, signature
from tests.test_customer_identity import FakeProvider
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_portal import portal_executable
from tests.test_inlet_customer_journey import JourneyClock
from tests.test_shopify_sales import configuration as configuration

SDK = """
let count = 0;
export const initializeApp = () => ({}), deleteApp = async () => {};
export const initializeAuth = () => ({}), inMemoryPersistence = {};
export const browserPopupRedirectResolver = {};
export class GoogleAuthProvider { setCustomParameters() {} }
export const signInWithPopup = async () => ({user:{getIdToken: async () =>
    (globalThis.__fixtureIdentity || 'browser-a') + ':' + (++count)}});
export const signOut = async () => {};
"""


def localhost_certificate(tmp_path: Path) -> tuple[Path, Path]:
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost offline fixture")])
    now = datetime.now(UTC)
    certificate = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=1))
        .not_valid_after(now + timedelta(hours=1))
        .add_extension(
            x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )
    cert_path, key_path = tmp_path / "localhost.crt", tmp_path / "localhost.key"
    cert_path.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    key_path.chmod(0o600)
    return cert_path, key_path


def test_real_browser_customer_api_journey(
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
    for name, value in {
        "customer_app_origin": origin,
        "customer_auth_enabled": True,
        "customer_browser_auth_enabled": True,
        "customer_identity_project_id": "offline-browser",
        "customer_identity_web_api_key": "offline-public-browser-key-000000",
        "customer_identity_web_app_id": "1:123456:web:abcdef",
        "billing_price_id": POLICY.price_id,
        "billing_webhook_secret": SecretStr(SECRET),
    }.items():
        monkeypatch.setattr(settings, name, value)
    for name in Settings.model_fields:
        if name.startswith("shopify_"):
            monkeypatch.setattr(settings, name, getattr(configuration, name))
    monkeypatch.setattr(settings, "shopify_customer_enabled", True)
    monkeypatch.setattr(settings, "shopify_measurement_enabled", True)
    provider_calls: list[str] = []

    class ProviderHTTP:
        def open(self, request: Request, timeout: int) -> BytesIO:
            assert timeout == 15
            parsed = urlsplit(request.full_url)
            assert parsed.scheme == "https" and parsed.hostname == "browser-fixture.myshopify.com"
            assert isinstance(request.data, bytes)
            body = json.loads(request.data)
            if parsed.path == "/admin/oauth/access_token":
                assert body["code"] == "offline-browser-code"
                provider_calls.append("token")
                result: dict[str, Any] = {
                    "access_token": "offline-access",
                    "refresh_token": "offline-refresh",
                    "expires_in": 3600,
                    "scope": ",".join(sorted(MEASUREMENT_SCOPES)),
                }
            else:
                assert parsed.path.endswith("/graphql.json")
                query = body["query"]
                page = {"hasNextPage": False, "endCursor": None}
                if "AnalyzerShop" in query:
                    provider_calls.append("shop")
                    result = {
                        "data": {
                            "shop": {
                                "id": "gid://shopify/Shop/123",
                                "name": "Browser Store",
                                "myshopifyDomain": parsed.hostname,
                                "currencyCode": "USD",
                                "ianaTimezone": "UTC",
                            },
                            "currentAppInstallation": {
                                "accessScopes": [
                                    {"handle": scope} for scope in sorted(MEASUREMENT_SCOPES)
                                ]
                            },
                        }
                    }
                elif "InletMeasurementOrders" in query:
                    provider_calls.append("orders")
                    result = {"data": {"orders": {"nodes": [source()], "pageInfo": page}}}
                elif "InletAgreements" in query:
                    provider_calls.append("agreements")
                    fact = agreement()
                    fact["sales"] = {"nodes": fact["sales"], "pageInfo": page}
                    result = {
                        "data": {"order": {"agreements": {"nodes": [fact], "pageInfo": page}}}
                    }
                else:
                    raise AssertionError("Unexpected provider HTTP request")
            return BytesIO(json.dumps(result).encode())

    monkeypatch.setattr(shopify_http, "build_opener", lambda *_: ProviderHTTP())
    for module in (customer_billing, customer_goals, customer_shopify, goals, reporting):
        monkeypatch.setattr(module, "datetime", JourneyClock)
    # The portal intentionally performs concurrent reads. A StaticPool in-memory
    # SQLite connection would let separate request sessions share one transaction.
    browser_engine = customer_engine
    if customer_engine.dialect.name == "sqlite":
        browser_engine = create_engine(
            f"sqlite:///{tmp_path / 'browser.sqlite'}",
            connect_args={"check_same_thread": False, "timeout": 10},
        )
        Base.metadata.create_all(browser_engine)
    factory = sessionmaker(browser_engine)
    provider, billing = FakeProvider(), FixtureBilling()

    def database() -> Generator[Session, None, None]:
        with factory() as db:
            yield db

    monkeypatch.setattr(
        app,
        "dependency_overrides",
        {
            get_db: database,
            get_identity_provider: lambda: provider,
            get_billing_transport: lambda: billing,
        },
    )
    completed = threading.Event()
    result: list[dict[str, Any]] = []
    responses: list[tuple[str, str, int, int]] = []
    interrupted: set[str] = set()
    event = payload("evt_browser_journey")

    async def harness(scope: Scope, receive: Receive, send: Send) -> None:
        path, method = scope.get("path", ""), scope.get("method", "")
        if path == "/app/assets/firebase-auth.mjs":
            await Response(SDK, media_type="text/javascript")(scope, receive, send)
            return
        if path == "/__fixture__/driver.mjs":
            await Response(
                Path("tests/javascript/customer_portal_api_browser.mjs").read_text(),
                media_type="text/javascript",
            )(scope, receive, send)
            return
        if path == "/__fixture__/shopify-sign":
            raw = bytearray()
            while True:
                incoming = await receive()
                raw.extend(incoming.get("body", b""))
                if not incoming.get("more_body", False):
                    break
            url = urlsplit(json.loads(raw)["authorization_url"])
            assert url.hostname == "browser-fixture.myshopify.com"
            params = parse_qs(url.query)
            assert params["redirect_uri"] == [origin + "/api/customer/v1/shopify/callback"]
            values = {
                "code": "offline-browser-code",
                "state": params["state"][0],
                "shop": url.hostname,
                "timestamp": str(int(NOW.timestamp())),
                "host": "offline-signed-host",
            }
            secret = settings.shopify_client_secret
            assert secret is not None
            signature_value = hmac.new(
                secret.get_secret_value().encode(),
                "&".join(f"{key}={values[key]}" for key in sorted(values)).encode(),
                hashlib.sha256,
            ).hexdigest()
            await JSONResponse({"query": [*values.items(), ("hmac", signature_value)]})(
                scope, receive, send
            )
            return
        if path == "/__fixture__/billing-event":
            await JSONResponse({"body": event.decode(), "signature": signature(event)})(
                scope, receive, send
            )
            return
        if path == "/__fixture__/billing-run":
            counts = billing_run(factory, POLICY, billing, NOW)
            await JSONResponse(counts, status_code=200 if counts["events"] == 1 else 500)(
                scope, receive, send
            )
            return
        if path == "/__fixture__/result":
            raw = bytearray()
            while True:
                incoming = await receive()
                raw.extend(incoming.get("body", b""))
                if not incoming.get("more_body", False):
                    break
            result.append(json.loads(raw))
            await JSONResponse({"received": True})(scope, receive, send)
            completed.set()
            return
        messages: list[Message] = []

        async def capture(message: Message) -> None:
            messages.append(message)

        await app(scope, receive, capture)
        start = next(m for m in messages if m["type"] == "http.response.start")
        body = b"".join(m.get("body", b"") for m in messages if m["type"] == "http.response.body")
        status = start["status"]
        if method == "POST" and path == "/api/customer/v1/shopify/callback" and status == 200:
            with factory() as db:
                synced = CommerceSyncService(db, settings).page(
                    json.loads(body)["workspace_id"], now=NOW
                )
                assert synced == {"status": "complete", "imported": 1}, synced
        if path == "/app":
            body = body.replace(
                b"</body>", b'<script type="module" src="/__fixture__/driver.mjs"></script></body>'
            )
        # Commit succeeds in the real route; only its first response is interrupted.
        interruptible = path in {
            "/api/customer/v1/session",
            "/api/customer/v1/workspaces",
        } or path.endswith("/goals")
        if method == "POST" and interruptible and status in (200, 201) and path not in interrupted:
            interrupted.add(path)
            body, start["status"] = b'{"detail":"fixture response lost after commit"}', 503
        responses.append((method, path, status, start["status"]))
        start["headers"] = [
            (key, value) for key, value in start["headers"] if key.lower() != b"content-length"
        ]
        start["headers"].append((b"content-length", str(len(body)).encode()))
        await send(start)
        await send({"type": "http.response.body", "body": body})

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
    assert server.started, "Local HTTPS server failed to start"
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
            origin + "/app",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        assert completed.wait(60), "Real API/browser journey did not report completion"
        assert result and result[0]["status"] == "passed", result
        wid = result[0]["workspace_id"]
        with factory() as db:
            assert db.scalar(select(func.count()).select_from(Workspace)) == 1
            assert db.scalar(select(func.count()).select_from(CustomerMembership)) == 1
            assert db.scalar(select(func.count()).select_from(CustomerUser)) == 2
            assert db.scalar(select(func.count()).select_from(Goal)) == 1
            assert db.scalar(select(func.count()).select_from(GoalCreation)) == 1
            goal = db.get(Goal, result[0]["goal_id"])
            assert goal is not None and goal.confirmed_preview_id is not None
            # Disconnect purges imported facts/snapshots while retaining a revoked identity.
            assert db.scalar(select(func.count()).select_from(ShopifyConnection)) == 0
            assert db.scalar(select(func.count()).select_from(ShopifyOAuthState)) == 0
            for model in (CommerceEntry, CommerceOrder, CommerceSnapshot):
                assert db.scalar(select(func.count()).select_from(model)) == 0
            store = db.scalar(select(CommerceStore).where(CommerceStore.workspace_id == wid))
            assert store is not None and store.status == "revoked"
            row = db.get(WorkspaceBilling, wid)
            assert row is not None and row.status == "active"
            billing_event = db.get(BillingEvent, "evt_browser_journey")
            assert billing_event is not None and billing_event.state == "processed"
            assert (
                db.scalar(
                    select(func.count())
                    .select_from(CustomerSession)
                    .where(CustomerSession.revoked_at.is_(None))
                )
                == 1
            )
        assert (
            sum(
                1
                for _, _, actual, delivered in responses
                if actual in (200, 201) and delivered == 503
            )
            == 3
        )
        assert provider_calls == ["token", "shop", "orders", "agreements"]
        assert ("DELETE", f"/api/customer/v1/workspaces/{wid}/shopify", 204, 204) in responses
        assert ("DELETE", "/api/customer/v1/session", 204, 204) in responses
        assert any(path.endswith("/goals") and actual == 404 for _, path, actual, _ in responses)
    finally:
        browser.terminate()
        try:
            browser.wait(timeout=5)
        except subprocess.TimeoutExpired:
            browser.kill()
            browser.wait(timeout=5)
        server.should_exit = True
        thread.join(timeout=5)
        listener.close()
        if browser_engine is not customer_engine:
            browser_engine.dispose()
