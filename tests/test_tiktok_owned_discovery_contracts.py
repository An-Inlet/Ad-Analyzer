from datetime import UTC, datetime
from typing import Any

import pytest
from app.collectors.tiktok_discovery_parser import parse_pixel_page
from app.collectors.tiktok_owned_discovery_contracts import (
    TikTokDiscoveryScopeV1,
    TikTokPixelDiscoveryV1,
)
from pydantic import ValidationError

from tests.test_tiktok_discovery_parser import envelope, pixel_request


def scope() -> TikTokDiscoveryScopeV1:
    return TikTokDiscoveryScopeV1(
        workspace_id=1,
        account_id=2,
        connection_id=3,
        external_advertiser_id="123",
        connection_version="version",
    )


@pytest.mark.parametrize("change", ["none", "totals", "scope", "missing", "unknown_id"])
def test_aggregate_cannot_claim_complete_from_partial_page(change: str) -> None:
    payload = envelope("pixels", [{"pixel_id": "p"}])
    if change == "totals":
        payload["data"]["page_info"]["total_number"] = 100
    if change == "missing":
        payload["data"]["pixels"] = []
    if change == "unknown_id":
        payload["data"]["pixels"] = [{}]
    page = parse_pixel_page(
        pixel_request(advertiser_id="123" if change != "scope" else "999"), payload
    )
    data: dict[str, Any] = dict(
        scope=scope(),
        observed_started_at=datetime.now(UTC),
        observed_ended_at=datetime.now(UTC),
        pages=(page,),
    )
    if change != "none":
        with pytest.raises(ValidationError):
            TikTokPixelDiscoveryV1(**data)
    else:
        result = TikTokPixelDiscoveryV1(**data)
        assert result.traversal_completeness == "complete_requested_scope"
        assert result.scalar_shape_qualification == "unverified"
        with pytest.raises(ValidationError):
            result.scope.account_id = 7
