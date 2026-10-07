"""Owned customer display projection, without native identifiers or write qualification."""

import unicodedata
from typing import Literal

from app.collectors.tiktok_customer_discovery_contracts import (
    EventReason,
    TikTokDiscoveryIntentV1,
    TikTokDiscoveryViewV1,
    TikTokEventDisplayV1,
    TikTokIdentityDisplayV1,
    TikTokPermissionDisplayV1,
    TikTokPixelDisplayV1,
)
from app.collectors.tiktok_discovery_contracts import (
    ObservedFieldV1,
    TikTokIdentityObservationV1,
    TikTokPixelEventV1,
    TikTokPixelObservationV1,
)
from app.collectors.tiktok_owned_discovery_contracts import (
    TikTokIdentityDiscoveryV1,
    TikTokPixelDiscoveryV1,
)


def unavailable(
    intent: TikTokDiscoveryIntentV1,
    reason: Literal["discovery_not_available", "business_center_selection_unavailable"],
) -> TikTokDiscoveryViewV1:
    return TikTokDiscoveryViewV1(
        account_id=intent.account_id,
        identity_type=intent.identity_type,
        status="unavailable",
        reason=reason,
        environment=None,
        collection_completeness="not_observed",
        observed_started_at=None,
        observed_ended_at=None,
        identity_count=None,
        pixel_count=None,
        event_count=None,
        identities=(),
        pixels=(),
        identities_display_truncated=False,
        pixels_display_truncated=False,
        display_truncated=False,
    )


def label(value: str | None, fallback: str) -> str:
    if value is None:
        return fallback
    cleaned = " ".join(
        "".join(char for char in value if not unicodedata.category(char).startswith("C")).split()
    )[:120]
    return cleaned or fallback


def state(value: ObservedFieldV1[bool]) -> str:
    if value.applicability == "not_applicable":
        return "not_applicable"
    if value.presence != "present":
        return value.presence
    if value.applicability != "applicable":
        return "unknown"
    return "true" if value.value else "false"


def identity_display(value: TikTokIdentityObservationV1, index: int) -> TikTokIdentityDisplayV1:
    status = value.available_status
    displayed = (
        "not_applicable"
        if status.applicability == "not_applicable"
        else status.presence
        if status.presence != "present"
        else status.value
        if status.applicability == "applicable" and status.recognition == "recognized"
        else "unknown"
    )
    return TikTokIdentityDisplayV1.model_validate(
        {
            "label": label(value.display_name.value, f"Identity {index}"),
            "status": displayed,
            "permissions": tuple(
                TikTokPermissionDisplayV1.model_validate(
                    {
                        "name": name,
                        "state": state(getattr(value, name)),
                    }
                )
                for name in (
                    "ads_only_mode",
                    "is_gpppa",
                    "can_push_video",
                    "can_pull_video",
                    "can_use_live_ads",
                    "can_manage_message",
                )
            ),
            "reasons": ("custom_identity_phaseout",)
            if value.identity_type.value == "CUSTOMIZED_USER"
            else ("identity_route_not_assessed",),
        }
    )


def event_display(value: TikTokPixelEventV1, index: int) -> TikTokEventDisplayV1:
    reasons: list[EventReason] = ["event_selection_not_assessed"]
    if value.deprecated.value is True:
        reasons.append("event_deprecated")
    elif value.deprecated.value is None:
        reasons.append("event_deprecation_unknown")
    if value.event_type.value == "PAGE_VIEW":
        reasons.append("event_not_optimizable")
    if value.optimization_event.value is None:
        reasons.append("optimization_event_unreported")
    return TikTokEventDisplayV1(
        label=label(value.name.value, f"Event {index}"), reasons=tuple(reasons)
    )


def pixel_display(value: TikTokPixelObservationV1, index: int) -> TikTokPixelDisplayV1:
    ownership: Literal["reported_owned", "shared", "unbound", "unknown"] = "unknown"
    facts = value.asset_ownership.value
    if facts is not None:
        relation = facts.asset_relation_status
        if facts.ownership_status.value is True and (
            relation.presence == "null" or relation.value == "TRANSFERRED"
        ):
            ownership = "reported_owned"
        elif facts.ownership_status.value is False and relation.value == "SHARED":
            ownership = "shared"
        elif facts.ownership_status.value is False and relation.value == "UNBOUND":
            ownership = "unbound"
    events = value.events.value
    return TikTokPixelDisplayV1(
        label=label(value.pixel_name.value, f"Pixel {index}"),
        ownership=ownership,
        events_count=len(events) if events is not None else None,
        events_presence=value.events.presence,
        events=tuple(
            event_display(event, number) for number, event in enumerate((events or ())[:20], 1)
        ),
        events_display_truncated=bool(events is not None and len(events) > 20),
        reasons=("pixel_scalar_shape_unverified", "tracking_readiness_unknown"),
    )


def project(
    intent: TikTokDiscoveryIntentV1,
    identity: TikTokIdentityDiscoveryV1,
    pixels: TikTokPixelDiscoveryV1,
) -> TikTokDiscoveryViewV1:
    if (
        identity.scope != pixels.scope
        or identity.scope.account_id != intent.account_id
        or (any(page.request.identity_type != intent.identity_type for page in identity.pages))
    ):
        raise ValueError("discovery projection scope changed")
    identities = tuple(value for page in identity.pages for value in page.identities)
    pixel_values = tuple(value for page in pixels.pages for value in page.pixels)
    displayed_pixels = tuple(
        pixel_display(value, index) for index, value in enumerate(pixel_values[:20], 1)
    )
    event_count = (
        sum(len(value.events.value or ()) for value in pixel_values)
        if all(value.events.presence == "present" for value in pixel_values)
        else None
    )
    return TikTokDiscoveryViewV1(
        account_id=intent.account_id,
        identity_type=intent.identity_type,
        status="observed",
        reason=None,
        environment="contract_test",
        collection_completeness="complete_requested_scope",
        observed_started_at=min(identity.observed_started_at, pixels.observed_started_at),
        observed_ended_at=max(identity.observed_ended_at, pixels.observed_ended_at),
        identity_count=len(identities),
        pixel_count=len(pixel_values),
        event_count=event_count,
        identities=tuple(
            identity_display(value, index) for index, value in enumerate(identities[:20], 1)
        ),
        pixels=displayed_pixels,
        identities_display_truncated=len(identities) > 20,
        pixels_display_truncated=len(pixel_values) > 20,
        display_truncated=len(identities) > 20
        or len(pixel_values) > 20
        or any(value.events_display_truncated for value in displayed_pixels),
    )
