"""CRM per-request consent fences with the real HTTP adapter and offline transport."""

from collections.abc import Callable, Generator
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from app.api import customer_sources as api
from app.api.customer import router as customer_router
from app.customer_context.http import HubSpotHTTPRead, KlaviyoHTTPRead, OmnisendHTTPRead
from app.customers.access import CSRF_COOKIE
from app.customers.identity import get_identity_provider
from app.customers.models import CustomerMembership, CustomerSession
from app.database.session import get_db
from app.sources.contracts import get_source_transport
from app.sources.models import SourceAuthorization, SourceConnection
from app.sources.security import SourceVault
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from tests.test_crm_http_runtime import ProviderHTTP
from tests.test_customer_identity import ORIGIN, FakeProvider, login
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_google_customer_connections import setup
from tests.test_omnisend_http_runtime import OmnisendIO
from tests.test_tiktok_sources import configured as configured


def crm_adapter(
    provider: str, handler: Callable[[httpx.Request], httpx.Response]
) -> KlaviyoHTTPRead | HubSpotHTTPRead | OmnisendHTTPRead:
    types: dict[str, type[KlaviyoHTTPRead] | type[HubSpotHTTPRead] | type[OmnisendHTTPRead]] = {
        "klaviyo": KlaviyoHTTPRead,
        "hubspot": HubSpotHTTPRead,
        "omnisend": OmnisendHTTPRead,
    }
    cls = types[provider]
    return cls(
        "fixture-client", SecretStr("fixture-secret"), transport=httpx.MockTransport(handler)
    )


@pytest.mark.parametrize("provider", ["klaviyo", "hubspot", "omnisend"])
@pytest.mark.parametrize("stage", ["token", "metadata"])
@pytest.mark.parametrize("change", ["session", "role", "retry"])
def test_guarded_exchange_stops_stale_actor_or_attempt(
    customer_engine: Engine, configured: None, stage: str, change: str, provider: str
) -> None:
    app = FastAPI()
    app.include_router(customer_router)
    app.include_router(api.router)

    def database() -> Generator[Session, None, None]:
        with Session(customer_engine) as db:
            yield db

    app.dependency_overrides[get_db] = database
    app.dependency_overrides[get_identity_provider] = lambda: FakeProvider()
    owner = TestClient(app, base_url=ORIGIN)
    uid = login(owner, "tiktok-owner:1")
    with Session(customer_engine) as db:
        wid, _ = setup(db, "tiktok-guard")
        db.add(CustomerMembership(user_id=uid, workspace_id=wid, role="owner"))
        db.commit()
    headers = {"Origin": ORIGIN, "X-CSRF-Token": owner.cookies[CSRF_COOKIE]}
    root = f"/api/customer/v1/workspaces/{wid}/sources/{provider}"
    calls: list[str] = []
    newest: list[str] = []

    def begin() -> str:
        value = owner.post(root + "/authorize", headers=headers)
        assert value.status_code == 200
        return str(parse_qs(urlsplit(value.json()["authorization_url"]).query)["state"][0])

    def handler(request: httpx.Request) -> httpx.Response:
        current = "token" if request.url.path.endswith("/token") else "metadata"
        calls.append(current)
        if current == stage:
            if change == "retry":
                newest.append(begin())
            else:
                with Session(customer_engine) as db:
                    if change == "role":
                        member = db.get(CustomerMembership, (uid, wid))
                        assert member is not None
                        member.role = "viewer"
                    else:
                        session = db.scalar(
                            select(CustomerSession).where(CustomerSession.user_id == uid)
                        )
                        assert session is not None
                        session.revoked_at = 1
                    db.commit()
        return io(request)

    io = OmnisendIO() if provider == "omnisend" else ProviderHTTP(provider)

    app.dependency_overrides[get_source_transport] = lambda: crm_adapter(provider, handler)
    nonce = begin()
    result = owner.post(
        f"/api/customer/v1/sources/{provider}/callback",
        headers=headers,
        json={"state": nonce, "code": "fixture"},
    )
    assert result.status_code == {"session": 401, "role": 403, "retry": 404}[change]
    assert calls == (["token"] if stage == "token" else ["token", "metadata"])
    with Session(customer_engine) as db:
        assert db.scalar(select(func.count()).select_from(SourceConnection)) == 0
        row = db.scalar(select(SourceAuthorization))
        assert row is not None
        if newest and provider == "klaviyo":
            assert row.encrypted_grant is not None
            context = SourceVault().open(wid, "klaviyo", row.digest, row.encrypted_grant)
            assert set(context) == {"pkce_verifier"}
        else:
            assert row.encrypted_grant is None
        assert row.state == ("pending" if newest else "failed")
    before = list(calls)
    owner.post(
        f"/api/customer/v1/sources/{provider}/callback",
        headers=headers,
        json={"state": nonce, "code": "fixture"},
    )
    assert calls == before


@pytest.mark.parametrize("provider", ["klaviyo", "hubspot", "omnisend"])
def test_crm_setup_scoped_disabled_independent_of_export(
    customer_engine: Engine, configured: None, provider: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.settings import settings
    from app.sources.contracts import UnavailableSource

    app = FastAPI()
    app.include_router(customer_router)
    app.include_router(api.router)

    def database() -> Generator[Session, None, None]:
        with Session(customer_engine) as db:
            yield db

    app.dependency_overrides[get_db] = database
    app.dependency_overrides[get_identity_provider] = lambda: FakeProvider()
    owner = TestClient(app, base_url=ORIGIN)
    uid = login(owner, "crm-setup:1")
    with Session(customer_engine) as db:
        wid, _ = setup(db, "crm-setup")
        db.add(CustomerMembership(user_id=uid, workspace_id=wid, role="owner"))
        db.commit()
    monkeypatch.setattr(settings, "customer_export_enabled", False)
    monkeypatch.setattr(settings, provider + "_client_id", "fixture-client")
    monkeypatch.setattr(api, "get_source_transport", lambda _: UnavailableSource())
    path = f"/api/customer/v1/workspaces/{wid}/sources/{provider}/setup"
    value = owner.get(path)
    assert value.status_code == 200 and value.headers["cache-control"] == "no-store"
    assert value.json()["enabled"] is False and value.json()["client_id"] == ""
    runtime = crm_adapter(provider, lambda _: (_ for _ in ()).throw(AssertionError("no HTTP")))
    monkeypatch.setattr(
        api,
        "get_source_transport",
        lambda name: runtime if name == provider else UnavailableSource(),
    )
    assert owner.get(path).json()["enabled"] is True
    for other in {"klaviyo", "hubspot", "omnisend"} - {provider}:
        assert owner.get(path.replace(provider, other)).json()["enabled"] is False
    outsider = TestClient(app, base_url=ORIGIN)
    login(outsider, "crm-outsider:1")
    assert outsider.get(path).status_code == 404
    with Session(customer_engine) as db:
        member = db.get(CustomerMembership, (uid, wid))
        assert member is not None
        member.role = "viewer"
        db.commit()
    assert owner.get(path).json()["can_manage"] is False


@pytest.mark.parametrize("provider", ["klaviyo", "hubspot", "omnisend"])
def test_crm_callback_bridge_headers_and_actual_access_filter(provider: str) -> None:
    import logging
    from io import StringIO

    from app.shopify.logging import install_access_filter

    application = FastAPI()
    application.include_router(api.router)
    bridge = TestClient(application).get(
        f"/api/customer/v1/sources/{provider}/callback?code=fixture-private-code&state=fixture-private-state"
    )
    assert bridge.status_code == 200
    assert bridge.headers["referrer-policy"] == "no-referrer"
    assert bridge.headers["cache-control"] == "no-store"
    assert "script-src 'self'" in bridge.headers["content-security-policy"]
    assert "fixture-private-code" not in bridge.text
    stream = StringIO()
    logger = logging.getLogger("uvicorn.access")
    handler = logging.StreamHandler(stream)
    install_access_filter()
    logger.addHandler(handler)
    try:
        logger.handle(
            logging.LogRecord(
                "uvicorn.access",
                logging.INFO,
                "",
                1,
                '%s - "%s %s HTTP/%s" %d',
                (
                    "127.0.0.1",
                    "GET",
                    f"/api/customer/v1/sources/{provider}/callback?code=fixture-private-code&state=fixture-private-state",
                    "1.1",
                    200,
                ),
                None,
            )
        )
        assert stream.getvalue() == ""
        logger.handle(
            logging.LogRecord("uvicorn.access", logging.INFO, "", 1, "GET /health", (), None)
        )
        assert "GET /health" in stream.getvalue()
    finally:
        logger.removeHandler(handler)
