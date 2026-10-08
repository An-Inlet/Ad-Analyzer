"""Meta exact existing-budget/pause HTTP operations; no live qualification or registration."""

import json
from datetime import datetime
from typing import Any

from app import advertising_capabilities
from app.executors.optimization_http import (
    OptimizationHTTP,
    OptimizationUnavailable,
    validated_read,
)
from app.meta.budget_snapshot import parse_meta_budget
from app.publication.execution_contracts import ExecutionAccount
from app.publication.optimization_contracts import (
    MetaBudgetSetV1,
    MetaCurrentState,
    MetaStatusSetV1,
    MoneyContext,
    OptimizationContext,
    OptimizationRequest,
    OptimizationResponse,
    OptimizationTarget,
)


class MetaOptimizationTransport(OptimizationHTTP):
    provider = "meta_ads"
    origin = "https://graph.facebook.com"

    def node(self, identity: str, fields: str, context: OptimizationContext) -> dict[str, Any]:
        return self.send("GET", "/v26.0/" + identity, context, params={"fields": fields})

    def children(self, campaign: str, context: OptimizationContext) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        cursor = None
        seen: set[str] = set()
        for _ in range(10):
            params = {"fields": "id,account_id,campaign_id", "limit": "100"}
            params["effective_status"] = json.dumps(
                [
                    "ACTIVE",
                    "PAUSED",
                    "ARCHIVED",
                    "DELETED",
                    "IN_PROCESS",
                    "WITH_ISSUES",
                    "CAMPAIGN_PAUSED",
                ]
            )
            if cursor:
                params["after"] = cursor
            data = self.send("GET", f"/v26.0/{campaign}/adsets", context, params=params)
            rows = data.get("data")
            if not isinstance(rows, list) or any(not isinstance(r, dict) for r in rows):
                raise OptimizationUnavailable("optimization_topology_unavailable")
            result.extend(rows)
            if len(result) > 199:
                raise OptimizationUnavailable("optimization_topology_capacity")
            paging = data.get("paging", {})
            if not isinstance(paging, dict):
                raise OptimizationUnavailable("optimization_topology_unavailable")
            if not paging.get("next"):
                return result
            cursors = paging.get("cursors")
            if not isinstance(cursors, dict):
                raise OptimizationUnavailable("optimization_topology_cursor")
            cursor = cursors.get("after")
            if not isinstance(cursor, str) or not 1 <= len(cursor) <= 1024 or cursor in seen:
                raise OptimizationUnavailable("optimization_topology_cursor")
            seen.add(cursor)
        raise OptimizationUnavailable("optimization_topology_capacity")

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
    ) -> MetaCurrentState:
        self.check(scope, context, now)
        if target.kind not in {"campaign", "adset"}:
            raise OptimizationUnavailable("optimization_target_invalid")
        account = self.node(
            "act_" + scope.external_advertiser_id,
            "account_id,currency,timezone_name,account_status",
            context,
        )
        if (
            account.get("account_id") != scope.external_advertiser_id
            or account.get("currency") != money.currency
            or account.get("timezone_name") != money.account_timezone
        ):
            raise OptimizationUnavailable("optimization_account_changed")
        fields = (
            "id,account_id,configured_status,effective_status,daily_budget,lifetime_budget,"
            "is_budget_schedule_enabled,start_time,"
        )
        campaign = self.node(
            target.campaign_id,
            fields + "stop_time,objective,buying_type,"
            "is_adset_budget_sharing_enabled,budget_rebalance_flag",
            context,
        )
        row = (
            campaign
            if target.kind == "campaign"
            else self.node(
                target.external_id,
                fields
                + "end_time,campaign_id,targeting,promoted_object,bid_strategy,optimization_goal",
                context,
            )
        )
        if (
            campaign.get("id") != target.campaign_id
            or row.get("id") != target.external_id
            or campaign.get("account_id") != scope.external_advertiser_id
            or row.get("account_id") != scope.external_advertiser_id
            or (target.kind == "adset" and row.get("campaign_id") != target.campaign_id)
        ):
            raise OptimizationUnavailable("optimization_owner_changed")
        children = self.children(target.campaign_id, context)
        snapshot = parse_meta_budget(
            scope, target, money.currency_exponent, account, campaign, row, children
        )
        return MetaCurrentState.model_validate(
            {
                **snapshot.model_dump(),
                "scope": scope,
                "money": money,
                "qualification_id": qualification_id,
                "qualification_revision": qualification_revision,
                "observation_started_at": now,
                "observed_at": now,
            }
        )

    def apply_once(
        self, request: OptimizationRequest, context: OptimizationContext, now: datetime
    ) -> OptimizationResponse:
        advertising_capabilities.require_advertising_write()
        validation = self.validate_only(request, context, now)
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
        action = request.intent.action
        body: dict[str, Any]
        if isinstance(action, MetaBudgetSetV1):
            body = {
                action.budget_field: action.amount_micros
                // 10 ** (6 - current.money.currency_exponent)
            }
        elif isinstance(action, MetaStatusSetV1):
            body = {"status": action.status}
        else:
            raise OptimizationUnavailable("optimization_action_invalid")
        try:
            result = self.send(
                "POST", "/v26.0/" + request.intent.target.external_id, context, body=body
            )
            outcome = "acknowledged" if result.get("success") is True else "unknown"
        except OptimizationUnavailable:
            outcome = "unknown"
        return OptimizationResponse.model_validate(
            {"request_digest": request.digest(), "outcome": outcome}
        )
