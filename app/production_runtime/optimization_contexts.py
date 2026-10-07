"""Direct owned optimization scopes; ephemeral vault credentials, no invented publication."""

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta

import httpx
from fastapi import HTTPException
from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.billing.entitlements import live_paid_work, paid_work
from app.collectors.account_diagnostics import _BorrowedTransport
from app.google_connections.http import GoogleHTTPRead, GoogleReadError
from app.google_connections.models import GoogleCustomerConnection
from app.google_connections.security import Vault as GoogleVault
from app.meta.models import MetaConnection
from app.meta.security import MetaError
from app.meta.security import Vault as MetaVault
from app.production_runtime.optimization_contracts import OptimizationExecutionManifestV1
from app.publication.execution_authorization import ExecutionAuthorizer
from app.publication.execution_contracts import ExecutionAccount
from app.publication.execution_mandates import current_account
from app.publication.optimization_contracts import OptimizationContext
from app.settings import Settings


def unavailable() -> HTTPException:
    return HTTPException(409, "optimization_credentials_unavailable")


class OwnedOptimizationContexts:
    def __init__(
        self,
        sessions: Callable[[], Session],
        authorize: ExecutionAuthorizer,
        actor_id: str,
        manifest: OptimizationExecutionManifestV1,
        configuration: Settings,
        clock: Callable[[], datetime],
        transport: httpx.BaseTransport,
    ) -> None:
        self.sessions, self.authorize, self.actor = sessions, authorize, actor_id
        self.manifest, self.configuration, self.clock = manifest, configuration, clock
        self.transport = transport
        self.closed = False
        self.cache: dict[str, tuple[str, SecretStr, datetime]] = {}

    def close(self) -> None:
        self.cache.clear()
        self.closed = True

    def now(self) -> datetime:
        value = self.clock()
        if value.tzinfo is None or value.utcoffset() is None:
            raise unavailable()
        return value.astimezone(UTC)

    def snapshot(self, scope: ExecutionAccount) -> tuple[str, str, str | None, datetime | None]:
        if (
            self.closed
            or scope.account.platform not in self.manifest.providers
            or (self.manifest.environment == "live" and not self.manifest.live_execution_enabled)
        ):
            raise unavailable()
        with self.sessions() as db:
            self.authorize(db, scope.workspace_id, self.actor)
            (live_paid_work if self.manifest.environment == "live" else paid_work)(
                db, scope.workspace_id, self.now()
            )
            current_account(db, scope)
            result: tuple[str, str, str | None, datetime | None]
            if scope.account.platform == "google_ads":
                google = db.scalar(
                    select(GoogleCustomerConnection).where(
                        GoogleCustomerConnection.workspace_id == scope.workspace_id,
                        GoogleCustomerConnection.integration_id == scope.account.connection_id,
                        GoogleCustomerConnection.account_id == scope.account.account_id,
                    )
                )
                if google is None or not google.encrypted_grant:
                    raise unavailable()
                raw = GoogleVault(self.configuration).open(
                    google.workspace_id, google.id, google.encrypted_grant
                )
                result = (google.encrypted_grant, raw, google.login_customer_id, None)
            else:
                meta = db.scalar(
                    select(MetaConnection).where(
                        MetaConnection.workspace_id == scope.workspace_id,
                        MetaConnection.workspace_integration_id == scope.account.connection_id,
                        MetaConnection.account_id == scope.account.account_id,
                    )
                )
                if meta is None:
                    raise unavailable()
                try:
                    grant = MetaVault(self.configuration).open(
                        meta.workspace_id, meta.external_account_id, meta.encrypted_credentials
                    )
                    token = grant["access_token"]
                    expiry = datetime.fromisoformat(grant["expires_at"])
                    if (
                        not isinstance(token, str)
                        or not 8 <= len(token) <= 8192
                        or expiry.tzinfo is None
                        or expiry.utcoffset() is None
                    ):
                        raise ValueError("unknown token lifetime")
                except (MetaError, ValueError, KeyError, TypeError):
                    raise unavailable() from None
                result = (meta.encrypted_credentials, token, None, expiry.astimezone(UTC))
            self.authorize(db, scope.workspace_id, self.actor)
            return result

    def optimization(self, scope: ExecutionAccount, /) -> OptimizationContext:
        before = self.snapshot(scope)  # private session closed before OAuth IO
        minimum = timedelta(seconds=self.manifest.credential_minimum_remaining_seconds)
        cached = self.cache.get(scope.digest())
        if scope.account.platform == "google_ads":
            settings = self.configuration
            if (
                not settings.google_customer_client_id
                or settings.google_customer_client_secret is None
            ):
                raise unavailable()
            if cached is None or cached[0] != before[0] or cached[2] <= self.now() + minimum:
                oauth = GoogleHTTPRead(
                    settings.google_customer_client_id,
                    settings.google_customer_client_secret,
                    settings.google_customer_developer_token,
                    "v25",
                    transport=_BorrowedTransport(self.transport),
                )
                started = self.now()
                try:
                    token, seconds = oauth.access_context(before[1])
                except GoogleReadError:
                    raise unavailable() from None
                cached = (before[0], token, started + timedelta(seconds=seconds))
                self.cache[scope.digest()] = cached
            token, expiry = cached[1:]
        else:
            token = SecretStr(before[1])
            if before[3] is None:
                raise unavailable()
            expiry = before[3]
        if self.snapshot(scope) != before:
            self.cache.pop(scope.digest(), None)
            raise unavailable()
        now = self.now()  # refreshed after blocking authority checks
        if expiry <= now + minimum:
            raise unavailable()
        return OptimizationContext(
            scope=scope,
            access_token=token,
            developer_token=self.configuration.google_customer_developer_token
            if scope.account.platform == "google_ads"
            else None,
            app_secret=self.configuration.meta_client_secret
            if scope.account.platform == "meta_ads"
            else None,
            login_customer_id=before[2],
            expires_at=min(expiry, now + timedelta(seconds=self.manifest.context_lifetime_seconds)),
        )


@contextmanager
def owned_optimization_contexts(
    sessions: Callable[[], Session],
    authorize: ExecutionAuthorizer,
    actor_id: str,
    manifest: OptimizationExecutionManifestV1,
    configuration: Settings,
    clock: Callable[[], datetime],
    transport: httpx.BaseTransport,
) -> Iterator[OwnedOptimizationContexts]:
    """Takes ownership of the explicit transport; closes it even on authority failure."""
    contexts = OwnedOptimizationContexts(
        sessions, authorize, actor_id, manifest, configuration, clock, transport
    )
    try:
        yield contexts
    finally:
        contexts.close()
        transport.close()
