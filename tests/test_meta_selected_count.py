"""Pinned Meta purchase count fixture qualification; no provider access."""

import json
import logging
from datetime import timedelta
from typing import Any

import httpx
import pytest
from app.campaign_performance.selected_contracts import (
    CustomerEventSelectionV1,
    SelectedCaptureRequestV1,
    capture_request_digest,
    selection_digest,
)
from app.meta.selected_collection import (
    MetaSelectedCollectionUnavailable,
    collect_meta_selected_capture,
)
from app.meta.selected_http import (
    MetaSelectedHTTPRead,
    MetaSelectedReadUnavailable,
    SelectedMetaContext,
)
from app.meta.selected_presence import parse_selected_page
from app.meta.selected_profile import EVENT, PRODUCER, query_profile_digest, settings
from app.planning_documents.selected_observation_provenance import selected_observation_provenance
from pydantic import SecretStr

from tests.test_capture_settings_contract import legacy


def request() -> SelectedCaptureRequestV1:
    body = legacy().request.model_dump(mode="json")
    scope = body["aggregate"]["scope"]
    scope.update(
        platform="meta_ads", native_account_id="101", source_connection_ref="1", time_zone="UTC"
    )
    choice = body["selection"]
    choice.update(
        scope=scope,
        event_namespace="meta_action_type",
        native_event_owner_id="101",
        native_event_id=EVENT,
        metric_family="actions",
        api_version="v26.0",
        query_profile_digest=query_profile_digest(),
    )
    body.update(
        schema_version="inlet.selected-capture-request.v2",
        producer_contract=PRODUCER,
        query_profile_digest=query_profile_digest(),
        settings=settings().model_dump(mode="json"),
        attribution=settings().effective.model_dump(mode="json"),
        selection_digest=selection_digest(CustomerEventSelectionV1.model_validate(choice)),
    )
    return SelectedCaptureRequestV1.model_validate(body)


def row(req: SelectedCaptureRequestV1, **changes: Any) -> dict[str, Any]:
    return (
        dict(
            account_id="101",
            campaign_id="201",
            account_currency=req.aggregate.scope.currency,
            date_start=req.requested_ends_on.isoformat(),
            date_stop=req.requested_ends_on.isoformat(),
            actions=[{"action_type": EVENT, "value": "2.5"}],
        )
        | changes
    )


def raw(rows: list[dict[str, Any]], **extra: Any) -> bytes:
    return json.dumps(dict(data=rows) | extra).encode()


@pytest.mark.parametrize(
    "actions,presence,value",
    [
        ([{"action_type": EVENT, "value": "2.5"}], "present", "2.5"),
        ([{"action_type": EVENT, "value": "0"}], "present", "0"),
        ([], "missing", None),
        ([{"action_type": EVENT}], "missing", None),
        ([{"action_type": "purchase", "value": "99"}], "missing", None),
        ([{"action_type": "app_custom_event.fb_mobile_purchase", "value": "99"}], "missing", None),
    ],
)
def test_exact_count_presence(actions: Any, presence: str, value: Any) -> None:
    req = request()
    page = parse_selected_page(raw([row(req, actions=actions)]), req, {"201": 3})
    cell = page.facts[0].selected_conversions
    assert (
        cell.presence == presence and (str(cell.value) if cell.value is not None else None) == value
    )
    assert page.facts[0].selected_value_micros.presence == "unsupported"


def test_missing_row_and_actions_are_not_zero() -> None:
    req = request()
    assert parse_selected_page(raw([]), req, {"201": 3}).facts == ()
    item = row(req)
    item.pop("actions")
    assert (
        parse_selected_page(raw([item]), req, {"201": 3}).facts[0].selected_conversions.presence
        == "missing"
    )


@pytest.mark.parametrize(
    "attack",
    [
        "account",
        "currency",
        "campaign",
        "dates",
        "range",
        "duplicate_row",
        "duplicate_action",
        "null",
        "negative",
        "boolean",
        "nonfinite",
        "precision",
        "window",
        "null_actions",
        "duplicate_key",
        "missing_data",
        "next_without_cursor",
        "repeat_cursor",
        "invalid_cursor",
        "body_limit",
    ],
)
def test_malformed_pages_fail_closed(attack: str) -> None:
    req, item = request(), row(request())
    if attack in {"account", "currency", "campaign"}:
        item[
            {"account": "account_id", "currency": "account_currency", "campaign": "campaign_id"}[
                attack
            ]
        ] = "999"
    elif attack == "dates":
        item["date_stop"] = "2020-01-01"
    elif attack == "range":
        item.update(date_start="2020-01-01", date_stop="2020-01-01")
    elif attack == "duplicate_action":
        item["actions"] *= 2
    elif attack in {"null", "negative", "boolean", "nonfinite", "precision"}:
        item["actions"][0]["value"] = {
            "null": None,
            "negative": "-1",
            "boolean": True,
            "nonfinite": "NaN",
            "precision": "0.0000001",
        }[attack]
    elif attack == "window":
        item["actions"][0]["7d_click"] = "1"
    elif attack == "null_actions":
        item["actions"] = None
    body = raw([item, item] if attack == "duplicate_row" else [item])
    if attack == "duplicate_key":
        body = b'{"data":[],"data":[]}'
    elif attack == "missing_data":
        body = b"{}"
    elif attack in {"next_without_cursor", "repeat_cursor", "invalid_cursor"}:
        paging: dict[str, Any] = {"next": "https://untrusted.invalid/?access_token=fixture"}
        if attack != "next_without_cursor":
            paging["cursors"] = {"after": "A" if attack == "repeat_cursor" else "?bad"}
        body = raw([], paging=paging)
    elif attack == "body_limit":
        body = b" " * 2_000_001
    with pytest.raises(ValueError, match="^meta_selected_observation_unavailable$"):
        parse_selected_page(body, req, {"201": 3}, requested_cursor="A")


@pytest.mark.parametrize(
    "attack", ["event", "profile", "request_flag", "effective", "money", "support"]
)
def test_exact_profile_and_unknown_basis_required(attack: str) -> None:
    body = request().model_dump(mode="json")
    if attack == "event":
        body["selection"]["native_event_id"] = "purchase"
        body["selection_digest"] = selection_digest(
            CustomerEventSelectionV1.model_validate(body["selection"])
        )
    elif attack == "profile":
        body["settings"]["profile"] = "meta.website-purchase.campaign-day.v1"
    elif attack == "request_flag":
        body["settings"]["requested"]["action_report_time"] = "conversion"
    elif attack == "effective":
        body["settings"]["effective"]["report_time_basis"] = "conversion"
    elif attack == "money":
        body["settings"]["value_unit"] = "account_currency_major"
    else:
        body["settings"]["report_support"] = "unverified"
    with pytest.raises(ValueError):
        SelectedCaptureRequestV1.model_validate(body)


def test_bounded_pagination_and_retained_provenance() -> None:
    req = request()
    cursors: list[str] = []
    guards: list[Any] = []

    def reader(r: Any, mapping: Any, *, requested_cursor: str = "") -> Any:
        cursors.append(requested_cursor)
        body = (
            raw(
                [row(req)],
                paging={"next": "https://not-followed.invalid", "cursors": {"after": "A"}},
            )
            if not requested_cursor
            else raw([])
        )
        return parse_selected_page(body, r, mapping, requested_cursor=requested_cursor)

    capture = collect_meta_selected_capture(
        req, {"201": 3}, reader, lambda r: guards.append(r), lambda: req.started_at
    )
    assert cursors == ["", "A"] and len(guards) >= 6
    assert capture.schema_version == "inlet.selected-capture.v2" and capture.page_count == 2
    provenance = selected_observation_provenance(capture)
    provenance.assert_aggregate(req.aggregate)
    assert provenance.settings == settings() and provenance.capability == "supported"
    assert provenance.attribution.provenance == "provider_default_unknown"


@pytest.mark.parametrize("attack", ["duplicate", "cycle", "page_limit", "revoke", "expired"])
def test_collection_never_returns_partial(attack: str) -> None:
    req = request()
    calls: list[Any] = []

    def guard(r: Any) -> None:
        if attack == "revoke" and calls:
            raise ValueError("revoked")

    def reader(r: Any, mapping: Any, *, requested_cursor: str = "") -> Any:
        calls.append(1)
        after = ("A" if len(calls) % 2 else "B") if attack == "cycle" else str(len(calls))
        return parse_selected_page(
            raw(
                [row(req)] if attack == "duplicate" else [],
                paging={"next": "ignored", "cursors": {"after": after}},
            ),
            r,
            mapping,
            requested_cursor=requested_cursor,
        )

    with pytest.raises(MetaSelectedCollectionUnavailable):
        collect_meta_selected_capture(
            req,
            {"201": 3},
            reader,
            guard,
            lambda: req.started_at + timedelta(seconds=60 if attack == "expired" else 0),
        )
    assert len(calls) <= 100


def http_reader(
    req: SelectedCaptureRequestV1, handler: Any, **changes: Any
) -> MetaSelectedHTTPRead:
    context = SelectedMetaContext(
        request_digest=capture_request_digest(req),
        expires_at=req.started_at + timedelta(seconds=90),
        access_token=SecretStr("offline-token"),
        app_secret=SecretStr("offline-secret"),
    )
    context = context.model_copy(update=changes)
    return MetaSelectedHTTPRead(
        lambda r: context,
        lambda r: None,
        transport=httpx.MockTransport(handler),
        clock=lambda: req.started_at,
    )


def test_http_fixed_query_no_ignored_flags_or_pagination_url(caplog: Any) -> None:
    caplog.set_level(logging.INFO, logger="httpx")
    req = request()
    calls: list[Any] = []

    def handler(r: httpx.Request) -> httpx.Response:
        calls.append(r)
        assert r.method == "GET" and r.url.host == "graph.facebook.com"
        assert r.headers["Authorization"] == "Bearer offline-token"
        if r.url.path.endswith("/insights"):
            params = dict(r.url.params)
            assert set(params) == {
                "fields",
                "level",
                "time_increment",
                "limit",
                "action_breakdowns",
                "time_range",
                "after",
                "appsecret_proof",
            }
            assert (
                params["after"] == "A"
                and params["level"] == "campaign"
                and params["time_increment"] == "1"
            )
            return httpx.Response(200, content=raw([row(req)]))
        return httpx.Response(
            200,
            json={
                "account_id": "101",
                "currency": req.aggregate.scope.currency,
                "timezone_name": "UTC",
                "id": "act_101",
            },
        )

    result = http_reader(req, handler)(req, {"201": 3}, requested_cursor="A")
    assert len(calls) == 2 and result.facts[0].selected_conversions.presence == "present"
    assert "offline-token" not in caplog.text and "appsecret_proof" not in caplog.text


@pytest.mark.parametrize(
    "attack",
    [
        "redirect",
        "provider_error",
        "metadata",
        "metadata_duplicate",
        "expired",
        "binding",
        "oversize",
    ],
)
def test_http_rejects_bad_scope_and_response(attack: str) -> None:
    req = request()
    calls: list[Any] = []

    def handler(r: httpx.Request) -> httpx.Response:
        calls.append(1)
        if attack == "redirect":
            return httpx.Response(302, headers={"location": "https://evil.invalid"})
        if attack == "provider_error":
            return httpx.Response(400, text="unretained fixture body")
        if attack == "metadata_duplicate":
            return httpx.Response(200, content=b'{"account_id":"101","account_id":"101"}')
        if attack == "oversize":
            return httpx.Response(200, content=b" " * 200_001)
        return httpx.Response(
            200, json={"account_id": "999", "currency": "USD", "timezone_name": "UTC"}
        )

    changes = (
        {"expires_at": req.started_at}
        if attack == "expired"
        else {"request_digest": "f" * 64}
        if attack == "binding"
        else {}
    )
    with pytest.raises(MetaSelectedReadUnavailable, match="^meta_selected_read_unavailable$"):
        http_reader(req, handler, **changes)(req, {"201": 3})
    assert len(calls) == (0 if changes else 1)


@pytest.mark.parametrize("failure", [False, True])
def test_borrowed_transport_and_response_stream_lifetime(failure: bool) -> None:
    req = request()
    closed_streams: list[int] = []

    class Stream(httpx.SyncByteStream):
        def __init__(self, body: bytes, ordinal: int) -> None:
            self.body, self.ordinal = body, ordinal

        def __iter__(self) -> Any:
            yield self.body

        def close(self) -> None:
            closed_streams.append(self.ordinal)

    class Transport(httpx.BaseTransport):
        def __init__(self) -> None:
            self.calls, self.closes = 0, 0

        def handle_request(self, wire: httpx.Request) -> httpx.Response:
            assert self.closes == 0, "underlying transport already closed"
            self.calls += 1
            if wire.url.path.endswith("/insights"):
                if wire.url.params.get("after"):
                    body = b'{"data":null}' if failure else raw([])
                else:
                    body = raw([row(req)], paging={"next": "ignored", "cursors": {"after": "A"}})
            else:
                body = json.dumps(
                    {
                        "account_id": "101",
                        "currency": req.aggregate.scope.currency,
                        "timezone_name": "UTC",
                    }
                ).encode()
            return httpx.Response(200, stream=Stream(body, self.calls))

        def close(self) -> None:
            self.closes += 1

    transport = Transport()
    context = SelectedMetaContext(
        request_digest=capture_request_digest(req),
        expires_at=req.started_at + timedelta(seconds=60),
        access_token=SecretStr("offline-token"),
        app_secret=SecretStr("offline-secret"),
    )
    reader = MetaSelectedHTTPRead(
        lambda r: context, lambda r: None, transport=transport, clock=lambda: req.started_at
    )
    try:
        if failure:
            with pytest.raises(MetaSelectedCollectionUnavailable):
                collect_meta_selected_capture(
                    req, {"201": 3}, reader, lambda r: None, lambda: req.started_at
                )
        else:
            capture = collect_meta_selected_capture(
                req, {"201": 3}, reader, lambda r: None, lambda: req.started_at
            )
            assert capture.page_count == 2
        assert transport.calls == 4 and transport.closes == 0
        assert closed_streams == [1, 2, 3, 4]
    finally:
        transport.close()
    assert transport.closes == 1
