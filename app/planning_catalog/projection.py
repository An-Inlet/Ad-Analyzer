"""Bounded native observations projected without execution eligibility filters."""

from typing import Any

from app.collectors.google_native_inventory import GoogleNativeInventory
from app.collectors.meta_native_inventory import MetaNativeInventory
from app.collectors.native_diagnostics import Inventory
from app.planning_catalog.contracts import TargetCatalogV1
from app.publication.contracts import fingerprint


def project(result: Inventory) -> TargetCatalogV1:
    request = result.request
    source = request.account
    source_digest = fingerprint("inlet.planning-source.v1", source.model_dump(mode="json"))

    def key(kind: str, native_id: str) -> str:
        return fingerprint(
            "inlet.planning-target.v1", dict(source=source_digest, kind=kind, native_id=native_id)
        )

    targets: list[dict[str, Any]] = []
    coverage: list[dict[str, Any]] = []

    def cover(kind: str, status: str, scope: str, reasons: list[str]) -> None:
        coverage.append(
            dict(
                kind=kind,
                status=status,
                scope=scope,
                reasons=reasons,
                observed_count=sum(t["kind"] == kind for t in targets),
            )
        )

    def target(
        kind: str, native_id: str, parent: str | None, budget: str | None, settings: dict[str, Any]
    ) -> None:
        targets.append(
            dict(
                selection_key=key(kind, native_id),
                kind=kind,
                parent_selection_key=key("campaign", parent) if parent else None,
                budget_owner_key=budget,
                name=None,
                name_source="unavailable",
                settings=settings,
                unavailable_fields=["name", *[k for k, v in settings.items() if v is None]],
                reasons=["native_name_not_collected"],
            )
        )

    platform = source.account.platform
    if isinstance(result, GoogleNativeInventory):
        budgets = {b.resource_name: b for b in result.campaign_budgets}
        if len(budgets) != len(result.campaign_budgets):
            raise ValueError("duplicate native budget")
        for c in result.campaigns:
            b = budgets.get(c.budget_resource)
            target(
                "campaign",
                c.resource_name,
                None,
                key("budget", b.resource_name) if b else None,
                dict(
                    platform=platform,
                    status=c.status,
                    channel=c.channel,
                    bidding_strategy=c.bidding_strategy,
                    starts_native=c.start_date_time,
                    ends_native=c.end_date_time,
                    budget_amount_micros=b.amount_micros if b else None,
                    budget_total_amount_micros=b.total_amount_micros if b else None,
                    budget_period=b.period if b else None,
                    budget_status=b.status if b else None,
                    budget_type=b.type if b else None,
                    budget_explicitly_shared=b.explicitly_shared if b else None,
                    budget_reference_count=b.reference_count if b else None,
                ),
            )
        complete = result.advertising_inventory_read_complete
        cover(
            "campaign",
            "complete" if complete else "partial",
            "provider_campaigns",
            [] if complete else ["advertising_inventory_incomplete"],
        )
        cover("adgroup", "unavailable", "not_collected", ["adgroups_not_collected"])
    elif isinstance(result, MetaNativeInventory):
        for kind, rows in (("campaign", result.campaigns), ("adset", result.adsets)):
            for row in rows:
                settings = row.model_dump(exclude={"id", "account_id", "campaign_id"})
                settings["platform"] = platform
                # Identify only explicit observed budget ownership. Do not guess inheritance.
                budget = (
                    key(kind, row.id)
                    if row.daily_budget_native is not None or row.lifetime_budget_native is not None
                    else None
                )
                target(kind, row.id, row.campaign_id, budget, settings)
            cover(
                kind, "partial", "sdk_known_effective_statuses", ["effective_status_scope_limited"]
            )
    else:
        for kind, tiktok_rows in (("campaign", result.campaigns), ("adgroup", result.adgroups)):
            for tiktok_row in tiktok_rows:
                settings = tiktok_row.model_dump(exclude={"id", "advertiser_id", "campaign_id"})
                settings["platform"] = platform
                target(
                    kind,
                    tiktok_row.id,
                    tiktok_row.campaign_id if kind != "campaign" else None,
                    key(kind, tiktok_row.id) if tiktok_row.budget_native is not None else None,
                    settings,
                )
            cover(kind, "partial", "regular_campaign_families", ["campaign_family_scope_limited"])
    return TargetCatalogV1.model_validate(
        dict(
            workspace_id=source.workspace_id,
            account_id=source.account.account_id,
            connection_id=source.account.connection_id,
            platform=platform,
            connection_version=source.connection_version,
            source_binding_digest=source_digest,
            inventory_digest=result.digest(),
            currency=request.currency,
            time_zone=request.time_zone,
            reporting_starts_at=request.period_start,
            reporting_ends_at=request.period_end,
            observation_started_at=result.observation_started_at,
            observed_at=result.observed_at,
            expires_at=result.expires_at,
            coverage=coverage,
            targets=targets,
        )
    )
