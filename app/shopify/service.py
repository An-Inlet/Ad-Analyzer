from datetime import datetime, timedelta
from secrets import token_urlsafe
from typing import Any
from urllib.parse import urlencode
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.imports.native import bind_shopify, revoke_native_integration
from app.settings import Settings
from app.shopify.client import ShopifyClient
from app.shopify.models import ShopifyAudit, ShopifyConnection, ShopifyOAuthState
from app.shopify.security import SCOPES, ShopifyError, Vault, configuration_ready, shop_domain, utc


def credentials(
    response: dict[str, Any], now: datetime, previous: dict[str, Any] | None = None
) -> dict[str, Any]:
    previous = previous or {}
    token = response.get("access_token")
    refresh = response.get("refresh_token")
    granted = set(str(response.get("scope", ",".join(previous.get("scopes", [])))).split(","))
    if not isinstance(token, str) or not 8 <= len(token) <= 4096:
        raise ShopifyError("shopify_invalid_token_response")
    if not granted >= SCOPES or any(not s.startswith("read_") for s in granted):
        raise ShopifyError("shopify_read_only_scopes_required")
    try:
        expires = int(response.get("expires_in", 0))
        if not 0 <= expires <= 31_536_000:
            raise ValueError("expiry")
        if expires and (not isinstance(refresh, str) or not 8 <= len(refresh) <= 4096):
            raise ValueError("refresh")
    except (ValueError, TypeError):
        raise ShopifyError("shopify_invalid_token_response") from None
    return {
        "access_token": token,
        "refresh_token": refresh,
        "expires_at": (now + timedelta(seconds=expires)).isoformat() if expires else None,
        "scopes": sorted(granted),
    }


class ConnectionService:
    def __init__(
        self, session: Session, settings: Settings, client: ShopifyClient | None = None
    ) -> None:
        self.session = session
        self.settings = settings
        self.client = client or ShopifyClient(settings)

    def get(self, workspace_id: int, *, lock: bool = False) -> ShopifyConnection | None:
        query = select(ShopifyConnection).where(ShopifyConnection.workspace_id == workspace_id)
        if lock:
            query = query.with_for_update()
        return self.session.scalar(query)

    def begin(self, workspace_id: int, shop: str, actor: str, now: datetime) -> str:
        if not configuration_ready(self.settings):
            raise ShopifyError("shopify_configuration_required")
        shop = shop_domain(shop)
        existing = self.get(workspace_id)
        if existing and existing.shop_domain != shop:
            raise ShopifyError("disconnect_existing_store_first")
        owned_elsewhere = self.session.scalar(
            select(ShopifyConnection.id).where(
                ShopifyConnection.shop_domain == shop,
                ShopifyConnection.workspace_id != workspace_id,
            )
        )
        if owned_elsewhere:
            raise ShopifyError("store_already_connected")
        vault = Vault(self.settings)
        nonce = token_urlsafe(32)
        self.session.execute(
            delete(ShopifyOAuthState)
            .execution_options(synchronize_session="fetch")
            .where(ShopifyOAuthState.expires_at < now)
        )
        self.session.execute(
            delete(ShopifyOAuthState)
            .execution_options(synchronize_session="fetch")
            .where(
                ShopifyOAuthState.workspace_id == workspace_id,
                ShopifyOAuthState.actor_digest == vault.digest("oauth_actor", actor),
            )
        )
        self.session.add(
            ShopifyOAuthState(
                digest=vault.digest("oauth_state", nonce),
                workspace_id=workspace_id,
                shop_domain=shop,
                actor_digest=vault.digest("oauth_actor", actor),
                expires_at=now + timedelta(minutes=10),
            )
        )
        self.session.commit()
        return f"https://{shop}/admin/oauth/authorize?" + urlencode(
            {
                "client_id": self.settings.shopify_client_id,
                "scope": ",".join(sorted(SCOPES)),
                "redirect_uri": self.settings.shopify_redirect_uri,
                "state": nonce,
            }
        )

    def pending(self, values: dict[str, str], actor: str, now: datetime) -> ShopifyOAuthState:
        vault = Vault(self.settings)
        row = self.session.scalar(
            select(ShopifyOAuthState).where(
                ShopifyOAuthState.digest == vault.digest("oauth_state", values["state"]),
                ShopifyOAuthState.shop_domain == values["shop"],
                ShopifyOAuthState.actor_digest == vault.digest("oauth_actor", actor),
                ShopifyOAuthState.expires_at > now,
            )
        )
        if row is None:
            raise ShopifyError("invalid_oauth_state")
        return row

    def finish(
        self, state: ShopifyOAuthState, code: str, role: str, now: datetime
    ) -> ShopifyConnection:
        workspace_id, shop, digest = state.workspace_id, state.shop_domain, state.digest
        result = self.session.execute(
            delete(ShopifyOAuthState)
            .execution_options(synchronize_session="fetch")
            .where(ShopifyOAuthState.digest == digest, ShopifyOAuthState.expires_at > now)
        )
        if result.rowcount != 1:  # type: ignore[attr-defined]
            raise ShopifyError("invalid_oauth_state")
        self.session.commit()  # Consume the authorization attempt before exchanging a one-use code.
        bundle = credentials(self.client.token(shop, code=code), now)
        metadata = self.client.shop(shop, bundle["access_token"])
        try:
            details = metadata["shop"]
            granted = {s["handle"] for s in metadata["currentAppInstallation"]["accessScopes"]}
            if not granted >= SCOPES or any(not s.startswith("read_") for s in granted):
                raise ValueError("scopes")
            if shop_domain(details["myshopifyDomain"]) != shop:
                raise ValueError("shop")
            currency = str(details["currencyCode"])
            if len(currency) != 3 or not currency.isalpha():
                raise ValueError("currency")
            zone = str(details["ianaTimezone"])
            ZoneInfo(zone)
            name = str(details["name"])[:255]
        except (ValueError, KeyError, TypeError, ZoneInfoNotFoundError):
            raise ShopifyError("shopify_store_verification_failed") from None
        row = self.get(workspace_id, lock=True)
        if row and row.shop_domain != shop:
            raise ShopifyError("disconnect_existing_store_first")
        if row is None:
            row = ShopifyConnection(workspace_id=workspace_id, shop_domain=shop)
            self.session.add(row)
        row.shop_name, row.currency_code, row.time_zone = name, currency, zone
        row.status = "connected"
        row.encrypted_credentials = Vault(self.settings).seal(workspace_id, shop, bundle)
        row.connected_at, row.error_code, row.next_attempt_at = now, None, None
        row.window_start, row.window_end, row.cursor = None, None, None
        self.session.add(
            ShopifyAudit(workspace_id=workspace_id, action="connected", actor_role=role)
        )
        bind_shopify(self.session, row)
        try:
            self.session.commit()
        except IntegrityError:
            self.session.rollback()
            raise ShopifyError("store_already_connected") from None
        return row

    def access_token(self, row: ShopifyConnection, now: datetime) -> str:
        vault = Vault(self.settings)
        bundle = vault.open(row.workspace_id, row.shop_domain, row.encrypted_credentials)
        expiry = bundle.get("expires_at")
        if expiry and utc(datetime.fromisoformat(expiry)) <= now + timedelta(minutes=5):
            response = self.client.token(row.shop_domain, refresh=bundle.get("refresh_token"))
            bundle = credentials(response, now, bundle)
            row.encrypted_credentials = vault.seal(row.workspace_id, row.shop_domain, bundle)
            # The caller holds the connection row lock until the page transaction commits.
            self.session.flush()
        return str(bundle["access_token"])

    def disconnect(self, workspace_id: int, role: str) -> None:
        row = self.get(workspace_id, lock=True)
        if row:
            revoke_native_integration(self.session, row.workspace_integration_id)
            self.session.delete(row)  # Cascades imported facts and encrypted authorization.
        self.session.execute(
            delete(ShopifyOAuthState)
            .execution_options(synchronize_session="fetch")
            .where(ShopifyOAuthState.workspace_id == workspace_id)
        )
        self.session.add(
            ShopifyAudit(
                workspace_id=workspace_id, action="disconnected_and_purged", actor_role=role
            )
        )
        self.session.commit()
