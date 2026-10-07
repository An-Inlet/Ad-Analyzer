"""Request-owned Meta credentials and private media; no token renewal or global actor."""

from collections.abc import Callable
from datetime import datetime, timedelta

from fastapi import HTTPException
from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.billing.entitlements import live_paid_work, paid_work
from app.campaign_review.contracts import MediaStore
from app.collectors.meta_catalog import MetaCatalogContext
from app.meta.models import MetaConnection
from app.meta.security import MetaError, Vault, utc
from app.production_runtime.meta_contracts import MetaExecutionManifestV1
from app.publication.activation_contracts import ActivationContext, ActivationRequest
from app.publication.execution_authorization import ExecutionAuthorizer
from app.publication.execution_contracts import ExecutionAccount
from app.publication.execution_mandates import current_account
from app.publication.scoped_media import ScopedProviderMediaReader
from app.publication.social_catalog import SocialCatalogRequest
from app.publication.social_contracts import (
    ProviderMediaBinding,
    SocialBoundRequest,
    SocialProviderContext,
)
from app.settings import Settings


class OwnedMetaContexts:
    def __init__(
        self,
        sessions: Callable[[], Session],
        authorize: ExecutionAuthorizer,
        actor: str,
        manifest: MetaExecutionManifestV1,
        configuration: Settings,
        clock: Callable[[], datetime],
    ) -> None:
        self.sessions, self.authorize, self.actor = sessions, authorize, actor
        self.manifest, self.configuration, self.clock = manifest, configuration, clock
        self.closed = False

    def close(self) -> None:
        self.closed = True

    def credentials(self, scope: ExecutionAccount) -> tuple[SecretStr, datetime]:
        if self.closed or scope.account.platform != "meta_ads":
            raise HTTPException(409, "meta_execution_context_unavailable")
        with self.sessions() as db:
            self.authorize(db, scope.workspace_id, self.actor)
            if self.manifest.environment == "live":
                live_paid_work(db, scope.workspace_id, self.clock())
            else:
                paid_work(db, scope.workspace_id, self.clock())
            current_account(db, scope)
            row = db.scalar(
                select(MetaConnection).where(
                    MetaConnection.workspace_id == scope.workspace_id,
                    MetaConnection.account_id == scope.account.account_id,
                    MetaConnection.workspace_integration_id == scope.account.connection_id,
                )
            )
            if row is None:
                raise HTTPException(409, "meta_execution_credential_unavailable")
            try:
                raw = Vault(self.configuration).open(
                    row.workspace_id, row.external_account_id, row.encrypted_credentials
                )
                token = raw["access_token"]
                expiry = utc(datetime.fromisoformat(raw["expires_at"]))
                if not isinstance(token, str) or not 8 <= len(token) <= 8192:
                    raise ValueError("invalid token")
                now = self.clock()
                if expiry <= now + timedelta(
                    seconds=self.manifest.credential_minimum_remaining_seconds
                ):
                    raise ValueError("token expired")
            except (MetaError, ValueError, KeyError, TypeError):
                raise HTTPException(409, "meta_execution_reconnect_required") from None
            self.authorize(db, scope.workspace_id, self.actor)
            return SecretStr(token), min(
                expiry, now + timedelta(seconds=self.manifest.context_lifetime_seconds)
            )

    def catalog(self, request: SocialCatalogRequest, now: datetime, /) -> MetaCatalogContext:
        if self.clock() < now:
            raise HTTPException(409, "meta_execution_clock_changed")
        token, expiry = self.credentials(request.account)
        return MetaCatalogContext(
            account=request.account,
            request_digest=request.digest(),
            access_token=token,
            app_secret=self.configuration.meta_client_secret,
            expires_at=expiry,
        )

    def publication(self, request: SocialBoundRequest, /) -> SocialProviderContext:
        token, expiry = self.credentials(ExecutionAccount.from_publication(request.scope))
        return SocialProviderContext(
            scope=request.scope,
            access_token=token,
            app_secret=self.configuration.meta_client_secret,
            expires_at=expiry,
        )

    def activation(self, request: ActivationRequest, /) -> ActivationContext:
        token, expiry = self.credentials(request.account)
        return ActivationContext(
            account=request.account,
            access_token=token,
            app_secret=self.configuration.meta_client_secret,
            expires_at=expiry,
        )


class OwnedMetaMedia:
    def __init__(self, contexts: OwnedMetaContexts, store: MediaStore) -> None:
        self.contexts, self.store = contexts, store

    def read_verified(self, workspace_id: int, binding: ProviderMediaBinding) -> bytes:
        if self.contexts.closed:
            raise HTTPException(409, "meta_execution_context_unavailable")
        with self.contexts.sessions() as db:
            self.contexts.authorize(db, workspace_id, self.contexts.actor)
            # Capture exact DB-owned media before releasing locks for private storage.
            from app.campaign_review.models import MediaObject

            row = db.get(MediaObject, binding.media_id)
            if row is None or row.workspace_id != workspace_id:
                raise HTTPException(409, "owned_media_unavailable")
            stamp = (row.sha256, row.size, row.mime, row.width, row.height)
            db.rollback()
            result = ScopedProviderMediaReader(db, self.store).read_verified(workspace_id, binding)
            self.contexts.authorize(db, workspace_id, self.contexts.actor)
            current = db.get(MediaObject, binding.media_id, populate_existing=True)
            if (
                current is None
                or current.workspace_id != workspace_id
                or stamp
                != (current.sha256, current.size, current.mime, current.width, current.height)
            ):
                raise HTTPException(409, "owned_media_changed")
            return result
