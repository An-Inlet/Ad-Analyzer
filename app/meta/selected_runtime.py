"""Explicit read-only composition over existing Meta credentials; disabled by default."""

import re
from datetime import UTC, datetime

import httpx

from app.meta.security import MetaError, Vault
from app.meta.selected_customer import MetaCustomerRuntime
from app.settings import Settings, settings


def available(config: Settings) -> bool:
    if not config.customer_meta_reporting_enabled or not config.meta_enabled:
        return False
    try:
        Vault(config)
        return bool(config.meta_client_secret and config.meta_client_secret.get_secret_value())
    except (ValueError, MetaError):
        return False


def network_transport() -> httpx.BaseTransport:
    """Only invoked by an authorized capture after opt-in and configuration checks."""
    return httpx.HTTPTransport(retries=0, trust_env=False)


class CountReadTransport(httpx.BaseTransport):
    def __init__(self, config: Settings) -> None:
        if not available(config):
            raise ValueError("meta_reporting_runtime_unavailable")
        self.config = config
        self.inner = network_transport()

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        url = request.url
        if (
            not available(self.config)
            or request.method != "GET"
            or url.scheme != "https"
            or url.host != "graph.facebook.com"
            or url.port not in {None, 443}
            or url.userinfo
            or url.fragment
            or re.fullmatch(r"/v26\.0/act_[0-9]{1,32}(?:/insights)?", url.path) is None
        ):
            raise ValueError("meta_reporting_read_unavailable")
        return self.inner.handle_request(request)

    def close(self) -> None:
        self.inner.close()


def configured_runtime() -> MetaCustomerRuntime | None:
    if not available(settings):
        return None
    return MetaCustomerRuntime(
        settings,
        lambda: CountReadTransport(settings),
        lambda: datetime.now(UTC),
        lambda: available(settings),
    )
