import hashlib
import hmac
import json
import re
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlsplit

from cryptography.fernet import Fernet, InvalidToken

from app.settings import Settings

API_VERSION = "v26.0"
SCOPES = frozenset({"ads_read"})
CONVERSION_ACTIONS = {
    "": "Spend and traffic only — no conversion event selected",
    "lead": "Meta-reported leads",
    "purchase": "Meta-reported purchases",
    "offsite_conversion.fb_pixel_lead": "Website leads",
    "offsite_conversion.fb_pixel_purchase": "Website purchases",
}
PURCHASE_ACTIONS = frozenset({"purchase", "offsite_conversion.fb_pixel_purchase"})


class MetaError(RuntimeError):
    def __init__(self, code: str = "meta_unavailable", *, retry_after: int = 60) -> None:
        self.code = code
        self.retry_after = max(30, min(retry_after, 3600))
        super().__init__(code)


def utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def identifier(value: object) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{1,32}", value):
        raise MetaError("meta_invalid_response")
    return value


def configuration_ready(settings: Settings) -> bool:
    try:
        if not settings.meta_enabled or not re.fullmatch(r"[0-9]{5,32}", settings.meta_client_id):
            return False
        uri = urlsplit(settings.meta_redirect_uri)
        if (
            uri.scheme != "https"
            or not uri.hostname
            or uri.username
            or uri.password
            or uri.query
            or uri.fragment
            or uri.port not in {None, 443}
            or uri.path != "/dashboard/meta/callback"
        ):
            return False
        Vault(settings)
        return bool(
            settings.meta_client_secret
            and len(settings.meta_client_secret.get_secret_value()) >= 16
        )
    except (ValueError, MetaError):
        return False


class Vault:
    def __init__(self, settings: Settings) -> None:
        if not settings.meta_token_encryption_key:
            raise MetaError("meta_configuration_required")
        try:
            key = settings.meta_token_encryption_key.get_secret_value().encode()
            self._cipher = Fernet(key)
            self._hash_key = hashlib.sha256(b"meta-state-binding\0" + key).digest()
        except ValueError:
            raise MetaError("meta_configuration_required") from None

    def digest(self, namespace: str, value: str) -> str:
        return hmac.new(
            self._hash_key, (namespace + "\0" + value).encode(), hashlib.sha256
        ).hexdigest()

    def seal(self, workspace_id: int, context: str, bundle: dict[str, Any]) -> str:
        return self._cipher.encrypt(
            json.dumps(
                {"workspace_id": workspace_id, "context": context, "bundle": bundle}
            ).encode()
        ).decode()

    def open(self, workspace_id: int, context: str, ciphertext: str) -> dict[str, Any]:
        try:
            data = json.loads(self._cipher.decrypt(ciphertext.encode()))
            if data["workspace_id"] != workspace_id or data["context"] != context:
                raise ValueError("context")
            return dict(data["bundle"])
        except (InvalidToken, ValueError, KeyError, TypeError):
            raise MetaError("meta_reconnect_required") from None


def callback_values(pairs: list[tuple[str, str]]) -> dict[str, str]:
    if len(pairs) != len({k for k, _v in pairs}) or sum(len(k) + len(v) for k, v in pairs) > 8192:
        raise MetaError("invalid_oauth_callback")
    values = dict(pairs)
    if values.get("error") or not re.fullmatch(r"[A-Za-z0-9_-]{32,128}", values.get("state", "")):
        raise MetaError("invalid_oauth_callback")
    if not 1 <= len(values.get("code", "")) <= 4096:
        raise MetaError("invalid_oauth_callback")
    return values
