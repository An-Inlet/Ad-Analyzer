"""Actual shared-owner topology and planning rejection; no native-edit qualification."""

import json
from pathlib import Path
from typing import Any

import httpx
import pytest
from app.api import customer_planning_target_catalog
from app.collectors import account_diagnostics
from app.customers.access import SESSION_COOKIE
from app.settings import Settings
from sqlalchemy import Engine

from tests.creative_common_basis_fixture import prepare_creative_common_basis
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_customer_optimization_api import headers
from tests.test_google_native_inventory import PREFIX, key, payloads
from tests.test_shopify_sales import configuration as configuration


def acquired_owner_catalog(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    partial: bool = False,
) -> tuple[Any, dict[str, Any], list[tuple[str, str]]]:
    fixture = prepare_creative_common_basis(
        customer_engine,
        configuration,
        replicas,
        monkeypatch,
        tmp_path / "media",
        platform="google_ads",
        selected_value="10",
    )
    alice, _, _ = replicas
    aid, wid = fixture.basis.account_id, fixture.basis.workspace_id
    original_session = alice.cookies[SESSION_COOKIE]
    data = payloads()
    original = data["campaign"][0]["campaign"]
    data["campaign"] = [
        {
            "campaign": {
                **original,
                "resourceName": PREFIX + f"campaigns/{native}",
                "campaignBudget": PREFIX + f"campaignBudgets/{budget}",
                "name": f"Mug Campaign {native}",
            }
        }
        for native, budget in (("1", "2"), ("2", "2"), ("3", "4"))
    ]
    shared = data["campaign_budget"][0]["campaignBudget"]
    shared.update(referenceCount="3" if partial else "2", explicitlyShared=True)
    data["campaign_budget"].append(
        {
            "campaignBudget": {
                **shared,
                "resourceName": PREFIX + "campaignBudgets/4",
                "referenceCount": "1",
                "explicitlyShared": False,
            }
        }
    )
    calls: list[tuple[str, str]] = []
    campaign_pages: list[str] = []

    def wire(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        calls.append((request.url.host, request.url.path))
        if request.url.host == "oauth2.googleapis.com":
            assert request.url.path == "/token"
            return httpx.Response(
                200,
                json=dict(access_token="synthetic-access", token_type="Bearer", expires_in=3600),
            )
        assert request.url.host == "googleads.googleapis.com"
        assert request.url.path.endswith("/googleAds:search")
        body = json.loads(request.content)
        query = body["query"]
        if "FROM ad_group" in query:
            rows = [
                {
                    "adGroup": dict(
                        id=str(10 + i),
                        resourceName=PREFIX + f"adGroups/{10 + i}",
                        campaign=PREFIX + f"campaigns/{i}",
                        name=f"Mug Child {i}",
                        status="ENABLED",
                        type="SEARCH_STANDARD",
                    )
                }
                for i in (1, 2, 3)
            ]
        elif "FROM campaign " in query or query.endswith("FROM campaign"):
            token = body.get("pageToken", "")
            assert token in {"", "second"}
            campaign_pages.append(token)
            return httpx.Response(
                200,
                json={
                    "results": data["campaign"][1:] if token else data["campaign"][:1],
                    **({} if token else {"nextPageToken": "second"}),
                },
            )
        else:
            rows = data[key(query)]
        return httpx.Response(200, json={"results": rows})

    monkeypatch.setattr(
        account_diagnostics, "diagnostic_transport", lambda: httpx.MockTransport(wire)
    )
    alice.app.include_router(customer_planning_target_catalog.router)
    root = f"/api/customer/v1/workspaces/{wid}"
    window = fixture.body["inputs"]["reporting_window"]
    response = alice.post(
        root + "/planning/target-catalog-v2",
        headers=headers(alice),
        json=dict(
            account_id=aid, starts_at=window["starts_at"], ends_at=window["ends_at_exclusive"]
        ),
    )
    assert response.status_code == 200, response.text
    assert alice.cookies[SESSION_COOKIE] == original_session
    return fixture, response.json(), calls
