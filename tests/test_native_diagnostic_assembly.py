"""Genuine retained mandates with current vault/HTTP readers, offline only."""

import json
import time
from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest
from app import advertising_capabilities
from app.ads.models import AdvertisingAccount
from app.collectors.meta_native_inventory import MetaNativeInventoryUnavailable
from app.collectors.native_diagnostics import NativeDiagnosticRequest, NativeDiagnosticService
from app.collectors.tiktok_native_inventory import TikTokNativeInventoryUnavailable
from app.customers.access import CustomerPrincipal
from app.customers.models import CustomerMembership, CustomerSession, CustomerUser
from app.google_connections.http import GoogleHTTPRead
from app.google_connections.models import GoogleCustomerConnection
from app.google_connections.security import Vault as GoogleVault
from app.meta.models import MetaConnection
from app.meta.security import Vault as MetaVault
from app.publication import execution_mandates
from app.publication.customer_authority import bind_authority
from app.publication.execution_contracts import ProviderMandateBinding
from app.publication.execution_models import (
    ProviderExecutionAttempt,
    ProviderExecutionConsent,
    ProviderExecutionReceipt,
    ProviderExecutionResponse,
    ProviderExposureReservation,
)
from app.settings import settings
from app.sources.models import SourceConnection
from app.sources.security import SourceVault
from cryptography.fernet import Fernet
from fastapi import HTTPException
from pydantic import SecretStr
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from tests.retired_producer_fixture import (
    NativeDiagnosticProvider,
    RetainedNativeDiagnosticIds,
    retained_native_diagnostic_fixture,
)
from tests.test_commerce_measurement import NOW
from tests.test_customer_identity import FakeProvider
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_google_native_inventory import key, payloads
from tests.test_meta_native_inventory import PRIVATE
from tests.test_meta_native_inventory import Server as MetaServer
from tests.test_tiktok_native_inventory import Server as TikTokServer


def assert_read_only(engine: Engine) -> None:
    with pytest.raises(advertising_capabilities.AdvertisingWritesDisabled):
        advertising_capabilities.require_advertising_write()
    with Session(engine) as db:
        for model in (
            ProviderExecutionAttempt, ProviderExecutionResponse,
            ProviderExecutionReceipt, ProviderExposureReservation,
        ):
            assert db.scalar(select(func.count()).select_from(model)) == 0


@pytest.fixture
def native_records(
    customer_engine: Engine, tmp_path: Path, provider: NativeDiagnosticProvider,
) -> Iterator[tuple[Engine, RetainedNativeDiagnosticIds]]:
    assert_read_only(customer_engine)
    with retained_native_diagnostic_fixture(
        customer_engine, tmp_path / "native-records", provider
    ) as result:
        engine, _ = result
        assert_read_only(engine)
        yield result
        assert_read_only(engine)


def seed(
    engine: Engine, ids: RetainedNativeDiagnosticIds, provider: NativeDiagnosticProvider,
) -> NativeDiagnosticRequest:
    with Session(engine) as db:
        wid, actor = ids.workspace_id, ids.actor_id
        ledger, mandate = execution_mandates.owned(db, wid, ids.mandate_id)
        policy = execution_mandates.policy(db, mandate)
        consent = db.get(ProviderExecutionConsent, ids.consent_id)
        account = db.get(AdvertisingAccount, ids.account_id)
        assert account is not None and account.workspace_id == wid and account.platform == provider
        assert consent is not None and consent.workspace_id == wid and consent.actor == actor
        assert consent.mandate_id == mandate.id and consent.revision == mandate.revision
        assert consent.policy_digest == policy.digest() == ids.policy_digest
        assert ledger.id == mandate.ledger_id == ids.ledger_id and ledger.workspace_id == wid
        assert policy.environment == ledger.environment == ids.environment
        assert mandate.revision == ids.revision and mandate.state == "active"
        assert any(scope.account.account_id == ids.account_id for scope in policy.accounts)
        binding = ProviderMandateBinding(
            mandate_id=mandate.id, revision=mandate.revision, consent_id=consent.id,
            policy_digest=policy.digest(), ledger_id=ledger.id, environment=policy.environment,
        )
        execution_mandates.checked(db, wid, binding, actor, lambda: NOW)
        account.currency_code, account.time_zone = "USD", "UTC"
        bundle = dict(access_token=PRIVATE, expires_at=(NOW + timedelta(hours=1)).isoformat())
        if provider == "google_ads":
            row = db.scalar(
                select(GoogleCustomerConnection).where(
                    GoogleCustomerConnection.account_id == ids.account_id
                )
            )
            assert row is not None
            row.encrypted_grant = GoogleVault().seal(wid, row.id, "synthetic-refresh")
        elif provider == "meta_ads":
            meta = db.scalar(
                select(MetaConnection).where(MetaConnection.account_id == ids.account_id)
            )
            assert meta is not None
            meta.encrypted_credentials = MetaVault(settings).seal(
                wid, meta.external_account_id, bundle
            )
        else:
            source = db.scalar(
                select(SourceConnection).where(
                    SourceConnection.account_id == ids.account_id
                )
            )
            assert source is not None
            source.encrypted_grant = SourceVault().seal(wid, source.provider, source.id, bundle)
        db.commit()
    return NativeDiagnosticRequest(
        workspace_id=wid, actor=actor, mandate=binding, account_id=ids.account_id
    )


@pytest.mark.parametrize("provider", ["google_ads", "meta_ads", "tiktok_ads"])
@pytest.mark.parametrize(
    "change", [None, "generation", "session", "account", "oauth_session", "role"]
)
def test_current_owned_vault_assembly(
    native_records: tuple[Engine, RetainedNativeDiagnosticIds],
    monkeypatch: pytest.MonkeyPatch,
    provider: NativeDiagnosticProvider,
    change: str | None,
) -> None:
    engine, ids = native_records
    for attr in (
        "google_customer_encryption_key",
        "meta_token_encryption_key",
        "source_token_encryption_key",
    ):
        monkeypatch.setattr(settings, attr, SecretStr(Fernet.generate_key().decode()))
    monkeypatch.setattr(settings, "meta_client_secret", SecretStr("synthetic-app-secret"))
    request = seed(engine, ids, provider)
    identity = FakeProvider()
    with Session(engine) as db:
        user = db.get(CustomerUser, request.actor)
        assert user is not None
        user.issuer = identity.issuer
        session = CustomerSession(
            digest="e" * 64,
            user_id=user.id,
            csrf_digest="f" * 64,
            created_at=int(time.time()),
            expires_at=int(time.time()) + 3600,
            authenticated_at=int(time.time()),
        )
        db.add(session)
        db.commit()
        authorize = bind_authority(CustomerPrincipal(user, session), identity)
    calls = 0
    oauth_calls = 0
    server = MetaServer() if provider == "meta_ads" else TikTokServer()

    def revoke() -> None:
        with Session(engine) as other:
            if change in {"session", "oauth_session"}:
                session = other.get(CustomerSession, "e" * 64)
                assert session is not None
                session.revoked_at = int(time.time())
            elif change == "role":
                membership = other.get(CustomerMembership, (request.actor, request.workspace_id))
                assert membership is not None
                membership.role = "viewer"
            else:
                model: Any = {
                    "google_ads": GoogleCustomerConnection,
                    "meta_ads": MetaConnection,
                    "tiktok_ads": SourceConnection,
                }[provider]
                native = other.scalar(select(model).where(model.account_id == request.account_id))
                assert native is not None
                if change == "generation":
                    native.generation += 1
                elif change == "account":
                    if provider == "tiktok_ads":
                        native.external_id = "999"
                    else:
                        native.external_account_id = "999"
            other.commit()

    def oauth(req: httpx.Request) -> httpx.Response:
        nonlocal oauth_calls
        oauth_calls += 1
        assert req.url.host == "oauth2.googleapis.com" and req.method == "POST"
        if change == "oauth_session":
            revoke()
        return httpx.Response(
            200, json=dict(access_token=PRIVATE, token_type="Bearer", expires_in=3600)
        )

    def wire(req: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if change and not (change == "oauth_session" and provider == "google_ads"):
            revoke()
        if provider == "google_ads":
            data = payloads()
            data["customer"][0]["customer"]["timeZone"] = "UTC"
            return httpx.Response(
                200, json={"results": data[key(json.loads(req.content)["query"])]}
            )
        return server(req)

    service = NativeDiagnosticService(
        lambda: Session(engine),
        authorize,
        transports={provider: httpx.MockTransport(wire)},
        clock=lambda: NOW,
        google_oauth=GoogleHTTPRead(
            "synthetic-client",
            SecretStr("synthetic-secret"),
            None,
            "v25",
            transport=httpx.MockTransport(oauth),
        ),
    )
    if change:
        with pytest.raises(
            (HTTPException, MetaNativeInventoryUnavailable, TikTokNativeInventoryUnavailable)
        ):
            service.read(request, NOW)
        assert calls <= 1
    else:
        result = service.read(request, NOW)
        assert result.request.account.account.account_id == request.account_id
        assert result.unreported_upper_micros is None
        assert result.unchanged_future_upper_micros is None
        assert result.proposed_owner_upper_micros is None
        assert PRIVATE not in result.model_dump_json()
        assert "synthetic-refresh" not in result.model_dump_json()
        assert calls >= 3
    assert oauth_calls == (1 if provider == "google_ads" else 0)


@pytest.mark.parametrize("provider", ["google_ads", "meta_ads", "tiktok_ads"])
@pytest.mark.parametrize(
    "failure",
    [
        "expired",
        "foreign_selection",
        "mandate",
        "currency",
        "missing_transport",
        "wrong_vault_context",
    ],
)
def test_invalid_current_context_never_emits_inventory(
    native_records: tuple[Engine, RetainedNativeDiagnosticIds],
    monkeypatch: pytest.MonkeyPatch,
    provider: NativeDiagnosticProvider,
    failure: str,
) -> None:
    engine, ids = native_records
    for attr in (
        "google_customer_encryption_key",
        "meta_token_encryption_key",
        "source_token_encryption_key",
    ):
        monkeypatch.setattr(settings, attr, SecretStr(Fernet.generate_key().decode()))
    request = seed(engine, ids, provider)
    if failure == "foreign_selection":
        request = request.model_copy(update={"account_id": request.account_id + 1000})
    if failure == "mandate":
        request = request.model_copy(
            update={"mandate": request.mandate.model_copy(update={"revision": 999})}
        )
    with Session(engine) as db:
        if failure == "currency":
            account = db.get(AdvertisingAccount, request.account_id)
            assert account is not None
            account.currency_code = "EUR"
        if failure in {"expired", "wrong_vault_context"}:
            bundle = dict(access_token=PRIVATE, expires_at=(NOW - timedelta(seconds=1)).isoformat())
            wid = request.workspace_id + (1 if failure == "wrong_vault_context" else 0)
            if provider == "google_ads":
                g = db.scalar(
                    select(GoogleCustomerConnection).where(
                        GoogleCustomerConnection.account_id == request.account_id
                    )
                )
                assert g is not None
                g.encrypted_grant = GoogleVault().seal(wid, g.id, "synthetic-refresh")
            elif provider == "meta_ads":
                m = db.scalar(
                    select(MetaConnection).where(MetaConnection.account_id == request.account_id)
                )
                assert m is not None
                m.encrypted_credentials = MetaVault(settings).seal(
                    wid, m.external_account_id, bundle
                )
            else:
                t = db.scalar(
                    select(SourceConnection).where(
                        SourceConnection.account_id == request.account_id
                    )
                )
                assert t is not None
                t.encrypted_grant = SourceVault().seal(wid, t.provider, t.id, bundle)
        db.commit()

    def no_inventory(req: httpx.Request) -> httpx.Response:
        pytest.fail("unavailable context emitted inventory HTTP")

    def oauth(req: httpx.Request) -> httpx.Response:
        assert provider == "google_ads" and failure == "expired"
        return httpx.Response(
            200, json=dict(access_token=PRIVATE, token_type="Bearer", expires_in=0)
        )

    from app.google_connections.http import GoogleReadError
    from app.meta.security import MetaError
    from app.publication.execution_authorization import owner_authorizer

    service = NativeDiagnosticService(
        lambda: Session(engine),
        owner_authorizer,
        transports={}
        if failure == "missing_transport"
        else {provider: httpx.MockTransport(no_inventory)},
        google_oauth=GoogleHTTPRead(
            "synthetic", SecretStr("synthetic"), None, "v25", transport=httpx.MockTransport(oauth)
        ),
        clock=lambda: NOW,
    )
    with pytest.raises(
        (
            HTTPException,
            GoogleReadError,
            MetaError,
            MetaNativeInventoryUnavailable,
            TikTokNativeInventoryUnavailable,
        )
    ) as error:
        service.read(request, NOW)
    assert PRIVATE not in str(error.value)
    assert "synthetic-refresh" not in str(error.value)


@pytest.mark.parametrize("seconds", [None, True, "3600", -1, 0, 86401])
def test_google_access_context_requires_documented_bounded_expiry(seconds: Any) -> None:
    from app.google_connections.http import GoogleReadError

    adapter = GoogleHTTPRead(
        "synthetic",
        SecretStr("synthetic"),
        None,
        "v25",
        transport=httpx.MockTransport(
            lambda r: httpx.Response(
                200, json=dict(access_token=PRIVATE, token_type="Bearer", expires_in=seconds)
            )
        ),
    )
    with pytest.raises(GoogleReadError, match="google_token_invalid"):
        adapter.access_context("synthetic-refresh")
