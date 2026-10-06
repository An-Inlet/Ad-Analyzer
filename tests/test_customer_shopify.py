"""Offline customer session/CSRF boundary and transactional Shopify callbacks."""

import hashlib
import hmac
import time
from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from typing import Any
from urllib.parse import parse_qs, urlsplit

import pytest
from app.api import customer_shopify as api
from app.api.customer import router as customer_router
from app.customers.access import CSRF_COOKIE, SESSION_COOKIE, digest
from app.customers.identity import get_identity_provider
from app.customers.models import CustomerMembership, CustomerSession
from app.database.session import get_db
from app.settings import Settings, settings
from app.shopify.models import ShopifyConnection, ShopifyOAuthState
from app.shopify.security import configuration_ready
from app.shopify.service import ConnectionService
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine, event, func, select
from sqlalchemy.orm import Session

from tests.test_customer_identity import ORIGIN, FakeProvider, login
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_google_customer_connections import setup
from tests.test_shopify_sales import SHOP, FakeShopify
from tests.test_shopify_sales import configuration as configuration


@pytest.fixture()
def configured(configuration: Settings, monkeypatch: pytest.MonkeyPatch) -> None:
    for name in Settings.model_fields:
        if name.startswith("shopify_"):
            monkeypatch.setattr(settings, name, getattr(configuration, name))
    monkeypatch.setattr(settings, "shopify_customer_enabled", True)
    monkeypatch.setattr(settings, "customer_app_origin", ORIGIN)


class FixtureShopify(FakeShopify):
    def __init__(self) -> None:
        super().__init__(settings)
        self.entered = Event()
        self.release = Event()
        self.pause = False
        self.after: Any = None

    def token(
        self, shop: str, *, code: str | None = None, refresh: str | None = None
    ) -> dict[str, Any]:
        self.entered.set()
        if self.pause:
            assert self.release.wait(10), "Test failed to release bounded fixture"
        if self.after:
            self.after()
        return super().token(shop, code=code, refresh=refresh)


def clients(
    engine: Engine, runtime: FixtureShopify
) -> tuple[TestClient, TestClient, int, FakeProvider]:
    app = FastAPI()
    app.include_router(customer_router)
    app.include_router(api.router)
    provider = FakeProvider()

    def database() -> Generator[Session, None, None]:
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = database
    app.dependency_overrides[get_identity_provider] = lambda: provider
    app.dependency_overrides[api.get_customer_shopify_client] = lambda: runtime
    owner, stranger = TestClient(app, base_url=ORIGIN), TestClient(app, base_url=ORIGIN)
    uid = login(owner, "owner:1")
    login(stranger, "stranger:1")
    with Session(engine) as db:
        wid, _ = setup(db, "shopify")
        db.add(CustomerMembership(user_id=uid, workspace_id=wid, role="owner", status="active"))
        db.commit()
    return owner, stranger, wid, provider


def headers(client: TestClient) -> dict[str, str]:
    return {"Origin": ORIGIN, "X-CSRF-Token": client.cookies[CSRF_COOKIE]}


def begin(client: TestClient, wid: int) -> list[tuple[str, str]]:
    reply = client.post(
        f"/api/customer/v1/workspaces/{wid}/shopify/authorize",
        headers=headers(client),
        json={"shop": SHOP},
    )
    assert reply.status_code == 200, reply.text
    params = parse_qs(urlsplit(reply.json()["authorization_url"]).query)
    assert params["redirect_uri"] == [ORIGIN + "/api/customer/v1/shopify/callback"]
    values = {
        "code": "fixture-code",
        "state": params["state"][0],
        "shop": SHOP,
        "timestamp": str(int(time.time())),
        "host": "signed-host-value",
    }
    secret = settings.shopify_client_secret
    assert secret is not None
    signature = hmac.new(
        secret.get_secret_value().encode(),
        "&".join(f"{k}={values[k]}" for k in sorted(values)).encode(),
        hashlib.sha256,
    ).hexdigest()
    return [*values.items(), ("hmac", signature)]


def finish(client: TestClient, query: list[tuple[str, str]]) -> Any:
    return client.post(
        "/api/customer/v1/shopify/callback", json={"query": query}, headers=headers(client)
    )


def test_customer_authorization_scope_callback_replay_and_disconnect(
    customer_engine: Engine, configured: None
) -> None:
    runtime = FixtureShopify()
    owner, stranger, wid, _ = clients(customer_engine, runtime)
    path = f"/api/customer/v1/workspaces/{wid}/shopify"
    assert stranger.get(path).status_code == 404
    assert owner.post(path + "/authorize", json={"shop": SHOP}).status_code == 403
    assert stranger.delete(path, headers=headers(stranger)).status_code == 404
    query = begin(owner, wid)
    assert finish(stranger, query).status_code == 422
    duplicate = [*query, ("host", "duplicate")]
    assert finish(owner, duplicate).status_code == 422
    assert runtime.token_calls == 0
    result = finish(owner, query)
    assert result.status_code == 200, result.text
    assert result.json()["workspace_id"] == wid
    assert result.json()["live_verified"] is False
    assert "encrypted" not in result.text and "access_token" not in result.text
    assert finish(owner, query).status_code == 422
    assert runtime.token_calls == 1
    listed = owner.get(path)
    assert listed.headers["cache-control"] == "no-store"
    assert len(listed.json()) == 1
    assert owner.delete(path, headers=headers(owner)).status_code == 204
    assert owner.get(path).json() == []
    with Session(customer_engine) as db:
        assert db.scalar(select(func.count()).select_from(ShopifyOAuthState)) == 0
        assert db.scalar(select(func.count()).select_from(ShopifyConnection)) == 0


def test_nonce_bound_to_session_and_pending_disconnect(
    customer_engine: Engine, configured: None
) -> None:
    runtime = FixtureShopify()
    owner, _, wid, _ = clients(customer_engine, runtime)
    query = begin(owner, wid)
    # A fresh login for the same user cannot spend the old session's nonce.
    login(owner, "owner:2")
    assert finish(owner, query).status_code == 422
    query = begin(owner, wid)
    assert (
        owner.delete(
            f"/api/customer/v1/workspaces/{wid}/shopify", headers=headers(owner)
        ).status_code
        == 204
    )
    assert finish(owner, query).status_code == 422
    assert runtime.token_calls == 0


def test_after_exchange_provider_revocation_rolls_back_credentials(
    customer_engine: Engine, configured: None
) -> None:
    runtime = FixtureShopify()
    owner, _, wid, provider = clients(customer_engine, runtime)
    query = begin(owner, wid)
    runtime.after = lambda: provider.revoked.add("owner")
    assert finish(owner, query).status_code == 401
    with Session(customer_engine) as db:
        assert db.scalar(select(func.count()).select_from(ShopifyConnection)) == 0


@pytest.mark.parametrize("change", ["session", "membership", "role"])
def test_revoked_session_or_membership_cannot_finish(
    customer_engine: Engine, configured: None, change: str
) -> None:
    runtime = FixtureShopify()
    owner, _, wid, _ = clients(customer_engine, runtime)
    query = begin(owner, wid)
    with Session(customer_engine) as db:
        session = db.get(CustomerSession, digest(owner.cookies[SESSION_COOKIE]))
        assert session is not None
        if change == "session":
            session.revoked_at = int(time.time())
        else:
            member = db.scalar(
                select(CustomerMembership).where(
                    CustomerMembership.user_id == session.user_id,
                    CustomerMembership.workspace_id == wid,
                )
            )
            assert member is not None
            if change == "membership":
                member.status = "suspended"
            else:
                member.role = "viewer"
        db.commit()
    assert (
        finish(owner, query).status_code == {"session": 401, "membership": 404, "role": 403}[change]
    )
    assert runtime.token_calls == 0


def test_config_disabled_and_callback_relay_preserves_signed_pairs(
    customer_engine: Engine, configured: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime = FixtureShopify()
    owner, _, wid, _ = clients(customer_engine, runtime)
    assert configuration_ready(settings)  # Dashboard callback remains unchanged.
    monkeypatch.setattr(settings, "shopify_customer_enabled", False)
    assert (
        owner.post(
            f"/api/customer/v1/workspaces/{wid}/shopify/authorize",
            headers=headers(owner),
            json={"shop": SHOP},
        ).status_code
        == 503
    )
    relay = owner.get("/api/customer/v1/shopify/callback?host=%3Cscript%3Eprivate%3C/script%3E")
    assert "private" not in relay.text
    assert "URLSearchParams(location.search).entries()" in relay.text
    assert "history.replaceState" in relay.text and "sessionStorage" not in relay.text
    assert "sha256-" in relay.headers["content-security-policy"]
    monkeypatch.setattr(settings, "shopify_customer_enabled", True)
    for origin in ("http://inlet.example", ORIGIN + "/evil", "https://user@inlet.example"):
        monkeypatch.setattr(settings, "customer_app_origin", origin)
        assert not configuration_ready(settings, customer=True)
    assert runtime.token_calls == 0


@pytest.mark.parametrize("competitor", ["callback", "disconnect"])
def test_postgres_callback_serializes_duplicate_and_disconnect(
    customer_engine: Engine, configured: None, competitor: str
) -> None:
    if customer_engine.dialect.name != "postgresql":
        pytest.skip("row lock ordering is PostgreSQL-specific")
    runtime = FixtureShopify()
    owner, _, wid, _ = clients(customer_engine, runtime)
    query = begin(owner, wid)
    runtime.pause = True
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(finish, owner, query)
        assert runtime.entered.wait(5)
        started = Event()

        def attempting_lock(
            conn: Any, cursor: Any, statement: str, parameters: Any, context: Any, many: bool
        ) -> None:
            if "FROM workspaces" in statement and "FOR UPDATE" in statement:
                started.set()

        event.listen(customer_engine, "before_cursor_execute", attempting_lock)

        def other() -> Any:
            if competitor == "callback":
                return finish(owner, query)
            with Session(customer_engine) as db:
                ConnectionService(db, settings).disconnect(wid, "owner")
            return None

        second = pool.submit(other)
        assert started.wait(5)
        assert not second.done()
        runtime.release.set()
        assert first.result(timeout=10).status_code == 200
        result = second.result(timeout=10)
        event.remove(customer_engine, "before_cursor_execute", attempting_lock)
        if competitor == "callback":
            assert result.status_code == 422
        assert runtime.token_calls == 1
    with Session(customer_engine) as db:
        expected = 1 if competitor == "callback" else 0
        assert db.scalar(select(func.count()).select_from(ShopifyConnection)) == expected


def test_customer_measurement_store_is_bound_and_purged(
    customer_engine: Engine, configured: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.commerce.ledger import MEASUREMENT_SCOPES
    from app.commerce.models import CommerceStore

    runtime = FixtureShopify()
    runtime.scope = ",".join(sorted(MEASUREMENT_SCOPES))
    original = runtime.shop

    def metadata(shop: str, token: str) -> dict[str, Any]:
        result = original(shop, token)
        result["shop"]["id"] = "gid://shopify/Shop/919"
        return result

    monkeypatch.setattr(runtime, "shop", metadata)
    monkeypatch.setattr(settings, "shopify_measurement_enabled", True)
    owner, _, wid, _ = clients(customer_engine, runtime)
    result = finish(owner, begin(owner, wid))
    assert result.status_code == 200, result.text
    store_id = result.json()["commerce_store_id"]
    assert store_id
    with Session(customer_engine) as db:
        store = db.get(CommerceStore, store_id)
        assert store is not None and store.workspace_id == wid
    assert (
        owner.delete(
            f"/api/customer/v1/workspaces/{wid}/shopify", headers=headers(owner)
        ).status_code
        == 204
    )
    with Session(customer_engine) as db:
        store = db.get(CommerceStore, store_id)
        assert store is not None and store.status == "revoked"
        assert store.covered_from is None and store.last_sync_at is None


def test_postgres_import_skips_workspace_callback_fence(
    customer_engine: Engine, configured: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    if customer_engine.dialect.name != "postgresql":
        pytest.skip("row lock ordering is PostgreSQL-specific")
    from app.shopify import sync
    from app.workspaces.models import Workspace

    monkeypatch.setattr(sync, "syncing_allowed", lambda db, wid: True)
    runtime = FixtureShopify()
    owner, _, wid, _ = clients(customer_engine, runtime)
    assert finish(owner, begin(owner, wid)).status_code == 200
    with Session(customer_engine) as locked:
        locked.scalar(select(Workspace).where(Workspace.id == wid).with_for_update())
        with Session(customer_engine) as worker:
            result = sync.ShopifySyncService(worker, settings, runtime).page(wid)
            assert result == {"status": "not_connected_or_busy", "imported": 0}
    assert runtime.requests == []


def test_postgres_privacy_callback_share_workspace_fence(
    customer_engine: Engine, configured: None
) -> None:
    if customer_engine.dialect.name != "postgresql":
        pytest.skip("row lock ordering is PostgreSQL-specific")
    from datetime import UTC, datetime

    from app.shopify.privacy import process_event

    runtime = FixtureShopify()
    owner, _, wid, _ = clients(customer_engine, runtime)
    assert finish(owner, begin(owner, wid)).status_code == 200
    query = begin(owner, wid)
    runtime.entered.clear()
    runtime.pause = True
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(finish, owner, query)
        assert runtime.entered.wait(5)
        reached = Event()
        first_lock: list[str] = []

        def attempting_lock(
            conn: Any, cursor: Any, statement: str, parameters: Any, context: Any, many: bool
        ) -> None:
            if "FOR UPDATE" in statement and not first_lock:
                first_lock.append(statement)
                reached.set()

        event.listen(customer_engine, "before_cursor_execute", attempting_lock)

        def erase() -> None:
            with Session(customer_engine) as db:
                process_event(db, settings, "app/uninstalled", SHOP, {}, datetime.now(UTC))

        second = pool.submit(erase)
        try:
            assert reached.wait(5)
            assert "FROM workspaces" in first_lock[0]
            assert not second.done()
        finally:
            runtime.release.set()
            event.remove(customer_engine, "before_cursor_execute", attempting_lock)
        assert first.result(timeout=10).status_code == 200
        second.result(timeout=10)
    with Session(customer_engine) as db:
        assert db.scalar(select(func.count()).select_from(ShopifyConnection)) == 0
        assert db.scalar(select(func.count()).select_from(ShopifyOAuthState)) == 0


def test_postgres_expiry_purge_waits_without_holding_measurement_store(
    customer_engine: Engine, configured: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    if customer_engine.dialect.name != "postgresql":
        pytest.skip("row lock ordering is PostgreSQL-specific")
    from datetime import UTC, datetime, timedelta

    from app.shopify.privacy import purge_expired_facts

    runtime = FixtureShopify()
    original = runtime.shop

    def metadata(shop: str, token: str) -> dict[str, Any]:
        result = original(shop, token)
        result["shop"]["id"] = "gid://shopify/Shop/919"
        return result

    monkeypatch.setattr(runtime, "shop", metadata)
    owner, _, wid, _ = clients(customer_engine, runtime)
    assert finish(owner, begin(owner, wid)).json()["commerce_store_id"]
    query = begin(owner, wid)
    # The purge's as-of time crosses nonce expiry while the callback is in exchange.
    with Session(customer_engine) as db:
        pending = db.scalar(select(ShopifyOAuthState))
        assert pending is not None
        pending.expires_at = datetime.now(UTC) + timedelta(minutes=1)
        db.commit()
    runtime.entered.clear()
    runtime.pause = True
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(finish, owner, query)
        assert runtime.entered.wait(5)
        reached = Event()
        actions: list[str] = []

        def attempting_purge(
            conn: Any, cursor: Any, statement: str, parameters: Any, context: Any, many: bool
        ) -> None:
            actions.append(statement)
            if statement.startswith("DELETE FROM shopify_oauth_states"):
                reached.set()

        event.listen(customer_engine, "before_cursor_execute", attempting_purge)
        second = pool.submit(
            purge_expired_facts, customer_engine, now=datetime.now(UTC) + timedelta(minutes=2)
        )
        try:
            assert reached.wait(5)
            assert not any("FROM commerce_stores" in sql for sql in actions)
            assert not second.done()
        finally:
            event.remove(customer_engine, "before_cursor_execute", attempting_purge)
            runtime.release.set()
        assert first.result(timeout=10).status_code == 200
        second.result(timeout=10)
    with Session(customer_engine) as db:
        assert db.scalar(select(func.count()).select_from(ShopifyConnection)) == 1
        assert db.scalar(select(func.count()).select_from(ShopifyOAuthState)) == 0


def test_postgres_login_email_refresh_and_rotation_precede_callback(
    customer_engine: Engine, configured: None
) -> None:
    if customer_engine.dialect.name != "postgresql":
        pytest.skip("row lock ordering is PostgreSQL-specific")
    runtime = FixtureShopify()
    owner, _, wid, provider = clients(customer_engine, runtime)
    query = begin(owner, wid)
    rotating = TestClient(owner.app, base_url=ORIGIN)
    rotating.cookies.update(owner.cookies)
    provider.email = "updated-contact@example.test"
    user_updated, callback_waiting, proceed = Event(), Event(), Event()

    def after_sql(
        conn: Any, cursor: Any, statement: str, parameters: Any, context: Any, many: bool
    ) -> None:
        if statement.startswith("UPDATE customer_users SET email"):
            user_updated.set()
            assert proceed.wait(10)

    def before_sql(
        conn: Any, cursor: Any, statement: str, parameters: Any, context: Any, many: bool
    ) -> None:
        if "FROM customer_users" in statement and "FOR UPDATE" in statement:
            callback_waiting.set()

    event.listen(customer_engine, "after_cursor_execute", after_sql)
    event.listen(customer_engine, "before_cursor_execute", before_sql)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            refreshed = pool.submit(login, rotating, "owner:rotated-token")
            assert user_updated.wait(5)
            callback = pool.submit(finish, owner, query)
            try:
                assert callback_waiting.wait(5)
            finally:
                proceed.set()
            assert refreshed.result(timeout=10)
            assert callback.result(timeout=10).status_code == 401
    finally:
        proceed.set()
        event.remove(customer_engine, "after_cursor_execute", after_sql)
        event.remove(customer_engine, "before_cursor_execute", before_sql)
    assert runtime.token_calls == 0
    with Session(customer_engine) as db:
        session = db.get(CustomerSession, digest(owner.cookies[SESSION_COOKIE]))
        assert session is not None and session.revoked_at is not None
        assert db.scalar(select(func.count()).select_from(ShopifyConnection)) == 0
