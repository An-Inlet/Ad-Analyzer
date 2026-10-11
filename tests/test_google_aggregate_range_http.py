"""Actual injected raw Google range parsing; no SQL or provider qualification."""

import json
from collections.abc import Iterator
from datetime import timedelta
from typing import Any

import httpx
import pytest
from app.campaign_performance.aggregate import descriptor
from app.executors.social_http import _private_http
from app.google_connections.range_http import (
    GoogleAggregateRangeHTTP,
    GoogleAggregateRangeRequestV1,
    GoogleAggregateRangeUnavailable,
    GoogleAggregateRangeV1,
)
from app.google_connections.selected_catalog import GoogleReportingCatalogContext
from pydantic import SecretStr, ValidationError

from tests.test_google_reporting_catalog import request as catalog_request
from tests.test_google_selected_http import NOW, response


def request() -> GoogleAggregateRangeRequestV1:
    return GoogleAggregateRangeRequestV1(
        base=catalog_request(), requested_starts_on="2026-08-01", requested_ends_on="2026-09-30"
    )


def campaign(number: str = "1") -> dict[str, Any]:
    return {
        "campaign": {
            "id": number,
            "resourceName": f"customers/1234567890/campaigns/{number}",
            "name": "Observed campaign",
            "status": "PAUSED",
            "advertisingChannelType": "SEARCH",
        }
    }


def metric(number: str = "1", day: str = "2026-09-30") -> dict[str, Any]:
    return {
        "campaign": {"id": number, "resourceName": f"customers/1234567890/campaigns/{number}"},
        "segments": {"date": day},
        "metrics": {
            "impressions": "1000",
            "clicks": "100",
            "costMicros": "100000000",
            "conversions": "10",
            "conversionsValue": "100.123456",
        },
    }


def raw(query: str) -> dict[str, Any]:
    if "FROM customer" in query:
        return response(query)
    return {"results": [metric() if "metrics." in query else campaign()]}


def adapter(
    handle: Any, *, clock: Any = lambda: NOW, validate: Any = lambda r: None, context: Any = None
) -> GoogleAggregateRangeHTTP:
    def ctx(req: Any) -> GoogleReportingCatalogContext:
        return GoogleReportingCatalogContext(
            request_digest=req.digest(),
            expires_at=NOW + timedelta(minutes=5),
            access_token=SecretStr("fixture-access"),
            developer_token=SecretStr("fixture-developer"),
        )

    return GoogleAggregateRangeHTTP(
        context or ctx, validate, transport=httpx.MockTransport(handle), clock=clock
    )


def test_exact_61_day_paginated_queries_and_aggregate_not_selected() -> None:
    calls = []

    def handle(req: httpx.Request) -> httpx.Response:
        assert req.url.path == "/v24/customers/1234567890/googleAds:search" and req.method == "POST"
        assert req.extensions["timeout"]["connect"] == 5
        body = json.loads(req.content)
        calls.append(body)
        query, token = body["query"], body["pageToken"]
        if "FROM customer" in query:
            return httpx.Response(200, json=raw(query))
        if "metrics." in query:
            assert "BETWEEN '2026-08-01' AND '2026-09-30'" in query
            assert "conversion_action" not in query and "all_conversions" not in query
            row = metric("2", "2026-08-01") if token else metric()
        else:
            row = campaign("2") if token else campaign()
        return httpx.Response(
            200, json={"results": [row], "nextPageToken": "" if token else "same-per-phase"}
        )

    reader = adapter(handle)
    result = reader(request())
    assert result.page_count == 5 and len(calls) == 5
    assert len(result.metrics) == 2 and len(result.campaigns) == 2
    assert result.metrics[0].clicks == 100 and result.metrics[0].conversions == 10
    assert result.metrics[0].cost_micros == 100_000_000
    assert result.metrics[0].conversion_value_micros == 100_123_456
    assert result.expires_at == NOW + timedelta(seconds=60)
    assert "b" * 64 not in result.model_dump_json()
    assert result.digest() == GoogleAggregateRangeV1.model_validate(result).digest()
    assert descriptor(reader) == reader.performance_contract
    assert (
        reader.performance_contract.query_version
        == "google.v24.campaign-day.metrics-conversions.v1"
    )


@pytest.mark.parametrize(
    "field", ["impressions", "clicks", "costMicros", "conversions", "conversionsValue"]
)
@pytest.mark.parametrize("kind", ["missing", "null"])
def test_every_queried_cell_required(field: str, kind: str) -> None:
    def handle(req: httpx.Request) -> httpx.Response:
        query = json.loads(req.content)["query"]
        data = raw(query)
        if "metrics." in query:
            if kind == "missing":
                del data["results"][0]["metrics"][field]
            else:
                data["results"][0]["metrics"][field] = None
        return httpx.Response(200, json=data)

    with pytest.raises(GoogleAggregateRangeUnavailable):
        adapter(handle)(request())


@pytest.mark.parametrize("kind", ["zero", "empty"])
def test_explicit_zero_and_omitted_rows_remain_distinct(kind: str) -> None:
    def handle(req: httpx.Request) -> httpx.Response:
        query = json.loads(req.content)["query"]
        data = raw(query)
        if "metrics." in query:
            if kind == "empty":
                data = {}
            else:
                data["results"][0]["metrics"] = dict.fromkeys(metric()["metrics"], "0")
        return httpx.Response(200, json=data)

    result = adapter(handle)(request())
    if kind == "empty":
        assert not result.metrics
    else:
        assert result.metrics[0].conversions == 0 and result.metrics[0].cost_micros == 0


@pytest.mark.parametrize(
    "kind",
    [
        "currency",
        "timezone",
        "account",
        "resource",
        "dangling",
        "duplicate",
        "date",
        "cursor",
        "fraction",
        "overflow",
        "precision",
        "duplicate_json",
        "status",
    ],
)
def test_invalid_graph_or_wire_rejected(kind: str) -> None:
    def handle(req: httpx.Request) -> httpx.Response:
        query = json.loads(req.content)["query"]
        data = raw(query)
        if "FROM customer" in query:
            if kind == "currency":
                data["results"][0]["customer"]["currencyCode"] = "EUR"
            if kind == "timezone":
                data["results"][0]["customer"]["timeZone"] = "UTC"
            if kind == "account":
                data["results"][0]["customer"]["id"] = "9999999999"
            if kind == "duplicate_json":
                return httpx.Response(200, content=b'{"results":[],"results":[]}')
            if kind == "status":
                return httpx.Response(500, json={"private": "payload"})
        elif "metrics." in query:
            row = data["results"][0]
            if kind == "resource":
                row["campaign"]["resourceName"] = "customers/9999999999/campaigns/1"
            if kind == "dangling":
                data["results"] = [metric("2")]
            if kind == "duplicate":
                data["results"] *= 2
            if kind == "date":
                row["segments"]["date"] = "2026-07-31"
            if kind == "fraction":
                row["metrics"]["costMicros"] = "0.5"
            if kind == "overflow":
                row["metrics"]["clicks"] = str(2**31)
            if kind == "precision":
                row["metrics"]["conversions"] = "0.0000001"
            if kind == "cursor":
                data = {"nextPageToken": "repeat"}
        return httpx.Response(200, json=data)

    with pytest.raises(
        GoogleAggregateRangeUnavailable, match="^google_aggregate_range_unavailable$"
    ):
        adapter(handle)(request())


@pytest.mark.parametrize("kind", ["pages", "rows", "bytes"])
def test_total_capacity_no_truncated_success(kind: str) -> None:
    count = [0]

    def handle(req: httpx.Request) -> httpx.Response:
        count[0] += 1
        query = json.loads(req.content)["query"]
        if kind == "bytes":
            return httpx.Response(200, content=b" " * (32 * 1024 * 1024 + 1))
        if "FROM customer" in query:
            return httpx.Response(200, json=raw(query))
        if kind == "rows":
            return httpx.Response(200, json={"results": [campaign()] * 50001})
        return httpx.Response(200, json={"nextPageToken": str(count[0])})

    with pytest.raises(GoogleAggregateRangeUnavailable):
        adapter(handle)(request())
    assert count[0] <= 100


@pytest.mark.parametrize("checkpoint", [1, 3, 9, 10])
def test_clock_after_authorizer_blocks_before_return(checkpoint: int) -> None:
    clock = [NOW]
    checks = [0]

    def validate(req: Any) -> None:
        checks[0] += 1
        if checks[0] == checkpoint:
            clock[0] += timedelta(seconds=61)

    with pytest.raises(GoogleAggregateRangeUnavailable):
        adapter(
            lambda req: httpx.Response(200, json=raw(json.loads(req.content)["query"])),
            clock=lambda: clock[0],
            validate=validate,
        )(request())


def test_stream_expiry_closes_and_restores_private_logging() -> None:
    clock = [NOW]
    closed = []

    class Stream(httpx.SyncByteStream):
        def __iter__(self) -> Iterator[bytes]:
            assert _private_http.get()
            yield b"{"
            clock[0] += timedelta(seconds=61)
            yield b" "
            pytest.fail("trickling read did not stop")

        def close(self) -> None:
            closed.append(True)

    before = _private_http.get()
    with pytest.raises(GoogleAggregateRangeUnavailable):
        adapter(lambda req: httpx.Response(200, stream=Stream()), clock=lambda: clock[0])(request())
    assert closed and before == _private_http.get()


def test_private_session_commitment_and_copied_graph_revalidation() -> None:
    req = request()
    changed = req.model_copy(
        update={"base": req.base.model_copy(update={"original_session_digest": "c" * 64})}
    )
    assert changed.digest() != req.digest()
    with pytest.raises(ValidationError):
        GoogleAggregateRangeRequestV1.model_validate_json(req.model_dump_json())
    result = adapter(lambda wire: httpx.Response(200, json=raw(json.loads(wire.content)["query"])))(
        req
    )
    for field, value in [
        ("cost_micros", True),
        ("conversions", 1.2),
        ("resource_name", b"customers/1234567890/campaigns/1"),
    ]:
        row = result.metrics[0].model_copy(update={field: value})
        with pytest.raises(ValidationError):
            GoogleAggregateRangeV1.model_validate(result.model_copy(update={"metrics": (row,)}))
    for key, value in [("pagination_complete", 1), ("request_digest", "0" * 64)]:
        with pytest.raises(ValidationError):
            GoogleAggregateRangeV1.model_validate(result.model_copy(update={key: value}))


@pytest.mark.parametrize("kind", ["future", "reversed", "overlong", "timestamp", "private_context"])
def test_closed_range_and_context_reject_before_http(kind: str) -> None:
    req = request()
    context = None
    if kind == "future":
        req = req.model_copy(update={"requested_ends_on": NOW.date()})
    if kind == "reversed":
        req = req.model_copy(
            update={"requested_starts_on": req.requested_ends_on + timedelta(days=1)}
        )
    if kind == "overlong":
        req = req.model_copy(
            update={"requested_starts_on": req.requested_ends_on - timedelta(days=400)}
        )
    if kind == "timestamp":
        req = req.model_copy(update={"requested_starts_on": NOW})
    if kind == "private_context":

        def bad_context(base: Any) -> GoogleReportingCatalogContext:
            return GoogleReportingCatalogContext(
                request_digest="0" * 64,
                expires_at=NOW + timedelta(seconds=60),
                access_token=SecretStr("fixture"),
                developer_token=SecretStr("fixture"),
            )

        context = bad_context
    with pytest.raises(GoogleAggregateRangeUnavailable):
        adapter(lambda wire: pytest.fail("invalid request issued HTTP"), context=context)(req)


def test_publication_descriptor_rejects_duck_types_and_subclasses() -> None:
    class Lookalike:
        performance_contract = adapter(
            lambda req: httpx.Response(200, json=raw(""))
        ).performance_contract

    class Derived(GoogleAggregateRangeHTTP):
        pass

    assert descriptor(Lookalike()) is None
    assert descriptor(object.__new__(Derived)) is None
