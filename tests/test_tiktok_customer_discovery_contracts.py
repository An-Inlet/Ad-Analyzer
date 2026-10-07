from typing import Any

import pytest
from app.collectors.tiktok_customer_discovery_contracts import (
    TikTokDiscoveryIntentV1,
    TikTokDiscoveryViewV1,
)
from pydantic import ValidationError


def unavailable() -> dict[str, Any]:
    return dict(
        account_id=1,
        identity_type="BC_AUTH_TT",
        status="unavailable",
        reason="business_center_selection_unavailable",
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


def test_unavailable_has_no_zero_counts_or_authority() -> None:
    view = TikTokDiscoveryViewV1.model_validate(unavailable())
    assert view.event_count is None
    assert view.publication_eligibility == "not_assessed"
    assert view.spending_authority == "none"
    for name, value in (
        ("pixel_count", 0),
        ("spending_authority", "granted"),
        ("display_truncated", True),
    ):
        with pytest.raises(ValidationError):
            TikTokDiscoveryViewV1.model_validate({**unavailable(), name: value})


@pytest.mark.parametrize("extra", ["advertiser_id", "identity_id", "access_token", "proof"])
def test_intent_cannot_supply_native_identity_or_proof(extra: str) -> None:
    with pytest.raises(ValidationError):
        TikTokDiscoveryIntentV1.model_validate(
            {"account_id": 1, "identity_type": "TT_USER", extra: "forbidden"}
        )


@pytest.mark.parametrize(
    "presence,count,truncated",
    [
        ("absent", 0, False),
        ("null", None, True),
        ("present", None, False),
        ("present", 1, False),
        ("present", 0, True),
    ],
)
def test_event_display_cannot_invent_missing_counts(
    presence: str,
    count: int | None,
    truncated: bool,
) -> None:
    from app.collectors.tiktok_customer_discovery_contracts import TikTokPixelDisplayV1

    with pytest.raises(ValidationError):
        TikTokPixelDisplayV1.model_validate(
            dict(
                label="Pixel",
                ownership="unknown",
                events_presence=presence,
                events_count=count,
                events=(),
                events_display_truncated=truncated,
                reasons=("pixel_scalar_shape_unverified", "tracking_readiness_unknown"),
            )
        )
