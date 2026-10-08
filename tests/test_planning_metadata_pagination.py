"""New sidecar pagination cannot turn repeated or changing pages into complete data."""

import json

import httpx
import pytest
from app.planning_catalog.metadata_http import PlanningMetadataUnavailable, read_metadata
from pydantic import SecretStr

from tests.test_planning_metadata_binding import bundle


@pytest.mark.parametrize("platform", ["google", "meta", "tiktok"])
def test_metadata_pagination_cycle_or_changed_totals_denies(platform: str) -> None:
    inventory, _ = bundle(platform)
    calls = []

    def wire(req: httpx.Request) -> httpx.Response:
        calls.append(req.url.path)
        if platform == "google":
            return httpx.Response(
                200,
                json=dict(
                    results=[
                        dict(
                            campaign=dict(
                                resourceName="customers/1234567890/campaigns/1", name="Owned"
                            )
                        )
                    ],
                    nextPageToken="same",
                ),
            )
        if platform == "meta":
            return httpx.Response(
                200,
                json=dict(
                    data=[dict(id="5", account_id="123", name="Owned")],
                    paging=dict(next="https://never-follow.invalid", cursors=dict(after="same")),
                ),
            )
        page = int(req.url.params["page"])
        assert json.loads(req.url.params["fields"]) == [
            "advertiser_id",
            "campaign_id",
            "campaign_name",
        ]
        return httpx.Response(
            200,
            json=dict(
                code=0,
                data=dict(
                    list=[dict(advertiser_id="123", campaign_id="5", campaign_name="Owned")],
                    page_info=dict(page=page, total_page=page + 1, total_number=2),
                ),
            ),
        )

    with pytest.raises(PlanningMetadataUnavailable):
        read_metadata(
            inventory,
            httpx.MockTransport(wire),
            lambda req, now: dict(
                scope=req.account,
                request_digest=req.digest(),
                access_token=SecretStr("synthetic"),
                expires_at=inventory.expires_at,
                developer_token=None,
                login_customer_id=None,
            ),
            lambda: inventory.observed_at,
        )
    assert len(calls) == 2
