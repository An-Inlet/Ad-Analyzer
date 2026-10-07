"""Shared pure Meta budget parser; native data alone grants no execution authority."""

from datetime import datetime
from typing import Any

from pydantic import AwareDatetime, Field

from app.executors.optimization_http import OptimizationUnavailable, micros
from app.initial_planning.contracts import Frozen
from app.publication.contracts import fingerprint
from app.publication.execution_contracts import ExecutionAccount
from app.publication.optimization_contracts import BudgetOwnerRef, OptimizationTarget


class MetaBudgetSnapshot(Frozen):
    target: OptimizationTarget
    budget_owner: BudgetOwnerRef
    account_status: str
    configured_status: str
    effective_status: str
    parent_configured_status: str
    starts_at: AwareDatetime | None
    ends_at: AwareDatetime | None
    sharing_enabled: bool | None
    schedule_adjustments_enabled: bool | None
    rebalance_enabled: bool | None
    unaffected_settings_digest: str
    unsupported_features: tuple[str, ...]
    complete: bool
    objective: str
    buying_type: str
    daily_budget_micros: int | None = Field(ge=0)
    lifetime_budget_micros: int | None = Field(ge=0)


def parse_meta_budget(
    scope: ExecutionAccount,
    target: OptimizationTarget,
    currency_exponent: int,
    account: dict[str, Any],
    campaign: dict[str, Any],
    row: dict[str, Any],
    children: list[dict[str, Any]],
) -> MetaBudgetSnapshot:
    target = OptimizationTarget.model_validate(target.model_dump())
    if (
        campaign.get("id") != target.campaign_id
        or row.get("id") != target.external_id
        or campaign.get("account_id") != scope.external_advertiser_id
        or row.get("account_id") != scope.external_advertiser_id
        or account.get("account_id") != scope.external_advertiser_id
        or (target.kind == "adset" and row.get("campaign_id") != target.campaign_id)
    ):
        raise OptimizationUnavailable("optimization_owner_changed")
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
        (micros(campaign.get(k), currency_exponent, minor=True) or 0) > 0
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
        k not in row for k in ("targeting", "promoted_object", "bid_strategy", "optimization_goal")
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
                exclude if target.kind == "campaign" else {"configured_status", "effective_status"}
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

    return MetaBudgetSnapshot(
        target=target,
        budget_owner=BudgetOwnerRef(
            provider="meta_ads",
            owner=owner,
            mode="campaign_pool" if pool else "independent",
            affected_targets=affected,
            topology_digest=topology,
        ),
        account_status=str(account["account_status"]),
        configured_status=row["configured_status"],
        effective_status=row["effective_status"],
        parent_configured_status=campaign["configured_status"],
        starts_at=instant("start_time"),
        ends_at=instant("stop_time" if target.kind == "campaign" else "end_time"),
        sharing_enabled=sharing if type(sharing) is bool else None,
        schedule_adjustments_enabled=schedule if type(schedule) is bool else None,
        rebalance_enabled=rebalance if type(rebalance) is bool else None,
        unaffected_settings_digest=fingerprint("inlet.meta-optimization-settings.v1", unchanged),
        unsupported_features=unsupported,
        complete=not unsupported,
        objective=campaign["objective"],
        buying_type=campaign["buying_type"],
        daily_budget_micros=micros(row.get("daily_budget"), currency_exponent, minor=True),
        lifetime_budget_micros=micros(row.get("lifetime_budget"), currency_exponent, minor=True),
    )
