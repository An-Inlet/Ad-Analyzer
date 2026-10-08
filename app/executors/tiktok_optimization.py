"""TikTok v1.3 bounded existing campaign/adgroup updates; no live authority."""

import json
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from app import advertising_capabilities
from app.executors.optimization_http import (
    OptimizationHTTP,
    OptimizationUnavailable,
    micros,
    validated_read,
)
from app.executors.social_http import decimal_budget
from app.publication.contracts import fingerprint
from app.publication.execution_contracts import ExecutionAccount
from app.publication.optimization_contracts import (
    BudgetOwnerRef,
    MoneyContext,
    OptimizationContext,
    OptimizationRequest,
    OptimizationResponse,
    OptimizationTarget,
    TikTokBudgetSetV1,
    TikTokCurrentState,
    TikTokStatusSetV1,
)


class TikTokOptimizationTransport(OptimizationHTTP):
    provider = "tiktok_ads"
    origin = "https://business-api.tiktok.com"

    def rows(
        self, edge: str, filtering: dict[str, Any], fields: list[str], context: OptimizationContext
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        total_pages: int | None = None
        for page in range(1, 11):
            data = self.send(
                "GET",
                f"/open_api/v1.3/{edge}/get/",
                context,
                params={
                    "advertiser_id": context.scope.external_advertiser_id,
                    "filtering": json.dumps({**filtering, "primary_status": "STATUS_ALL"}),
                    "fields": json.dumps(fields),
                    "page": str(page),
                    "page_size": "100",
                },
            )
            batch, paging = data.get("list"), data.get("page_info")
            if (
                not isinstance(batch, list)
                or any(not isinstance(r, dict) for r in batch)
                or not isinstance(paging, dict)
                or type(paging.get("total_page")) is not int
                or paging.get("page") != page
                or not 1 <= paging["total_page"] <= 10
            ):
                raise OptimizationUnavailable("optimization_pagination_invalid")
            if total_pages is not None and paging["total_page"] != total_pages:
                raise OptimizationUnavailable("optimization_pagination_changed")
            total_pages = paging["total_page"]
            rows.extend(batch)
            if len(rows) > 199:
                raise OptimizationUnavailable("optimization_topology_capacity")
            if page == paging["total_page"]:
                return rows
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
    ) -> TikTokCurrentState:
        self.check(scope, context, now)
        if target.kind not in {"campaign", "adgroup"}:
            raise OptimizationUnavailable("optimization_target_invalid")
        data = self.send(
            "GET",
            "/open_api/v1.3/advertiser/info/",
            context,
            params={
                "advertiser_ids": json.dumps([scope.external_advertiser_id]),
                "fields": json.dumps(["advertiser_id", "currency", "timezone", "status"]),
            },
        )
        accounts = data.get("list")
        if (
            not isinstance(accounts, list)
            or len(accounts) != 1
            or not isinstance(accounts[0], dict)
        ):
            raise OptimizationUnavailable("optimization_account_unavailable")
        account = accounts[0]
        if (
            account.get("advertiser_id") != scope.external_advertiser_id
            or account.get("currency") != money.currency
            or account.get("timezone") != money.account_timezone
        ):
            raise OptimizationUnavailable("optimization_account_changed")
        common = [
            "advertiser_id",
            "campaign_id",
            "operation_status",
            "secondary_status",
            "budget",
            "budget_mode",
        ]
        campaigns = self.rows(
            "campaign",
            {"campaign_ids": [target.campaign_id]},
            common
            + [
                "campaign_type",
                "objective_type",
                "budget_optimize_on",
                "is_smart_performance_campaign",
            ],
            context,
        )
        if len(campaigns) != 1:
            raise OptimizationUnavailable("optimization_campaign_unavailable")
        campaign = campaigns[0]
        children = self.rows(
            "adgroup",
            {"campaign_ids": [target.campaign_id]},
            common
            + [
                "adgroup_id",
                "promotion_type",
                "schedule_type",
                "schedule_start_time",
                "schedule_end_time",
                "dayparting",
                "creative_material_mode",
                "placement_type",
                "placements",
                "pixel_id",
                "optimization_event",
                "optimization_goal",
                "bid_type",
                "billing_event",
                "location_ids",
                "languages",
                "identity_id",
            ],
            context,
        )
        if (
            campaign.get("campaign_id") != target.campaign_id
            or campaign.get("advertiser_id") != scope.external_advertiser_id
        ):
            raise OptimizationUnavailable("optimization_owner_changed")
        targets = [
            OptimizationTarget(
                kind="campaign", external_id=target.campaign_id, campaign_id=target.campaign_id
            )
        ]
        for child in children:
            if (
                child.get("advertiser_id") != scope.external_advertiser_id
                or child.get("campaign_id") != target.campaign_id
            ):
                raise OptimizationUnavailable("optimization_owner_changed")
            targets.append(
                OptimizationTarget(
                    kind="adgroup", external_id=child["adgroup_id"], campaign_id=target.campaign_id
                )
            )
        if target not in targets or len({t.external_id for t in targets}) != len(targets):
            raise OptimizationUnavailable("optimization_topology_changed")
        row = (
            campaign
            if target.kind == "campaign"
            else next(c for c in children if c["adgroup_id"] == target.external_id)
        )
        optimize = campaign.get("budget_optimize_on")
        pool = target.kind == "campaign" or optimize is not False
        affected = sorted(targets if pool else [target], key=lambda t: (t.kind, t.external_id))
        owner = targets[0] if pool else target
        unsupported = []
        if (
            campaign.get("campaign_type") != "REGULAR_CAMPAIGN"
            or campaign.get("objective_type") != "WEB_CONVERSIONS"
        ):
            unsupported.append("unsupported_campaign_profile")
        if campaign.get("is_smart_performance_campaign") is not False or type(optimize) is not bool:
            unsupported.append("automation_state_unavailable")
        if account.get("status") != "STATUS_ENABLE":
            unsupported.append("account_not_active")
        if any(c.get("promotion_type") != "WEBSITE" for c in children):
            unsupported.append("unsupported_promotion")
        if row.get("operation_status") not in {"ENABLE", "DISABLE"}:
            unsupported.append("target_not_editable")
        # An explicit all-hours bitset proves no daypart restriction for this profile.
        schedule_clear = bool(children) and all(c.get("dayparting") == "1" * 336 for c in children)
        if not schedule_clear:
            unsupported.append("schedule_semantics_unqualified")
        ignored = {"operation_status", "secondary_status", "budget"}
        unchanged = {
            "campaign": {
                k: v
                for k, v in campaign.items()
                if k
                not in (
                    ignored
                    if target.kind == "campaign"
                    else {"operation_status", "secondary_status"}
                )
            },
            "target": {k: v for k, v in row.items() if k not in ignored},
        }

        def instant(key: str) -> datetime | None:
            value = row.get(key)
            if value is None:
                return None
            dt = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
            return dt.replace(tzinfo=ZoneInfo("UTC"))

        return TikTokCurrentState(
            scope=scope,
            target=target,
            budget_owner=BudgetOwnerRef(
                provider="tiktok_ads",
                owner=owner,
                mode="campaign_pool" if pool else "independent",
                affected_targets=affected,
                topology_digest=fingerprint(
                    "inlet.optimization-topology.v1",
                    {"targets": [t.model_dump() for t in affected]},
                ),
            ),
            money=money,
            account_status=account["status"],
            configured_status=row["operation_status"],
            effective_status=row["secondary_status"],
            parent_configured_status=campaign["operation_status"],
            starts_at=instant("schedule_start_time"),
            ends_at=instant("schedule_end_time"),
            sharing_enabled=False if optimize is False else None,
            schedule_adjustments_enabled=False if schedule_clear else None,
            rebalance_enabled=False if optimize is False else None,
            unaffected_settings_digest=fingerprint(
                "inlet.tiktok-optimization-settings.v1", unchanged
            ),
            qualification_id=qualification_id,
            qualification_revision=qualification_revision,
            unsupported_features=unsupported,
            complete=not unsupported,
            observation_started_at=now,
            observed_at=now,
            campaign_type=campaign["campaign_type"],
            objective_type=campaign["objective_type"],
            promotion_type="WEBSITE" if target.kind == "campaign" else row["promotion_type"],
            budget_optimize_on=optimize if type(optimize) is bool else None,
            budget_mode=row["budget_mode"],
            budget_micros=micros(row.get("budget"), money.currency_exponent),
            schedule_type="CAMPAIGN_CHILD_SCHEDULES"
            if target.kind == "campaign"
            else row["schedule_type"],
            schedule_wire_timezone="UTC",
        )

    def apply_once(
        self, request: OptimizationRequest, context: OptimizationContext, now: datetime
    ) -> OptimizationResponse:
        advertising_capabilities.require_advertising_write()
        if not self.validate_only(request, context, now).valid:
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
        kind = request.intent.target.kind
        body: dict[str, Any] = {"advertiser_id": request.intent.scope.external_advertiser_id}
        action = request.intent.action
        if isinstance(action, TikTokBudgetSetV1):
            endpoint = kind + "/update/"
            body.update(
                {
                    kind + "_id": request.intent.target.external_id,
                    "budget": decimal_budget(action.amount_micros),
                }
            )
        elif isinstance(action, TikTokStatusSetV1):
            endpoint = kind + "/status/update/"
            body.update(
                {
                    kind + "_ids": [request.intent.target.external_id],
                    "operation_status": action.operation_status,
                }
            )
            if kind == "adgroup":
                body["allow_partial_success"] = False
        else:
            raise OptimizationUnavailable("optimization_action_invalid")
        try:
            self.send("POST", "/open_api/v1.3/" + endpoint, context, body=body)
            outcome = "acknowledged"
        except OptimizationUnavailable:
            outcome = "unknown"
        return OptimizationResponse.model_validate(
            {"request_digest": request.digest(), "outcome": outcome}
        )
