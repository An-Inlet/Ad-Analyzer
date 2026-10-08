"""Observed native amounts must not fabricate independently controlled budget pools."""

from datetime import timedelta

import httpx
import pytest
from app.collectors.meta_native_inventory import MetaNativeInventoryHTTP
from app.collectors.tiktok_native_inventory import TikTokNativeInventoryHTTP
from app.planning_catalog.projection import project

from tests.test_meta_native_inventory import (
    NOW,
)
from tests.test_meta_native_inventory import (
    Server as MetaServer,
)
from tests.test_meta_native_inventory import (
    context as meta_context,
)
from tests.test_meta_native_inventory import (
    request as meta_request,
)
from tests.test_tiktok_native_inventory import (
    Server as TikTokServer,
)
from tests.test_tiktok_native_inventory import (
    context as tiktok_context,
)
from tests.test_tiktok_native_inventory import (
    request as tiktok_request,
)


@pytest.mark.parametrize("optimize", [True, False, None])
def test_tiktok_budget_amount_does_not_establish_owner(optimize: bool | None) -> None:
    server = TikTokServer()

    def wire(request: httpx.Request) -> httpx.Response:
        response = server(request)
        data = response.json()
        if request.url.path.endswith("campaign/get/"):
            data["data"]["list"][0]["budget_optimize_on"] = optimize
        return httpx.Response(200, json=data)

    req = tiktok_request().model_copy(
        update={"period_start": NOW - timedelta(days=1), "period_end": NOW}
    )
    result = TikTokNativeInventoryHTTP(
        tiktok_context, clock=lambda: NOW, transport=httpx.MockTransport(wire)
    )(req, NOW)
    catalog = project(result)
    assert len(catalog.targets) >= 2
    assert catalog.targets[0].settings.model_dump()["budget_native"] == str(server.budget)
    for target in catalog.targets:
        assert target.budget_owner_key is None
        assert "budget_owner" in target.unavailable_fields
        assert "budget_owner_unresolved" in target.reasons


@pytest.mark.parametrize("sharing", [True, False, None])
def test_meta_amount_does_not_establish_owner(sharing: bool | None) -> None:
    server = MetaServer()

    def wire(request: httpx.Request) -> httpx.Response:
        response = server(request)
        data = response.json()
        if request.url.path.endswith("/campaigns"):
            data["data"][0]["is_adset_budget_sharing_enabled"] = sharing
        return httpx.Response(200, json=data)

    req = meta_request().model_copy(
        update={"period_start": NOW - timedelta(days=1), "period_end": NOW}
    )
    result = MetaNativeInventoryHTTP(
        meta_context, clock=lambda: NOW, transport=httpx.MockTransport(wire)
    )(req, NOW)
    catalog = project(result)
    assert len(catalog.targets) >= 2
    assert all(t.budget_owner_key is None for t in catalog.targets)
    assert catalog.targets[0].settings.model_dump()["daily_budget_native"] == 100
