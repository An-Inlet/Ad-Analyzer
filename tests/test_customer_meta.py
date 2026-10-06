"""Customer Meta receipts and current actor fences; all providers are offline fixtures."""

from collections.abc import Generator
from datetime import UTC, datetime
from typing import Any
from urllib.parse import parse_qs, urlsplit

import pytest
from app.api import customer_meta as api
from app.api.customer import router as customer_router
from app.customers.access import CSRF_COOKIE
from app.customers.identity import get_identity_provider
from app.customers.models import CustomerMembership, CustomerSession
from app.database.session import get_db
from app.meta import customer as flow
from app.meta.models import MetaConnection, MetaOAuthState, MetaPendingGrant
from app.meta.security import MetaError
from app.meta.service import ConnectionService
from app.settings import Settings, settings
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from tests.test_customer_identity import ORIGIN, FakeProvider, login
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_google_customer_connections import setup
from tests.test_meta_connection import FakeMeta
from tests.test_meta_connection import configuration as configuration


@pytest.fixture()
def configured(configuration: Settings, monkeypatch: pytest.MonkeyPatch) -> None:
    for name in Settings.model_fields:
        if name.startswith("meta_"):
            monkeypatch.setattr(settings, name, getattr(configuration, name))
    monkeypatch.setattr(settings, "meta_customer_enabled", True)
    monkeypatch.setattr(settings, "customer_app_origin", ORIGIN)


class FixtureMeta(FakeMeta):
    after: Any = None

    def token(
        self, *, code: str | None = None, exchange_token: str | None = None
    ) -> dict[str, Any]:
        result = super().token(code=code, exchange_token=exchange_token)
        if self.after:
            self.after()
        return result


def clients(engine: Engine, runtime: FixtureMeta) -> tuple[TestClient, int, str]:
    application = FastAPI()
    application.include_router(customer_router)
    application.include_router(api.router)

    def database() -> Generator[Session, None, None]:
        with Session(engine) as db:
            yield db

    application.dependency_overrides[get_db] = database
    application.dependency_overrides[get_identity_provider] = lambda: FakeProvider()
    application.dependency_overrides[api.get_customer_meta_client] = lambda: runtime
    owner = TestClient(application, base_url=ORIGIN)
    uid = login(owner, "meta-owner:1")
    with Session(engine) as db:
        wid, _ = setup(db, "meta-customer")
        db.add(CustomerMembership(user_id=uid, workspace_id=wid, role="owner"))
        db.commit()
    return owner, wid, uid


def headers(owner: TestClient) -> dict[str, str]:
    return {"Origin": ORIGIN, "X-CSRF-Token": owner.cookies[CSRF_COOKIE]}


def begin(owner: TestClient, wid: int) -> str:
    response = owner.post(
        f"/api/customer/v1/workspaces/{wid}/meta/authorize", headers=headers(owner)
    )
    assert response.status_code == 200
    return str(parse_qs(urlsplit(response.json()["authorization_url"]).query)["state"][0])


@pytest.mark.parametrize("interruption", ["retry", "session", "role", "failure"])
def test_exchange_never_replays_or_overwrites_newer_flow(
    customer_engine: Engine, configured: None, interruption: str
) -> None:
    runtime = FixtureMeta(api.configuration())
    owner, wid, uid = clients(customer_engine, runtime)
    nonce = begin(owner, wid)
    replacements: list[str] = []

    def interrupt() -> None:
        runtime.after = None
        if interruption == "retry":
            replacements.append(begin(owner, wid))
        elif interruption == "failure":
            raise MetaError("meta_query_failed")
        else:
            with Session(customer_engine) as db:
                if interruption == "session":
                    row = db.scalar(select(CustomerSession).where(CustomerSession.user_id == uid))
                    assert row is not None
                    row.revoked_at = 1
                else:
                    member = db.get(CustomerMembership, (uid, wid))
                    assert member is not None
                    member.role = "viewer"
                db.commit()

    runtime.after = interrupt
    response = owner.post(
        "/api/customer/v1/meta/callback",
        json={"state": nonce, "code": "fixture"},
        headers=headers(owner),
    )
    assert response.status_code in {401, 403, 409, 422}
    with Session(customer_engine) as db:
        assert db.scalar(select(func.count()).select_from(MetaPendingGrant)) == 0
        state = db.scalar(select(MetaOAuthState))
        assert state is not None and state.phase == (
            "pending" if interruption == "retry" else "failed"
        )
    before = runtime.token_calls
    owner.post(
        "/api/customer/v1/meta/callback",
        json={"state": nonce, "code": "fixture"},
        headers=headers(owner),
    )
    assert runtime.token_calls == before
    if replacements:
        assert (
            owner.post(
                "/api/customer/v1/meta/callback",
                json={"state": replacements[0], "code": "new"},
                headers=headers(owner),
            ).status_code
            == 200
        )


def test_customer_requires_nonce_bound_grant_operator_legacy_still_works(
    customer_engine: Engine, configured: None
) -> None:
    runtime = FixtureMeta(api.configuration())
    owner, wid, _ = clients(customer_engine, runtime)
    nonce = begin(owner, wid)
    assert (
        owner.post(
            "/api/customer/v1/meta/callback",
            json={"state": nonce, "code": "fixture"},
            headers=headers(owner),
        ).status_code
        == 200
    )
    with Session(customer_engine) as db:
        grant = db.scalar(select(MetaPendingGrant))
        assert grant is not None
        actor_session = db.scalar(select(CustomerSession).where(CustomerSession.digest != ""))
        # Read the exact actor from the receipt, without constructing another grant.
        assert actor_session is not None
        grant.oauth_state_digest = None
        db.commit()
    response = owner.post(
        f"/api/customer/v1/workspaces/{wid}/meta/select",
        headers=headers(owner),
        json={"state": nonce, "external_account_id": "101", "conversion_action_type": "purchase"},
    )
    assert response.status_code == 409
    with Session(customer_engine) as db:
        assert db.scalar(select(func.count()).select_from(MetaConnection)) == 0
        # Legacy operator grants are intentionally nullable and still selected through
        # the existing service signature. Customer flow cannot use them.
        service = ConnectionService(db, api.configuration(), runtime)
        actor = "legacy-operator"
        service.begin(wid, actor, datetime.now(UTC), customer=True)
        state = db.scalar(select(MetaOAuthState))
        assert state is not None
        service.finish(state, "legacy", "admin", datetime.now(UTC))
        legacy = service.grant(wid, actor, datetime.now(UTC))
        assert legacy is not None and legacy.oauth_state_digest is None
        with pytest.raises(MetaError):
            flow.bound_grant(service, wid, actor, nonce, datetime.now(UTC))
        row = service.select_account(wid, actor, "101", "", "admin", datetime.now(UTC))
        assert row.status == "connected" and row.conversion_action_type is None


@pytest.mark.parametrize("stage", ["second_token", "permissions", "accounts"])
def test_old_exchange_cannot_replace_completed_retry(
    customer_engine: Engine, configured: None, stage: str
) -> None:
    from app.meta.security import Vault

    class Interleaved(FixtureMeta):
        hook: Any = None

        def fire(self, current: str) -> None:
            if self.hook and current == stage:
                hook, self.hook = self.hook, None
                hook()

        def token(
            self, *, code: str | None = None, exchange_token: str | None = None
        ) -> dict[str, Any]:
            result = super().token(code=code, exchange_token=exchange_token)
            if exchange_token:
                self.fire("second_token")
            return result

        def permissions(self, token: str) -> dict[str, Any]:
            result = super().permissions(token)
            self.fire("permissions")
            return result

        def accounts(self, token: str, cursor: str | None = None) -> dict[str, Any]:
            result = super().accounts(token, cursor)
            self.fire("accounts")
            return result

    runtime = Interleaved(api.configuration())
    owner, wid, _ = clients(customer_engine, runtime)
    nonce = begin(owner, wid)
    latest: list[str] = []

    def retry() -> None:
        latest.append(begin(owner, wid))
        response = owner.post(
            "/api/customer/v1/meta/callback",
            headers=headers(owner),
            json={"state": latest[0], "code": "new"},
        )
        assert response.status_code == 200

    runtime.hook = retry
    response = owner.post(
        "/api/customer/v1/meta/callback",
        headers=headers(owner),
        json={"state": nonce, "code": "old"},
    )
    assert response.status_code == 409
    with Session(customer_engine) as db:
        grant = db.scalar(select(MetaPendingGrant))
        assert grant is not None and grant.oauth_state_digest == Vault(settings).digest(
            "state", latest[0]
        )
        assert db.scalar(select(func.count()).select_from(MetaPendingGrant)) == 1


@pytest.mark.parametrize("operation", ["select", "accounts"])
def test_current_actor_rechecked_after_account_io(
    customer_engine: Engine, configured: None, operation: str
) -> None:
    from tests.test_meta_connection import metadata, page

    class Interleaved(FixtureMeta):
        hook: Any = None

        def account(self, account_id: str, token: str) -> dict[str, Any]:
            result = super().account(account_id, token)
            if self.hook:
                self.hook()
            return result

        def accounts(self, token: str, cursor: str | None = None) -> dict[str, Any]:
            if cursor and self.hook:
                self.hook()
            return page(metadata("101"), cursor="next" if not cursor else None)

    runtime = Interleaved(api.configuration())
    owner, wid, uid = clients(customer_engine, runtime)
    nonce = begin(owner, wid)
    assert (
        owner.post(
            "/api/customer/v1/meta/callback",
            headers=headers(owner),
            json={"state": nonce, "code": "fixture"},
        ).status_code
        == 200
    )

    def revoke() -> None:
        with Session(customer_engine) as db:
            member = db.get(CustomerMembership, (uid, wid))
            assert member is not None
            member.role = "viewer"
            db.commit()

    runtime.hook = revoke
    body = {"state": nonce}
    if operation == "select":
        body.update(external_account_id="101", conversion_action_type="purchase")
    response = owner.post(
        f"/api/customer/v1/workspaces/{wid}/meta/{operation}", headers=headers(owner), json=body
    )
    assert response.status_code == 403
    with Session(customer_engine) as db:
        assert db.scalar(select(func.count()).select_from(MetaConnection)) == 0
        grant = db.scalar(select(MetaPendingGrant))
        assert grant is not None and grant.cursor == "next"


def test_customer_setup_scope_selection_reconnect_and_local_disconnect(
    customer_engine: Engine, configured: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime = FixtureMeta(api.configuration())
    owner, wid, uid = clients(customer_engine, runtime)
    root = f"/api/customer/v1/workspaces/{wid}/meta"
    assert owner.get(root + "/setup").json()["enabled"] is True
    assert owner.post(root + "/authorize").status_code == 403
    assert owner.get(f"/api/customer/v1/workspaces/{wid + 999}/meta").status_code == 404
    for generation in (1, 2):
        nonce = begin(owner, wid)
        callback = owner.post(
            "/api/customer/v1/meta/callback",
            headers=headers(owner),
            json={"state": nonce, "code": "fixture"},
        )
        assert callback.status_code == 200
        assert (
            owner.post(
                root + "/select",
                headers=headers(owner),
                json={
                    "state": "x" * 43,
                    "external_account_id": "101",
                    "conversion_action_type": "purchase",
                },
            ).status_code
            == 409
        )
        assert (
            owner.post(
                root + "/select",
                headers=headers(owner),
                json={
                    "state": nonce,
                    "external_account_id": "999",
                    "conversion_action_type": "purchase",
                },
            ).status_code
            == 422
        )
        response = owner.post(
            root + "/select",
            headers=headers(owner),
            json={
                "state": nonce,
                "external_account_id": "101",
                "conversion_action_type": "purchase",
            },
        )
        assert response.status_code == 200 and response.json()["generation"] == generation
    assert owner.get(root).json()["connected"] is True
    with Session(customer_engine) as db:
        member = db.get(CustomerMembership, (uid, wid))
        assert member is not None
        member.role = "viewer"
        db.commit()
    assert owner.delete(root, headers=headers(owner)).status_code == 403
    with Session(customer_engine) as db:
        member = db.get(CustomerMembership, (uid, wid))
        assert member is not None
        member.role = "owner"
        db.commit()
    monkeypatch.setattr(settings, "meta_customer_enabled", False)
    assert owner.get(root + "/setup").json()["enabled"] is False
    assert owner.post(root + "/authorize", headers=headers(owner)).status_code == 503
    calls = runtime.token_calls
    assert owner.delete(root, headers=headers(owner)).status_code == 204
    assert owner.get(root).json()["connected"] is False
    assert runtime.token_calls == calls
