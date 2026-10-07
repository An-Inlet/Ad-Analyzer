"""Ephemeral original-session Google credentials; no provider IO under DB locks."""

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import datetime, timedelta

import httpx
from fastapi import HTTPException
from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.billing.entitlements import live_paid_work, paid_work
from app.collectors.account_diagnostics import _BorrowedTransport
from app.collectors.google_catalog import GoogleCatalogContext
from app.google_connections.http import GoogleHTTPRead, GoogleReadError
from app.google_connections.models import GoogleCustomerConnection
from app.google_connections.security import Vault
from app.production_runtime.contracts import GoogleExecutionManifestV1
from app.publication.activation_contracts import ActivationContext, ActivationRequest
from app.publication.contracts import PublicationScope
from app.publication.customer_catalog import GoogleCatalogRequest
from app.publication.execution_authorization import ExecutionAuthorizer
from app.publication.execution_contracts import ExecutionAccount
from app.publication.execution_mandates import current_account
from app.publication.provider_contracts import ProviderContext
from app.settings import Settings


def google_execution_transport(manifest: GoogleExecutionManifestV1) -> httpx.BaseTransport:
    """Real transport never admits synthetic financial evidence, even from trusted code."""
    if manifest.environment != "live" or not manifest.live_execution_enabled:
        raise HTTPException(409, "google_execution_test_transport_required")
    return httpx.HTTPTransport(retries=0, trust_env=False)


class OwnedGoogleContexts:
    def __init__(
        self,
        sessions: Callable[[], Session],
        authorize: ExecutionAuthorizer,
        actor: str,
        manifest: GoogleExecutionManifestV1,
        configuration: Settings,
        clock: Callable[[], datetime],
        oauth: GoogleHTTPRead,
    ) -> None:
        self.sessions, self.authorize, self.actor = sessions, authorize, actor
        self.manifest, self.configuration, self.clock, self.oauth = (
            manifest,
            configuration,
            clock,
            oauth,
        )
        self._cache: dict[str, tuple[str, SecretStr, datetime]] = {}
        self.closed = False

    def close(self) -> None:
        self._cache.clear()
        self.closed = True

    def snapshot(self, scope: ExecutionAccount) -> tuple[str, str, str | None]:
        if self.closed or scope.account.platform != "google_ads":
            raise HTTPException(409, "google_execution_context_unavailable")
        with self.sessions() as db:
            self.authorize(db, scope.workspace_id, self.actor)
            if self.manifest.environment == "live":
                live_paid_work(db, scope.workspace_id, self.clock())
            else:
                paid_work(db, scope.workspace_id, self.clock())
            current_account(db, scope)
            row = db.scalar(
                select(GoogleCustomerConnection).where(
                    GoogleCustomerConnection.workspace_id == scope.workspace_id,
                    GoogleCustomerConnection.account_id == scope.account.account_id,
                    GoogleCustomerConnection.integration_id == scope.account.connection_id,
                )
            )
            if row is None or not row.encrypted_grant:
                raise HTTPException(409, "google_execution_credential_unavailable")
            encrypted, login = row.encrypted_grant, row.login_customer_id
            refresh = Vault().open(row.workspace_id, row.id, encrypted)
            self.authorize(db, scope.workspace_id, self.actor)
            return encrypted, refresh, login

    def credentials(self, scope: ExecutionAccount) -> tuple[SecretStr, datetime, str | None]:
        before = self.snapshot(scope)
        now = self.clock()
        minimum = timedelta(seconds=self.manifest.credential_minimum_remaining_seconds)
        key = scope.digest()
        cached = self._cache.get(key)
        if cached is None or cached[0] != before[0] or cached[2] <= now + minimum:
            try:
                token, seconds = self.oauth.access_context(before[1])
            except GoogleReadError:
                raise HTTPException(409, "google_execution_credential_unavailable") from None
            expiry = now + timedelta(seconds=seconds)
            if expiry <= self.clock() + minimum:
                raise HTTPException(409, "google_execution_credential_lifetime_unavailable")
            cached = (before[0], token, expiry)
            self._cache[key] = cached
        if self.snapshot(scope) != before:
            self._cache.pop(key, None)
            raise HTTPException(409, "google_execution_source_changed")
        expiry = min(
            cached[2], self.clock() + timedelta(seconds=self.manifest.context_lifetime_seconds)
        )
        return cached[1], expiry, before[2]

    def publication(self, scope: PublicationScope, /) -> ProviderContext:
        token, expiry, login = self.credentials(ExecutionAccount.from_publication(scope))
        return ProviderContext(
            scope=scope,
            login_customer_id=login,
            access_token=token,
            developer_token=self.oauth.developer,
            expires_at=expiry,
        )

    def catalog(self, request: GoogleCatalogRequest, now: datetime, /) -> GoogleCatalogContext:
        if self.clock() < now:
            raise HTTPException(409, "google_execution_clock_changed")
        token, expiry, login = self.credentials(request.account)
        return GoogleCatalogContext(
            account=request.account,
            request_digest=request.digest(),
            access_token=token,
            developer_token=self.oauth.developer,
            login_customer_id=login,
            expires_at=expiry,
        )

    def activation(self, request: ActivationRequest, /) -> ActivationContext:
        token, expiry, login = self.credentials(request.account)
        return ActivationContext(
            account=request.account,
            access_token=token,
            developer_token=self.oauth.developer,
            login_customer_id=login,
            expires_at=expiry,
        )


@contextmanager
def owned_google_contexts(
    sessions: Callable[[], Session],
    authorize: ExecutionAuthorizer,
    actor_id: str,
    manifest: GoogleExecutionManifestV1,
    configuration: Settings,
    clock: Callable[[], datetime],
    transport: httpx.BaseTransport,
) -> Iterator[OwnedGoogleContexts]:
    if (
        not configuration.google_customer_client_id
        or configuration.google_customer_client_secret is None
        or configuration.google_customer_encryption_key is None
    ):
        raise HTTPException(503, "google_execution_configuration_unavailable")
    oauth = GoogleHTTPRead(
        configuration.google_customer_client_id,
        configuration.google_customer_client_secret,
        configuration.google_customer_developer_token,
        manifest.api_version,
        transport=_BorrowedTransport(transport),
    )
    contexts = OwnedGoogleContexts(
        sessions, authorize, actor_id, manifest, configuration, clock, oauth
    )
    try:
        yield contexts
    finally:
        contexts.close()
