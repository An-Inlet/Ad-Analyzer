import json
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from typing import Any
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from app.settings import settings
from app.sources.contracts import ProviderName, UnavailableSource, get_source_transport
from app.tiktok.http import TikTokHTTPRead, TikTokReadError
from pydantic import SecretStr

NOW = datetime(2026, 10, 6, tzinfo=UTC)
DAY = date(2026, 10, 5)
A = "123456"
META = {"advertiser_id": A, "name": "Fixture", "currency": "USD", "timezone": "UTC"}


def adapter(handler: Callable[[httpx.Request], httpx.Response]) -> TikTokHTTPRead:
    return TikTokHTTPRead(
        "1234",
        SecretStr("fixture-secret"),
        transport=httpx.MockTransport(handler),
        clock=lambda: NOW,
    )


def response(data: Any) -> httpx.Response:
    return httpx.Response(200, json={"code": 0, "data": data})


def test_factory_is_disabled_and_tiktok_only(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "tiktok_runtime_mode", "disabled")
    assert isinstance(get_source_transport("tiktok_ads"), UnavailableSource)
    monkeypatch.setattr(settings, "tiktok_runtime_mode", "provider_read")
    monkeypatch.setattr(settings, "tiktok_app_id", "1234")
    monkeypatch.setattr(settings, "tiktok_app_secret", SecretStr("fixture-secret"))
    assert isinstance(get_source_transport("tiktok_ads"), TikTokHTTPRead)
    providers: tuple[ProviderName, ...] = ("klaviyo", "hubspot", "omnisend")
    for provider in providers:
        assert isinstance(get_source_transport(provider), UnavailableSource)
    monkeypatch.setattr(settings, "tiktok_app_id", "../../invalid")
    assert isinstance(get_source_transport("tiktok_ads"), UnavailableSource)


@pytest.mark.parametrize("ttl", [None, 3600])
def test_exchange_identity_lifetime_and_headers(ttl: int | None) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "business-api.tiktok.com"
        assert request.extensions["timeout"]["connect"] == 5
        if request.method == "POST":
            body = json.loads(request.content)
            assert body == {
                "app_id": "1234",
                "secret": "fixture-secret",
                "auth_code": "fixture-code",
            }
            data: dict[str, Any] = {"access_token": "fixture-token", "advertiser_ids": [A]}
            if ttl is not None:
                data["expires_in"] = ttl
            return response(data)
        assert request.headers["Access-Token"] == "fixture-token"
        assert json.loads(request.url.params["advertiser_ids"]) == [A]
        assert "secret" not in str(request.url)
        return response({"list": [META]})

    runtime = adapter(handler)
    url = runtime.authorize_url("fixture-state", "https://inlet.example/callback")
    assert urlsplit(url).netloc == "business-api.tiktok.com"
    assert parse_qs(urlsplit(url).query)["state"] == ["fixture-state"]
    grant = runtime.exchange("fixture-code", "https://inlet.example/callback")
    assert grant.accounts[0].external_id == A
    assert grant.expires_at == (NOW + timedelta(seconds=ttl) if ttl else None)


def test_all_read_phases_and_pagination() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.method == "GET"
        assert request.headers["Access-Token"] == "fixture-token"
        if request.url.path.endswith("advertiser/info/"):
            return response({"list": [META]})
        assert request.url.params["advertiser_id"] == A
        page = int(request.url.params["page"])
        path = request.url.path
        rows: list[dict[str, Any]]
        if path.endswith("campaign/get/"):
            rows = [
                {
                    "campaign_id": "1",
                    "campaign_name": "Fixture",
                    "operation_status": "ENABLE",
                    "objective_type": "CONVERSIONS",
                }
            ]
        elif path.endswith("adgroup/get/"):
            rows = [
                {
                    "adgroup_id": "2",
                    "campaign_id": "1",
                    "adgroup_name": "Fixture",
                    "operation_status": "ENABLE",
                }
            ]
        elif path.endswith("ad/get/"):
            rows = [
                {
                    "ad_id": "3",
                    "adgroup_id": "2",
                    "ad_name": "Fixture",
                    "operation_status": "ENABLE",
                }
            ]
        else:
            dims = json.loads(request.url.params["dimensions"])
            assert json.loads(request.url.params["enable_total_metrics"]) is False
            assert json.loads(request.url.params["metrics"]) == [
                "impressions",
                "clicks",
                "spend",
                "conversion",
            ]
            rows = [
                {
                    "dimensions": {dims[0]: "1", "stat_time_day": DAY.isoformat()},
                    "metrics": {
                        "impressions": "100",
                        "clicks": "10",
                        "spend": "12.34",
                        "conversion": "1.5",
                    },
                }
            ]
        return response(
            {
                "list": rows,
                "page_info": {
                    "page": page,
                    "total_page": 2 if path.endswith("campaign/get/") else 1,
                },
            }
        )

    runtime, cursor, pages = adapter(handler), None, []
    for _ in range(7):
        result = runtime.read(A, "fixture-token", DAY, DAY, cursor)
        cursor = result["next_cursor"]
        pages.append(result)
    assert cursor is None
    assert pages[0]["next_cursor"] == "campaigns:2"
    assert pages[-1]["metrics"][0]["cost_micros"] == 12340000
    assert pages[-1]["metrics"][0]["conversions"] == "1.5"
    assert pages[-1]["metrics"][0]["conversion_value_micros"] == 0
    assert len(requests) == 14


@pytest.mark.parametrize("metadata", [[{**META, "advertiser_id": "999"}], [], [META, META]])
def test_exchange_rejects_missing_duplicate_foreign_advertisers(metadata: Any) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return response(
            {"access_token": "fixture-token", "advertiser_ids": [A]}
            if request.method == "POST"
            else {"list": metadata}
        )

    with pytest.raises(TikTokReadError):
        adapter(handler).exchange("fixture-code", "https://inlet.example/callback")


@pytest.mark.parametrize("ttl", [0, -1, "3600", True, 40000000])
def test_invalid_lifetime(ttl: Any) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return response(
            {"access_token": "fixture-token", "advertiser_ids": [A], "expires_in": ttl}
            if request.method == "POST"
            else {"list": [META]}
        )

    with pytest.raises(TikTokReadError):
        adapter(handler).exchange("fixture", "https://inlet.example/callback")


@pytest.mark.parametrize("status", [302, 401, 403, 429, 500])
def test_http_errors_sanitized(status: int) -> None:
    with pytest.raises(TikTokReadError) as error:
        adapter(lambda _: httpx.Response(status, text="private-response")).read(
            A, "fixture-token", DAY, DAY, None
        )
    assert "private-response" not in str(error.value)


@pytest.mark.parametrize(
    "body",
    [
        [],
        {"code": 1, "message": "private-response"},
        {"code": False, "data": {}},
        {"code": 0, "data": []},
    ],
)
def test_provider_and_malformed_errors(body: Any) -> None:
    with pytest.raises(TikTokReadError):
        adapter(lambda _: httpx.Response(200, json=body)).read(A, "fixture-token", DAY, DAY, None)


def test_timeout_size_and_nonread_endpoint() -> None:
    def timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("private-response", request=request)

    for handler in (timeout, lambda _: httpx.Response(200, content=b"x" * 2000001)):
        with pytest.raises(TikTokReadError):
            adapter(handler).read(A, "fixture-token", DAY, DAY, None)
    with pytest.raises(TikTokReadError):
        adapter(timeout)._http("POST", "/open_api/v1.3/campaign/update/", {}, "fixture-token")


@pytest.mark.parametrize("cursor", ["ads:0", "ads:101", "bad:1", "ads:../../x"])
def test_invalid_cursor_without_io(cursor: str) -> None:
    def no_io(_: httpx.Request) -> httpx.Response:
        pytest.fail("Invalid cursor must not invoke HTTP")

    with pytest.raises(TikTokReadError):
        adapter(no_io).read(A, "fixture-token", DAY, DAY, cursor)


@pytest.mark.parametrize("phase", ["campaigns", "groups", "ads"])
def test_foreign_advertiser_rejected_at_each_inventory_level(phase: str) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("advertiser/info/"):
            return response({"list": [META]})
        return response(
            {"list": [{"advertiser_id": "999"}], "page_info": {"page": 1, "total_page": 1}}
        )

    with pytest.raises(TikTokReadError):
        adapter(handler).read(A, "fixture-token", DAY, DAY, phase + ":1")


@pytest.mark.parametrize(
    "info",
    [
        {"page": True, "total_page": 1},
        {"page": 2, "total_page": 1},
        {"page": 1, "total_page": 101},
        {"page": 1, "total_page": "1"},
    ],
)
def test_invalid_pagination(info: dict[str, Any]) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return response(
            {"list": [META]}
            if request.url.path.endswith("advertiser/info/")
            else {"list": [], "page_info": info}
        )

    with pytest.raises(TikTokReadError):
        adapter(handler).read(A, "fixture-token", DAY, DAY, None)
