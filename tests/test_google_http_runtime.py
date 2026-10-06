import json
from collections.abc import Callable
from datetime import date
from typing import Any
from urllib.parse import parse_qs

import httpx
import pytest
from app.google_connections.contracts import UnavailableTransport, get_transport
from app.google_connections.http import GoogleHTTPRead, GoogleReadError
from app.settings import settings
from pydantic import SecretStr

A, M = "1234567890", "9999999999"
DAY = date(2026, 1, 1)
TOKEN = {
    "access_token": "fixture-access",
    "token_type": "Bearer",
    "refresh_token": "fixture-refresh",
}


def runtime(handler: Callable[[httpx.Request], httpx.Response]) -> GoogleHTTPRead:
    return GoogleHTTPRead(
        "fixture-client",
        SecretStr("fixture-secret"),
        SecretStr("fixture-developer"),
        "v25",
        transport=httpx.MockTransport(handler),
    )


def test_disabled_factory_and_explicit_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "google_customer_runtime_mode", "disabled")
    assert isinstance(get_transport(), UnavailableTransport)
    monkeypatch.setattr(settings, "google_customer_runtime_mode", "google_read")
    monkeypatch.setattr(settings, "google_customer_client_id", "fixture-client")
    monkeypatch.setattr(settings, "google_customer_client_secret", SecretStr("fixture-secret"))
    monkeypatch.setattr(settings, "google_customer_developer_token", SecretStr("fixture-developer"))
    monkeypatch.setattr(settings, "google_customer_api_version", "v25")
    assert isinstance(get_transport(), GoogleHTTPRead)
    monkeypatch.setattr(settings, "google_customer_api_version", "")
    assert isinstance(get_transport(), UnavailableTransport)


def test_manager_discovery_and_token_exchange() -> None:
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.extensions["timeout"]["connect"] == 5
        if request.url.host == "oauth2.googleapis.com":
            form = parse_qs(request.content.decode())
            assert form["grant_type"] == ["authorization_code"]
            assert form["redirect_uri"] == ["https://app.example/callback"]
            return httpx.Response(200, json=TOKEN)
        assert request.headers["developer-token"] == "fixture-developer"
        assert request.headers["Authorization"] == "Bearer fixture-access"
        if request.method == "GET":
            return httpx.Response(200, json={"resourceNames": [f"customers/{M}"]})
        query = json.loads(request.content)["query"]
        if "customer_client" in query:
            return httpx.Response(200, json={"results": [{"customerClient": {"id": A}}]})
        manager = M in request.url.path
        if not manager:
            assert request.headers["login-customer-id"] == M
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "customer": {
                            "id": M if manager else A,
                            "manager": manager,
                            "descriptiveName": "Fixture",
                            "currencyCode": "USD",
                            "timeZone": "UTC",
                        }
                    }
                ]
            },
        )

    grant = runtime(handler).exchange("fixture-code", "https://app.example/callback")
    assert len(requests) == 5
    assert grant.accounts[0].external_id == A
    assert grant.accounts[0].login_customer_id == M
    assert grant.refresh_token.get_secret_value() == "fixture-refresh"


def test_pagination_refresh_zero_metrics_and_micros() -> None:
    queries = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "oauth2.googleapis.com":
            assert parse_qs(request.content.decode())["grant_type"] == ["refresh_token"]
            return httpx.Response(200, json=TOKEN)
        assert request.headers["login-customer-id"] == M
        body = json.loads(request.content)
        queries.append(body)
        if "segments.date" in body["query"]:
            return httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "campaign": {"id": "1"},
                            "segments": {"date": DAY.isoformat()},
                            "metrics": {"conversions": 10, "conversionsValue": 12.34},
                        }
                    ]
                },
            )
        row = {
            "campaign": {
                "id": "1",
                "name": "Fixture",
                "status": "ENABLED",
                "advertisingChannelType": "SEARCH",
                "resourceName": f"customers/{A}/campaigns/1",
            }
        }
        return httpx.Response(
            200,
            json={
                "results": [row] * (10000 if not body["pageToken"] else 1),
                "nextPageToken": "next" if not body["pageToken"] else "",
            },
        )

    adapter = runtime(handler)
    first = adapter.page("fixture-refresh", A, DAY, DAY, None, M)
    assert len(first.campaigns) == 10000
    second = adapter.page("fixture-refresh", A, DAY, DAY, first.next_cursor, M)
    assert queries[0]["query"] == queries[1]["query"]
    assert queries[1]["pageToken"] == "next"
    final = adapter.page("fixture-refresh", A, DAY, DAY, second.next_cursor, M)
    assert final.next_cursor is None
    assert final.metrics[0].conversions == "10.000000"
    assert final.metrics[0].conversion_value_micros == 12340000
    assert final.metrics[0].clicks == 0


@pytest.mark.parametrize("status", [301, 400, 401, 403, 429, 500])
def test_provider_errors_sanitized(status: int) -> None:
    with pytest.raises(GoogleReadError) as error:
        runtime(lambda _: httpx.Response(status, text="private-response")).page(
            "fixture-refresh", A, DAY, DAY, None
        )
    assert "private-response" not in str(error.value)


@pytest.mark.parametrize("body", [[], {"access_token": "x"}, {**TOKEN, "scope": "wrong"}])
def test_invalid_token_response(body: Any) -> None:
    with pytest.raises(GoogleReadError):
        runtime(lambda _: httpx.Response(200, json=body)).page("fixture-refresh", A, DAY, DAY, None)


def test_timeout_and_size() -> None:
    def timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("private-response", request=request)

    for handler in [timeout, lambda _: httpx.Response(200, content=b"x" * 8000001)]:
        with pytest.raises(GoogleReadError):
            runtime(handler).page("fixture-refresh", A, DAY, DAY, None)


@pytest.mark.parametrize("cursor", ["wrong:", "campaigns:%%%", "x" * 4097])
def test_invalid_cursor_before_network(cursor: str) -> None:
    def unexpected(_: httpx.Request) -> httpx.Response:
        pytest.fail("Network must not be attempted")

    with pytest.raises(GoogleReadError):
        runtime(unexpected).page("fixture-refresh", A, DAY, DAY, cursor)


def test_wrong_account_rejected() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "oauth2.googleapis.com":
            return httpx.Response(200, json=TOKEN)
        return httpx.Response(
            200, json={"results": [{"campaign": {"resourceName": f"customers/{M}/campaigns/1"}}]}
        )

    with pytest.raises(GoogleReadError, match="account_mismatch"):
        runtime(handler).page("fixture-refresh", A, DAY, DAY, None)


@pytest.mark.parametrize(
    "payload",
    [
        {"results": {}, "nextPageToken": ""},
        {"results": [], "nextPageToken": "x" * 3001},
        {"results": [], "nextPageToken": "repeat"},
        {"results": [{"campaign": None}]},
    ],
)
def test_malformed_or_repeated_page(payload: dict[str, Any]) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json=TOKEN if request.url.host == "oauth2.googleapis.com" else payload
        )

    with pytest.raises(GoogleReadError):
        runtime(handler).page("fixture-refresh", A, DAY, DAY, "campaigns:cmVwZWF0")


def test_missing_refresh_token_requires_new_consent() -> None:
    with pytest.raises(GoogleReadError, match="fresh_consent"):
        runtime(
            lambda _: httpx.Response(200, json={"access_token": "fixture", "token_type": "Bearer"})
        ).exchange("fixture", "https://app.example/callback")
