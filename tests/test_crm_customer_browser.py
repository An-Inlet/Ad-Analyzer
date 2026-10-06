"""Real portal/navigation/GET bridge; consent HTTP is intercepted before any network."""

import asyncio
import base64
import hashlib
import html
import json
import socket
import subprocess
import threading
import time
from collections.abc import Generator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlencode, urlsplit
from urllib.request import urlopen
from uuid import uuid4

import httpx
import pytest
import uvicorn
from app.api import customer_sources as source_api
from app.customers.identity import get_identity_provider
from app.customers.models import CustomerMembership, CustomerSession, CustomerUser
from app.database.session import Base, get_db
from app.google_connections.security import digest
from app.main import app
from app.settings import settings
from app.sources import service as source_service
from app.sources.contracts import get_source_transport
from app.sources.models import SourceConnection
from sqlalchemy import Engine, create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker
from starlette.types import Receive, Scope, Send

from tests.browser_targets import wait_for_page_target
from tests.test_crm_http_runtime import ProviderHTTP
from tests.test_customer_browser_api_journey import localhost_certificate
from tests.test_customer_crm import crm_adapter
from tests.test_customer_identity import ISSUER, FakeProvider
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_portal import portal_executable
from tests.test_google_customer_connections import setup
from tests.test_omnisend_http_runtime import OmnisendIO
from tests.test_shopify_consent_browser import Browser
from tests.test_tiktok_sources import configured as configured


class CRMBrowser(Browser):
    provider: str = "klaviyo"
    challenge: str | None = None

    def evaluate(self, expression: str) -> Any:
        return super().evaluate(expression.replace("PROVIDER", self.provider))

    def consent_document(self, url: str) -> str:
        parsed = urlsplit(url)
        assert parsed.scheme == "https"
        assert parsed.hostname in {"www.klaviyo.com", "app.hubspot.com", "app.omnisend.com"}
        params = parse_qs(parsed.query)
        self.challenge = params.get("code_challenge", [None])[0]
        assert params["redirect_uri"] == [
            self.origin + f"/api/customer/v1/sources/{self.provider}/callback"
        ]
        callback = (
            params["redirect_uri"][0]
            + "?"
            + urlencode({"state": params["state"][0], "code": "fixture-consent"})
        )
        self.callbacks.append(callback)
        cancel = (
            params["redirect_uri"][0]
            + "?"
            + urlencode({"error": "access_denied", "state": params["state"][0]})
        )
        return (
            "<title>Offline CRM Consent</title>"
            f'<a id="consent-approve" href="{html.escape(callback)}">Approve</a>'
            f'<a id="consent-cancel" href="{html.escape(cancel)}">Cancel</a>'
        )


@pytest.mark.parametrize("provider", ["klaviyo", "hubspot", "omnisend"])
def test_crm_navigation_selection_cancel_retry_and_disconnect(
    customer_engine: Engine,
    configured: None,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    provider: str,
) -> None:
    chromium = portal_executable(
        "chromium", "chromium-browser", "google-chrome", "google-chrome-stable"
    )
    listener = socket.socket()
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind(("127.0.0.1", 0))
    origin = "https://inlet.example"
    monkeypatch.setattr(settings, "customer_app_origin", origin)
    calls: list[str] = []

    io = OmnisendIO() if provider == "omnisend" else ProviderHTTP(provider)

    def provider_http(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        if provider == "klaviyo" and request.url.path.endswith("/token"):
            values = parse_qs(request.content.decode())
            verifier = values["code_verifier"][0]
            assert isinstance(browser, CRMBrowser)
            assert (
                base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
                .rstrip(b"=")
                .decode()
                == browser.challenge
            )
        return io(request)

    transport = crm_adapter(provider, provider_http)
    account_id = {"klaviyo": "account1", "hubspot": "123", "omnisend": "brand_123"}[provider]
    monkeypatch.setattr(settings, provider + "_client_id", "fixture-client")
    monkeypatch.setattr(
        source_api,
        "get_source_transport",
        lambda name: transport if name == provider else get_source_transport(name),
    )
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
        {
            get_db: database,
            get_identity_provider: lambda: FakeProvider(),
            get_source_transport: lambda: transport,
        },
    )
    initial_probe, release_probe = threading.Event(), threading.Event()

    async def delayed_initial_session(scope: Scope, receive: Receive, send: Send) -> None:
        # Force startup/login overlap so a disabled Retry click cannot pass by luck.
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
            "--no-proxy-server",
            f"--host-resolver-rules=MAP inlet.example 127.0.0.1:{listener.getsockname()[1]}, "
            "MAP * ~NOTFOUND, EXCLUDE 127.0.0.1",
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

        browser = CRMBrowser(wait_for_page_target(tabs), origin)
        browser.provider = provider
        browser.call(
            "Fetch.enable",
            {
                "patterns": [
                    {
                        "urlPattern": {
                            "klaviyo": "https://www.klaviyo.com/oauth/authorize*",
                            "hubspot": "https://app.hubspot.com/oauth/authorize*",
                            "omnisend": "https://app.omnisend.com/oauth2/authorize*",
                        }[provider],
                        "requestStage": "Request",
                    }
                ]
            },
        )
        browser.call(
            "Page.addScriptToEvaluateOnNewDocument",
            {
                "source": (
                    "globalThis.__fixtureMessages=[]; "
                    "for(const name of ['log','error','warn']) "
                    "console[name]=(...args)=>__fixtureMessages.push(args.map(String).join(' ')); "
                    "addEventListener('error',event=>__fixtureMessages.push(event.message));"
                )
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

        def workspace() -> None:
            browser.wait(
                "document.getElementById('workspace')?.options.length === 2 && "
                "!document.getElementById('workspace').disabled"
            )
            browser.evaluate(
                f"document.getElementById('workspace').value='{wid}';"
                "document.getElementById('workspace').dispatchEvent(new Event('change'))"
            )
            browser.wait(
                "!document.getElementById('PROVIDER-authorize').hidden && "
                "!document.getElementById('PROVIDER-authorize').disabled"
            )

        def begin() -> None:
            browser.evaluate("document.getElementById('PROVIDER-authorize').click()")
            try:
                browser.wait("document.getElementById('consent-cancel') !== null")
            except AssertionError:
                raise AssertionError(
                    browser.evaluate("document.getElementById('message')?.textContent")
                ) from None

        workspace()
        begin()
        browser.evaluate("document.getElementById('consent-cancel').click()")
        browser.wait("document.getElementById('crm-result')?.textContent.includes('not completed')")
        assert calls == []
        assert browser.evaluate("location.search") == ""
        assert (
            browser.evaluate(
                "JSON.stringify([localStorage,sessionStorage,globalThis.__fixtureMessages,document.referrer])"
            ).find("fixture-consent")
            == -1
        )
        browser.evaluate("document.getElementById('crm-return').click()")
        workspace()
        begin()
        old_callback = browser.callbacks[-1]
        alias = old_callback.replace("code=", "auth_code=")
        browser.call("Page.navigate", {"url": alias})
        browser.wait(
            "document.getElementById('crm-result')?.textContent.includes('No valid callback')"
        )
        assert calls == []
        browser.evaluate("document.getElementById('crm-return').click()")
        workspace()
        begin()
        old_callback = browser.callbacks[-1]
        browser.evaluate("history.back()")
        browser.wait("document.getElementById('workspace') !== null")
        workspace()
        begin()
        browser.call("Page.navigate", {"url": old_callback})
        browser.wait("document.getElementById('crm-result')?.textContent.includes('restart')")
        assert calls == []
        browser.evaluate("document.getElementById('crm-return').click()")
        workspace()
        begin()
        browser.evaluate("document.getElementById('consent-approve').click()")
        browser.wait("document.getElementById('crm-account')?.options.length === 1")
        assert browser.evaluate("location.search") == ""
        assert (
            browser.evaluate(
                "JSON.stringify([localStorage,sessionStorage,globalThis.__fixtureMessages,document.referrer])"
            ).find("fixture-consent")
            == -1
        )
        # Role changed in another session while the selection page is open.
        with factory() as db:
            membership = db.get(CustomerMembership, (actor, wid))
            assert membership is not None
            membership.role = "viewer"
            db.commit()
        browser.evaluate("document.getElementById('crm-select').click()")
        browser.wait("document.getElementById('crm-result').textContent.includes('restart')")
        with factory() as db:
            assert db.scalar(select(func.count()).select_from(SourceConnection)) == 0
            membership = db.get(CustomerMembership, (actor, wid))
            assert membership is not None
            membership.role = "owner"
            db.commit()
        browser.evaluate("document.getElementById('crm-return').click()")
        workspace()
        begin()
        browser.evaluate("document.getElementById('consent-approve').click()")
        browser.wait("document.getElementById('crm-account')?.options.length === 1")
        login(browser, "consent-stranger:second")
        browser.evaluate("document.getElementById('crm-select').click()")
        browser.wait("document.getElementById('crm-result').textContent.includes('restart')")
        with factory() as db:
            assert db.scalar(select(func.count()).select_from(SourceConnection)) == 0
        login(browser, "consent-owner:third")
        browser.evaluate("document.getElementById('crm-return').click()")
        workspace()
        begin()
        browser.evaluate("document.getElementById('consent-approve').click()")
        browser.wait("document.getElementById('crm-account')?.options.length === 1")
        browser.evaluate(
            f"document.getElementById('crm-account').value='{account_id}';"
            "document.getElementById('crm-select').click()"
        )
        browser.wait(
            f"document.getElementById('connections')?.textContent.includes('{account_id}')"
        )
        assert browser.evaluate("document.getElementById('workspace').value") == str(wid)
        assert browser.evaluate("location.search") == ""
        assert (
            browser.evaluate(
                "JSON.stringify([localStorage,sessionStorage,globalThis.__fixtureMessages,document.referrer])"
            ).find("fixture-consent")
            == -1
        )
        with factory() as db:
            row = db.scalar(select(SourceConnection))
            assert row is not None and row.workspace_id == wid and row.external_id == account_id
        assert len(calls) == 6  # Only grant exchanges; no advertising reads or writes.
        history = browser.call("Page.getNavigationHistory")
        assert all("code=" not in entry["url"] for entry in history["entries"])
        with factory() as db:
            row = db.scalar(select(SourceConnection))
            assert row is not None
            cid, generation = row.id, row.generation
            session = db.scalar(
                select(CustomerSession).where(
                    CustomerSession.user_id == actor, CustomerSession.revoked_at.is_(None)
                )
            )
            assert session is not None
            sid = session.digest
            if isinstance(io, OmnisendIO):
                io.brand["brandID"] = "brand_sibling"
                sibling_external = "brand_sibling"
            else:
                io.account = "456"
                sibling_external = "456"
            now = datetime.now(UTC)
            nonce = parse_qs(
                urlsplit(
                    source_service.begin(db, transport.provider, wid, sid, transport, now)
                ).query
            )["state"][0]
            # This additional offline connection uses the same real adapter, with
            # the source service's encrypted per-attempt PKCE context.
            if provider == "klaviyo":
                from app.sources.models import SourceAuthorization
                from app.sources.security import SourceVault

                pending = db.get(SourceAuthorization, digest(nonce))
                assert pending is not None and pending.encrypted_grant is not None
                verifier = SourceVault().open(
                    wid, transport.provider, pending.digest, pending.encrypted_grant
                )["pkce_verifier"]
                browser.challenge = (
                    base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
                    .rstrip(b"=")
                    .decode()
                )
            source_service.finish(
                db, transport.provider, nonce, sid, "fixture-sibling", transport, now
            )
            sibling = source_service.select_account(
                db, transport.provider, nonce, sid, sibling_external, now
            )
            sibling_id, sibling_grant = sibling.id, sibling.encrypted_grant
        calls_before_disconnect = list(calls)
        workspace()
        browser.wait("document.getElementById('PROVIDER-disconnect-account').options.length === 2")
        browser.evaluate(
            f"document.getElementById('PROVIDER-disconnect-account').value='{cid}';document.getElementById('PROVIDER-disconnect-open').click()"
        )
        assert "does not delete provider data" in browser.evaluate(
            "document.getElementById('PROVIDER-disconnect-effects').textContent"
        )
        browser.evaluate("document.getElementById('PROVIDER-disconnect-confirm').click()")
        browser.wait(
            "document.getElementById('message').textContent.includes('confirm the data effects')"
        )
        browser.evaluate("document.getElementById('PROVIDER-disconnect-cancel').click()")
        assert browser.evaluate("document.getElementById('PROVIDER-disconnect-review').hidden")
        browser.evaluate(
            "document.getElementById('PROVIDER-disconnect-open').click();document.getElementById('PROVIDER-disconnect-consent').checked=true"
        )
        with factory() as db:
            membership = db.get(CustomerMembership, (actor, wid))
            assert membership is not None
            membership.role = "viewer"
            db.commit()
        browser.evaluate("document.getElementById('PROVIDER-disconnect-confirm').click()")
        browser.wait(
            "document.getElementById('message').textContent.includes('does not permit') && "
            "!document.getElementById('retry').disabled"
        )
        with factory() as db:
            row = db.get(SourceConnection, cid)
            assert row is not None and row.status == "connected"
            membership = db.get(CustomerMembership, (actor, wid))
            assert membership is not None
            membership.role = "owner"
            db.commit()
        browser.evaluate("document.getElementById('PROVIDER-disconnect-confirm').click()")
        browser.wait(
            "document.getElementById('message').textContent.includes('disconnected locally') && "
            "!document.getElementById('retry').disabled"
        )
        assert (
            browser.evaluate(
                "document.getElementById('PROVIDER-disconnect-account').options.length"
            )
            == 1
        )
        with factory() as db:
            row = db.get(SourceConnection, cid)
            assert row is not None and row.status == "disconnected"
            assert row.encrypted_grant is None and row.generation == generation + 1
            assert row.cursor is None and row.staged == {} and row.next_attempt_at is None
            retained_sibling = db.get(SourceConnection, sibling_id)
            assert retained_sibling is not None and retained_sibling.status == "connected"
            assert retained_sibling.encrypted_grant == sibling_grant
        assert calls == calls_before_disconnect
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
