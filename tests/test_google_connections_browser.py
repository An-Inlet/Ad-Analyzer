"""Real portal/navigation/GET bridge; consent HTTP is intercepted before any network."""

import asyncio
import html
import json
import socket
import subprocess
import threading
import time
from collections.abc import Generator
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlencode, urlsplit
from urllib.request import urlopen
from uuid import uuid4

import pytest
import uvicorn
from app.customers.identity import get_identity_provider
from app.customers.models import CustomerMembership, CustomerUser
from app.database.session import Base, get_db
from app.google_connections.contracts import Account, get_transport
from app.google_connections.models import GoogleCustomerConnection
from app.main import app
from app.settings import settings
from sqlalchemy import Engine, create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker
from starlette.types import Receive, Scope, Send

from tests.test_customer_browser_api_journey import localhost_certificate
from tests.test_customer_identity import ISSUER, FakeProvider
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_portal import portal_executable
from tests.test_google_customer_connections import FixtureTransport, setup
from tests.test_google_customer_connections import configured as configured
from tests.test_shopify_consent_browser import Browser


class GoogleBrowser(Browser):
    def consent_document(self, url: str) -> str:
        parsed = urlsplit(url)
        assert parsed.scheme == "https" and parsed.hostname == "accounts.google.com"
        assert parsed.path == "/o/oauth2/v2/auth"
        params = parse_qs(parsed.query)
        assert params["redirect_uri"] == [self.origin + "/api/customer/v1/google/callback"]
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
            "<title>Offline Google Consent</title>"
            f'<a id="consent-approve" href="{html.escape(callback)}">Approve</a>'
            f'<a id="consent-cancel" href="{html.escape(cancel)}">Cancel</a>'
        )


def test_google_navigation_selection_cancel_retry_and_current_role(
    customer_engine: Engine, configured: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    chromium = portal_executable(
        "chromium", "chromium-browser", "google-chrome", "google-chrome-stable"
    )
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    origin = f"https://127.0.0.1:{listener.getsockname()[1]}"
    monkeypatch.setattr(settings, "customer_app_origin", origin)
    transport = FixtureTransport()
    transport.accounts += [
        Account(
            external_id="9876543210", name="Second advertiser", currency="USD", time_zone="UTC"
        ),
        Account(
            external_id="1111111111",
            name="Unsupported manager",
            currency="USD",
            time_zone="UTC",
            manager=True,
        ),
    ]
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
            get_transport: lambda: transport,
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

        browser = GoogleBrowser(tabs()[0]["webSocketDebuggerUrl"], origin)
        browser.call(
            "Fetch.enable",
            {
                "patterns": [
                    {
                        "urlPattern": "https://accounts.google.com/o/oauth2/v2/auth*",
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
                "!document.getElementById('google-authorize').hidden && "
                "!document.getElementById('google-authorize').disabled"
            )

        def begin() -> None:
            browser.evaluate("document.getElementById('google-authorize').click()")
            browser.wait("document.getElementById('consent-cancel') !== null")

        workspace()
        begin()
        browser.evaluate("document.getElementById('consent-cancel').click()")
        browser.wait(
            "document.getElementById('google-result')?.textContent.includes('not completed')"
        )
        assert transport.calls == 0
        assert browser.evaluate("location.search") == ""
        browser.evaluate("document.getElementById('google-return').click()")
        workspace()
        begin()
        old_callback = browser.callbacks[-1]
        browser.evaluate("history.back()")
        browser.wait("document.getElementById('workspace') !== null")
        workspace()
        begin()
        browser.call("Page.navigate", {"url": old_callback})
        browser.wait("document.getElementById('google-result')?.textContent.includes('restart')")
        assert transport.calls == 0
        browser.evaluate("document.getElementById('google-return').click()")
        workspace()
        begin()
        browser.evaluate("document.getElementById('consent-approve').click()")
        browser.wait("document.getElementById('google-account')?.options.length === 2")
        assert "Unsupported manager" not in browser.evaluate("document.body.textContent")
        assert browser.evaluate("location.search") == ""
        # Role changed in another session while the selection page is open.
        with factory() as db:
            membership = db.get(CustomerMembership, (actor, wid))
            assert membership is not None
            membership.role = "viewer"
            db.commit()
        browser.evaluate("document.getElementById('google-select').click()")
        browser.wait("document.getElementById('google-result').textContent.includes('restart')")
        with factory() as db:
            assert db.scalar(select(func.count()).select_from(GoogleCustomerConnection)) == 0
            membership = db.get(CustomerMembership, (actor, wid))
            assert membership is not None
            membership.role = "owner"
            db.commit()
        browser.evaluate("document.getElementById('google-return').click()")
        workspace()
        begin()
        browser.evaluate("document.getElementById('consent-approve').click()")
        browser.wait("document.getElementById('google-account')?.options.length === 2")
        login(browser, "consent-stranger:second")
        browser.evaluate("document.getElementById('google-select').click()")
        browser.wait("document.getElementById('google-result').textContent.includes('restart')")
        with factory() as db:
            assert db.scalar(select(func.count()).select_from(GoogleCustomerConnection)) == 0
        login(browser, "consent-owner:third")
        browser.evaluate("document.getElementById('google-return').click()")
        workspace()
        begin()
        browser.evaluate("document.getElementById('consent-approve').click()")
        browser.wait("document.getElementById('google-account')?.options.length === 2")
        browser.evaluate(
            "document.getElementById('google-account').value='9876543210';"
            "document.getElementById('google-select').click()"
        )
        browser.wait("document.getElementById('connections')?.textContent.includes('9876543210')")
        assert browser.evaluate("document.getElementById('workspace').value") == str(wid)
        assert browser.evaluate("location.search") == ""
        with factory() as db:
            row = db.scalar(select(GoogleCustomerConnection))
            assert (
                row is not None
                and row.workspace_id == wid
                and row.external_account_id == "9876543210"
            )
        assert transport.calls == 3  # Only grant exchanges; no advertising reads or writes.
        history = browser.call("Page.getNavigationHistory")
        assert all("code=" not in entry["url"] for entry in history["entries"])
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
