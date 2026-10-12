"""Actual shared-owner topology and planning rejection; no native-edit qualification."""

import copy
import hmac
import json
import threading
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


class OwnerCatalogResponseControl:
    """One-way native-response fixture switch; never changes retained evidence."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._partial = False
        self._partial_responses = 0

    @property
    def partial_responses(self) -> int:
        with self._lock:
            return self._partial_responses

    def make_partial(self) -> None:
        with self._lock:
            if self._partial:
                raise ValueError("Native response already switched")
            self._partial = True

    def _budget_rows(self, original: list[dict[str, Any]]) -> list[dict[str, Any]]:
        with self._lock:
            rows = copy.deepcopy(original)
            shared = [
                row["campaignBudget"]
                for row in rows
                if row["campaignBudget"]["resourceName"] == PREFIX + "campaignBudgets/2"
            ]
            assert len(shared) == 1 and shared[0]["referenceCount"] == "2"
            if self._partial:
                assert self._partial_responses < 20
                shared[0]["referenceCount"] = "3"
                self._partial_responses += 1
            return rows


def acquired_owner_catalog(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    partial: bool = False,
    *,
    response_control: OwnerCatalogResponseControl | None = None,
    native_names: dict[str, str] | None = None,
    configured_runtime: bool = False,
) -> tuple[Any, dict[str, Any], list[tuple[str, str]]]:
    # Copy once before bootstrap; callers cannot mutate later acquisition responses.
    names = {} if native_names is None else dict(native_names)
    if any(
        type(key) is not str or key not in {"1", "2", "3"}
        or type(value) is not str or not 1 <= len(value) <= 160
        or any(ord(char) < 32 or ord(char) > 126 for char in value)
        for key, value in names.items()
    ):
        raise ValueError("Invalid synthetic native campaign names")
    if partial and response_control is not None:
        raise ValueError("Static partial and response controller are mutually exclusive")
    fixture = prepare_creative_common_basis(
        customer_engine,
        configuration,
        replicas,
        monkeypatch,
        tmp_path / "media",
        platform="google_ads",
        selected_value="10",
        configured_runtime=configured_runtime,
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
                "name": names.get(native, f"Mug Campaign {native}"),
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
            query_key = key(query)
            rows = data[query_key]
            if query_key == "campaign_budget" and response_control is not None:
                rows = response_control._budget_rows(rows)
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
    if not hmac.compare_digest(alice.cookies[SESSION_COOKIE], original_session):
        raise AssertionError("Original authenticated session changed")
    return fixture, response.json(), calls
