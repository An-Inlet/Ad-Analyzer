"""Pure parser qualification, deliberately not live or complete-capture evidence."""

import json
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
from app.campaign_performance.selected_contracts import ReportingScopeV1
from app.tiktok.count_contracts import (
    MAX_BODY,
    CampaignScopeV1,
    TikTokCountProofV1,
    TikTokCountQueryV1,
)
from app.tiktok.count_parser import assemble_count_proof, parse_count_page


def query() -> TikTokCountQueryV1:
    return TikTokCountQueryV1(
        request_digest="a" * 64,
        scope=ReportingScopeV1(
            workspace_id=1,
            connection_id=2,
            account_id=3,
            platform="tiktok_ads",
            source_connection_ref="b" * 32,
            generation=1,
            privacy_revision=0,
            native_account_id="123",
            currency="USD",
            time_zone="America/Los_Angeles",
        ),
        campaigns=tuple(
            CampaignScopeV1(
                native_id=str(i), local_id=i, kind="regular_auction", origin="TT_ADS_PLATFORM"
            )
            for i in range(1, 101)
        ),
        starts_on=date(2026, 10, 1),
        ends_on=date(2026, 10, 2),
        started_at=datetime(2026, 10, 3, 8, tzinfo=UTC),
    )


def row(campaign: str = "1", day: str = "2026-10-01", value: Any = "10") -> dict[str, Any]:
    return {
        "dimensions": {"campaign_id": campaign, "stat_time_day": day + " 00:00:00"},
        "metrics": {"complete_payment": value},
    }


def body(rows: list[dict[str, Any]], page: int = 1, total: int | None = None) -> bytes:
    n = len(rows) if total is None else total
    return json.dumps(
        {
            "code": 0,
            "request_id": "synthetic_request",
            "data": {
                "list": rows,
                "page_info": {
                    "page": page,
                    "page_size": 100,
                    "total_number": n,
                    "total_page": (n + 99) // 100,
                },
            },
        }
    ).encode()


def parse(raw: bytes, *, page: int = 1, headers: tuple[tuple[str, str], ...] = ()) -> Any:
    q = query()
    return parse_count_page(q, raw, headers, requested_page=page, acquired_at=q.started_at)


@pytest.mark.parametrize(
    "value,expected",
    [("10", Decimal(10)), ("0", Decimal(0)), (0, Decimal(0)), ("1.25", Decimal("1.25"))],
)
def test_exact_count_without_complete_capture(value: Any, expected: Decimal) -> None:
    page = parse(body([row(value=value)]))
    assert page.rows[0].count.value == expected
    assert page.rows[0].count.presence == "present"
    proof = assemble_count_proof(query(), (page,))
    assert (proof.capability, proof.uncapped, proof.value, proof.effective_attribution) == (
        "unknown",
        "unknown",
        "unsupported",
        "unknown",
    )
    assert TikTokCountProofV1.model_validate_json(proof.model_dump_json()) == proof
    with pytest.raises(ValueError, match="positive uncapped"):
        proof.require_complete_capture()


@pytest.mark.parametrize("kind", ["omitted", "dash"])
def test_missing_never_becomes_zero(kind: str) -> None:
    r = row(value="-")
    if kind == "omitted":
        r["metrics"] = {}
    parsed = parse(body([r]))
    assert parsed.rows[0].count.presence == "missing"
    assert parsed.rows[0].count.value is None
    assert len(assemble_count_proof(query(), (parsed,)).pages[0].rows) == 1


@pytest.mark.parametrize(
    "value",
    [None, True, -1, "-1", "NaN", "Infinity", "1e2", "1.0000001", "1000000000000", "", " 0", "00"],
)
def test_bad_counts_refused(value: Any) -> None:
    with pytest.raises(ValueError, match="tiktok_count_page_unavailable"):
        parse(body([row(value=value)]))


@pytest.mark.parametrize(
    "kind",
    [
        "foreign",
        "wrong_day",
        "non_midnight",
        "generic_metric",
        "extra_dimension",
        "duplicate",
        "null_metrics",
        "float_id",
        "wrong_event",
        "wrong_code",
        "missing_request_id",
        "boolean_page",
        "wrong_total",
        "wrong_page",
        "empty",
    ],
)
def test_wire_and_scope_refusals(kind: str) -> None:
    raw = json.loads(body([row()]))
    r = raw["data"]["list"][0]
    if kind == "foreign":
        r["dimensions"]["campaign_id"] = "999"
    elif kind == "wrong_day":
        r["dimensions"]["stat_time_day"] = "2026-10-03 00:00:00"
    elif kind == "non_midnight":
        r["dimensions"]["stat_time_day"] = "2026-10-01 01:00:00"
    elif kind == "generic_metric":
        r["metrics"] = {"conversion": "10"}
    elif kind == "extra_dimension":
        r["dimensions"]["event_source_id"] = "pixel"
    elif kind == "duplicate":
        raw = json.loads(body([row(), row()]))
    elif kind == "null_metrics":
        r["metrics"] = None
    elif kind == "float_id":
        r["dimensions"]["campaign_id"] = 1.0
    elif kind == "wrong_event":
        r["metrics"] = {"purchase": "10"}
    elif kind == "wrong_code":
        raw["code"] = False
    elif kind == "missing_request_id":
        del raw["request_id"]
    elif kind == "boolean_page":
        raw["data"]["page_info"]["page"] = True
    elif kind == "wrong_total":
        raw["data"]["page_info"]["total_number"] = 2
    elif kind == "wrong_page":
        raw["data"]["page_info"]["page"] = 2
    else:
        raw = json.loads(body([]))
    with pytest.raises(ValueError, match="tiktok_count_page_unavailable"):
        parse(json.dumps(raw).encode())


@pytest.mark.parametrize("header", ["1", "0", "", "true", "unknown"])
def test_every_unqualified_throttle_value_prevents_completeness(header: str) -> None:
    page = parse(body([row()]), headers=(("X-Tt-Ads-Throttle", header),))
    proof = assemble_count_proof(query(), (page,))
    assert proof.uncapped == "warning_present"
    with pytest.raises(ValueError):
        proof.require_complete_capture()
    with pytest.raises(ValueError):
        TikTokCountProofV1.model_validate(proof.model_copy(update={"uncapped": "unknown"}))


@pytest.mark.parametrize("kind", ["duplicate_json", "oversize", "duplicate_header", "huge_headers"])
def test_bounded_unambiguous_input(kind: str) -> None:
    raw = body([row()])
    headers: tuple[tuple[str, str], ...] = ()
    if kind == "duplicate_json":
        raw = raw.replace(b'"code": 0', b'"code": 0, "code": 0')
    elif kind == "oversize":
        raw = b" " * (MAX_BODY + 1)
    elif kind == "duplicate_header":
        headers = (("X-Tt-Ads-Throttle", "1"), ("x-tt-ads-throttle", "1"))
    else:
        headers = (("Unrelated", "x" * 16_385),)
    with pytest.raises(ValueError):
        parse(raw, headers=headers)


def test_two_pages_raw_row_totals_and_no_missing_fact_synthesis() -> None:
    first = parse(body([row(str(i)) for i in range(1, 101)], total=101))
    second = parse(body([row(day="2026-10-02")], page=2, total=101), page=2)
    proof = assemble_count_proof(query(), (first, second))
    assert sum(len(p.rows) for p in proof.pages) == 101  # Not 100 campaigns x 2 dates.
    assert proof.pages[0].request_id == proof.pages[1].request_id
    assert proof.uncapped == "unknown"
    with pytest.raises(ValueError):
        proof.require_complete_capture()


@pytest.mark.parametrize(
    "kind",
    [
        "gap",
        "repeat",
        "changed_scope",
        "changed_total",
        "duplicate_row",
        "expired",
        "backwards",
        "forged_complete",
    ],
)
def test_collection_fails_closed(kind: str) -> None:
    first = parse(body([row(str(i)) for i in range(1, 101)], total=101))
    second = parse(body([row(day="2026-10-02")], page=2, total=101), page=2)
    pages: tuple[Any, ...] = (first, second)
    if kind == "gap":
        pages = (second,)
    elif kind == "repeat":
        pages = (first, first)
    elif kind == "changed_scope":
        second = second.model_copy(update={"query_digest": "f" * 64})
    elif kind == "changed_total":
        second = second.model_copy(update={"total_number": 102})
    elif kind == "duplicate_row":
        second = second.model_copy(update={"rows": (first.rows[0],)})
    elif kind == "expired":
        second = second.model_copy(
            update={"acquired_at": query().started_at + timedelta(seconds=60)}
        )
    elif kind == "backwards":
        first = first.model_copy(update={"acquired_at": query().started_at + timedelta(seconds=1)})
    if kind not in {"gap", "repeat"}:
        pages = (first, second)
    with pytest.raises(ValueError):
        if kind == "forged_complete":
            TikTokCountProofV1(query=query(), pages=pages, uncapped=True)
        else:
            assemble_count_proof(query(), pages)


@pytest.mark.parametrize(
    "kind",
    [
        "ios14",
        "promote",
        "unknown",
        "wrong_event",
        "long_range",
        "open_local_day",
        "duplicate_mapping",
        "other_platform",
    ],
)
def test_query_refuses_unqualified_scope(kind: str) -> None:
    raw = query().model_dump(mode="json")
    if kind in {"ios14", "unknown"}:
        raw["campaigns"][0]["kind"] = kind
    elif kind == "promote":
        raw["campaigns"][0]["origin"] = "PROMOTE"
    elif kind == "wrong_event":
        raw["event"] = "purchase"
    elif kind == "long_range":
        raw["starts_on"] = "2026-09-02"
    elif kind == "open_local_day":
        raw["started_at"] = "2026-10-03T06:00:00Z"  # Still Oct 2 in account timezone.
    elif kind == "duplicate_mapping":
        raw["campaigns"][1]["local_id"] = raw["campaigns"][0]["local_id"]
    else:
        raw["scope"]["platform"] = "google_ads"
    with pytest.raises(ValueError):
        TikTokCountQueryV1.model_validate(raw)


def test_inclusive_thirty_days_and_acquisition_deadline() -> None:
    raw = query().model_dump(mode="json")
    raw["starts_on"] = "2026-09-03"
    q = TikTokCountQueryV1.model_validate(raw)
    page = parse_count_page(
        q,
        body([row(day="2026-09-03"), row(day="2026-10-02")]),
        (),
        requested_page=1,
        acquired_at=q.started_at + timedelta(seconds=59),
    )
    assert len(page.rows) == 2
    for delta in (-1, 60):
        with pytest.raises(ValueError):
            parse_count_page(
                q,
                body([row()]),
                (),
                requested_page=1,
                acquired_at=q.started_at + timedelta(seconds=delta),
            )


def test_existing_unverified_profile_cannot_be_promoted() -> None:
    from app.campaign_performance.capture_settings import CaptureSettingsV1

    assert "tiktok.website-payment-count.campaign-day.v1" not in str(
        CaptureSettingsV1.model_fields["profile"].annotation
    )


@pytest.mark.parametrize("constant", ["NaN", "Infinity", "-Infinity"])
def test_nonfinite_json_even_in_unused_envelope_field(constant: str) -> None:
    raw = body([row()]).replace(b'"code": 0', b'"code": 0, "message": ' + constant.encode())
    with pytest.raises(ValueError, match="tiktok_count_page_unavailable"):
        parse(raw)
