"""Actual HTTPS/CSRF, persisted vaults and all three fixed HTTP collectors."""

import json
import time
from datetime import timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest
from app.api import customer_account_diagnostics as api
from app.automation.models import PlatformAutomationControl
from app.collectors import account_diagnostics
from app.customers.models import CustomerMembership, CustomerSession, CustomerUser
from app.google_connections.models import GoogleCustomerConnection
from app.meta.models import MetaConnection
from app.publication import execution_mandates
from app.settings import Settings, settings
from app.sources.models import SourceConnection
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from tests.test_commerce_measurement import NOW
from tests.test_customer_identity import ISSUER, FakeProvider, login
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_customer_optimization_api import headers
from tests.test_google_native_inventory import key, payloads
from tests.test_meta_native_inventory import PRIVATE
from tests.test_meta_native_inventory import Server as MetaServer
from tests.test_native_diagnostic_assembly import seed
from tests.test_shopify_sales import configuration as configuration
from tests.test_tiktok_native_inventory import Server as TikTokServer


@pytest.mark.parametrize("provider", ["google_ads", "meta_ads", "tiktok_ads"])
@pytest.mark.parametrize(
    "change",
    [
        None,
        "disabled",
        "session",
        "generation",
        "role",
        "oauth_session",
        "control",
        "billing",
        "expired",
        "missing_credentials",
    ],
)
def test_real_account_diagnostic_api(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    replicas: tuple[TestClient, TestClient, FakeProvider],
    provider: str,
    change: str | None,
) -> None:
    for attr in (
        "google_customer_encryption_key",
        "meta_token_encryption_key",
        "source_token_encryption_key",
    ):
        monkeypatch.setattr(settings, attr, SecretStr(Fernet.generate_key().decode()))
    monkeypatch.setattr(settings, "google_customer_client_id", "synthetic-client")
    monkeypatch.setattr(settings, "google_customer_client_secret", SecretStr("synthetic-secret"))
    monkeypatch.setattr(settings, "meta_client_secret", SecretStr("synthetic-app-secret"))
    monkeypatch.setattr(settings, "customer_native_diagnostics_enabled", change != "disabled")
    request = seed(customer_engine, configuration, tmp_path, provider)
    with Session(customer_engine) as db:
        user = db.get(CustomerUser, request.actor)
        assert user
        user.issuer, user.subject = ISSUER, "diagnostic-owner"
        db.commit()
    alice, bob, _ = replicas
    for client in (alice, bob):
        client.app.include_router(api.router)  # type: ignore[attr-defined]
    assert login(alice, "diagnostic-owner:1") == request.actor
    login(bob, "other:1")
    monkeypatch.setattr(api, "utc_now", lambda: NOW)

    # Account observations must not consult or create a spending consent.
    def forbidden(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("account diagnostics must not require a mandate")

    monkeypatch.setattr(execution_mandates, "checked", forbidden)
    calls: list[str] = []
    constructed: list[bool] = []
    closed: list[bool] = []
    server = MetaServer() if provider == "meta_ads" else TikTokServer()

    def revoke() -> None:
        with Session(customer_engine) as db:
            if change in {"session", "oauth_session"}:
                for session in db.scalars(
                    select(CustomerSession).where(CustomerSession.user_id == request.actor)
                ):
                    session.revoked_at = int(time.time())
            elif change == "control":
                db.merge(
                    PlatformAutomationControl(
                        key="all_data_syncs", enabled=False, updated_by="test"
                    )
                )
            elif change == "billing":
                monkeypatch.setattr(settings, "billing_required", True)
            elif change == "expired":
                for session in db.scalars(
                    select(CustomerSession).where(CustomerSession.user_id == request.actor)
                ):
                    session.expires_at = int(time.time()) - 1
            elif change == "missing_credentials":
                if provider == "google_ads":
                    row = db.scalar(
                        select(GoogleCustomerConnection).where(
                            GoogleCustomerConnection.account_id == request.account_id
                        )
                    )
                    assert row
                    row.encrypted_grant = None
                elif provider == "meta_ads":
                    meta = db.scalar(
                        select(MetaConnection).where(
                            MetaConnection.account_id == request.account_id
                        )
                    )
                    assert meta
                    meta.encrypted_credentials = ""
                else:
                    source = db.scalar(
                        select(SourceConnection).where(
                            SourceConnection.account_id == request.account_id
                        )
                    )
                    assert source
                    source.encrypted_grant = None
            elif change == "role":
                member = db.get(CustomerMembership, (request.actor, request.workspace_id))
                assert member
                member.role = "viewer"
            elif change == "generation":
                model: Any = {
                    "google_ads": GoogleCustomerConnection,
                    "meta_ads": MetaConnection,
                    "tiktok_ads": SourceConnection,
                }[provider]
                native = db.scalar(select(model).where(model.account_id == request.account_id))
                assert native
                native.generation += 1
            db.commit()

    def wire(req: httpx.Request) -> httpx.Response:
        calls.append(str(req.url.host))
        if req.url.host == "oauth2.googleapis.com":
            if change == "oauth_session":
                revoke()
            return httpx.Response(
                200, json=dict(access_token=PRIVATE, token_type="Bearer", expires_in=3600)
            )
        if change in {
            "session",
            "generation",
            "role",
            "oauth_session",
            "control",
            "billing",
            "expired",
            "missing_credentials",
        }:
            revoke()
        if provider == "google_ads":
            data = payloads()
            data["customer"][0]["customer"]["timeZone"] = "UTC"
            return httpx.Response(
                200, json={"results": data[key(json.loads(req.content)["query"])]}
            )
        return server(req)

    class Transport(httpx.MockTransport):
        def close(self) -> None:
            closed.append(True)
            super().close()

    def transport() -> httpx.BaseTransport:
        constructed.append(True)
        return Transport(wire)

    monkeypatch.setattr(account_diagnostics, "diagnostic_transport", transport)
    path = f"/api/customer/v1/workspaces/{request.workspace_id}/execution/diagnostics"
    payload = dict(
        account_id=request.account_id,
        starts_at=(NOW - timedelta(days=1)).isoformat(),
        ends_at=NOW.isoformat(),
    )
    assert alice.post(path, json=payload).status_code == 403
    assert bob.post(path, json=payload, headers=headers(bob)).status_code in {403, 404}
    assert not calls and not constructed
    response = alice.post(path, json=payload, headers=headers(alice))
    if change == "disabled":
        assert response.status_code == 503
        assert not calls and not constructed
    elif change:
        assert response.status_code in (
            {401, 402, 403, 409, 503} if change == "billing" else {401, 402, 403, 409}
        ), response.text
        assert len([c for c in calls if c != "oauth2.googleapis.com"]) <= 1
        assert len(closed) == 1
    else:
        assert response.status_code == 200, response.text
        result = response.json()
        assert result["optimization_available"] is False
        assert result["cap_semantics"] == "unqualified"
        assert result["unreported_upper_micros"] is None
        assert result["inventory_counts"]
        assert response.headers["cache-control"] == "no-store"
        assert len(calls) >= 3 and len(closed) == 1
        for forbidden_text in (
            PRIVATE,
            "synthetic-refresh",
            "synthetic-secret",
            "mandate",
            "native_integer",
            "resource_name",
        ):
            assert forbidden_text not in response.text
        # No future/oversized periods or browser authority, and no subsequent HTTP.
        before = len(calls)
        for extra in (
            {"actor": request.actor},
            {"ends_at": (NOW + timedelta(days=1)).isoformat()},
            {"starts_at": (NOW - timedelta(days=367)).isoformat()},
        ):
            assert (
                alice.post(path, json={**payload, **extra}, headers=headers(alice)).status_code
                == 422
            )
        assert len(calls) == before
