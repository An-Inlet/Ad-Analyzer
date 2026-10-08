"""Default planning policy denies actual transport entrypoints before any HTTP."""

from types import SimpleNamespace
from typing import Any, cast

import httpx
import pytest
from app.advertising_capabilities import AdvertisingWritesDisabled
from app.executors.google_activation import GoogleActivationHTTP
from app.executors.google_optimization import GoogleOptimizationTransport
from app.executors.google_publication import GooglePublicationHTTP
from app.executors.meta_activation import MetaActivationHTTP
from app.executors.meta_optimization import MetaOptimizationTransport
from app.executors.meta_publication import MetaPublicationTransport
from app.executors.tiktok_activation import TikTokActivationHTTP
from app.executors.tiktok_linked_activation import LinkedPushTikTokActivationHTTP
from app.executors.tiktok_linked_publication import LinkedPushTikTokTransport
from app.executors.tiktok_optimization import TikTokOptimizationTransport
from app.executors.tiktok_publication import TikTokPublicationTransport
from app.production_runtime.provider_composition import LazyGoogleHTTP
from pydantic import SecretStr


@pytest.mark.parametrize(
    "adapter",
    [
        GoogleActivationHTTP,
        GoogleOptimizationTransport,
        GooglePublicationHTTP,
        MetaActivationHTTP,
        MetaOptimizationTransport,
        MetaPublicationTransport,
        TikTokActivationHTTP,
        TikTokOptimizationTransport,
        TikTokPublicationTransport,
        LinkedPushTikTokActivationHTTP,
        LinkedPushTikTokTransport,
    ],
)
def test_apply_denies_before_context_or_transport_resolution(adapter: Any) -> None:
    # Invalid sentinels deliberately prove the guard precedes all context/IO work.
    with pytest.raises(AdvertisingWritesDisabled):
        adapter.apply_once(None, None, None, None)


def sinks(transport: httpx.MockTransport) -> dict[str, Any]:
    context: Any = SimpleNamespace(
        access_token=SecretStr("fixture"),
        developer_token=None,
        login_customer_id=None,
        app_secret=None,
        scope=SimpleNamespace(external_advertiser_id="1234567890"),
    )
    request: Any = SimpleNamespace(scope=context.scope)
    google = GooglePublicationHTTP(transport=transport)
    opt = GoogleOptimizationTransport(transport=transport)
    return {
        "google_publication": lambda path, body: google._post(request, context, path, body),
        "google_optimization": lambda path, body: opt.post(context, path, body),
        "meta_publication": lambda method, path, **kw: MetaPublicationTransport(
            cast(Any, None), transport=transport
        ).send(method, path, {}, **kw),
        "meta_optimization": lambda method, path, **kw: MetaOptimizationTransport(
            transport=transport
        ).send(method, path, context, **kw),
        "tiktok_publication": lambda method, path, **kw: TikTokPublicationTransport(
            cast(Any, None), transport=transport
        ).send(method, path, {}, **kw),
        "tiktok_optimization": lambda method, path, **kw: TikTokOptimizationTransport(
            transport=transport
        ).send(method, path, context, **kw),
        "tiktok_linked": lambda method, path, **kw: LinkedPushTikTokTransport(
            cast(Any, None), transport=transport
        ).send(method, path, {}, **kw),
    }


@pytest.mark.parametrize("name", ["google_publication", "google_optimization"])
@pytest.mark.parametrize(
    "path,body",
    [
        ("campaigns:mutate", {"validateOnly": True}),
        ("googleAds:unknown", {}),
        ("googleAds:search", {"query": "SELECT campaign.id FROM campaign", "_method": "POST"}),
    ],
)
def test_google_sink_denies_without_http(name: str, path: str, body: dict[str, Any]) -> None:
    calls: list[Any] = []
    transport = httpx.MockTransport(cast(Any, lambda request: calls.append(request)))
    with pytest.raises(AdvertisingWritesDisabled):
        sinks(transport)[name](path, body)
    assert calls == []


@pytest.mark.parametrize(
    "name",
    [
        "meta_publication",
        "meta_optimization",
        "tiktok_publication",
        "tiktok_optimization",
        "tiktok_linked",
    ],
)
@pytest.mark.parametrize("attack", ["post", "unknown", "override", "body"])
def test_social_sinks_deny_without_http(name: str, attack: str) -> None:
    calls: list[Any] = []
    transport = httpx.MockTransport(cast(Any, lambda request: calls.append(request)))
    path = "/v26.0/123" if name.startswith("meta") else "/open_api/v1.3/campaign/get/"
    kwargs = (
        {"params": {"method": "DELETE"}}
        if attack == "override"
        else {"body": {}}
        if attack == "body"
        else {}
    )
    with pytest.raises(AdvertisingWritesDisabled):
        sinks(transport)[name](
            "POST" if attack == "post" else "GET",
            "/unknown" if attack == "unknown" else path,
            **kwargs,
        )
    assert calls == []


def test_lazy_google_denies_before_resolving_runtime() -> None:
    calls: list[Any] = []
    lazy = LazyGoogleHTTP(cast(Any, lambda: calls.append(True)))
    with pytest.raises(AdvertisingWritesDisabled):
        lazy._post(cast(Any, None), cast(Any, None), "campaigns:mutate", {})
    assert calls == []


@pytest.mark.parametrize(
    "name",
    [
        "google_publication",
        "google_optimization",
        "meta_publication",
        "meta_optimization",
        "tiktok_publication",
        "tiktok_optimization",
        "tiktok_linked",
    ],
)
def test_known_reads_reach_real_mock_http(name: str) -> None:
    calls: list[Any] = []

    def handle(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json={"results": [], "code": 0, "data": {}})

    invoke = sinks(httpx.MockTransport(handle))[name]
    if name.startswith("google"):
        invoke("googleAds:search", {"query": "SELECT campaign.id FROM campaign"})
    else:
        invoke(
            "GET",
            "/v26.0/123" if name.startswith("meta") else "/open_api/v1.3/campaign/get/",
            params={"fields": "id"},
        )
    assert len(calls) == 1
    assert calls[0].method == ("POST" if name.startswith("google") else "GET")


@pytest.mark.parametrize(
    "extra",
    [
        {"headers": {"X-HTTP-Method-Override": "DELETE"}},
        {"form": {"method": "POST"}},
        {"files": {"image": ("fixture", b"fixture", "image/png")}},
    ],
)
def test_social_get_cannot_smuggle_mutation(extra: dict[str, Any]) -> None:
    calls: list[Any] = []
    transport = httpx.MockTransport(cast(Any, lambda request: calls.append(request)))
    http = MetaPublicationTransport(cast(Any, None), transport=transport)
    arguments = {"headers": {}, **extra}
    with pytest.raises(AdvertisingWritesDisabled):
        http.send("GET", "/v26.0/123", **arguments)
    assert calls == []


def test_google_read_cannot_override_path_through_customer_id() -> None:
    calls: list[Any] = []
    http = GooglePublicationHTTP(
        transport=httpx.MockTransport(cast(Any, lambda request: calls.append(request)))
    )
    request: Any = SimpleNamespace(
        scope=SimpleNamespace(external_advertiser_id="123/campaigns:mutate?override=")
    )
    with pytest.raises(AdvertisingWritesDisabled):
        http._post(
            request,
            cast(Any, None),
            "googleAds:search",
            {"query": "SELECT campaign.id FROM campaign"},
        )
    assert calls == []


@pytest.mark.parametrize("campaign", [False, True])
def test_actual_meta_current_read_preserves_account_and_all_status_children(campaign: bool) -> None:
    import json

    from tests.test_provider_publication_contracts import NOW
    from tests.test_social_optimization_http import setup

    adapter, server, request, context = setup("meta_ads", campaign=campaign)
    calls: list[httpx.Request] = []

    def handle(incoming: httpx.Request) -> httpx.Response:
        calls.append(incoming)
        assert incoming.method == "GET"
        return server(incoming)

    adapter.transport = httpx.MockTransport(handle)
    state = adapter.read_current(
        request.intent.scope,
        request.intent.target,
        request.before.money,
        request.intent.qualification_id,
        request.intent.qualification_revision,
        context,
        NOW,
    )
    assert state == request.before
    assert calls[0].url.path == "/v26.0/act_123"
    children = next(call for call in calls if call.url.path == "/v26.0/5/adsets")
    assert "DELETED" in json.loads(children.url.params["effective_status"])
    assert server.posts == []
    # The same now-permitted account endpoint cannot admit a mutation or override.
    for method, params in [("POST", {}), ("GET", {"method": "DELETE"})]:
        before = len(calls)
        with pytest.raises(AdvertisingWritesDisabled):
            adapter.send(method, "/v26.0/act_123", context, params=params)
        assert len(calls) == before
