"""Meta exact existing-budget/pause HTTP operations; no live qualification or registration."""

import json
from datetime import datetime
from typing import Any

from app.executors.optimization_http import (
    OptimizationHTTP,
    OptimizationUnavailable,
    micros,
    validated_read,
)
from app.publication.contracts import fingerprint
from app.publication.execution_contracts import ExecutionAccount
from app.publication.optimization_contracts import (
    BudgetOwnerRef,
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
        targets = [
            OptimizationTarget(
                kind="campaign", external_id=target.campaign_id, campaign_id=target.campaign_id
            )
        ]
        for child in children:
            if (
                child.get("account_id") != scope.external_advertiser_id
                or child.get("campaign_id") != target.campaign_id
            ):
                raise OptimizationUnavailable("optimization_owner_changed")
            targets.append(
                OptimizationTarget(
                    kind="adset", external_id=child["id"], campaign_id=target.campaign_id
                )
            )
        if target not in targets or len({t.external_id for t in targets}) != len(targets):
            raise OptimizationUnavailable("optimization_topology_changed")
        campaign_has_budget = any(
            (micros(campaign.get(k), money.currency_exponent, minor=True) or 0) > 0
            for k in ("daily_budget", "lifetime_budget")
        )
        pool = target.kind == "campaign" or campaign_has_budget
        owner = targets[0] if pool else target
        affected = sorted(targets if pool else [target], key=lambda t: (t.kind, t.external_id))
        topology = fingerprint(
            "inlet.optimization-topology.v1", {"targets": [t.model_dump() for t in affected]}
        )
        unsupported = []
        if target.kind == "adset" and any(
            k not in row
            for k in ("targeting", "promoted_object", "bid_strategy", "optimization_goal")
        ):
            unsupported.append("required_settings_unavailable")
        if campaign.get("objective") != "OUTCOME_SALES" or campaign.get("buying_type") != "AUCTION":
            unsupported.append("unsupported_campaign_profile")
        if account.get("account_status") != 1:
            unsupported.append("account_not_active")
        statuses = {"ACTIVE", "PAUSED"}
        if (
            row.get("configured_status") not in statuses
            or campaign.get("configured_status") not in statuses
        ):
            unsupported.append("target_not_editable")
        sharing = campaign.get("is_adset_budget_sharing_enabled")
        schedule = row.get("is_budget_schedule_enabled")
        if campaign.get("is_budget_schedule_enabled") is not False:
            schedule = None
        rebalance = campaign.get("budget_rebalance_flag")
        if any(type(v) is not bool for v in (sharing, schedule, rebalance)):
            unsupported.append("required_flags_unavailable")
        exclude = {"configured_status", "effective_status", "daily_budget", "lifetime_budget"}
        unchanged = {
            "campaign": {
                k: v
                for k, v in campaign.items()
                if k
                not in (
                    exclude
                    if target.kind == "campaign"
                    else {"configured_status", "effective_status"}
                )
            },
            "target": {k: v for k, v in row.items() if k not in exclude},
        }

        def instant(key: str) -> datetime | None:
            value = row.get(key)
            if value is None:
                return None
            value = datetime.fromisoformat(value)
            if value.tzinfo is None:
                raise OptimizationUnavailable("optimization_schedule_invalid")
            return value

        return MetaCurrentState(
            scope=scope,
            target=target,
            budget_owner=BudgetOwnerRef(
                provider="meta_ads",
                owner=owner,
                mode="campaign_pool" if pool else "independent",
                affected_targets=affected,
                topology_digest=topology,
            ),
            money=money,
            account_status=str(account["account_status"]),
            configured_status=row["configured_status"],
            effective_status=row["effective_status"],
            parent_configured_status=campaign["configured_status"],
            starts_at=instant("start_time"),
            ends_at=instant("stop_time" if target.kind == "campaign" else "end_time"),
            sharing_enabled=sharing if type(sharing) is bool else None,
            schedule_adjustments_enabled=schedule if type(schedule) is bool else None,
            rebalance_enabled=rebalance if type(rebalance) is bool else None,
            unaffected_settings_digest=fingerprint(
                "inlet.meta-optimization-settings.v1", unchanged
            ),
            qualification_id=qualification_id,
            qualification_revision=qualification_revision,
            unsupported_features=unsupported,
            complete=not unsupported,
            observation_started_at=now,
            observed_at=now,
            objective=campaign["objective"],
            buying_type=campaign["buying_type"],
            daily_budget_micros=micros(
                row.get("daily_budget"), money.currency_exponent, minor=True
            ),
            lifetime_budget_micros=micros(
                row.get("lifetime_budget"), money.currency_exponent, minor=True
            ),
        )

    def apply_once(
        self, request: OptimizationRequest, context: OptimizationContext, now: datetime
    ) -> OptimizationResponse:
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
