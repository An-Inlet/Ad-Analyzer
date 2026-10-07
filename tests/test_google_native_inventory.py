"""Native read diagnostics never manufacture portfolio spending proof."""

import copy
import json
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from app.collectors.google_native_inventory import (
    GoogleInventoryRequest,
    GoogleNativeInventory,
    GoogleNativeInventoryContext,
    GoogleNativeInventoryHTTP,
    GoogleNativeInventoryRequest,
    GoogleNativeInventoryUnavailable,
)
from pydantic import SecretStr, ValidationError

NOW = datetime(2026, 10, 6, tzinfo=UTC)
CUSTOMER = "1234567890"
PREFIX = f"customers/{CUSTOMER}/"


def request() -> GoogleNativeInventoryRequest:
    return GoogleNativeInventoryRequest.model_validate(
        {
            "account": {
                "workspace_id": 1,
                "account": {"platform": "google_ads", "account_id": 2, "connection_id": 3},
                "external_advertiser_id": CUSTOMER,
                "connection_version": "google:3:1",
            },
            "mandate": {
                "mandate_id": "a" * 32,
                "revision": 1,
                "consent_id": "b" * 32,
                "policy_digest": "c" * 64,
                "ledger_id": "d" * 32,
                "environment": "contract_test",
            },
            "currency": "USD",
            "time_zone": "America/New_York",
            "period_start": NOW - timedelta(days=5),
            "period_end": NOW + timedelta(days=5),
        }
    )


def context(req: GoogleInventoryRequest, now: datetime) -> GoogleNativeInventoryContext:
    return GoogleNativeInventoryContext(
        scope=req.account,
        request_digest=req.digest(),
        access_token=SecretStr("test-secret"),
        expires_at=now + timedelta(minutes=3),
    )


def payloads() -> dict[str, list[dict[str, Any]]]:
    return {
        "customer": [
            {
                "customer": {
                    "id": CUSTOMER,
                    "resourceName": PREFIX[:-1],
                    "currencyCode": "USD",
                    "timeZone": "America/New_York",
                    "status": "ENABLED",
                }
            }
        ],
        "campaign": [
            {
                "campaign": {
                    "resourceName": PREFIX + "campaigns/1",
                    "campaignBudget": PREFIX + "campaignBudgets/2",
                    "status": "ENABLED",
                    "advertisingChannelType": "SEARCH",
                    "biddingStrategyType": "MANUAL_CPC",
                    "startDateTime": "2026-10-01 00:00:00",
                }
            }
        ],
        "campaign_budget": [
            {
                "campaignBudget": {
                    "resourceName": PREFIX + "campaignBudgets/2",
                    "amountMicros": "10000000",
                    "referenceCount": "1",
                    "period": "DAILY",
                    "status": "ENABLED",
                    "type": "STANDARD",
                }
            }
        ],
        "cost": [{"customer": {"id": CUSTOMER}, "metrics": {"costMicros": "75000000"}}],
        "billing_setup": [
            {"billingSetup": {"resourceName": PREFIX + "billingSetups/3", "status": "APPROVED"}}
        ],
        "account_budget": [
            {
                "accountBudget": {
                    "resourceName": PREFIX + "accountBudgets/4",
                    "billingSetup": PREFIX + "billingSetups/3",
                    "status": "APPROVED",
                    "approvedSpendingLimitMicros": "100000000",
                    "adjustedSpendingLimitMicros": "120000000",
                    "proposedStartDateTime": "2026-10-01 00:00:00",
                    "approvedEndDateTime": "2026-11-01 00:00:00",
                    "amountServedMicros": "75000000",
                }
            }
        ],
    }


def key(query: str) -> str:
    return "cost" if "metrics.cost_micros" in query else query.split(" FROM ")[1].split(" ")[0]


def reader(
    data: dict[str, list[dict[str, Any]]] | None = None,
) -> tuple[GoogleNativeInventoryHTTP, list[httpx.Request]]:
    data = data if data is not None else payloads()
    calls: list[httpx.Request] = []

    def handler(req: httpx.Request) -> httpx.Response:
        calls.append(req)
        return httpx.Response(200, json={"results": data[key(json.loads(req.content)["query"])]})

    return GoogleNativeInventoryHTTP(
        context, transport=httpx.MockTransport(handler), clock=lambda: NOW
    ), calls


def test_actual_inventory_never_qualifies_even_finite_account_cap() -> None:
    adapter, calls = reader()
    result = adapter(request(), NOW)
    assert result.reported_cost_micros == 75000000
    assert result.account_budgets[0].approved_limit_micros == 100000000
    assert result.account_budgets[0].adjusted_limit_micros == 120000000
    assert result.campaigns[0].end_date_time is None
    assert result.advertising_inventory_read_complete and result.billing_inventory_read_complete
    assert result.cap_semantics == "unqualified"
    assert result.reporting_watermark is None
    assert result.unreported_upper_micros is None
    assert result.unchanged_future_upper_micros is None
    assert result.proposed_owner_upper_micros is None
    assert {
        "billing_basis_unqualified",
        "external_writer_boundary_unproven",
        "reporting_completeness_unproven",
        "daily_budget_not_total_cap",
    } <= set(result.reasons)
    assert result.queried_start_date == "2026-09-30"
    assert result.queried_end_date == "2026-10-10"
    assert len(calls) == 6
    assert all(
        str(r.url) == f"https://googleads.googleapis.com/v25/customers/{CUSTOMER}/googleAds:search"
        for r in calls
    )
    assert all("mutate" not in str(r.url) for r in calls)
    assert "'REMOVED'" in json.loads(calls[1].content)["query"]
    assert len(result.digest()) == 64
    raw = result.model_dump()
    raw["unreported_upper_micros"] = 0
    with pytest.raises(ValidationError):
        GoogleNativeInventory.model_validate(raw)


def test_complete_pagination_includes_other_campaign_and_shared_budget() -> None:
    data = payloads()
    next_campaign = copy.deepcopy(data["campaign"][0])
    next_campaign["campaign"]["resourceName"] = PREFIX + "campaigns/9"
    next_campaign["campaign"]["advertisingChannelType"] = "DISPLAY"
    data["campaign_budget"][0]["campaignBudget"]["explicitlyShared"] = True
    data["campaign_budget"][0]["campaignBudget"]["referenceCount"] = "2"

    def handler(req: httpx.Request) -> httpx.Response:
        body = json.loads(req.content)
        table = key(body["query"])
        if table == "campaign":
            return httpx.Response(
                200,
                json={"results": [next_campaign]}
                if body.get("pageToken")
                else {"results": data[table], "nextPageToken": "page-two"},
            )
        return httpx.Response(200, json={"results": data[table]})

    result = GoogleNativeInventoryHTTP(
        context, transport=httpx.MockTransport(handler), clock=lambda: NOW
    )(request(), NOW)
    assert len(result.campaigns) == 2
    assert result.campaigns[1].channel == "DISPLAY"
    assert result.campaign_budgets[0].explicitly_shared
    assert result.cap_semantics == "unqualified"


@pytest.mark.parametrize(
    "mutation",
    ["pending", "unlimited", "future", "total", "missing_budget", "missing_setup", "missing_cost"],
)
def test_unknown_and_changing_caps_remain_diagnostics(mutation: str) -> None:
    data = payloads()
    ab = data["account_budget"][0]["accountBudget"]
    if mutation == "pending":
        ab["pendingProposal"] = {"accountBudgetProposal": PREFIX + "accountBudgetProposals/5"}
    elif mutation == "unlimited":
        ab["adjustedSpendingLimitType"] = "INFINITE"
    elif mutation == "future":
        other = dict(
            ab,
            resourceName=PREFIX + "accountBudgets/8",
            approvedStartDateTime="2026-10-10 00:00:00",
            approvedSpendingLimitMicros="900000000",
        )
        data["account_budget"].append({"accountBudget": other})
    elif mutation == "total":
        data["campaign_budget"][0]["campaignBudget"].update(
            period="CUSTOM_PERIOD", totalAmountMicros="100000000"
        )
    elif mutation == "missing_budget":
        data["campaign_budget"] = []
    elif mutation == "missing_setup":
        data["billing_setup"] = []
    else:
        data["cost"] = []
    adapter, _ = reader(data)
    result = adapter(request(), NOW)
    assert result.cap_semantics == "unqualified" and result.reporting_watermark is None
    if mutation == "pending":
        assert "pending_cap_change" in result.reasons
    if mutation == "unlimited":
        assert "unlimited_account_budget" in result.reasons
    if mutation == "future":
        assert len(result.account_budgets) == 2
    if mutation == "missing_budget":
        assert not result.advertising_inventory_read_complete
    if mutation == "missing_setup":
        assert not result.billing_inventory_read_complete
    if mutation == "missing_cost":
        assert result.reported_cost_micros is None


@pytest.mark.parametrize("status", [403, 429, 500])
def test_billing_failure_never_looks_like_complete_empty_inventory(status: int) -> None:
    data = payloads()

    def handler(req: httpx.Request) -> httpx.Response:
        table = key(json.loads(req.content)["query"])
        return (
            httpx.Response(status, json={"error": "private"})
            if table == "account_budget"
            else httpx.Response(200, json={"results": data[table]})
        )

    result = GoogleNativeInventoryHTTP(
        context, transport=httpx.MockTransport(handler), clock=lambda: NOW
    )(request(), NOW)
    assert not result.billing_inventory_read_complete
    assert result.account_budgets == [] and result.billing_setups == []
    assert "billing_inventory_unavailable" in result.reasons


@pytest.mark.parametrize(
    "mutation", ["foreign", "duplicate", "currency", "timezone", "negative", "wrong_cost"]
)
def test_native_lineage_and_values_fail_closed(mutation: str) -> None:
    data = payloads()
    if mutation == "foreign":
        data["campaign"][0]["campaign"]["campaignBudget"] = "customers/9999999999/campaignBudgets/1"
    elif mutation == "duplicate":
        data["campaign"].append(copy.deepcopy(data["campaign"][0]))
    elif mutation == "currency":
        data["customer"][0]["customer"]["currencyCode"] = "CAD"
    elif mutation == "timezone":
        data["customer"][0]["customer"]["timeZone"] = "UTC"
    elif mutation == "negative":
        data["cost"][0]["metrics"]["costMicros"] = "-1"
    else:
        data["cost"][0]["customer"]["id"] = "9999999999"
    adapter, _ = reader(data)
    with pytest.raises(GoogleNativeInventoryUnavailable):
        adapter(request(), NOW)


def test_changed_scope_context_prevents_io() -> None:
    def wrong(req: GoogleInventoryRequest, now: datetime) -> GoogleNativeInventoryContext:
        value = context(req, now)
        value.scope = value.scope.model_copy(update={"connection_version": "google:3:2"})
        return value

    def forbidden(req: httpx.Request) -> httpx.Response:
        raise AssertionError("unexpected IO")

    adapter = GoogleNativeInventoryHTTP(
        wrong, transport=httpx.MockTransport(forbidden), clock=lambda: NOW
    )
    with pytest.raises(GoogleNativeInventoryUnavailable):
        adapter(request(), NOW)


@pytest.mark.parametrize("cycle", [True, False])
def test_expired_during_last_response_and_pagination_cycles(cycle: bool) -> None:
    data = payloads()
    clock = [NOW]

    def handler(req: httpx.Request) -> httpx.Response:
        table = key(json.loads(req.content)["query"])
        if cycle and table == "campaign":
            return httpx.Response(200, json={"nextPageToken": "same"})
        if not cycle and table == "account_budget":
            clock[0] = NOW + timedelta(minutes=4)
        return httpx.Response(200, json={"results": data[table]})

    adapter = GoogleNativeInventoryHTTP(
        context, transport=httpx.MockTransport(handler), clock=lambda: clock[0]
    )
    with pytest.raises(GoogleNativeInventoryUnavailable):
        adapter(request(), NOW)


def test_reference_count_detects_missing_owner_without_qualified_snapshot() -> None:
    data = payloads()
    data["campaign_budget"][0]["campaignBudget"]["referenceCount"] = "2"
    adapter, _ = reader(data)
    result = adapter(request(), NOW)
    assert not result.advertising_inventory_read_complete
    assert "campaign_budget_inventory_changed" in result.reasons


def test_late_cost_and_budget_decrease_never_release_or_recalculate_a_cap() -> None:
    data = payloads()
    adapter, _ = reader(data)
    initial = adapter(request(), NOW)
    data["campaign_budget"][0]["campaignBudget"]["amountMicros"] = "1000000"
    data["cost"][0]["metrics"]["costMicros"] = "150000000"
    later = adapter(request(), NOW)
    assert initial.reported_cost_micros == 75000000
    assert later.reported_cost_micros == 150000000
    assert initial.digest() != later.digest()
    assert later.unreported_upper_micros is None and later.unchanged_future_upper_micros is None
    assert later.cap_semantics == "unqualified"


def test_inventory_capacity_fails_without_truncation() -> None:
    data = payloads()
    data["campaign"] *= 201
    adapter, _ = reader(data)
    with pytest.raises(GoogleNativeInventoryUnavailable, match="native_inventory_capacity"):
        adapter(request(), NOW)
