"""Strict, non-authorizing planning catalog contract before consumer wiring."""

from datetime import UTC, datetime, timedelta

import pytest
from app.planning_catalog.contracts import CoverageV1, TargetCatalogIntentV1, TargetCatalogV1
from pydantic import ValidationError


@pytest.mark.parametrize(
    "platform,child", [("google_ads", "adgroup"), ("meta_ads", "adset"), ("tiktok_ads", "adgroup")]
)
def test_empty_unavailable_catalog_is_explicit(platform: str, child: str) -> None:
    now = datetime(2026, 10, 8, tzinfo=UTC)
    value = dict(
        workspace_id=1,
        account_id=2,
        connection_id=3,
        platform=platform,
        connection_version="generation:1",
        source_binding_digest="a" * 64,
        inventory_digest="b" * 64,
        currency="USD",
        time_zone="UTC",
        reporting_starts_at=now - timedelta(days=1),
        reporting_ends_at=now,
        observation_started_at=now,
        observed_at=now,
        expires_at=now + timedelta(seconds=60),
        coverage=[
            dict(
                kind=k,
                status="unavailable",
                observed_count=0,
                scope="not_collected",
                reasons=["inventory_unavailable"],
            )
            for k in ["campaign", child]
        ],
        targets=[],
    )
    result = TargetCatalogV1.model_validate(value)
    assert result.advertising_writes_enabled is False
    assert result.spending_authority == "none"
    changes: list[dict[str, object]] = [
        {"advertising_writes_enabled": True},
        {"mandate_id": "a" * 32},
        {"coverage": []},
        {"expires_at": now},
        {"time_zone": "Invalid/Zone"},
        {"connection_version": b"generation:1"},
        {
            "coverage": [
                result.coverage[0].model_copy(update={"status": "complete"}),
                result.coverage[1],
            ]
        },
    ]
    for changed in changes:
        with pytest.raises(ValidationError):
            TargetCatalogV1.model_validate({**value, **changed})


def test_missing_coverage_reason_and_unbounded_window_deny() -> None:
    with pytest.raises(ValidationError):
        CoverageV1(
            kind="campaign",
            status="partial",
            observed_count=0,
            scope="provider_campaigns",
            reasons=(),
        )
    now = datetime(2026, 10, 8, tzinfo=UTC)
    with pytest.raises(ValidationError):
        TargetCatalogIntentV1(account_id=1, starts_at=now - timedelta(days=367), ends_at=now)


@pytest.mark.parametrize(
    "scope", ["sdk_known_effective_statuses", "regular_campaign_families", "not_collected"]
)
def test_limited_coverage_cannot_be_complete(scope: str) -> None:
    with pytest.raises(ValidationError):
        CoverageV1.model_validate(
            dict(kind="campaign", status="complete", observed_count=0, scope=scope, reasons=[])
        )
