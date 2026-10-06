"""TikTok per-request consent fences with the real HTTP adapter and offline transport."""

from collections.abc import Generator
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from app.api import customer_sources as api
from app.api.customer import router as customer_router
from app.customers.access import CSRF_COOKIE
from app.customers.identity import get_identity_provider
from app.customers.models import CustomerMembership, CustomerSession
from app.database.session import get_db
from app.sources.contracts import get_source_transport
from app.sources.models import SourceAuthorization, SourceConnection
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from tests.test_customer_identity import ORIGIN, FakeProvider, login
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_google_customer_connections import setup
from tests.test_tiktok_http_runtime import META, A, adapter, response
from tests.test_tiktok_sources import configured as configured


@pytest.mark.parametrize("stage", ["token", "metadata"])
@pytest.mark.parametrize("change", ["session", "role", "retry"])
def test_guarded_exchange_stops_stale_actor_or_attempt(
    customer_engine: Engine, configured: None, stage: str, change: str
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
    root = f"/api/customer/v1/workspaces/{wid}/sources/tiktok_ads"
    calls: list[str] = []
    newest: list[str] = []

    def begin() -> str:
        value = owner.post(root + "/authorize", headers=headers)
        assert value.status_code == 200
        return str(parse_qs(urlsplit(value.json()["authorization_url"]).query)["state"][0])

    def handler(request: httpx.Request) -> httpx.Response:
        current = "token" if request.method == "POST" else "metadata"
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
        return response(
            {"access_token": "offline-tiktok-token", "advertiser_ids": [A]}
            if current == "token"
            else {"list": [META]}
        )

    app.dependency_overrides[get_source_transport] = lambda: adapter(handler)
    nonce = begin()
    result = owner.post(
        "/api/customer/v1/sources/tiktok_ads/callback",
        headers=headers,
        json={"state": nonce, "code": "fixture"},
    )
    assert result.status_code == {"session": 401, "role": 403, "retry": 404}[change]
    assert calls == (["token"] if stage == "token" else ["token", "metadata"])
    with Session(customer_engine) as db:
        assert db.scalar(select(func.count()).select_from(SourceConnection)) == 0
        row = db.scalar(select(SourceAuthorization))
        assert row is not None and row.encrypted_grant is None
        assert row.state == ("pending" if newest else "failed")
    before = list(calls)
    owner.post(
        "/api/customer/v1/sources/tiktok_ads/callback",
        headers=headers,
        json={"state": nonce, "code": "fixture"},
    )
    assert calls == before


def test_retry_only_replaces_current_provider_session_workspace(
    customer_engine: Engine, configured: None
) -> None:
    from urllib.parse import urlencode

    from app.sources import service

    from tests.test_commerce_measurement import NOW
    from tests.test_tiktok_sources import TikTokFixture, connect

    class CRMFixture(TikTokFixture):
        def authorize_url(self, state: str, redirect_uri: str) -> str:
            return "https://www.klaviyo.com/oauth/authorize?" + urlencode(
                {"state": state, "redirect_uri": redirect_uri}
            )

    with Session(customer_engine) as db:
        wid, sid = setup(db, "retry-tiktok")
        other, sid2 = setup(db, "other-tiktok")
        runtime = TikTokFixture()
        _, selected = connect(db, wid, sid, runtime)

        def begin(w: int, s: str) -> str:
            return parse_qs(urlsplit(service.begin(db, "tiktok_ads", w, s, runtime, NOW)).query)[
                "state"
            ][0]

        same_provider_other_session = begin(wid, sid2)
        other_workspace = begin(other, sid)
        other_provider = parse_qs(
            urlsplit(service.begin(db, "klaviyo", wid, sid, CRMFixture(), NOW)).query
        )["state"][0]
        old = begin(wid, sid)
        new = begin(wid, sid)
        from fastapi import HTTPException

        with pytest.raises(HTTPException):
            service.authorization(db, "tiktok_ads", old, sid, NOW)
        for nonce, workspace_session in [
            (selected, sid),
            (new, sid),
            (same_provider_other_session, sid2),
            (other_workspace, sid),
        ]:
            assert service.authorization(db, "tiktok_ads", nonce, workspace_session, NOW)
        assert service.authorization(db, "klaviyo", other_provider, sid, NOW)


@pytest.mark.parametrize("initially_disabled", [False, True])
def test_auth_code_callback_bridge_headers_and_actual_access_filter(
    monkeypatch: pytest.MonkeyPatch, initially_disabled: bool
) -> None:
    import logging
    from io import StringIO

    from app.shopify.logging import install_access_filter

    application = FastAPI()
    application.include_router(api.router)
    bridge = TestClient(application).get(
        "/api/customer/v1/sources/tiktok_ads/callback?auth_code=fixture-private-code&state=fixture-private-state"
    )
    assert bridge.status_code == 200
    assert bridge.headers["referrer-policy"] == "no-referrer"
    assert bridge.headers["cache-control"] == "no-store"
    assert "script-src 'self'" in bridge.headers["content-security-policy"]
    assert "fixture-private-code" not in bridge.text
    stream = StringIO()
    logger = logging.getLogger("uvicorn.access")
    # Alembic fileConfig disables existing loggers after earlier browser tests
    # create uvicorn.access. Exercise both incoming states, then restore them.
    monkeypatch.setattr(logger, "disabled", initially_disabled)
    handler = logging.StreamHandler(stream)
    install_access_filter()
    logger.addHandler(handler)
    logger.disabled = False
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
                    "/api/customer/v1/sources/tiktok_ads/callback?auth_code=fixture-private-code&state=fixture-private-state",
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
        logger.disabled = initially_disabled
