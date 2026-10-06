"""Bounded native diagnostics only. No spending qualification or runtime factory."""

import re
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from time import monotonic
from typing import Any, Literal
from zoneinfo import ZoneInfo

import httpx
from pydantic import AwareDatetime, Field, model_validator

from app.executors.google_optimization import GoogleOptimizationTransport
from app.executors.optimization_http import OptimizationUnavailable
from app.goals.schemas import StrictModel
from app.publication.contracts import fingerprint
from app.publication.execution_contracts import ExecutionAccount, ProviderMandateBinding
from app.publication.optimization_contracts import OptimizationContext


class GoogleNativeInventoryUnavailable(RuntimeError):
    """Fixed reason only; never includes raw provider data."""


class GoogleNativeInventoryRequest(StrictModel):
    account: ExecutionAccount
    mandate: ProviderMandateBinding
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    time_zone: str = Field(min_length=1, max_length=64)
    period_start: AwareDatetime
    period_end: AwareDatetime

    @model_validator(mode="after")
    def bounded(self) -> "GoogleNativeInventoryRequest":
        ZoneInfo(self.time_zone)
        if (
            self.account.account.platform != "google_ads"
            or not re.fullmatch(r"[0-9]{10}", self.account.external_advertiser_id)
            or not timedelta(0) < self.period_end - self.period_start <= timedelta(days=366)
        ):
            raise ValueError("invalid native inventory request")
        return self

    def digest(self) -> str:
        return fingerprint("inlet.google-native-inventory-request.v1", self.model_dump(mode="json"))


class NativeCampaign(StrictModel):
    resource_name: str
    budget_resource: str
    status: str
    channel: str
    bidding_strategy: str
    start_date_time: str | None
    end_date_time: str | None


class NativeCampaignBudget(StrictModel):
    resource_name: str
    amount_micros: int | None
    total_amount_micros: int | None
    explicitly_shared: bool
    reference_count: int
    period: str
    status: str
    type: str


class NativeAccountBudget(StrictModel):
    resource_name: str
    billing_setup: str
    status: str
    proposed_limit_micros: int | None
    approved_limit_micros: int | None
    adjusted_limit_micros: int | None
    proposed_limit_type: str | None
    approved_limit_type: str | None
    adjusted_limit_type: str | None
    proposed_start: str | None
    approved_start: str | None
    proposed_end: str | None
    approved_end: str | None
    proposed_end_type: str | None
    approved_end_type: str | None
    pending_proposal: str | None
    amount_served_micros: int | None


class NativeBillingSetup(StrictModel):
    resource_name: str
    status: str


class GoogleNativeInventory(StrictModel):
    request: GoogleNativeInventoryRequest
    observation_started_at: AwareDatetime
    observed_at: AwareDatetime
    expires_at: AwareDatetime
    campaigns: list[NativeCampaign] = Field(max_length=200)
    campaign_budgets: list[NativeCampaignBudget] = Field(max_length=200)
    account_budgets: list[NativeAccountBudget] = Field(max_length=200)
    billing_setups: list[NativeBillingSetup] = Field(max_length=200)
    # These are completed inventory reads, not an atomic provider snapshot or portfolio proof.
    advertising_inventory_read_complete: bool
    billing_inventory_read_complete: bool
    reported_cost_micros: int | None = Field(ge=0, le=10**15)
    queried_start_date: str
    queried_end_date: str
    reporting_watermark: None = None
    unreported_upper_micros: None = None
    unchanged_future_upper_micros: None = None
    proposed_owner_upper_micros: None = None
    cap_semantics: Literal["unqualified"] = "unqualified"
    reasons: list[str] = Field(min_length=1, max_length=20)

    def digest(self) -> str:
        return fingerprint("inlet.google-native-inventory.v1", self.model_dump(mode="json"))


class GoogleNativeInventoryContext(OptimizationContext):
    # Request lineage is server supplied, never a browser assertion.
    request_digest: str = Field(pattern=r"^[a-f0-9]{64}$")


ContextReader = Callable[[GoogleNativeInventoryRequest, datetime], GoogleNativeInventoryContext]


def _ref(value: Any, customer: str, collection: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(
        rf"customers/{customer}/{collection}/[0-9]{{1,20}}", value
    ):
        raise GoogleNativeInventoryUnavailable("native_inventory_reference_invalid")
    return value


def _text(value: Any, *, optional: bool = False) -> str | None:
    if optional and value is None:
        return None
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_: -]{1,64}", value):
        raise GoogleNativeInventoryUnavailable("native_inventory_field_invalid")
    return value


def _enum(value: Any) -> str:
    result = _text(value)
    if result is None or not re.fullmatch(r"[A-Z_]{1,64}", result):
        raise GoogleNativeInventoryUnavailable("native_inventory_field_invalid")
    return result


def _number(value: Any, *, optional: bool = False) -> int | None:
    if optional and value is None:
        return None
    if (
        isinstance(value, bool)
        or not isinstance(value, str | int)
        or not re.fullmatch(r"[0-9]{1,16}", str(value))
        or int(value) > 10**15
    ):
        raise GoogleNativeInventoryUnavailable("native_inventory_number_invalid")
    return int(value)


class GoogleNativeInventoryHTTP:
    def __init__(
        self,
        context_reader: ContextReader,
        *,
        transport: httpx.BaseTransport | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self.context_reader = context_reader
        # Reuse bounded wire serialization only. No mutation method is invoked/exposed here.
        self._wire = GoogleOptimizationTransport(transport=transport)
        self.clock = clock

    def __call__(
        self, request: GoogleNativeInventoryRequest, now: datetime, /
    ) -> GoogleNativeInventory:
        request = GoogleNativeInventoryRequest.model_validate(request.model_dump())
        context = self.context_reader(request, now)
        if context.request_digest != request.digest():
            raise GoogleNativeInventoryUnavailable("native_inventory_context_invalid")
        deadline = monotonic() + 60
        expires = min(context.expires_at, now + timedelta(minutes=5))

        def check() -> None:
            nonlocal context, expires
            current = self.clock()
            context = self.context_reader(request, current)
            if context.request_digest != request.digest():
                raise GoogleNativeInventoryUnavailable("native_inventory_context_invalid")
            expires = min(expires, context.expires_at)
            current = self.clock()
            if not now <= current < expires or monotonic() >= deadline:
                raise GoogleNativeInventoryUnavailable("native_inventory_expired")
            try:
                self._wire.check(request.account, context, current)
            except OptimizationUnavailable:
                raise GoogleNativeInventoryUnavailable("native_inventory_context_invalid") from None

        def search(query: str, key: str) -> list[dict[str, Any]]:
            result: list[dict[str, Any]] = []
            seen: set[str] = set()
            body: dict[str, Any] = {"query": query}
            for _ in range(10):
                check()
                data = self._wire.post(context, "googleAds:search", body)
                check()
                rows = data.get("results", [])
                if not isinstance(rows, list) or any(
                    not isinstance(r, dict) or (bool(key) and not isinstance(r.get(key), dict))
                    for r in rows
                ):
                    raise GoogleNativeInventoryUnavailable("native_inventory_response_invalid")
                result.extend(r[key] if key else r for r in rows)
                if len(result) > 200:
                    raise GoogleNativeInventoryUnavailable("native_inventory_capacity")
                token = data.get("nextPageToken")
                if token is None or token == "":
                    return result
                if not isinstance(token, str) or len(token) > 4096 or token in seen:
                    raise GoogleNativeInventoryUnavailable("native_inventory_cursor_invalid")
                seen.add(token)
                body["pageToken"] = token
            raise GoogleNativeInventoryUnavailable("native_inventory_capacity")

        def unique(rows: list[dict[str, Any]], collection: str) -> list[dict[str, Any]]:
            seen: set[str] = set()
            for row in rows:
                ref = _ref(row.get("resourceName"), customer, collection)
                if ref in seen:
                    raise GoogleNativeInventoryUnavailable("native_inventory_duplicate")
                seen.add(ref)
            return rows

        customer = request.account.external_advertiser_id
        try:
            check()
            accounts = search(
                "SELECT customer.id, customer.resource_name, customer.currency_code, "
                "customer.time_zone, customer.status, customer.manager FROM customer",
                "customer",
            )
            if len(accounts) != 1 or (
                str(accounts[0].get("id")) != customer
                or accounts[0].get("resourceName") != f"customers/{customer}"
                or accounts[0].get("currencyCode") != request.currency
                or accounts[0].get("timeZone") != request.time_zone
                or accounts[0].get("status") != "ENABLED"
                or accounts[0].get("manager", False) is not False
            ):
                raise GoogleNativeInventoryUnavailable("native_inventory_account_mismatch")
            campaigns = [
                NativeCampaign(
                    resource_name=r["resourceName"],
                    budget_resource=_ref(r.get("campaignBudget"), customer, "campaignBudgets"),
                    status=_enum(r.get("status")),
                    channel=_enum(r.get("advertisingChannelType")),
                    bidding_strategy=_enum(r.get("biddingStrategyType")),
                    start_date_time=_text(r.get("startDateTime"), optional=True),
                    end_date_time=_text(r.get("endDateTime"), optional=True),
                )
                for r in unique(
                    search(
                        "SELECT campaign.resource_name, campaign.campaign_budget, campaign.status, "
                        "campaign.advertising_channel_type, campaign.bidding_strategy_type, "
                        "campaign.start_date_time, campaign.end_date_time FROM campaign "
                        "WHERE campaign.status IN ('ENABLED', 'PAUSED', 'REMOVED')",
                        "campaign",
                    ),
                    "campaigns",
                )
            ]
            budgets: list[NativeCampaignBudget] = []
            for row in unique(
                search(
                    "SELECT campaign_budget.resource_name, campaign_budget.amount_micros, "
                    "campaign_budget.total_amount_micros, campaign_budget.explicitly_shared, "
                    "campaign_budget.reference_count, campaign_budget.period, "
                    "campaign_budget.status, campaign_budget.type FROM campaign_budget "
                    "WHERE campaign_budget.status IN ('ENABLED', 'REMOVED')",
                    "campaignBudget",
                ),
                "campaignBudgets",
            ):
                shared = row.get("explicitlyShared", False)
                if type(shared) is not bool:
                    raise GoogleNativeInventoryUnavailable("native_inventory_field_invalid")
                count = _number(row.get("referenceCount", "0"))
                assert count is not None
                budgets.append(
                    NativeCampaignBudget(
                        resource_name=row["resourceName"],
                        amount_micros=_number(row.get("amountMicros"), optional=True),
                        total_amount_micros=_number(row.get("totalAmountMicros"), optional=True),
                        explicitly_shared=shared,
                        reference_count=count,
                        period=_enum(row.get("period")),
                        status=_enum(row.get("status")),
                        type=_enum(row.get("type")),
                    )
                )
            reasons = {
                "billing_basis_unqualified",
                "external_writer_boundary_unproven",
                "reporting_completeness_unproven",
                "native_snapshot_not_atomic",
            }
            budget_ids = {b.resource_name for b in budgets}
            topology_complete = all(c.budget_resource in budget_ids for c in campaigns) and all(
                b.reference_count
                == sum(
                    c.budget_resource == b.resource_name and c.status != "REMOVED"
                    for c in campaigns
                )
                for b in budgets
            )
            if not topology_complete:
                reasons.add("campaign_budget_inventory_changed")
            if any(b.period == "DAILY" for b in budgets):
                reasons.add("daily_budget_not_total_cap")
            if any(b.total_amount_micros is not None for b in budgets):
                reasons.add("total_budget_profile_unqualified")
            local = ZoneInfo(request.time_zone)
            start = request.period_start.astimezone(local).date().isoformat()
            end = (
                (request.period_end - timedelta(microseconds=1))
                .astimezone(local)
                .date()
                .isoformat()
            )
            cost = search(
                "SELECT customer.id, metrics.cost_micros FROM customer "
                f"WHERE segments.date BETWEEN '{start}' AND '{end}'",
                "",
            )
            if len(cost) > 1 or any(
                not isinstance(r.get("customer"), dict) or str(r["customer"].get("id")) != customer
                for r in cost
            ):
                raise GoogleNativeInventoryUnavailable("native_inventory_cost_invalid")
            reported: int | None = None
            if cost and isinstance(cost[0].get("metrics"), dict):
                reported = _number(cost[0]["metrics"].get("costMicros"), optional=True)
            if reported is None:
                reasons.add("reported_cost_unavailable")
            account_budgets: list[NativeAccountBudget] = []
            billing_setups: list[NativeBillingSetup] = []
            billing_complete = False
            try:
                setups = unique(
                    search(
                        "SELECT billing_setup.resource_name, billing_setup.status "
                        "FROM billing_setup",
                        "billingSetup",
                    ),
                    "billingSetups",
                )
                billing_setups = [
                    NativeBillingSetup(
                        resource_name=r["resourceName"], status=_enum(r.get("status"))
                    )
                    for r in setups
                ]
                fields = [
                    "resource_name",
                    "billing_setup",
                    "status",
                    "proposed_spending_limit_micros",
                    "approved_spending_limit_micros",
                    "adjusted_spending_limit_micros",
                    "proposed_spending_limit_type",
                    "approved_spending_limit_type",
                    "adjusted_spending_limit_type",
                    "proposed_start_date_time",
                    "approved_start_date_time",
                    "proposed_end_date_time",
                    "approved_end_date_time",
                    "proposed_end_time_type",
                    "approved_end_time_type",
                    "pending_proposal.account_budget_proposal",
                    "amount_served_micros",
                ]
                query = (
                    "SELECT "
                    + ", ".join("account_budget." + f for f in fields)
                    + " FROM account_budget"
                )
                for row in unique(search(query, "accountBudget"), "accountBudgets"):
                    pending = row.get("pendingProposal", {})
                    if not isinstance(pending, dict):
                        raise GoogleNativeInventoryUnavailable("native_inventory_field_invalid")
                    proposal = pending.get("accountBudgetProposal")
                    if proposal is not None:
                        proposal = _ref(proposal, customer, "accountBudgetProposals")
                        reasons.add("pending_cap_change")
                    account_budgets.append(
                        NativeAccountBudget(
                            resource_name=row["resourceName"],
                            billing_setup=_ref(row.get("billingSetup"), customer, "billingSetups"),
                            status=_enum(row.get("status")),
                            proposed_limit_micros=_number(
                                row.get("proposedSpendingLimitMicros"), optional=True
                            ),
                            approved_limit_micros=_number(
                                row.get("approvedSpendingLimitMicros"), optional=True
                            ),
                            adjusted_limit_micros=_number(
                                row.get("adjustedSpendingLimitMicros"), optional=True
                            ),
                            proposed_limit_type=_text(
                                row.get("proposedSpendingLimitType"), optional=True
                            ),
                            approved_limit_type=_text(
                                row.get("approvedSpendingLimitType"), optional=True
                            ),
                            adjusted_limit_type=_text(
                                row.get("adjustedSpendingLimitType"), optional=True
                            ),
                            proposed_start=_text(row.get("proposedStartDateTime"), optional=True),
                            approved_start=_text(row.get("approvedStartDateTime"), optional=True),
                            proposed_end=_text(row.get("proposedEndDateTime"), optional=True),
                            approved_end=_text(row.get("approvedEndDateTime"), optional=True),
                            proposed_end_type=_text(row.get("proposedEndTimeType"), optional=True),
                            approved_end_type=_text(row.get("approvedEndTimeType"), optional=True),
                            pending_proposal=proposal,
                            amount_served_micros=_number(
                                row.get("amountServedMicros"), optional=True
                            ),
                        )
                    )
                billing_complete = all(
                    b.billing_setup in {s.resource_name for s in billing_setups}
                    for b in account_budgets
                )
                if not billing_complete:
                    reasons.add("billing_setup_inventory_changed")
                if not account_budgets:
                    reasons.add("finite_account_cap_unavailable")
                if any(
                    "INFINITE"
                    in (b.proposed_limit_type, b.approved_limit_type, b.adjusted_limit_type)
                    for b in account_budgets
                ):
                    reasons.add("unlimited_account_budget")
            except OptimizationUnavailable:
                # Do not confuse permission/transient failure with an empty complete inventory.
                account_budgets = []
                billing_setups = []
                reasons.add("billing_inventory_unavailable")
            check()
            observed = self.clock()
            return GoogleNativeInventory(
                request=request,
                observation_started_at=now,
                observed_at=observed,
                expires_at=expires,
                campaigns=campaigns,
                campaign_budgets=budgets,
                account_budgets=account_budgets,
                billing_setups=billing_setups,
                advertising_inventory_read_complete=topology_complete,
                billing_inventory_read_complete=billing_complete,
                reported_cost_micros=reported,
                queried_start_date=start,
                queried_end_date=end,
                reasons=sorted(reasons),
            )
        except (OptimizationUnavailable, ValueError, TypeError, KeyError):
            raise GoogleNativeInventoryUnavailable("native_inventory_unavailable") from None
