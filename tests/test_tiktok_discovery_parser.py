"""Synthetic table-shaped examples, not captured/native qualification fixtures."""

from copy import deepcopy
from typing import Any

import pytest
from app.collectors.tiktok_discovery_contracts import (
    ObservedFieldV1,
    ObservedIdV1,
    TikTokIdentityPageRequestV1,
    TikTokPixelPageRequestV1,
)
from app.collectors.tiktok_discovery_parser import (
    TikTokDiscoveryParseError,
    parse_identity_page,
    parse_pixel_page,
)
from pydantic import ValidationError


def identity_request(**updates: Any) -> TikTokIdentityPageRequestV1:
    return TikTokIdentityPageRequestV1.model_validate(
        {
            "advertiser_id": "synthetic-advertiser",
            "identity_type": "TT_USER",
            "page": 1,
            "page_size": 20,
            **updates,
        }
    )


def pixel_request(**updates: Any) -> TikTokPixelPageRequestV1:
    return TikTokPixelPageRequestV1.model_validate(
        {
            "advertiser_id": "synthetic-advertiser",
            "page": 1,
            "page_size": 10,
            "order_by": "EARLIEST_CREATE",
            "available_for_catalog_only": False,
            **updates,
        }
    )


def envelope(key: str, rows: list[dict[str, Any]], size: int = 10) -> dict[str, Any]:
    return {
        "code": 0,
        "message": "ignored",
        "request_id": "ignored",
        "data": {
            key: rows,
            "page_info": {
                "page": 1,
                "page_size": size,
                "total_page": 1 if rows else 0,
                "total_number": len(rows),
            },
        },
    }


def identity(**updates: Any) -> dict[str, Any]:
    return {"identity_id": "synthetic-identity", "identity_type": "TT_USER", **updates}


def test_linked_identity_preserves_missing_null_false_unknown_and_strips_unused() -> None:
    payload = envelope(
        "identity_list",
        [
            identity(
                available_status="FUTURE_STATUS",
                can_push_video=False,
                can_pull_video=None,
                display_name="",
                username="not-retained",
                profile_image="not-retained",
            )
        ],
        20,
    )
    original = deepcopy(payload)
    result = parse_identity_page(identity_request(), payload)
    item = result.identities[0]
    assert item.available_status.recognition == "unrecognized"
    assert item.available_status.applicability == "applicable"
    assert item.can_push_video.value is False
    assert item.can_pull_video.presence == "null"
    assert item.can_manage_message.presence == "absent"
    assert item.ads_only_mode.applicability == "not_applicable"
    assert item.display_name.value == ""
    assert "not-retained" not in result.model_dump_json()
    assert result.publication_eligibility == "not_assessed"
    assert result.spending_authority == "none"
    assert payload == original


@pytest.mark.parametrize("kind", ["CUSTOMIZED_USER", "AUTH_CODE"])
def test_nonlinked_status_is_not_applicable_even_if_available(kind: str) -> None:
    result = parse_identity_page(
        identity_request(identity_type=kind),
        envelope(
            "identity_list",
            [identity(identity_type=kind, available_status="AVAILABLE")],
            20,
        ),
    )
    assert result.identities[0].available_status.applicability == "not_applicable"
    assert result.publication_eligibility == "not_assessed"


def test_unknown_identity_type_not_inferred_from_request() -> None:
    result = parse_identity_page(
        identity_request(),
        envelope(
            "identity_list",
            [identity(identity_type="FUTURE")],
            20,
        ),
    )
    assert result.identities[0].identity_type.recognition == "unrecognized"
    assert result.identities[0].available_status.applicability == "unknown"


def test_bc_identity_scope_and_ads_only() -> None:
    request = identity_request(identity_type="BC_AUTH_TT", identity_authorized_bc_id="bc")
    row = identity(identity_type="BC_AUTH_TT", identity_authorized_bc_id="bc", ads_only_mode=True)
    assert (
        parse_identity_page(request, envelope("identity_list", [row], 20))
        .identities[0]
        .ads_only_mode.applicability
        == "applicable"
    )
    row["identity_authorized_bc_id"] = "other"
    with pytest.raises(TikTokDiscoveryParseError):
        parse_identity_page(request, envelope("identity_list", [row], 20))


@pytest.mark.parametrize(
    "updates",
    [
        {"identity_type": "BC_AUTH_TT"},
        {"identity_authorized_bc_id": "unexpected"},
        {"keyword": "search"},
        {"page": True},
        {"page": "1"},
        {"page": 0},
        {"page_size": 101},
        {"identity_type": "FUTURE"},
    ],
)
def test_identity_request_requires_explicit_valid_scope(updates: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        identity_request(**updates)


@pytest.mark.parametrize(
    "updates",
    [
        {"available_status": True},
        {"can_push_video": "true"},
        {"can_pull_video": 1},
        {"identity_id": 123},
        {"identity_id": ""},
        {"identity_type": "AUTH_CODE"},
    ],
)
def test_malformed_or_mismatched_identity_rejected(updates: dict[str, Any]) -> None:
    with pytest.raises(TikTokDiscoveryParseError, match="^tiktok_discovery_response_unavailable$"):
        parse_identity_page(
            identity_request(), envelope("identity_list", [identity(**updates)], 20)
        )


@pytest.mark.parametrize("native_id", ["00123", 123, 0, 2**64 - 1])
def test_unverified_id_shape_preserved_without_normalization(native_id: str | int) -> None:
    result = parse_pixel_page(
        pixel_request(),
        envelope(
            "pixels",
            [
                {
                    "pixel_id": native_id,
                    "events": [{"event_id": native_id}],
                }
            ],
        ),
    )
    pixel = result.pixels[0]
    assert type(pixel.pixel_id.value) is type(native_id)
    assert pixel.pixel_id.value == native_id
    assert pixel.events.value is not None
    assert type(pixel.events.value[0].event_id.value) is type(native_id)
    assert result.scalar_shape_qualification == "unverified"
    assert pixel.pixel_id.scalar_shape_qualification == "unverified"
    assert result.publication_eligibility == "not_assessed"


@pytest.mark.parametrize("native_id", [True, False, 1.5, -1, 2**64, "", "a" * 129, [], {}])
def test_ids_are_bounded_strict_and_never_bool(native_id: Any) -> None:
    with pytest.raises(ValidationError):
        ObservedIdV1(presence="present", value=native_id)
    with pytest.raises(TikTokDiscoveryParseError):
        parse_pixel_page(pixel_request(), envelope("pixels", [{"pixel_id": native_id}]))


@pytest.mark.parametrize("events,presence", [(None, "null"), ([], "present")])
def test_missing_null_and_empty_events_never_mean_missing_tracking(
    events: Any,
    presence: str,
) -> None:
    missing = parse_pixel_page(pixel_request(), envelope("pixels", [{}])).pixels[0]
    assert missing.events.presence == "absent"
    pixel = parse_pixel_page(pixel_request(), envelope("pixels", [{"events": events}])).pixels[0]
    assert pixel.events.presence == presence
    assert pixel.tracking_readiness == "unknown"


def test_event_optimization_is_verbatim_not_derived_from_name_or_code() -> None:
    result = parse_pixel_page(
        pixel_request(),
        envelope(
            "pixels",
            [
                {
                    "events": [
                        {
                            "name": "Purchase",
                            "event_code": "Purchase",
                            "event_type": "PAGE_VIEW",
                            "optimization_event": None,
                        },
                        {"name": "Purchase", "event_code": "Purchase"},
                        {
                            "optimization_event": "NEW_NATIVE_EVENT",
                            "currency": "EUR",
                            "statistic_type": "NEW_MODE",
                            "rules": [{"pii": "not-retained"}],
                        },
                    ],
                    "pixel_script": "not-retained",
                    "advanced_matching_fields": {"email": "not-retained"},
                    "activity_status": "NO_RECENT_ACTIVITY",
                    "pixel_setup_mode": "NEW_MODE",
                }
            ],
        ),
    )
    events = result.pixels[0].events.value
    assert events is not None
    assert events[0].optimization_event.presence == "null"
    assert events[1].optimization_event.presence == "absent"
    assert events[2].optimization_event.value == "NEW_NATIVE_EVENT"
    assert events[2].optimization_event.recognition == "not_evaluated"
    assert events[2].currency.recognition == "unrecognized"
    assert events[2].statistic_type.recognition == "unrecognized"
    assert "not-retained" not in result.model_dump_json()
    assert "NO_RECENT_ACTIVITY" not in result.model_dump_json()


@pytest.mark.parametrize(
    "row",
    [
        {"events": [{"event_type": "PAGE_VIEW", "optimization_event": "PAGE_VIEW"}]},
        {"events": {}},
        {"events": [None]},
        {"events": [{}] * 1001},
        {"asset_ownership": {"ownership_status": 1}},
        {"asset_ownership": {"asset_relation_status": "SHARED", "ownership_status": True}},
        {"asset_ownership": {"asset_relation_status": None, "ownership_status": False}},
        {"asset_ownership": {"asset_relation_status": "TRANSFERRED", "owner_bc_id": None}},
        {"asset_ownership": {"asset_relation_status": "UNBOUND", "owner_bc_id": "bc"}},
    ],
)
def test_malformed_or_contradictory_pixel_fields_rejected(row: dict[str, Any]) -> None:
    with pytest.raises(TikTokDiscoveryParseError):
        parse_pixel_page(pixel_request(), envelope("pixels", [row]))


@pytest.mark.parametrize(
    "relation,owned,bc",
    [
        (None, True, None),
        ("TRANSFERRED", True, "bc"),
        ("SHARED", False, None),
        ("UNBOUND", False, None),
        ("NEW_RELATION", True, "unknown-bc"),
    ],
)
def test_ownership_preserves_native_observation_without_eligibility(
    relation: str | None,
    owned: bool,
    bc: str | None,
) -> None:
    result = parse_pixel_page(
        pixel_request(),
        envelope(
            "pixels",
            [
                {
                    "asset_ownership": {
                        "asset_relation_status": relation,
                        "ownership_status": owned,
                        "owner_bc_id": bc,
                    }
                }
            ],
        ),
    )
    observation = result.pixels[0].asset_ownership.value
    assert observation is not None
    assert observation.ownership_status.value is owned
    assert observation.asset_relation_status.value == relation
    assert result.publication_eligibility == "not_assessed"


@pytest.mark.parametrize(
    "key,value",
    [
        ("page", "1"),
        ("page", True),
        ("page", 2),
        ("page_size", 20),
        ("total_number", 0),
        ("total_page", 0),
        ("total_page", -1),
    ],
)
def test_pagination_requires_matching_bounded_request(key: str, value: Any) -> None:
    payload = envelope("pixels", [{}])
    payload["data"]["page_info"][key] = value
    with pytest.raises(TikTokDiscoveryParseError):
        parse_pixel_page(pixel_request(), payload)


@pytest.mark.parametrize("code", [True, "0", 1, None])
def test_errors_are_sanitized_and_never_echo_provider_message(code: Any) -> None:
    with pytest.raises(TikTokDiscoveryParseError) as error:
        parse_pixel_page(pixel_request(), {"code": code, "message": "SENSITIVE"})
    assert str(error.value) == "tiktok_discovery_response_unavailable"
    assert error.value.__cause__ is None


def test_empty_page_and_tampered_request_and_result_contracts() -> None:
    result = parse_pixel_page(pixel_request(), envelope("pixels", []))
    assert result.pixels == ()
    tampered = pixel_request().model_copy(update={"page_size": 100})
    with pytest.raises(TikTokDiscoveryParseError):
        parse_pixel_page(tampered, envelope("pixels", [], 100))
    with pytest.raises(ValidationError):
        ObservedFieldV1[bool](presence="absent", value=False)
    with pytest.raises(ValidationError):
        type(result).model_validate({**result.model_dump(), "publication_eligibility": "eligible"})


@pytest.mark.parametrize("value,presence", [(True, "present"), (False, "present"), (None, "null")])
def test_deprecated_event_observation_is_not_lost(value: bool | None, presence: str) -> None:
    result = parse_pixel_page(
        pixel_request(),
        envelope(
            "pixels",
            [
                {
                    "events": [
                        {"deprecated": value},
                        {},
                    ]
                }
            ],
        ),
    )
    events = result.pixels[0].events.value
    assert events is not None
    assert events[0].deprecated.presence == presence
    assert events[0].deprecated.value is value
    assert events[1].deprecated.presence == "absent"
    with pytest.raises(TikTokDiscoveryParseError):
        parse_pixel_page(pixel_request(), envelope("pixels", [{"events": [{"deprecated": 1}]}]))


def test_duplicate_known_ids_rejected_but_scalar_shapes_never_collapsed() -> None:
    with pytest.raises(TikTokDiscoveryParseError):
        parse_identity_page(identity_request(), envelope("identity_list", [identity()] * 2, 20))
    with pytest.raises(TikTokDiscoveryParseError):
        parse_pixel_page(pixel_request(), envelope("pixels", [{"pixel_id": 42}] * 2))
    result = parse_pixel_page(
        pixel_request(),
        envelope(
            "pixels",
            [
                {"pixel_id": 42},
                {"pixel_id": "42"},
                {},
                {},
            ],
        ),
    )
    assert len(result.pixels) == 4
    assert result.scalar_shape_qualification == "unverified"


def test_page_counts_are_not_complete_inventory_proof() -> None:
    payload = envelope("pixels", [{"pixel_id": "p"}])
    payload["data"]["page_info"].update(total_number=100, total_page=1)
    result = parse_pixel_page(pixel_request(), payload)
    assert result.collection_completeness == "page_only"
    assert result.pagination_consistency == "unverified"
    assert result.page_info.total_number == 100
    assert type(result).model_validate_json(result.model_dump_json()) == result
