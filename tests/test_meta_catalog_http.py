from datetime import timedelta
from typing import Any

import httpx
import pytest
from app.collectors.meta_catalog import MetaCatalogContext, MetaCatalogHTTP, MetaCatalogUnavailable
from app.publication.social_catalog import MetaConfigurationProfile
from pydantic import SecretStr

from tests.test_provider_publication_contracts import NOW
from tests.test_social_customer_catalog import request


def profile() -> MetaConfigurationProfile:
    return MetaConfigurationProfile(
        profile_id="explicit_contract_case",
        label="Website purchases",
        currency="USD",
        currency_exponent=2,
        language_locale_ids={k: 1000 + i for i, k in enumerate(request().languages)},
        attribution=[{"event_type": "CLICK_THROUGH", "window_days": 7}],
        age_min=18,
        age_max=65,
        dsa_required=True,
        url_tags="",
    )


class Server:
    def __init__(self, change: str = "") -> None:
        self.change = change
        self.calls: list[httpx.Request] = []

    def __call__(self, req: httpx.Request) -> httpx.Response:
        self.calls.append(req)
        assert req.method == "GET" and req.url.host == "graph.facebook.com"
        assert req.headers["authorization"] == "Bearer offline-fixture"
        assert req.headers["accept-encoding"] == "identity"
        assert len(req.url.params["appsecret_proof"]) == 64
        if self.change == "redirect":
            return httpx.Response(302, headers={"location": "https://attacker.invalid/"})
        if self.change == "timeout":
            raise httpx.ReadTimeout("private-response")
        if self.change == "large":
            return httpx.Response(200, content=b"x" * 1_000_001)
        if self.change == "compressed":
            return httpx.Response(200, headers={"Content-Encoding": "unknown"}, content=b"x")
        if req.url.path.endswith("adspixels"):
            return httpx.Response(200, json={"data": [{"id": "81", "name": "Store pixel"}]})
        if req.url.path.endswith("promote_pages"):
            data: dict[str, Any] = {
                "data": [
                    {"id": "71" if "after" not in req.url.params else "72", "name": "Store page"}
                ]
            }
            if "after" not in req.url.params or self.change == "cycle":
                data["paging"] = {
                    "next": "https://attacker.invalid/do-not-follow",
                    "cursors": {"after": "safe-cursor"},
                }
            if self.change == "duplicate":
                data["data"].append(data["data"][0])
            if self.change == "bad_name":
                data["data"][0]["name"] = "private\nvalue"
            return httpx.Response(200, json=data)
        assert req.url.params["fields"] == "account_id,currency,timezone_name,account_status"
        return httpx.Response(
            200,
            json={
                "account_id": "999"
                if self.change == "foreign"
                else request().account.external_advertiser_id,
                "currency": "USD",
                "timezone_name": "UTC",
                "account_status": 2 if self.change == "disabled" else 1,
            },
        )


def reader(server: Server, **kwargs: Any) -> MetaCatalogHTTP:
    def context(r: Any, now: Any) -> MetaCatalogContext:
        return MetaCatalogContext(
            account=r.account,
            request_digest="f" * 64 if kwargs.get("bad_context") else r.digest(),
            expires_at=NOW + timedelta(seconds=60),
            access_token=SecretStr("offline-fixture"),
            app_secret=SecretStr("offline-secret"),
        )

    return MetaCatalogHTTP(
        context,
        [profile()],
        transport=httpx.MockTransport(server),
        clock=kwargs.get("clock", lambda: NOW),
    )


def test_actual_scoped_http_pagination_named_opaque_choices() -> None:
    server = Server()
    port = reader(server)
    assert not server.calls
    c = port(request(), NOW)
    assert len(c.options) == 2 and len(server.calls) == 4
    assert c.options[0].identifier(request()) != c.options[1].identifier(request())
    assert c.qualification_blockers and c.discovery_evidence == "meta_account_edges"
    assert server.calls[2].url.params["after"] == "safe-cursor"


@pytest.mark.parametrize(
    "change",
    [
        "foreign",
        "disabled",
        "duplicate",
        "cycle",
        "bad_name",
        "redirect",
        "timeout",
        "large",
        "compressed",
    ],
)
def test_fail_closed_without_retry_or_external_cursor_url(change: str) -> None:
    server = Server(change)
    with pytest.raises(MetaCatalogUnavailable) as error:
        reader(server)(request(), NOW)
    assert "private" not in str(error.value)
    assert len(server.calls) <= 4


def test_exact_context_and_expiry_checked_before_io() -> None:
    server = Server()
    with pytest.raises(MetaCatalogUnavailable):
        reader(server, bad_context=True)(request(), NOW)
    with pytest.raises(MetaCatalogUnavailable):
        reader(server, clock=lambda: NOW + timedelta(seconds=61))(request(), NOW)
    assert not server.calls
