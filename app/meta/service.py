from collections.abc import Callable
from datetime import datetime, timedelta
from secrets import token_urlsafe
from typing import Any
from urllib.parse import urlencode

from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.ads.enums import AdvertisingPlatform
from app.ads.models import AdvertisingAccount, Campaign, DailyMetric
from app.ads.repository import AdvertisingMetricsRepository
from app.ads.schemas import AdvertisingAccountCreate
from app.imports.native import bind_meta, revoke_native_integration
from app.meta.client import MetaClient, unpack_page
from app.meta.locking import lock_workspace
from app.meta.models import (
    MetaAudit,
    MetaConnection,
    MetaOAuthState,
    MetaPendingGrant,
    MetaStagedMetric,
)
from app.meta.normalize import account_metadata
from app.meta.security import (
    API_VERSION,
    CONVERSION_ACTIONS,
    SCOPES,
    MetaError,
    Vault,
    configuration_ready,
    identifier,
    utc,
)
from app.settings import Settings


def credentials(response: dict[str, Any], now: datetime) -> dict[str, Any]:
    try:
        token = response["access_token"]
        expires = int(response["expires_in"])
        if (
            not isinstance(token, str)
            or not 8 <= len(token) <= 8192
            or not 60 <= expires <= 31_536_000
        ):
            raise ValueError("token")
        return {"access_token": token, "expires_at": (now + timedelta(seconds=expires)).isoformat()}
    except (KeyError, TypeError, ValueError):
        raise MetaError("meta_invalid_token_response") from None


class ConnectionService:
    def __init__(
        self, session: Session, settings: Settings, client: MetaClient | None = None
    ) -> None:
        self.session, self.settings = session, settings
        self.client = client or MetaClient(settings)

    def get(self, workspace_id: int, *, lock: bool = False) -> MetaConnection | None:
        query = select(MetaConnection).where(MetaConnection.workspace_id == workspace_id)
        if lock:
            lock_workspace(self.session, workspace_id)
            query = query.with_for_update().execution_options(populate_existing=True)
        return self.session.scalar(query)

    def begin(self, workspace_id: int, actor: str, now: datetime, *, customer: bool = False) -> str:
        if not configuration_ready(self.settings, customer=customer):
            raise MetaError("meta_configuration_required")
        vault = Vault(self.settings)
        digest = vault.digest("actor", actor)
        nonce = token_urlsafe(32)
        self.session.execute(
            delete(MetaOAuthState)
            .execution_options(synchronize_session="fetch")
            .where(MetaOAuthState.expires_at <= now)
        )
        self.session.execute(
            delete(MetaPendingGrant)
            .execution_options(synchronize_session="fetch")
            .where(MetaPendingGrant.expires_at <= now)
        )
        self.session.execute(
            delete(MetaOAuthState)
            .execution_options(synchronize_session="fetch")
            .where(
                MetaOAuthState.workspace_id == workspace_id,
                MetaOAuthState.actor_digest == digest,
            )
        )
        self.session.execute(
            delete(MetaPendingGrant)
            .execution_options(synchronize_session="fetch")
            .where(
                MetaPendingGrant.workspace_id == workspace_id,
                MetaPendingGrant.actor_digest == digest,
            )
        )
        self.session.add(
            MetaOAuthState(
                digest=vault.digest("state", nonce),
                workspace_id=workspace_id,
                actor_digest=digest,
                expires_at=now + timedelta(minutes=10),
            )
        )
        self.session.commit()
        return f"https://www.facebook.com/{API_VERSION}/dialog/oauth?" + urlencode(
            {
                "client_id": self.settings.meta_client_id,
                "redirect_uri": self.settings.meta_redirect_uri,
                "scope": ",".join(sorted(SCOPES)),
                "response_type": "code",
                "state": nonce,
                "auth_type": "rerequest",
            }
        )

    def pending(self, values: dict[str, str], actor: str, now: datetime) -> MetaOAuthState:
        vault = Vault(self.settings)
        row = self.session.scalar(
            select(MetaOAuthState).where(
                MetaOAuthState.digest == vault.digest("state", values["state"]),
                MetaOAuthState.actor_digest == vault.digest("actor", actor),
                MetaOAuthState.expires_at > now,
            )
        )
        if row is None:
            raise MetaError("invalid_oauth_state")
        return row

    def finish(self, state: MetaOAuthState, code: str, role: str, now: datetime) -> None:
        workspace_id, actor = state.workspace_id, state.actor_digest
        result = self.session.execute(
            delete(MetaOAuthState)
            .execution_options(synchronize_session="fetch")
            .where(
                MetaOAuthState.digest == state.digest,
                MetaOAuthState.expires_at > now,
            )
        )
        if result.rowcount != 1:  # type: ignore[attr-defined]
            raise MetaError("invalid_oauth_state")
        self.session.commit()
        short = credentials(self.client.token(code=code), now)
        bundle = credentials(self.client.token(exchange_token=short["access_token"]), now)
        permissions, cursor = unpack_page(self.client.permissions(bundle["access_token"]))
        granted = {p.get("permission") for p in permissions if p.get("status") == "granted"}
        if not granted >= SCOPES or "ads_management" in granted or cursor:
            raise MetaError("meta_read_only_scope_required")
        items, cursor = unpack_page(self.client.accounts(bundle["access_token"]))
        accounts = [account_metadata(item) for item in items]
        self.session.execute(
            delete(MetaPendingGrant)
            .execution_options(synchronize_session="fetch")
            .where(
                MetaPendingGrant.workspace_id == workspace_id,
                MetaPendingGrant.actor_digest == actor,
            )
        )
        self.session.add(
            MetaPendingGrant(
                workspace_id=workspace_id,
                actor_digest=actor,
                expires_at=now + timedelta(minutes=10),
                encrypted_credentials=Vault(self.settings).seal(
                    workspace_id, "grant:" + actor, bundle
                ),
                accounts=accounts,
                cursor=cursor,
            )
        )
        self.session.add(MetaAudit(workspace_id=workspace_id, action="authorized", actor_role=role))
        self.session.commit()

    def grant(
        self, workspace_id: int, actor: str, now: datetime, *, lock: bool = False
    ) -> MetaPendingGrant | None:
        query = select(MetaPendingGrant).where(
            MetaPendingGrant.workspace_id == workspace_id,
            MetaPendingGrant.actor_digest == Vault(self.settings).digest("actor", actor),
            MetaPendingGrant.expires_at > now,
        )
        if lock:
            lock_workspace(self.session, workspace_id)
            query = query.with_for_update().execution_options(populate_existing=True)
        return self.session.scalar(query)

    def more_accounts(self, workspace_id: int, actor: str, now: datetime) -> None:
        grant = self.grant(workspace_id, actor, now, lock=True)
        if grant is None or not grant.cursor:
            raise MetaError("meta_authorization_expired")
        bundle = Vault(self.settings).open(
            workspace_id, "grant:" + grant.actor_digest, grant.encrypted_credentials
        )
        items, cursor = unpack_page(
            self.client.accounts(bundle["access_token"], grant.cursor), grant.cursor
        )
        grant.accounts, grant.cursor = [account_metadata(item) for item in items], cursor
        self.session.commit()

    def _require_account_owner(self, workspace_id: int, external_id: str) -> None:
        if self.session.scalar(
            select(AdvertisingAccount.id).where(
                AdvertisingAccount.platform == AdvertisingPlatform.META_ADS,
                AdvertisingAccount.external_account_id == external_id,
                AdvertisingAccount.workspace_id != workspace_id,
            )
        ):
            raise MetaError("meta_account_already_connected")

    def select_account(
        self,
        workspace_id: int,
        actor: str,
        external_id: str,
        action_type: str,
        role: str,
        now: datetime,
        *,
        before_persist: Callable[[], None] | None = None,
    ) -> MetaConnection:
        if action_type not in CONVERSION_ACTIONS:
            raise MetaError("meta_invalid_conversion_event")
        external_id = identifier(external_id)
        grant = self.grant(workspace_id, actor, now, lock=True)
        if grant is None or not any(a.get("account_id") == external_id for a in grant.accounts):
            raise MetaError("meta_account_not_authorized")
        existing = self.get(workspace_id, lock=True)
        if existing and existing.external_account_id != external_id:
            raise MetaError("meta_disconnect_existing_first")
        self._require_account_owner(workspace_id, external_id)
        vault = Vault(self.settings)
        bundle = vault.open(
            workspace_id, "grant:" + grant.actor_digest, grant.encrypted_credentials
        )
        grant_id = grant.id
        generation = (existing.id, existing.generation) if existing else None
        if before_persist:
            self.session.commit()  # Release customer locks before provider IO.
        details = account_metadata(self.client.account(external_id, bundle["access_token"]))
        if before_persist:
            before_persist()
            grant = self.grant(workspace_id, actor, now, lock=True)
            existing = self.get(workspace_id, lock=True)
            if (
                grant is None
                or grant.id != grant_id
                or ((existing.id, existing.generation) if existing else None) != generation
            ):
                raise MetaError("meta_authorization_expired")
        if details["account_id"] != external_id:
            raise MetaError("meta_account_not_authorized")
        # Provider IO can release customer locks. Recheck retained ownership here;
        # the Meta-only unique index serializes concurrent inserts after this read.
        self._require_account_owner(workspace_id, external_id)
        try:
            account = AdvertisingMetricsRepository(self.session).upsert_account(
                AdvertisingAccountCreate(
                    workspace_id=workspace_id,
                    platform=AdvertisingPlatform.META_ADS,
                    external_account_id=external_id,
                    name=details["name"],
                    currency_code=details["currency_code"],
                    time_zone=details["time_zone"],
                )
            )
            if existing is None:
                existing = MetaConnection(
                    workspace_id=workspace_id,
                    account_id=account.id,
                    external_account_id=external_id,
                )
                self.session.add(existing)
            else:
                existing.generation += 1
            existing.encrypted_credentials = vault.seal(workspace_id, external_id, bundle)
            existing.status, existing.conversion_action_type = "connected", action_type or None
            existing.connected_at, existing.last_sync_at = now, None
            existing.covered_from, existing.covered_through = None, None
            existing.last_attempt_at, existing.next_attempt_at, existing.error_code = (
                None,
                None,
                None,
            )
            existing.window_start, existing.window_end, existing.cursor = None, None, None
            existing.phase = "campaigns"
            if existing.id:
                from app.meta.staging import clear

                clear(self.session, existing.id)
                self.session.execute(
                    delete(MetaStagedMetric).where(MetaStagedMetric.connection_id == existing.id)
                )
            self.session.execute(
                update(DailyMetric)
                .where(
                    DailyMetric.campaign_id.in_(
                        select(Campaign.id).where(Campaign.account_id == account.id)
                    ),
                    DailyMetric.platform == AdvertisingPlatform.META_ADS,
                )
                .values(conversions=0, conversion_value_micros=0)
            )
            bind_meta(self.session, existing, reconnect=True)
            self.session.delete(grant)
            self.session.add(
                MetaAudit(workspace_id=workspace_id, action="connected", actor_role=role)
            )
            self.session.commit()
        except IntegrityError:
            self.session.rollback()
            raise MetaError("meta_account_already_connected") from None
        return existing

    def access_token(self, row: MetaConnection, now: datetime) -> str:
        bundle = Vault(self.settings).open(
            row.workspace_id, row.external_account_id, row.encrypted_credentials
        )
        try:
            if utc(datetime.fromisoformat(bundle["expires_at"])) <= now + timedelta(minutes=5):
                raise MetaError("meta_reconnect_required")
            return str(bundle["access_token"])
        except (KeyError, TypeError, ValueError):
            raise MetaError("meta_reconnect_required") from None

    def disconnect(self, workspace_id: int, role: str) -> None:
        row = self.get(workspace_id, lock=True)
        if row:
            from app.meta.staging import clear

            clear(self.session, row.id)
            revoke_native_integration(self.session, row.workspace_integration_id)
            self.session.delete(row)
        for model in (MetaOAuthState, MetaPendingGrant):
            self.session.execute(delete(model).where(model.workspace_id == workspace_id))
        self.session.add(
            MetaAudit(workspace_id=workspace_id, action="disconnected", actor_role=role)
        )
        self.session.commit()
