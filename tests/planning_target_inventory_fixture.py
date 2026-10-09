"""Closed offline inventory phases; actual native readers still produce every catalog."""

from typing import Literal

import httpx
import pytest
from app.collectors import account_diagnostics

Platform = Literal["google_ads", "meta_ads", "tiktok_ads"]
Phase = Literal["original", "absent", "replacement"]


class InventoryScenario:
    def __init__(self, platform: Platform) -> None:
        if platform not in ("google_ads", "meta_ads", "tiktok_ads"):
            raise ValueError("unsupported inventory fixture platform")
        self.platform = platform
        self.phase: Phase = "original"
        self._transport = account_diagnostics.diagnostic_transport

    def advance(self, phase: Literal["absent", "replacement"]) -> None:
        if (self.phase, phase) not in (("original", "absent"), ("absent", "replacement")):
            raise ValueError("ordered inventory phase required")
        self.phase = phase

    def wire(self, request: httpx.Request) -> httpx.Response:
        phase = self.phase
        transport = self._transport()
        assert transport is not None
        with transport:
            response = transport.handle_request(request)
            response.read()
        payload = response.json()
        if self.platform == "google_ads" and "results" in payload:
            rows = payload["results"]
            if any("campaign" in row for row in rows):
                if phase == "absent":
                    payload["results"] = []
                elif phase == "replacement":
                    for row in rows:
                        row["campaign"]["resourceName"] = "customers/1234567890/campaigns/9"
        elif self.platform == "meta_ads" and request.url.path.endswith(("/campaigns", "/adsets")):
            if phase == "absent":
                payload["data"] = []
            elif phase == "replacement":
                for row in payload["data"]:
                    if "campaign_id" in row:
                        row["campaign_id"] = "9"
                    else:
                        row["id"] = "9"
        elif self.platform == "tiktok_ads" and request.url.path.endswith(
            ("/campaign/get/", "/adgroup/get/")
        ):
            if phase == "absent":
                payload["data"]["list"] = []
                payload["data"]["page_info"]["total_number"] = 0
            elif phase == "replacement":
                for row in payload["data"]["list"]:
                    row["campaign_id"] = "9"
        return httpx.Response(response.status_code, json=payload)


def install_inventory_scenario(platform: Platform, patch: pytest.MonkeyPatch) -> InventoryScenario:
    scenario = InventoryScenario(platform)
    patch.setattr(
        account_diagnostics, "diagnostic_transport", lambda: httpx.MockTransport(scenario.wire)
    )
    return scenario
