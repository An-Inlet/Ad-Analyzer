"""Bounded v25 Google Search budget/pause IO; unregistered and live-unqualified."""

import json
import re
from datetime import datetime, timedelta
from time import monotonic
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from app.executors.optimization_http import (
    OptimizationHTTP,
    OptimizationUnavailable,
    validated_read,
)
from app.executors.social_http import _private_http
from app.publication.contracts import fingerprint
from app.publication.execution_contracts import ExecutionAccount
from app.publication.optimization_contracts import (
    GoogleBudgetOwnerRef,
    GoogleBudgetSetV1,
    GoogleCurrentState,
    GoogleStatusSetV1,
    MoneyContext,
    OptimizationContext,
    OptimizationReceipt,
    OptimizationRequest,
    OptimizationResponse,
    OptimizationState,
    OptimizationTarget,
    OptimizationValidation,
)

CAMPAIGN_FIELDS = (
    "campaign.resource_name, campaign.id, campaign.campaign_budget, campaign.status, "
    "campaign.primary_status, campaign.advertising_channel_type, "
    "campaign.advertising_channel_sub_type, campaign.bidding_strategy_type, "
    "campaign.bidding_strategy, campaign.manual_cpc.enhanced_cpc_enabled, "
    "campaign.network_settings.target_google_search, "
    "campaign.network_settings.target_search_network, "
    "campaign.network_settings.target_partner_search_network, "
    "campaign.network_settings.target_content_network, "
    "campaign.network_settings.target_google_tv_network, "
    "campaign.network_settings.target_youtube, campaign.start_date_time, "
    "campaign.end_date_time, campaign.ai_max_setting.enable_ai_max, "
    "campaign.dynamic_search_ads_setting.domain_name"
)
BUDGET_FIELDS = (
    "campaign_budget.resource_name, campaign_budget.amount_micros, "
    "campaign_budget.total_amount_micros, campaign_budget.explicitly_shared, "
    "campaign_budget.reference_count, campaign_budget.period, "
    "campaign_budget.delivery_method, campaign_budget.status, campaign_budget.type"
)


def integer(value: Any) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, str | int)
        or not re.fullmatch(r"[0-9]{1,16}", str(value))
    ):
        raise OptimizationUnavailable("google_optimization_number_invalid")
    result = int(value)
    if result > 10**15:
        raise OptimizationUnavailable("google_optimization_number_invalid")
    return result


def boolean(value: Any) -> bool:
    if type(value) is not bool:
        raise OptimizationUnavailable("google_optimization_boolean_invalid")
    return bool(value)


class GoogleOptimizationTransport(OptimizationHTTP):
    provider = "google_ads"
    origin = "https://googleads.googleapis.com"

    def check(self, scope: ExecutionAccount, context: OptimizationContext, now: datetime) -> None:
        super().check(scope, context, now)
        if not re.fullmatch(r"[0-9]{10}", scope.external_advertiser_id):
            raise OptimizationUnavailable("google_optimization_customer_invalid")

    def post(
        self, context: OptimizationContext, endpoint: str, body: dict[str, Any]
    ) -> dict[str, Any]:
        if endpoint not in {"googleAds:search", "campaigns:mutate", "campaignBudgets:mutate"}:
            raise OptimizationUnavailable("google_optimization_endpoint_invalid")
        customer = context.scope.external_advertiser_id
        if not re.fullmatch(r"[0-9]{10}", customer):
            raise OptimizationUnavailable("google_optimization_customer_invalid")
        headers = {
            "Authorization": "Bearer " + context.access_token.get_secret_value(),
            "Accept-Encoding": "identity",
        }
        if context.developer_token:
            headers["developer-token"] = context.developer_token.get_secret_value()
        if context.login_customer_id:
            headers["login-customer-id"] = context.login_customer_id
        private = _private_http.set(True)
        deadline = monotonic() + 30
        try:
            with (
                httpx.Client(
                    transport=self.transport,
                    timeout=httpx.Timeout(12, connect=5),
                    follow_redirects=False,
                    trust_env=False,
                ) as client,
                client.stream(
                    "POST",
                    f"{self.origin}/v25/customers/{customer}/{endpoint}",
                    headers=headers,
                    json=body,
                ) as response,
            ):
                if (
                    response.status_code != 200
                    or response.headers.get("Content-Encoding", "identity") != "identity"
                ):
                    raise OptimizationUnavailable("google_optimization_provider_unavailable")
                raw = bytearray()
                for chunk in response.iter_bytes():
                    raw.extend(chunk)
                    if len(raw) > 2_000_000 or monotonic() > deadline:
                        raise OptimizationUnavailable("google_optimization_response_bounds")
                result = json.loads(raw)
                if (
                    not isinstance(result, dict)
                    or "error" in result
                    or "partialFailureError" in result
                ):
                    raise OptimizationUnavailable("google_optimization_response_invalid")
                return result
        except (httpx.HTTPError, ValueError, TypeError, OSError):
            raise OptimizationUnavailable("google_optimization_provider_unavailable") from None
        finally:
            _private_http.reset(private)

    def search(self, context: OptimizationContext, query: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        token: str | None = None
        seen: set[str] = set()
        for _ in range(10):
            body = {"query": query}
            if token:
                body["pageToken"] = token
            result = self.post(context, "googleAds:search", body)
            page = result.get("results", [])  # protobuf JSON omits an empty repeated field
            if not isinstance(page, list) or any(not isinstance(row, dict) for row in page):
                raise OptimizationUnavailable("google_optimization_page_invalid")
            rows.extend(page)
            if len(rows) > 200:
                raise OptimizationUnavailable("google_optimization_topology_capacity")
            token = result.get("nextPageToken")
            if token is None or token == "":
                return rows
            if not isinstance(token, str) or len(token) > 4096 or token in seen:
                raise OptimizationUnavailable("google_optimization_cursor_invalid")
            seen.add(token)
        raise OptimizationUnavailable("google_optimization_topology_capacity")

    def single(self, context: OptimizationContext, query: str, key: str) -> dict[str, Any]:
        rows = self.search(context, query)
        if len(rows) != 1 or not isinstance(rows[0].get(key), dict):
            raise OptimizationUnavailable("google_optimization_resource_unavailable")
        return dict(rows[0][key])

    @validated_read
    def read_current(
        self,
        scope: ExecutionAccount,
        target: OptimizationTarget,
        money: MoneyContext,
        qualification_id: str,
        qualification_revision: int,
        context: OptimizationContext,
        now: datetime,
    ) -> GoogleCurrentState:
        self.check(scope, context, now)
        if target.kind != "campaign":
            raise OptimizationUnavailable("google_optimization_target_invalid")
        customer = scope.external_advertiser_id
        account = self.single(
            context,
            "SELECT customer.id, customer.resource_name, customer.status, "
            "customer.currency_code, customer.time_zone, customer.manager FROM customer",
            "customer",
        )
        if (
            str(account.get("id")) != customer
            or account.get("resourceName") != f"customers/{customer}"
            or account.get("currencyCode") != money.currency
            or account.get("timeZone") != money.account_timezone
            or boolean(account.get("manager", False))
        ):
            raise OptimizationUnavailable("google_optimization_account_changed")
        campaign = self.single(
            context,
            f"SELECT {CAMPAIGN_FIELDS} FROM campaign WHERE campaign.id = {target.external_id}",
            "campaign",
        )
        native = campaign.get("campaignBudget")
        if (
            str(campaign.get("id")) != target.external_id
            or campaign.get("resourceName")
            != f"customers/{customer}/campaigns/{target.external_id}"
            or not isinstance(native, str)
            or not re.fullmatch(rf"customers/{customer}/campaignBudgets/[0-9]{{1,32}}", native)
        ):
            raise OptimizationUnavailable("google_optimization_resource_mismatch")
        budget = self.single(
            context,
            f"SELECT {BUDGET_FIELDS} FROM campaign_budget "
            f"WHERE campaign_budget.resource_name = '{native}'",
            "campaignBudget",
        )
        if budget.get("resourceName") != native:
            raise OptimizationUnavailable("google_optimization_resource_mismatch")
        owner_rows = self.search(
            context,
            "SELECT campaign.resource_name, campaign.id, campaign.campaign_budget, "
            "campaign.status FROM campaign WHERE campaign.campaign_budget = '"
            + native
            + "' AND campaign.status != 'REMOVED'",
        )
        owners = []
        for row in owner_rows:
            c = row["campaign"]
            identifier = str(c["id"])
            if (
                not re.fullmatch(r"[0-9]{1,32}", identifier)
                or c.get("resourceName") != f"customers/{customer}/campaigns/{identifier}"
                or c.get("campaignBudget") != native
                or c.get("status") not in {"ENABLED", "PAUSED"}
            ):
                raise OptimizationUnavailable("google_optimization_owner_invalid")
            owners.append(identifier)
        if (
            owners != [target.campaign_id]
            or integer(budget.get("referenceCount")) != 1
            or boolean(budget.get("explicitlyShared", False))
        ):
            raise OptimizationUnavailable("google_optimization_independent_budget_required")
        subscriptions = self.search(
            context,
            "SELECT recommendation_subscription.resource_name, recommendation_subscription.type, "
            "recommendation_subscription.status FROM recommendation_subscription",
        )
        for row in subscriptions:
            sub = row["recommendationSubscription"]
            if (
                not isinstance(sub.get("resourceName"), str)
                or not sub["resourceName"].startswith(
                    f"customers/{customer}/recommendationSubscriptions/"
                )
                or sub.get("status") != "PAUSED"
            ):
                raise OptimizationUnavailable("google_optimization_automation_unsupported")
        # JSON omits selected scalar defaults; omission means false/UNSPECIFIED,
        # never infer absent identity, status, amount, count or required dates.
        network = campaign.get("networkSettings", {})
        network = {
            name: boolean(network.get(name, False))
            for name in (
                "targetGoogleSearch",
                "targetSearchNetwork",
                "targetPartnerSearchNetwork",
                "targetContentNetwork",
                "targetGoogleTvNetwork",
                "targetYoutube",
            )
        }
        manual = campaign.get("manualCpc", {})
        manual = {"enhancedCpcEnabled": boolean(manual.get("enhancedCpcEnabled", False))}
        ai = boolean(campaign.get("aiMaxSetting", {}).get("enableAiMax", False))
        start_raw, end_raw = campaign.get("startDateTime"), campaign.get("endDateTime")
        if not isinstance(start_raw, str) or (end_raw is not None and not isinstance(end_raw, str)):
            raise OptimizationUnavailable("google_optimization_schedule_invalid")
        start = datetime.strptime(start_raw, "%Y-%m-%d %H:%M:%S").replace(
            tzinfo=ZoneInfo(money.account_timezone)
        )
        end = (
            datetime.strptime(end_raw, "%Y-%m-%d %H:%M:%S").replace(
                tzinfo=ZoneInfo(money.account_timezone)
            )
            if end_raw
            else None
        )
        if start_raw[-8:] != "00:00:00" or (
            end is not None
            and (
                not isinstance(end_raw, str)
                or end_raw[-8:] != "23:59:59"
                or start >= end
                or end.year == 9999
            )
        ):
            raise OptimizationUnavailable("google_optimization_schedule_unsupported")
        blockers = []
        if account.get("status") != "ENABLED" or campaign.get("status") not in {
            "ENABLED",
            "PAUSED",
        }:
            blockers.append("google_account_or_campaign_unavailable")
        if (
            campaign.get("advertisingChannelType") != "SEARCH"
            or campaign.get("advertisingChannelSubType", "UNSPECIFIED") != "UNSPECIFIED"
            or campaign.get("biddingStrategyType") != "MANUAL_CPC"
            or campaign.get("biddingStrategy")
        ):
            blockers.append("google_search_manual_cpc_required")
        if (
            ai
            or campaign.get("dynamicSearchAdsSetting", {}).get("domainName")
            or manual["enhancedCpcEnabled"]
            or not network["targetGoogleSearch"]
            or any(
                network[name]
                for name in (
                    "targetPartnerSearchNetwork",
                    "targetContentNetwork",
                    "targetGoogleTvNetwork",
                    "targetYoutube",
                )
            )
        ):
            blockers.append("google_campaign_features_unsupported")
        total = budget.get("totalAmountMicros")
        total_amount = integer(total) if total is not None else None
        if (
            budget.get("period") != "DAILY"
            or budget.get("deliveryMethod") != "STANDARD"
            or budget.get("status") != "ENABLED"
            or budget.get("type") != "STANDARD"
            or total_amount not in {None, 0}
        ):
            blockers.append("google_daily_standard_budget_required")
        topology = fingerprint(
            "google.optimization-topology.v25", {"budget": native, "owners": owners}
        )
        # Exclude only fields these two masked actions can change, plus derived
        # delivery status. The complete remaining selected provider settings bind.
        unchanged = {k: v for k, v in campaign.items() if k not in {"status", "primaryStatus"}}
        return GoogleCurrentState(
            scope=scope,
            target=target,
            budget_owner=GoogleBudgetOwnerRef(
                owner=target,
                affected_targets=[target],
                native_budget_resource=native,
                topology_digest=topology,
            ),
            money=money,
            account_status=account["status"],
            configured_status=campaign["status"],
            effective_status=campaign["primaryStatus"],
            parent_configured_status=campaign["status"],
            starts_at=start,
            ends_at=end + timedelta(seconds=1) if end is not None else None,
            sharing_enabled=False,
            schedule_adjustments_enabled=False,
            rebalance_enabled=False,
            unaffected_settings_digest=fingerprint(
                "google.optimization-settings.v25",
                {
                    "campaign": unchanged,
                    "budget": {k: v for k, v in budget.items() if k != "amountMicros"},
                    "subscriptions": subscriptions,
                },
            ),
            qualification_id=qualification_id,
            qualification_revision=qualification_revision,
            unsupported_features=blockers,
            complete=True,
            observation_started_at=now,
            observed_at=now,
            native_budget_resource=native,
            budget_amount_micros=integer(budget.get("amountMicros")),
            budget_total_amount_micros=total_amount,
            budget_explicitly_shared=False,
            budget_reference_count=1,
            owning_campaign_ids=owners,
            budget_period=budget["period"],
            budget_delivery_method=budget["deliveryMethod"],
            budget_status=budget["status"],
            budget_type=budget["type"],
            advertising_channel_type=campaign["advertisingChannelType"],
            advertising_channel_sub_type=campaign.get("advertisingChannelSubType", "UNSPECIFIED"),
            bidding_strategy_type=campaign["biddingStrategyType"],
            manual_cpc_digest=fingerprint("google.manual-cpc.v25", manual),
            network_settings_digest=fingerprint("google.network-settings.v25", network),
            campaign_start_date=start.date().isoformat(),
            campaign_end_date=end.date().isoformat() if end is not None else None,
        )

    def blockers(self, request: OptimizationRequest, now: datetime) -> list[str]:
        result = super().blockers(request, now)
        if not isinstance(request.before, GoogleCurrentState) or not isinstance(
            request.intent.action, GoogleBudgetSetV1 | GoogleStatusSetV1
        ):
            result.append("google_optimization_action_invalid")
        elif (
            isinstance(request.intent.action, GoogleBudgetSetV1)
            and request.intent.action.amount_micros == request.before.budget_amount_micros
        ) or (
            isinstance(request.intent.action, GoogleStatusSetV1)
            and request.before.configured_status == "PAUSED"
        ):
            result.append("google_optimization_already_matches")
        return sorted(set(result))[:32]

    def operation(self, request: OptimizationRequest) -> tuple[str, str, dict[str, Any]]:
        state, action = request.before, request.intent.action
        if not isinstance(state, GoogleCurrentState):
            raise OptimizationUnavailable("google_optimization_action_invalid")
        if isinstance(action, GoogleBudgetSetV1):
            resource = state.native_budget_resource
            return (
                "campaignBudgets:mutate",
                resource,
                {
                    "update": {"resourceName": resource, "amountMicros": str(action.amount_micros)},
                    "updateMask": "amountMicros",
                },
            )
        if isinstance(action, GoogleStatusSetV1):
            resource = (
                f"customers/{state.scope.external_advertiser_id}/campaigns/"
                f"{state.target.external_id}"
            )
            return (
                "campaigns:mutate",
                resource,
                {"update": {"resourceName": resource, "status": "PAUSED"}, "updateMask": "status"},
            )
        raise OptimizationUnavailable("google_optimization_action_invalid")

    def validate_only(
        self, request: OptimizationRequest, context: OptimizationContext, now: datetime
    ) -> OptimizationValidation:
        result = super().validate_only(request, context, now)
        if not result.valid:
            return result
        endpoint, _, operation = self.operation(request)
        try:
            payload = self.post(
                context,
                endpoint,
                {"operations": [operation], "validateOnly": True, "partialFailure": False},
            )
            valid = payload == {}
        except OptimizationUnavailable:
            valid = False
        return OptimizationValidation(
            request_digest=request.digest(),
            kind="provider_validate_only",
            valid=valid,
            blockers=[] if valid else ["google_optimization_validation_unavailable"],
        )

    def apply_once(
        self, request: OptimizationRequest, context: OptimizationContext, now: datetime
    ) -> OptimizationResponse:
        validation = super().validate_only(request, context, now)
        if not validation.valid:
            raise OptimizationUnavailable("optimization_not_qualified")
        current = self.read_current(
            request.intent.scope,
            request.intent.target,
            request.before.money,
            request.intent.qualification_id,
            request.intent.qualification_revision,
            context,
            now,
        )
        if current.digest() != request.before.digest():
            raise OptimizationUnavailable("optimization_preflight_changed")
        endpoint, resource, operation = self.operation(request)
        outcome = "unknown"
        try:
            result = self.post(
                context,
                endpoint,
                {"operations": [operation], "validateOnly": False, "partialFailure": False},
            )
            if result.get("results") == [{"resourceName": resource}]:
                outcome = "acknowledged"
        except OptimizationUnavailable:
            pass
        return OptimizationResponse(request_digest=request.digest(), outcome=outcome)

    def compare(
        self, request: OptimizationRequest, after: OptimizationState, now: datetime
    ) -> OptimizationReceipt:
        if not isinstance(after, GoogleCurrentState) or not isinstance(
            request.before, GoogleCurrentState
        ):
            return self.receipt(request, now, "conflict")
        action = request.intent.action
        updates: dict[str, Any] = {}
        if isinstance(action, GoogleBudgetSetV1):
            updates["budget_amount_micros"] = action.amount_micros
        elif isinstance(action, GoogleStatusSetV1):
            updates.update(
                configured_status="PAUSED",
                parent_configured_status="PAUSED",
                effective_status=after.effective_status,
            )
        else:
            return self.receipt(request, now, "conflict")
        wanted = request.before.model_copy(update=updates)
        if wanted.digest() == after.digest():
            return self.receipt(request, now, "verified_target_state", after)
        return self.receipt(
            request, now, "unknown" if request.before.digest() == after.digest() else "conflict"
        )
