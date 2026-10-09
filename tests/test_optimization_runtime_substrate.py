"""Owned actual vault/session/DB contexts and pinned server configuration, no network."""

import time
from datetime import timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest
from app.customers.access import SESSION_COOKIE, CustomerPrincipal, digest
from app.customers.models import CustomerSession, CustomerUser
from app.google_connections.models import GoogleCustomerConnection
from app.google_connections.security import Vault as GoogleVault
from app.meta.models import MetaConnection
from app.meta.security import Vault as MetaVault
from app.production_runtime.optimization_configuration import (
    OptimizationRuntimeConfigurationError,
    load_optimization_execution_configuration,
)
from app.production_runtime.optimization_contexts import owned_optimization_contexts
from app.production_runtime.optimization_sources import registered_optimization_evidence
from app.production_runtime.optimization_transport import optimization_execution_transport
from app.publication.customer_authority import bind_authority
from app.publication.execution_contracts import ExecutionAccount
from app.settings import Settings, settings
from cryptography.fernet import Fernet
from fastapi import HTTPException
from pydantic import SecretStr, ValidationError
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from tests.test_commerce_measurement import NOW
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import login
from tests.test_customer_identity import replicas as replicas
from tests.test_optimization_runtime_contracts import manifest, policy
from tests.test_planning_target_catalog_api import seed as source_seed
from tests.test_shopify_sales import configuration as configuration
from tests.tiktok_read_fixture import read_only_graph as read_only_graph


@pytest.mark.parametrize(
    "failure", [None, "partial", "duplicate", "oversize", "pin", "environment", "profile"]
)
def test_loader_exact_pinned_immutable_configuration(tmp_path: Path, failure: str | None) -> None:
    p = policy()
    m = manifest().model_copy(update={"operating_policy_digest": p.digest()})
    mp, bp = tmp_path / "manifest.json", tmp_path / "policy.json"
    mp.write_text(m.model_dump_json())
    bp.write_text(p.model_dump_json())
    expected = m.digest()
    if failure == "partial":
        with pytest.raises(OptimizationRuntimeConfigurationError):
            load_optimization_execution_configuration(str(mp), expected, None)
        return
    if failure == "duplicate":
        bp.write_text('{"rules":[],"rules":[]}')
    if failure == "oversize":
        bp.write_text("x" * 16385)
    if failure == "pin":
        expected = "f" * 64
    if failure in {"environment", "profile"}:
        p = p.model_copy(
            update={"environment": "live"}
            if failure == "environment"
            else {"evidence_profile_digest": "c" * 64}
        )
        bp.write_text(p.model_dump_json())
        m = m.model_copy(update={"operating_policy_digest": p.digest()})
        mp.write_text(m.model_dump_json())
        expected = m.digest()
    if failure:
        with pytest.raises(
            OptimizationRuntimeConfigurationError, match="^optimization_configuration_invalid$"
        ):
            load_optimization_execution_configuration(str(mp), expected, str(bp))
    else:
        loaded = load_optimization_execution_configuration(str(mp), expected, str(bp))
        assert loaded and loaded == (m, p)
        with pytest.raises(ValidationError):
            setattr(loaded[1].rules[0], "cooldown_seconds", 2)  # noqa: B010 - test runtime immutability
        assert load_optimization_execution_configuration(None, None, None) is None


def test_empty_registry_and_real_transport_do_not_construct_io(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("real network constructor")

    monkeypatch.setattr(httpx, "HTTPTransport", forbidden)
    assert registered_optimization_evidence("anything") is None
    with pytest.raises(HTTPException):
        optimization_execution_transport(manifest())


@pytest.mark.parametrize("platform", ["google_ads", "meta_ads"])
@pytest.mark.parametrize(
    "change",
    [None, "revoked", "expired", "source", "provider", "unknown_expiry", "billing", "final_expiry"],
)
@pytest.mark.planning_boundary
@pytest.mark.usefixtures("read_only_graph")
def test_owned_credentials_context_and_cleanup(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    platform: str,
    change: str | None,
) -> None:
    # Current credential readers need owned sources and a real session, not execution approval.
    for key in ("google_customer_encryption_key", "meta_token_encryption_key"):
        monkeypatch.setattr(settings, key, SecretStr(Fernet.generate_key().decode()))
    monkeypatch.setattr(settings, "google_customer_client_id", "offline-client")
    monkeypatch.setattr(settings, "google_customer_client_secret", SecretStr("offline-secret"))
    owned = source_seed(customer_engine, configuration, tmp_path, platform)
    wid = owned.workspace_id
    with Session(customer_engine) as db:
        if platform == "google_ads":
            google = db.scalar(select(GoogleCustomerConnection))
            assert google is not None
            google.encrypted_grant = GoogleVault().seal(wid, google.id, "offline-refresh")
        else:
            meta = db.scalar(select(MetaConnection))
            assert meta is not None
            meta.encrypted_credentials = MetaVault(settings).seal(
                wid, meta.external_account_id,
                {"access_token": "offline-meta-access",
                 "expires_at": (NOW + timedelta(hours=2)).isoformat()},
            )
        db.commit()
    alice = replicas[0]
    assert login(alice, "diagnostic-owner:read") == owned.actor
    provider = replicas[2]
    with Session(customer_engine) as db:
        session = db.get(CustomerSession, digest(alice.cookies[SESSION_COOKIE]))
        assert session
        user = db.get(CustomerUser, session.user_id)
        assert user
        principal = CustomerPrincipal(user, session)
        native: Any = db.scalar(
            select(GoogleCustomerConnection if platform == "google_ads" else MetaConnection)
        )
        assert native
        scope = ExecutionAccount(
            workspace_id=wid,
            account={
                "platform": platform,
                "account_id": native.account_id,
                "connection_id": native.integration_id
                if platform == "google_ads"
                else native.workspace_integration_id,
            },
            external_advertiser_id=native.external_account_id,
            connection_version=(
                f"{'google' if platform == 'google_ads' else 'meta'}:"
                f"{native.id}:{native.generation}"
            ),
        )
        native_id = native.id
        session_id = session.digest
        actor = user.id
    calls = []
    closed = []

    def mutate() -> None:
        with Session(customer_engine) as db:
            if change == "revoked":
                s = db.get(CustomerSession, session_id)
                assert s
                s.revoked_at = int(time.time())
            elif change == "source":
                n: Any = db.get(
                    GoogleCustomerConnection if platform == "google_ads" else MetaConnection,
                    native_id,
                )
                assert n
                n.generation += 1
            elif change in {"expired", "unknown_expiry"} and platform == "meta_ads":
                n = db.get(MetaConnection, native_id)
                assert n
                n.encrypted_credentials = MetaVault(settings).seal(
                    wid,
                    n.external_account_id,
                    {
                        "access_token": "offline-meta-access",
                        **(
                            {"expires_at": (NOW - timedelta(seconds=1)).isoformat()}
                            if change == "expired"
                            else {}
                        ),
                    },
                )
            db.commit()

    def wire(req: httpx.Request) -> httpx.Response:
        calls.append(req.url.path)
        assert platform == "google_ads" and req.url.host == "oauth2.googleapis.com"
        mutate()  # independent DB transaction proves caller released its workspace locks
        return httpx.Response(
            200,
            json={
                "access_token": "offline-access",
                **(
                    {"expires_in": 60 if change == "expired" else 3600}
                    if change != "unknown_expiry"
                    else {}
                ),
                "token_type": "Bearer",
            },
        )

    class Transport(httpx.MockTransport):
        def close(self) -> None:
            closed.append(True)

    if change == "billing":
        monkeypatch.setattr(settings, "billing_required", True)
        monkeypatch.setattr(settings, "billing_price_id", None)
    if platform == "meta_ads":
        mutate()
    if change == "provider":
        scope = scope.model_copy(
            update={"account": scope.account.model_copy(update={"platform": "tiktok_ads"})}
        )
    authorizer = bind_authority(principal, provider)
    authorizations: list[bool] = []
    clock = {"now": NOW}

    def authorize(db: Session, workspace: int, original_actor: str) -> None:
        authorizer(db, workspace, original_actor)
        authorizations.append(True)
        if change == "final_expiry" and len(authorizations) == 4:
            clock["now"] = NOW + timedelta(hours=3)

    with owned_optimization_contexts(
        lambda: Session(customer_engine),
        authorize,
        actor,
        manifest(),
        settings,
        lambda: clock["now"],
        Transport(wire),
    ) as contexts:
        if change:
            with pytest.raises(HTTPException):
                contexts.optimization(scope)
        else:
            value = contexts.optimization(scope)
            assert value.scope == scope and value.expires_at == NOW + timedelta(seconds=60)
            assert "offline" not in repr(value) and "access_token" not in value.model_dump()
            again = contexts.optimization(scope)
            assert again.expires_at == value.expires_at
            assert len(calls) == (1 if platform == "google_ads" else 0)
    assert closed == [True] and contexts.closed and not contexts.cache
    with pytest.raises(HTTPException):
        contexts.optimization(scope)
    if change == "provider":
        assert calls == []


def test_google_vault_uses_explicit_non_global_configuration() -> None:
    import base64

    from app.google_connections.security import Vault
    from pydantic import SecretStr

    first = Settings(
        _env_file=None,
        AD_ANALYZER_GOOGLE_CUSTOMER_ENCRYPTION_KEY=SecretStr(
            base64.urlsafe_b64encode(b"1" * 32).decode()
        ),
    )
    second = Settings(
        _env_file=None,
        AD_ANALYZER_GOOGLE_CUSTOMER_ENCRYPTION_KEY=SecretStr(
            base64.urlsafe_b64encode(b"2" * 32).decode()
        ),
    )
    encrypted = Vault(first).seal(1, "owned", "offline-refresh")
    assert Vault(first).open(1, "owned", encrypted) == "offline-refresh"
    with pytest.raises(HTTPException):
        Vault(second).open(1, "owned", encrypted)
