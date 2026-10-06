"""Real portal/navigation/GET bridge; consent HTTP is intercepted before any network."""

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
from uuid import uuid4

import pytest
import uvicorn
from app.api.customer_meta import configuration as runtime_configuration
from app.api.customer_meta import get_customer_meta_client
from app.customers.identity import get_identity_provider
from app.customers.models import CustomerMembership, CustomerUser
from app.database.session import Base, get_db
from app.main import app
from app.meta import client as meta_http
from app.meta.client import MetaClient
from app.meta.models import MetaConnection
from app.settings import settings
from sqlalchemy import Engine, create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from tests.browser_targets import wait_for_page_target
from tests.test_customer_browser_api_journey import localhost_certificate
from tests.test_customer_identity import ISSUER, FakeProvider
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_meta import configured as configured
from tests.test_customer_portal import portal_executable
from tests.test_google_customer_connections import setup
from tests.test_meta_connection import configuration as configuration
from tests.test_meta_connection import metadata, page
from tests.test_shopify_consent_browser import Browser


class MetaBrowser(Browser):
    def consent_document(self, url: str) -> str:
        parsed = urlsplit(url)
        assert parsed.scheme == "https" and parsed.hostname == "www.facebook.com"
        assert parsed.path == "/v26.0/dialog/oauth"
        params = parse_qs(parsed.query)
        assert params["redirect_uri"] == [self.origin + "/api/customer/v1/meta/callback"]
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
            f'<a id="consent-approve" href="{html.escape(callback)}">Approve</a>'
            f'<a id="consent-cancel" href="{html.escape(cancel)}">Cancel</a>'
        )


def test_meta_customer_browser_consent_selection_disconnect(
    customer_engine: Engine, configured: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    chromium = portal_executable(
        "chromium", "chromium-browser", "google-chrome", "google-chrome-stable"
    )
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    origin = f"https://127.0.0.1:{listener.getsockname()[1]}"
    monkeypatch.setattr(settings, "customer_app_origin", origin)
    provider_calls: list[str] = []

    class ProviderHTTP:
        def open(self, request: Request, timeout: int) -> BytesIO:
            assert timeout == 12
            parsed = urlsplit(request.full_url)
            assert parsed.scheme == "https" and parsed.hostname == "graph.facebook.com"
            provider_calls.append(parsed.path)
            if parsed.path.endswith("/oauth/access_token"):
                value = {"access_token": "offline-meta-access", "expires_in": 86400}
            elif parsed.path.endswith("/me/permissions"):
                value = page({"permission": "ads_read", "status": "granted"})
            elif parsed.path.endswith("/me/adaccounts"):
                value = page(metadata("101"))
            else:
                assert parsed.path.endswith("/act_101")
                value = metadata("101")
            return BytesIO(json.dumps(value).encode())

    monkeypatch.setattr(meta_http, "build_opener", lambda *_: ProviderHTTP())
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
            get_customer_meta_client: lambda: MetaClient(runtime_configuration()),
        },
    )
    cert, key = localhost_certificate(tmp_path)
    server = uvicorn.Server(
        uvicorn.Config(
            app, log_level="critical", lifespan="off", ssl_certfile=str(cert), ssl_keyfile=str(key)
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

        browser = MetaBrowser(wait_for_page_target(tabs), origin)
        browser.call(
            "Fetch.enable",
            {
                "patterns": [
                    {
                        "urlPattern": "https://www.facebook.com/v26.0/dialog/oauth*",
                        "requestStage": "Request",
                    }
                ]
            },
        )
        browser.call("Page.navigate", {"url": origin + "/app"})
        browser.wait(
            "document.getElementById('retry') && !document.getElementById('retry').disabled"
        )

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
                "!document.getElementById('meta-authorize').hidden && "
                "!document.getElementById('meta-authorize').disabled"
            )

        def begin() -> None:
            browser.evaluate("document.getElementById('meta-authorize').click()")
            browser.wait("document.getElementById('consent-approve') !== null")

        workspace()
        begin()
        browser.evaluate("document.getElementById('consent-cancel').click()")
        browser.wait(
            "document.getElementById('meta-result')?.textContent.includes('not completed')"
        )
        assert provider_calls == []
        assert browser.evaluate("location.search") == ""
        browser.evaluate("document.getElementById('meta-return').click()")
        workspace()
        begin()
        old = browser.callbacks[-1]
        browser.evaluate("history.back()")
        browser.wait("document.getElementById('workspace') !== null")
        workspace()
        begin()
        browser.call("Page.navigate", {"url": old})
        browser.wait("document.getElementById('meta-result')?.textContent.includes('restart')")
        assert provider_calls == []
        browser.evaluate("document.getElementById('meta-return').click()")
        workspace()
        begin()
        browser.evaluate("document.getElementById('consent-approve').click()")
        browser.wait("document.getElementById('meta-account')?.options.length === 1")
        assert browser.evaluate("location.search") == ""
        with factory() as db:
            member = db.get(CustomerMembership, (actor, wid))
            assert member is not None
            member.role = "viewer"
            db.commit()
        browser.evaluate("document.getElementById('meta-select').click()")
        browser.wait("document.getElementById('meta-result').textContent.includes('restart')")
        with factory() as db:
            assert db.scalar(select(func.count()).select_from(MetaConnection)) == 0
            member = db.get(CustomerMembership, (actor, wid))
            assert member is not None
            member.role = "owner"
            db.commit()
        browser.evaluate("document.getElementById('meta-return').click()")
        workspace()
        begin()
        browser.evaluate("document.getElementById('consent-approve').click()")
        browser.wait("document.getElementById('meta-account')?.options.length === 1")
        browser.evaluate(
            "document.getElementById('meta-conversion').value='purchase';document.getElementById('meta-select').click()"
        )
        browser.wait(
            "document.getElementById('meta-disconnect')?.hidden === false && "
            "!document.getElementById('meta-disconnect-open').disabled && "
            "!document.getElementById('meta-disconnect-confirm').disabled"
        )
        with factory() as db:
            row = db.scalar(select(MetaConnection))
            assert row is not None and row.workspace_id == wid
            assert row.conversion_action_type == "purchase" and row.generation == 1
        before = len(provider_calls)
        browser.evaluate(
            "document.getElementById('meta-disconnect-open').click();document.getElementById('meta-disconnect-confirm').click()"
        )
        browser.wait(
            "document.getElementById('message').textContent.includes('Confirm the data effects')"
            " && "
            "!document.getElementById('retry').disabled"
        )
        browser.evaluate(
            "document.getElementById('meta-disconnect-consent').checked=true;document.getElementById('meta-disconnect-confirm').click()"
        )
        browser.wait("document.getElementById('message').textContent.includes('Meta disconnected')")
        with factory() as db:
            assert db.scalar(select(func.count()).select_from(MetaConnection)) == 0
        assert len(provider_calls) == before
        assert all(
            "code=" not in entry["url"]
            for entry in browser.call("Page.getNavigationHistory")["entries"]
        )
    finally:
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
