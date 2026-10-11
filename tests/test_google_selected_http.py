"""MockHTTP acquisition; no native/provider capability or customer API qualification."""

import json
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from app.campaign_performance.selected_contracts import capture_request_digest
from app.google_connections.selected_http import (
    GoogleSelectedHTTPRead,
    GoogleSelectedReadUnavailable,
    SelectedGoogleContext,
)
from pydantic import SecretStr

from tests.test_selected_raw_observations import google_request, google_row

NOW = datetime(2026, 10, 1, 12, 1, tzinfo=UTC)


def context() -> SelectedGoogleContext:
    return SelectedGoogleContext(
        request_digest=capture_request_digest(google_request()),
        expires_at=NOW + timedelta(minutes=2),
        access_token=SecretStr("fixture-access-not-real"),
        developer_token=SecretStr("fixture-developer-not-real"),
    )


def response(query: str) -> dict[str, Any]:
    if "FROM customer" in query:
        return dict(
            results=[
                dict(
                    customer=dict(
                        id="1234567890",
                        resourceName="customers/1234567890",
                        currencyCode="USD",
                        timeZone="America/New_York",
                    )
                )
            ]
        )
    if "FROM conversion_action" in query:
        return dict(
            results=[
                dict(
                    conversionAction=dict(
                        resourceName="customers/1234567890/conversionActions/123",
                        ownerCustomer="customers/1234567890",
                    )
                )
            ]
        )
    return {"results": [google_row()]}


def test_actual_search_only_requests_and_exact_raw_value() -> None:
    requests = []
    checkpoints = []

    def handle(req: httpx.Request) -> httpx.Response:
        requests.append(req)
        assert req.method == "POST" and req.url.path == "/v24/customers/1234567890/googleAds:search"
        query = json.loads(req.content)["query"]
        body = json.dumps(response(query)).replace('"10"', "0.123456")
        return httpx.Response(200, content=body.encode())

    reader = GoogleSelectedHTTPRead(
        lambda req: context(),
        lambda req: checkpoints.append(req.capture_id),
        transport=httpx.MockTransport(handle),
        clock=lambda: NOW,
    )
    page = reader(google_request(), {"555": 5})
    assert str(page.facts[0].selected_conversions.value) == "0.123456"
    assert len(requests) == 3 and len(checkpoints) == 8
    query = json.loads(requests[-1].content)["query"]
    assert "metrics.conversions, metrics.conversions_value" in query
    assert "segments.date BETWEEN '2026-09-29' AND '2026-09-30'" in query
    assert "segments.conversion_action = 'customers/1234567890/conversionActions/123'" in query


@pytest.mark.parametrize(
    "kind", ["currency", "timezone", "owner", "account", "pagination", "empty_metadata"]
)
def test_metadata_disagreement_cannot_relabel_request(kind: str) -> None:
    calls = []

    def handle(req: httpx.Request) -> httpx.Response:
        query = json.loads(req.content)["query"]
        calls.append(query)
        body = response(query)
        if "FROM customer" in query:
            if kind == "currency":
                body["results"][0]["customer"]["currencyCode"] = "EUR"
            if kind == "timezone":
                body["results"][0]["customer"]["timeZone"] = "UTC"
            if kind == "account":
                body["results"][0]["customer"]["id"] = "9999999999"
            if kind == "pagination":
                body["nextPageToken"] = "unexpected"
            if kind == "empty_metadata":
                body["results"] = []
        if kind == "owner" and "FROM conversion_action" in query:
            body["results"][0]["conversionAction"]["ownerCustomer"] = "customers/9999999999"
        return httpx.Response(200, json=body)

    reader = GoogleSelectedHTTPRead(
        lambda req: context(),
        lambda req: None,
        transport=httpx.MockTransport(handle),
        clock=lambda: NOW,
    )
    with pytest.raises(GoogleSelectedReadUnavailable, match="^google_selected_read_unavailable$"):
        reader(google_request(), {"555": 5})
    assert all("FROM campaign" not in query for query in calls)


@pytest.mark.parametrize("status", [301, 400, 401, 403, 429, 500])
def test_http_errors_sanitized_and_not_empty_success(status: int) -> None:
    calls = []

    def handle(req: httpx.Request) -> httpx.Response:
        calls.append(req)
        return httpx.Response(
            status,
            json={"error": "private-fixture-error"},
            headers={"location": "https://example.invalid"},
        )

    reader = GoogleSelectedHTTPRead(
        lambda req: context(),
        lambda req: None,
        transport=httpx.MockTransport(handle),
        clock=lambda: NOW,
    )
    with pytest.raises(GoogleSelectedReadUnavailable, match="^google_selected_read_unavailable$"):
        reader(google_request(), {"555": 5})
    assert len(calls) == 1


def test_expiry_during_io_rejects_before_next_query() -> None:
    clock = [NOW]
    calls = []

    def handle(req: httpx.Request) -> httpx.Response:
        calls.append(req)
        clock[0] = NOW + timedelta(minutes=3)
        return httpx.Response(200, json=response(json.loads(req.content)["query"]))

    reader = GoogleSelectedHTTPRead(
        lambda req: context(),
        lambda req: None,
        transport=httpx.MockTransport(handle),
        clock=lambda: clock[0],
    )
    with pytest.raises(GoogleSelectedReadUnavailable):
        reader(google_request(), {"555": 5})
    assert len(calls) == 1


def test_revalidation_after_io_can_deny_publication() -> None:
    calls = []

    def handle(req: httpx.Request) -> httpx.Response:
        calls.append(req)
        return httpx.Response(200, json=response(json.loads(req.content)["query"]))

    def validate(req: Any) -> None:
        if calls:
            raise ValueError("fixture-session-revoked")

    reader = GoogleSelectedHTTPRead(
        lambda req: context(), validate, transport=httpx.MockTransport(handle), clock=lambda: NOW
    )
    with pytest.raises(GoogleSelectedReadUnavailable):
        reader(google_request(), {"555": 5})
    assert len(calls) == 1


def test_empty_page_still_has_request_provenance() -> None:
    def handle(req: httpx.Request) -> httpx.Response:
        query = json.loads(req.content)["query"]
        return httpx.Response(200, json={} if "FROM campaign" in query else response(query))

    reader = GoogleSelectedHTTPRead(
        lambda req: context(),
        lambda req: None,
        transport=httpx.MockTransport(handle),
        clock=lambda: NOW,
    )
    page = reader(google_request(), {"555": 5})
    assert not page.facts and page.request_digest == capture_request_digest(google_request())


def test_context_mismatch_prevents_any_io_and_secrets_excluded() -> None:
    calls = []
    ctx = context().model_copy(update={"request_digest": "9" * 64})

    def unexpected(req: httpx.Request) -> httpx.Response:
        calls.append(req)
        raise AssertionError("unexpected HTTP request")

    reader = GoogleSelectedHTTPRead(
        lambda req: ctx,
        lambda req: None,
        transport=httpx.MockTransport(unexpected),
        clock=lambda: NOW,
    )
    with pytest.raises(GoogleSelectedReadUnavailable):
        reader(google_request(), {"555": 5})
    assert not calls
    assert "fixture-access" not in repr(ctx) and "fixture-developer" not in ctx.model_dump_json()


@pytest.mark.parametrize("revalidation_number,expected_calls", [(2, 0), (8, 3)])
def test_expiry_inside_revalidation_is_checked_after_callback(
    revalidation_number: int,
    expected_calls: int,
) -> None:
    clock = [NOW]
    checks = []
    calls = []

    def handle(req: httpx.Request) -> httpx.Response:
        calls.append(req)
        return httpx.Response(200, json=response(json.loads(req.content)["query"]))

    def validate(req: Any) -> None:
        checks.append(req.capture_id)
        if len(checks) == revalidation_number:
            clock[0] = NOW + timedelta(minutes=3)

    reader = GoogleSelectedHTTPRead(
        lambda req: context(),
        validate,
        transport=httpx.MockTransport(handle),
        clock=lambda: clock[0],
    )
    with pytest.raises(GoogleSelectedReadUnavailable):
        reader(google_request(), {"555": 5})
    assert len(calls) == expected_calls


def test_trickling_response_stops_and_closes_at_deadline() -> None:
    from collections.abc import Iterator

    clock = [NOW]
    closed = []
    chunks = []

    class Stream(httpx.SyncByteStream):
        def __iter__(self) -> Iterator[bytes]:
            chunks.append(1)
            yield b"{"
            clock[0] = NOW + timedelta(seconds=61)
            chunks.append(2)
            yield b" "
            chunks.append(3)
            yield b"}"

        def close(self) -> None:
            closed.append(True)

    reader = GoogleSelectedHTTPRead(
        lambda req: context(),
        lambda req: None,
        transport=httpx.MockTransport(lambda req: httpx.Response(200, stream=Stream())),
        clock=lambda: clock[0],
    )
    with pytest.raises(GoogleSelectedReadUnavailable):
        reader(google_request(), {"555": 5})
    assert chunks == [1, 2] and closed
