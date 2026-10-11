"""Raw decoding only; these fixtures do not qualify a native query or import."""

import json
from datetime import date
from decimal import Decimal, localcontext
from typing import Any

import pytest
from app.campaign_performance import raw_cells as raw
from app.campaign_performance import selected_contracts as c
from app.google_connections import selected_presence as google
from app.tiktok.presence import TikTokCampaignPresenceV1, parse_generic_campaign_row

from tests.test_selected_reporting_contracts import request


def google_request(family: str = "conversions") -> c.SelectedCaptureRequestV1:
    values = request().model_dump(mode="python")
    profile = google.query_profile_digest(
        "conversions" if family == "conversions" else "all_conversions"
    )
    values["selection"].update(metric_family=family, query_profile_digest=profile)
    values["selection_digest"] = c.selection_digest(
        c.CustomerEventSelectionV1.model_validate(values["selection"])
    )
    values.update(producer_contract=google.PRODUCER, query_profile_digest=profile)
    values["attribution"]["producer_contract"] = google.PRODUCER
    return c.SelectedCaptureRequestV1.model_validate(values)


def google_row() -> dict[str, Any]:
    return dict(
        campaign=dict(id="555", resourceName="customers/1234567890/campaigns/555"),
        segments=dict(
            date="2026-09-30", conversionAction="customers/1234567890/conversionActions/123"
        ),
        metrics=dict(conversions="10", conversionsValue="100.123456"),
    )


def parse_google(row: dict[str, Any]) -> google.GoogleSelectedPageV1:
    return google.parse_selected_page(
        json.dumps({"results": [row]}).encode(), google_request(), {"555": 5}
    )


def test_google_exact_selected_identity_and_independent_value() -> None:
    page = parse_google(google_row())
    fact = page.facts[0]
    assert fact.selected_conversions.value == 10
    assert fact.selected_value_micros.value == 100_123_456
    assert fact.native_campaign_id == "555" and fact.campaign_id == 5
    assert fact.request_digest == c.capture_request_digest(google_request())


def test_google_original_json_fraction_never_passes_through_float() -> None:
    body = json.dumps({"results": [google_row()]}).replace('"10"', "0.123456").encode()
    page = google.parse_selected_page(body, google_request(), {"555": 5})
    assert page.facts[0].selected_conversions.value == Decimal("0.123456")


@pytest.mark.parametrize(
    "metrics,count,value",
    [
        ({"conversions": 0}, "present", "missing"),
        ({"conversionsValue": 0}, "missing", "present"),
        ({}, "missing", "missing"),
    ],
)
def test_google_presence_not_defaulted(
    metrics: dict[str, Any],
    count: str,
    value: str,
) -> None:
    row = google_row()
    row["metrics"] = metrics
    fact = parse_google(row).facts[0]
    assert fact.selected_conversions.presence == count
    assert fact.selected_value_micros.presence == value


def test_google_empty_response_not_synthesized_zero() -> None:
    for body in (b"{}", b'{"results":[]}'):
        page = google.parse_selected_page(body, google_request(), {"555": 5})
        assert page.facts == () and page.following_cursor == ""


@pytest.mark.parametrize(
    "family,key,value_key",
    [
        ("conversions", "conversions", "conversionsValue"),
        ("all_conversions", "allConversions", "allConversionsValue"),
    ],
)
def test_google_metric_family_is_exact(family: str, key: str, value_key: str) -> None:
    row = google_row()
    row["metrics"] = {key: "7", value_key: "25"}
    page = google.parse_selected_page(
        json.dumps({"results": [row]}).encode(), google_request(family), {"555": 5}
    )
    assert page.facts[0].selected_conversions.value == 7
    assert page.facts[0].selected_value_micros.value == 25_000_000


@pytest.mark.parametrize(
    "section,key,value",
    [
        ("campaign", "id", 555),
        ("campaign", "id", "999"),
        ("campaign", "resourceName", "customers/9999999999/campaigns/555"),
        ("segments", "conversionAction", "customers/1234567890/conversionActions/999"),
        ("segments", "date", "2026-08-31"),
        ("segments", "date", "2026-09-30T00:00:00Z"),
        ("metrics", "conversions", None),
        ("metrics", "conversions", True),
        ("metrics", "conversions", "0.0000001"),
        ("metrics", "conversionsValue", "9223372036854.775808"),
    ],
)
def test_google_foreign_malformed_or_lossy_rows_fail_sanitized(
    section: str,
    key: str,
    value: Any,
) -> None:
    row = google_row()
    row[section][key] = value
    with pytest.raises(ValueError, match="^google_selected_observation_unavailable$"):
        parse_google(row)


@pytest.mark.parametrize(
    "body",
    [
        b'{"error":{"message":"private-fixture-error"}}',
        b'{"results":null}',
        b'{"results":[null]}',
        b'{"results":[],"results":[]}',
        b'{"results":[],"nextPageToken":null}',
        b'{"anything":NaN}',
        b'{"anything":Infinity}',
        b"[]",
        b"not-json",
    ],
)
def test_google_invalid_envelopes_do_not_become_empty_success(body: bytes) -> None:
    with pytest.raises(ValueError, match="^google_selected_observation_unavailable$"):
        google.parse_selected_page(body, google_request(), {"555": 5})


def test_google_duplicate_and_repeated_cursor_rejected() -> None:
    duplicate = json.dumps({"results": [google_row(), google_row()]}).encode()
    with pytest.raises(ValueError):
        google.parse_selected_page(duplicate, google_request(), {"555": 5})
    with pytest.raises(ValueError):
        google.parse_selected_page(
            b'{"nextPageToken":"again"}', google_request(), {"555": 5}, requested_cursor="again"
        )
    page = google.parse_selected_page(b'{"nextPageToken":"next"}', google_request(), {"555": 5})
    assert page.following_cursor == "next" and not page.facts


@pytest.mark.parametrize("mapping", [{"555": True}, {"555": 5, "556": 5}, {"555": 0}])
def test_google_mapping_not_coerced(mapping: dict[str, Any]) -> None:
    with pytest.raises(ValueError):
        google.parse_selected_page(b"{}", google_request(), mapping)


def tiktok_row() -> dict[str, Any]:
    return dict(
        advertiser_id="123",
        dimensions=dict(campaign_id="555", stat_time_day="2026-09-30"),
        metrics=dict(impressions="1000", clicks="100", spend="100", conversion="10"),
    )


def parse_tiktok(row: dict[str, Any]) -> TikTokCampaignPresenceV1:
    return parse_generic_campaign_row(
        row, advertiser="123", starts_on=date(2026, 9, 1), ends_on=date(2026, 9, 30)
    )


@pytest.mark.parametrize("count", ["10", "0", 0])
def test_tiktok_generic_counts_never_qualify_selected_event(count: Any) -> None:
    row = tiktok_row()
    row["metrics"]["conversion"] = count
    row["metrics"]["purchase"] = "999"  # Unrequested field must never become event authority.
    result = parse_tiktok(row)
    assert result.aggregate_conversions.value == Decimal(count)
    assert result.selected_conversions.presence == "unsupported"
    assert result.selected_value_micros.value is None
    assert result.clicks.value == 100 and result.spend_micros.value == 100_000_000


def test_tiktok_missing_fields_remain_missing_and_copies_revalidate() -> None:
    row = tiktok_row()
    row["metrics"] = {}
    result = parse_tiktok(row)
    assert result.aggregate_conversions.presence == "missing" and result.clicks.value is None
    with pytest.raises(ValueError):
        TikTokCampaignPresenceV1.model_validate(
            result.model_copy(
                update={
                    "selected_conversions": {"presence": "present", "value": "0"},
                }
            )
        )


@pytest.mark.parametrize(
    "section,key,value",
    [
        ("dimensions", "stat_time_day", "2026-09-30 00:00:00"),
        ("dimensions", "stat_time_day", "2026-08-31"),
        ("dimensions", "campaign_id", 555),
        ("metrics", "clicks", 1.5),
        ("metrics", "clicks", True),
        ("metrics", "clicks", "2147483648"),
        ("metrics", "conversion", None),
        ("metrics", "conversion", "0.0000001"),
        ("metrics", "spend", "0.0000001"),
    ],
)
def test_tiktok_does_not_truncate_or_coerce(section: str, key: str, value: Any) -> None:
    row = tiktok_row()
    row[section][key] = value
    with pytest.raises(ValueError, match="^tiktok_raw_observation_unavailable$"):
        parse_tiktok(row)


def test_tiktok_foreign_advertiser_rejected() -> None:
    row = tiktok_row()
    row["advertiser_id"] = "999"
    with pytest.raises(ValueError):
        parse_tiktok(row)


@pytest.mark.parametrize("precision", [2, 6, 28])
def test_money_boundary_independent_of_decimal_context(precision: int) -> None:
    with localcontext() as context:
        context.prec = precision
        assert raw.money_cell({"v": "9223372036854.775807"}, "v").value == 2**63 - 1
        assert raw.money_cell({"v": "0.000001"}, "v").value == 1
        with pytest.raises(ValueError):
            raw.money_cell({"v": "9223372036854.775808"}, "v")


@pytest.mark.parametrize(
    "value", [None, True, 1.5, "NaN", "Infinity", "-1", "1e2", "01", "0.0000001"]
)
def test_money_requires_exact_bounded_token(value: Any) -> None:
    with pytest.raises(ValueError):
        raw.money_cell({"v": value}, "v")


def test_json_byte_bound_and_nested_duplicate_keys() -> None:
    assert raw.exact_json(b'{"v":0.123456}', limit=20)["v"] == Decimal("0.123456")
    with pytest.raises(ValueError):
        raw.exact_json(b'{"v":{ "x":0,"x":1 }}', limit=100)
    with pytest.raises(ValueError):
        raw.exact_json(b"{}", limit=1)


@pytest.mark.parametrize("encoding", ["utf-16", "utf-32"])
def test_non_utf8_json_rejected(encoding: str) -> None:
    with pytest.raises(ValueError):
        raw.exact_json('{"results": []}'.encode(encoding), limit=100)


def test_empty_google_page_bound_to_exact_request() -> None:
    req = google_request()
    page = google.parse_selected_page(b"{}", req, {"555": 5})
    assert page.capture_id == req.capture_id
    assert page.request_digest == c.capture_request_digest(req)
    other = c.SelectedCaptureRequestV1.model_validate(
        req.model_copy(update={"capture_id": "9" * 32})
    )
    different = google.parse_selected_page(b"{}", other, {"555": 5})
    assert page.request_digest != different.request_digest
    populated = parse_google(google_row())
    with pytest.raises(ValueError):
        google.GoogleSelectedPageV1.model_validate(
            populated.model_copy(
                update={
                    "request_digest": "9" * 64,
                }
            )
        )


@pytest.mark.parametrize(
    "body", [b" " * 8_000_001, json.dumps({"results": [{}] * 10_001}).encode()]
)
def test_google_actual_response_and_row_caps(body: bytes) -> None:
    with pytest.raises(ValueError, match="^google_selected_observation_unavailable$"):
        google.parse_selected_page(body, google_request(), {"555": 5})


def test_google_unsupported_or_tampered_query_profile_fails() -> None:
    req = google_request()
    for changed in [
        req.model_copy(update={"query_profile_digest": "9" * 64}),
        req.model_copy(update={"producer_contract": "unknown.v1"}),
    ]:
        with pytest.raises(ValueError, match="^google_selected_observation_unavailable$"):
            google.parse_selected_page(b"{}", changed, {"555": 5})
    selection = c.CustomerEventSelectionV1.model_validate(
        req.selection.model_copy(
            update={
                "native_event_owner_id": "9999999999",
                "native_event_id": "customers/9999999999/conversionActions/123",
            }
        )
    )
    other_owner = c.SelectedCaptureRequestV1.model_validate(
        req.model_copy(
            update={
                "selection": selection,
                "selection_digest": c.selection_digest(selection),
            }
        )
    )
    with pytest.raises(ValueError, match="^google_selected_observation_unavailable$"):
        google.parse_selected_page(b"{}", other_owner, {"555": 5})
