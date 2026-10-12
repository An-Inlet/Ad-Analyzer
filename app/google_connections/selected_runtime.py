"""Opt-in customer reporting composition; existing grants, read endpoints only."""

import re
from datetime import UTC, datetime
from urllib.parse import parse_qs

import httpx
from fastapi import HTTPException

from app.database.session import SessionLocal
from app.google_connections.http import GoogleHTTPRead
from app.google_connections.security import Vault
from app.google_connections.selected_customer import SelectedCustomerRuntime
from app.settings import Settings, settings


def available(config: Settings) -> bool:
    if (
        not config.customer_google_reporting_enabled
        or config.google_customer_runtime_mode != "google_read"
        or config.google_customer_api_version != "v24"
        or not config.google_customer_client_id
        or not config.google_customer_client_secret
        or not config.google_customer_client_secret.get_secret_value()
        or not config.google_customer_developer_token
        or not config.google_customer_developer_token.get_secret_value()
    ):
        return False
    try:
        Vault(config)
        return True
    except HTTPException:
        return False


def network_transport() -> httpx.BaseTransport:
    return httpx.HTTPTransport(retries=0, trust_env=False)


class ReportingTransport(httpx.BaseTransport):
    """Lazy owned transport; each enclosing Client closes its current inner transport."""

    def __init__(self, config: Settings) -> None:
        self.config = config
        self.inner: httpx.BaseTransport | None = None

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        url = request.url
        if (
            not available(self.config)
            or request.method != "POST"
            or url.scheme != "https"
            or url.port not in {None, 443}
            or url.userinfo
            or url.fragment
            or url.query
        ):
            raise ValueError("google_reporting_read_unavailable")
        if url.host == "oauth2.googleapis.com" and url.path == "/token":
            if len(request.content) > 65536:
                raise ValueError("google_reporting_read_unavailable")
            try:
                fields = parse_qs(
                    request.content.decode("ascii"),
                    strict_parsing=True,
                    keep_blank_values=True,
                    max_num_fields=4,
                )
            except ValueError:
                raise ValueError("google_reporting_read_unavailable") from None
            if (
                set(fields) != {"client_id", "client_secret", "grant_type", "refresh_token"}
                or any(len(v) != 1 or not v[0] for v in fields.values())
                or fields["grant_type"] != ["refresh_token"]
            ):
                raise ValueError("google_reporting_read_unavailable")
        elif not (
            url.host == "googleads.googleapis.com"
            and re.fullmatch(r"/v24/customers/[0-9]{10}/googleAds:search", url.path)
        ):
            raise ValueError("google_reporting_read_unavailable")
        if self.inner is None:
            self.inner = network_transport()
        return self.inner.handle_request(request)

    def close(self) -> None:
        inner, self.inner = self.inner, None
        if inner is not None:
            inner.close()


def configured_runtime() -> SelectedCustomerRuntime | None:
    if not available(settings):
        return None
    assert settings.google_customer_client_secret is not None
    return SelectedCustomerRuntime(
        SessionLocal,
        GoogleHTTPRead(
            settings.google_customer_client_id,
            settings.google_customer_client_secret,
            settings.google_customer_developer_token,
            "v24",
            transport=ReportingTransport(settings),
        ),
        Vault(settings),
        lambda: ReportingTransport(settings),
        lambda: datetime.now(UTC),
        lambda: available(settings),
    )
