"""Pure bounded projections of the supplied rendered v1.3 tables; no provider IO."""

from typing import Any, Literal

from pydantic import ValidationError

from app.collectors.tiktok_discovery_contracts import (
    Applicability,
    ObservedFieldV1,
    ObservedIdV1,
    TikTokIdentityObservationV1,
    TikTokIdentityPageRequestV1,
    TikTokIdentityPageV1,
    TikTokPageInfoV1,
    TikTokPixelEventV1,
    TikTokPixelObservationV1,
    TikTokPixelOwnershipV1,
    TikTokPixelPageRequestV1,
    TikTokPixelPageV1,
)

IDENTITY_TYPES = frozenset({"CUSTOMIZED_USER", "AUTH_CODE", "TT_USER", "BC_AUTH_TT"})
IDENTITY_STATUS = frozenset(
    {
        "AVAILABLE",
        "NO_VALID_BIND_ACCOUNT",
        "SCOPE_UNAVAILABLE",
        "IS_PRIVATE_ACCOUNT",
        "NOT_BUSINESS_ACCOUNT",
    }
)


class TikTokDiscoveryParseError(ValueError):
    """Sanitized error; no provider message, raw object or personal fields attached."""


def invalid() -> TikTokDiscoveryParseError:
    return TikTokDiscoveryParseError("tiktok_discovery_response_unavailable")


def object_value(value: object) -> dict[str, Any]:
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise invalid()
    return value


def field[S: (str, bool)](
    row: dict[str, Any],
    key: str,
    kind: type[S],
    *,
    applicability: Applicability = "unknown",
    known: frozenset[str] | None = None,
) -> ObservedFieldV1[S]:
    if key not in row or row[key] is None:
        return ObservedFieldV1(
            presence="absent" if key not in row else "null", applicability=applicability
        )
    value = row[key]
    if type(value) is not kind or (isinstance(value, str) and len(value) > 512):
        raise invalid()
    recognition: Literal["recognized", "unrecognized", "not_evaluated"] = (
        ("recognized" if value in known else "unrecognized") if known else "not_evaluated"
    )
    return ObservedFieldV1(
        presence="present", applicability=applicability, recognition=recognition, value=value
    )


def identifier(row: dict[str, Any], key: str) -> ObservedIdV1:
    if key not in row or row[key] is None:
        return ObservedIdV1(presence="absent" if key not in row else "null")
    value = row[key]
    if (
        type(value) not in (str, int)
        or (isinstance(value, str) and (not value or len(value) > 128))
        or (type(value) is int and not 0 <= value <= 2**64 - 1)
    ):
        raise invalid()
    return ObservedIdV1(presence="present", value=value)


def page(
    payload: object, key: str, requested_page: int, size: int
) -> tuple[TikTokPageInfoV1, list[dict[str, Any]]]:
    envelope = object_value(payload)
    if type(envelope.get("code")) is not int or envelope["code"] != 0:
        raise invalid()
    data = object_value(envelope.get("data"))
    raw_info = object_value(data.get("page_info"))
    info = TikTokPageInfoV1.model_validate(
        {name: raw_info.get(name) for name in ("page", "page_size", "total_page", "total_number")}
    )
    rows = data.get(key)
    if (
        not isinstance(rows, list)
        or len(rows) > size
        or info.page != requested_page
        or info.page_size != size
        or info.total_number < len(rows)
        or (info.total_page == 0 and (rows or info.total_number))
        or (info.total_page > 0 and info.page > info.total_page)
    ):
        raise invalid()
    return info, [object_value(row) for row in rows]


def parse_identity_page(
    request: TikTokIdentityPageRequestV1, payload: object
) -> TikTokIdentityPageV1:
    try:
        request = TikTokIdentityPageRequestV1.model_validate(request.model_dump())
        info, rows = page(payload, "identity_list", request.page, request.page_size)
        identities = []
        seen: set[str] = set()
        for row in rows:
            kind = field(row, "identity_type", str, known=IDENTITY_TYPES)
            if kind.recognition == "recognized" and kind.value != request.identity_type:
                raise invalid()
            linked: Applicability = (
                "applicable"
                if kind.value in {"TT_USER", "BC_AUTH_TT"}
                else "not_applicable"
                if kind.recognition == "recognized"
                else "unknown"
            )
            bc = field(row, "identity_authorized_bc_id", str)
            if (
                kind.value == "BC_AUTH_TT"
                and bc.presence == "present"
                and (bc.value != request.identity_authorized_bc_id)
            ):
                raise invalid()
            identity_id = row.get("identity_id")
            if not isinstance(identity_id, str) or identity_id in seen:
                raise invalid()
            seen.add(identity_id)
            identities.append(
                TikTokIdentityObservationV1(
                    identity_id=identity_id,
                    identity_type=kind,
                    identity_authorized_bc_id=bc,
                    display_name=field(row, "display_name", str),
                    available_status=field(
                        row, "available_status", str, applicability=linked, known=IDENTITY_STATUS
                    ),
                    ads_only_mode=field(
                        row,
                        "ads_only_mode",
                        bool,
                        applicability=(
                            "applicable"
                            if kind.value == "BC_AUTH_TT"
                            else "not_applicable"
                            if kind.recognition == "recognized"
                            else "unknown"
                        ),
                    ),
                    **{
                        key: field(row, key, bool, applicability=linked)
                        for key in (
                            "is_gpppa",
                            "can_push_video",
                            "can_pull_video",
                            "can_use_live_ads",
                            "can_manage_message",
                        )
                    },
                )
            )
        return TikTokIdentityPageV1(request=request, page_info=info, identities=tuple(identities))
    except (ValidationError, TypeError, KeyError, ValueError):
        raise invalid() from None


def ownership(raw: object) -> TikTokPixelOwnershipV1:
    row = object_value(raw)
    relation = field(
        row, "asset_relation_status", str, known=frozenset({"TRANSFERRED", "SHARED", "UNBOUND"})
    )
    owned = field(row, "ownership_status", bool)
    bc = field(row, "owner_bc_id", str)
    if owned.presence == "present":
        expected = (
            True
            if relation.presence == "null" or relation.value == "TRANSFERRED"
            else (False if relation.value in {"SHARED", "UNBOUND"} else None)
        )
        if expected is not None and owned.value != expected:
            raise invalid()
    if relation.value == "TRANSFERRED" and bc.presence == "null":
        raise invalid()
    if (relation.presence == "null" or relation.value in {"SHARED", "UNBOUND"}) and (
        bc.presence == "present"
    ):
        raise invalid()
    return TikTokPixelOwnershipV1(
        asset_relation_status=relation, ownership_status=owned, owner_bc_id=bc
    )


def event(raw: object) -> TikTokPixelEventV1:
    row = object_value(raw)
    event_type = field(row, "event_type", str)
    optimization = field(row, "optimization_event", str)
    if event_type.value == "PAGE_VIEW" and optimization.presence == "present":
        raise invalid()
    return TikTokPixelEventV1(
        deprecated=field(row, "deprecated", bool),
        name=field(row, "name", str),
        event_type=event_type,
        custom_event_type=field(row, "custom_event_type", str),
        event_code=field(row, "event_code", str),
        event_id=identifier(row, "event_id"),
        optimization_event=optimization,
        statistic_type=field(row, "statistic_type", str, known=frozenset({"EVERY_TIME", "ONCE"})),
        currency=field(row, "currency", str, known=frozenset({"INR", "JPY", "USD"})),
    )


def parse_pixel_page(request: TikTokPixelPageRequestV1, payload: object) -> TikTokPixelPageV1:
    try:
        request = TikTokPixelPageRequestV1.model_validate(request.model_dump())
        info, rows = page(payload, "pixels", request.page, request.page_size)
        pixels = []
        seen: set[tuple[type[str] | type[int], str | int]] = set()
        for row in rows:
            pixel_id = identifier(row, "pixel_id")
            if pixel_id.value is not None:
                key = (type(pixel_id.value), pixel_id.value)
                if key in seen:
                    raise invalid()
                seen.add(key)
            owner: ObservedFieldV1[TikTokPixelOwnershipV1] = ObservedFieldV1(
                presence="absent" if "asset_ownership" not in row else "null"
            )
            if row.get("asset_ownership") is not None:
                owner = ObservedFieldV1(presence="present", value=ownership(row["asset_ownership"]))
            events: ObservedFieldV1[tuple[TikTokPixelEventV1, ...]] = ObservedFieldV1(
                presence="absent" if "events" not in row else "null"
            )
            if row.get("events") is not None:
                if not isinstance(row["events"], list) or len(row["events"]) > 1000:
                    raise invalid()
                events = ObservedFieldV1(presence="present", value=tuple(map(event, row["events"])))
            pixels.append(
                TikTokPixelObservationV1(
                    pixel_id=pixel_id,
                    pixel_code=field(row, "pixel_code", str),
                    pixel_name=field(row, "pixel_name", str),
                    pixel_setup_mode=field(
                        row, "pixel_setup_mode", str, known=frozenset({"STANDARD", "DEVELOPER"})
                    ),
                    asset_ownership=owner,
                    events=events,
                )
            )
        return TikTokPixelPageV1(request=request, page_info=info, pixels=tuple(pixels))
    except (ValidationError, TypeError, KeyError, ValueError):
        raise invalid() from None
