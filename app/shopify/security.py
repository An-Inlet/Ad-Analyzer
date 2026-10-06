import hashlib
import hmac
import json
import re
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlsplit

from cryptography.fernet import Fernet, InvalidToken

from app.settings import Settings

SCOPES = frozenset({"read_orders", "read_products"})
API_VERSION = "2026-07"


class ShopifyError(RuntimeError):
    def __init__(self, code: str = "shopify_unavailable", *, retry_after: int = 60) -> None:
        self.code = code
        self.retry_after = max(30, min(retry_after, 3600))
        super().__init__(code)


def utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def shop_domain(value: str) -> str:
    value = value.strip().lower()
    if not re.fullmatch(
        r"[a-z0-9][a-z0-9-]{0,61}[a-z0-9]\.myshopify\.com|[a-z0-9]\.myshopify\.com", value
    ):
        raise ShopifyError("invalid_shop_domain")
    return value


def customer_redirect_uri(settings: Settings) -> str:
    origin = urlsplit(settings.customer_app_origin)
    if (
        origin.scheme != "https"
        or not origin.hostname
        or origin.username
        or origin.password
        or origin.path
        or origin.query
        or origin.fragment
    ):
        raise ShopifyError("shopify_configuration_required")
    return settings.customer_app_origin + "/api/customer/v1/shopify/callback"


def configuration_ready(settings: Settings, *, customer: bool = False) -> bool:
    try:
        if not settings.shopify_enabled or not re.fullmatch(
            r"[a-zA-Z0-9_-]{8,128}", settings.shopify_client_id
        ):
            return False
        if customer and not settings.shopify_customer_enabled:
            return False
        uri = urlsplit(
            customer_redirect_uri(settings) if customer else settings.shopify_redirect_uri
        )
        if (
            uri.scheme != "https"
            or not uri.hostname
            or uri.username
            or uri.password
            or uri.query
            or uri.fragment
        ):
            return False
        expected_path = (
            "/api/customer/v1/shopify/callback" if customer else "/dashboard/shopify/callback"
        )
        if uri.path != expected_path:
            return False
        if not re.fullmatch(
            r"projects/[a-zA-Z0-9_.:-]+/subscriptions/[a-zA-Z0-9_.-]+",
            settings.shopify_webhook_subscription,
        ):
            return False
        Vault(settings)
        return bool(
            settings.shopify_client_secret
            and len(settings.shopify_client_secret.get_secret_value()) >= 16
        )
    except (ValueError, ShopifyError):
        return False


class Vault:
    def __init__(self, settings: Settings) -> None:
        if not settings.shopify_token_encryption_key or not settings.shopify_identifier_hash_key:
            raise ShopifyError("shopify_configuration_required")
        try:
            self._cipher = Fernet(settings.shopify_token_encryption_key.get_secret_value().encode())
            self._hash_key = settings.shopify_identifier_hash_key.get_secret_value().encode()
            if len(self._hash_key) < 32:
                raise ValueError("invalid key")
        except ValueError:
            raise ShopifyError("shopify_configuration_required") from None

    def digest(self, namespace: str, value: str) -> str:
        return hmac.new(
            self._hash_key, (namespace + "\0" + value).encode(), hashlib.sha256
        ).hexdigest()

    def seal(self, workspace_id: int, shop: str, credentials: dict[str, Any]) -> str:
        raw = json.dumps({"workspace_id": workspace_id, "shop": shop, "credentials": credentials})
        return self._cipher.encrypt(raw.encode()).decode()

    def open(self, workspace_id: int, shop: str, value: str) -> dict[str, Any]:
        try:
            data = json.loads(self._cipher.decrypt(value.encode()))
            if data["workspace_id"] != workspace_id or data["shop"] != shop:
                raise ValueError("wrong context")
            return dict(data["credentials"])
        except (InvalidToken, ValueError, KeyError, TypeError):
            raise ShopifyError("shopify_credentials_unavailable") from None


def verify_callback(pairs: list[tuple[str, str]], secret: str, now: datetime) -> dict[str, str]:
    if len(pairs) != len({k for k, _v in pairs}) or sum(len(k) + len(v) for k, v in pairs) > 8192:
        raise ShopifyError("invalid_oauth_callback")
    values = dict(pairs)
    try:
        signature = values.pop("hmac")
        message = "&".join(f"{k}={values[k]}" for k in sorted(values))
        expected = hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, signature):
            raise ValueError("signature")
        if abs(now.timestamp() - int(values["timestamp"])) > 600:
            raise ValueError("expired")
        if not values["code"] or not re.fullmatch(r"[a-zA-Z0-9_-]{32,128}", values["state"]):
            raise ValueError("invalid")
        values["shop"] = shop_domain(values["shop"])
        return values
    except (KeyError, ValueError, TypeError):
        raise ShopifyError("invalid_oauth_callback") from None
