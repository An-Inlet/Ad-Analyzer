"""Independent, read-only capabilities from the evidence one workspace already has.

Platform delivery is useful without CRM attribution. Missing observations stay missing,
currencies and providers stay separate, and suggestions never imply business outcomes.
"""

from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.ads.enums import AdvertisingPlatform
from app.ads.models import AdvertisingAccount, Campaign, DailyMetric
from app.measurement.models import MeasurementContract
from app.meta.models import MetaConnection
from app.meta.security import PURCHASE_ACTIONS
from app.shopify.reporting import sales_report

WINDOW_DAYS = 28
FRESHNESS_DAYS = 3
MIN_OBSERVED_DAYS = 7
MIN_IMPRESSIONS = 1_000
MIN_CLICKS = 50


def _snapshot(
    rows: list[DailyMetric],
    start: date,
    end: date,
    campaign_count: int,
    conversions_available: bool = False,
    covered: bool = False,
    conversion_value_available: bool = True,
) -> dict[str, Any] | None:
    selected = [row for row in rows if start <= row.metric_date <= end]
    if not selected and not covered:
        return None
    impressions = sum(row.impressions for row in selected)
    clicks = sum(row.clicks for row in selected)
    cost = sum(row.cost_micros for row in selected)
    days = {row.metric_date for row in selected}
    observed = {(row.campaign_id, row.metric_date) for row in selected}
    return {
        "impressions": impressions,
        "clicks": clicks,
        "cost_micros": cost,
        "ctr": clicks / impressions if impressions else None,
        "cpc_micros": cost / clicks if clicks else None,
        # Meta's unselected or unimported event is a zero storage placeholder, not
        # an observed zero. A selected, imported event remains platform-reported.
        "platform_conversions_available": conversions_available,
        "platform_conversions": float(sum(row.conversions for row in selected))
        if conversions_available
        else None,
        "platform_conversion_value_available": conversions_available and conversion_value_available,
        "platform_conversion_value_micros": sum(row.conversion_value_micros for row in selected)
        if conversions_available and conversion_value_available
        else None,
        "business_outcomes": None,
        "revenue_micros": None,
        "observed_days": len(days),
        "observed_campaign_days": len(observed),
        "expected_campaign_days": campaign_count * WINDOW_DAYS,
        "covered_days": WINDOW_DAYS if covered else len(days),
        "coverage_basis": "completed_meta_import" if covered else "daily_rows",
        "complete": covered or len(observed) == campaign_count * WINDOW_DAYS,
        "last_metric_date": max(days).isoformat() if days else None,
        "last_covered_date": end.isoformat() if covered else max(days).isoformat(),
    }


def _comparison(
    current: dict[str, Any] | None, previous: dict[str, Any] | None, fresh: bool
) -> dict[str, Any]:
    complete = bool(current and previous and current["complete"] and previous["complete"])
    ready = complete and fresh
    sample_ready = bool(
        ready
        and current
        and previous
        and current["impressions"] >= MIN_IMPRESSIONS
        and previous["impressions"] >= MIN_IMPRESSIONS
        and current["clicks"] >= MIN_CLICKS
        and previous["clicks"] >= MIN_CLICKS
    )
    result: dict[str, Any] = {
        "ready": ready,
        "sample_ready": sample_ready,
        "ctr_change_ratio": None,
        "cpc_change_ratio": None,
        "spend_change_ratio": None,
        "basis": "Equal 28-day windows; comparisons require every campaign-day in both windows.",
        "reason": (
            "Complete periods; patterns remain observational."
            if ready
            else "A fresh import and two complete periods are needed for a fair comparison."
        ),
    }
    if ready and current and previous:
        for field, output in (
            ("ctr", "ctr_change_ratio"),
            ("cpc_micros", "cpc_change_ratio"),
            ("cost_micros", "spend_change_ratio"),
        ):
            old, new = previous[field], current[field]
            if old is not None and old > 0 and new is not None:
                result[output] = (new - old) / old
    return result


def _capability(ready: bool, status: str, reason: str) -> dict[str, Any]:
    return {"ready": ready, "status": status, "reason": reason}


def _meta_covers(meta: Any, first: date, last: date, now: datetime) -> bool:
    """Coverage certifies omitted zero-delivery rows in a completed atomic snapshot.

    A refresh in progress does not invalidate the previous published snapshot. A
    reconnect resets its coverage in the connection service; stale snapshots remain
    visible with their historical zeros while freshness independently gates advice.
    """
    return bool(
        meta
        and meta.last_sync_at
        and meta.last_sync_at.replace(tzinfo=UTC) <= now
        and meta.covered_from
        and meta.covered_through
        and meta.covered_from <= first
        and meta.covered_through >= last
    )


def _fresh(snapshot: dict[str, Any] | None, today: date) -> bool:
    return bool(
        snapshot
        and today - date.fromisoformat(snapshot["last_covered_date"])
        <= timedelta(days=FRESHNESS_DAYS)
    )


def _suggestion(
    *,
    key: str,
    title: str,
    evidence: str,
    action: str,
    today: date,
    account: AdvertisingAccount,
    campaign: Campaign,
    priority: int = 4,
) -> dict[str, Any]:
    return {
        "key": key,
        "priority": priority,
        "title": title,
        "evidence": evidence,
        "evidence_basis": "Imported platform delivery metrics; campaign-level observation.",
        "account_id": account.id,
        "campaign_id": campaign.id,
        "platform": account.platform.value,
        "currency_code": account.currency_code,
        "goal": "Improve measured campaign delivery",
        "action": action,
        "cost_change_micros": 0,
        "confidence": "directional",
        "review_on": (today + timedelta(days=7)).isoformat(),
        "expected_result": "A reviewed next step; uplift is not estimated.",
        "effort": "operator review",
        "approval_required": True,
        "limitations": [
            "Clicks and impressions do not establish customers, revenue, or profit.",
            "Delivery changes may reflect targeting, placement, auction, or creative changes.",
        ],
    }


def _campaign_suggestions(
    account: AdvertisingAccount,
    campaign: Campaign,
    current: dict[str, Any] | None,
    comparison: dict[str, Any],
    fresh: bool,
    today: date,
) -> list[dict[str, Any]]:
    if not current or not fresh or current["observed_days"] < MIN_OBSERVED_DAYS:
        return []
    items: list[dict[str, Any]] = []

    def add(key: str, title: str, evidence: str, action: str) -> None:
        items.append(
            _suggestion(
                key=f"platform_{account.id}_{campaign.id}_{key}",
                title=title,
                evidence=evidence,
                action=action,
                today=today,
                account=account,
                campaign=campaign,
            )
        )

    if (
        current["impressions"] >= MIN_IMPRESSIONS
        and current["clicks"] == 0
        and current["cost_micros"] > 0
    ):
        add(
            "no_clicks",
            f"Review delivery without clicks: {campaign.name}",
            f"{current['impressions']:,} impressions and zero recorded clicks across "
            f"{current['observed_days']} observed days, with recorded spend.",
            "Check whether the campaign objective expects clicks, verify click reporting, "
            "and review the offer and destination before considering a change in spend.",
        )
    if comparison["sample_ready"]:
        ctr_change = comparison["ctr_change_ratio"]
        cpc_change = comparison["cpc_change_ratio"]
        if ctr_change is not None and ctr_change <= -0.20:
            add(
                "engagement_decline",
                f"Review declining click engagement: {campaign.name}",
                f"Click-through rate fell {abs(ctr_change):.0%} between complete 28-day periods; "
                "each period has at least 1,000 impressions and 50 clicks.",
                "Review recent campaign changes and test one creative or offer variation "
                "within the approved budget. Confirm the campaign objective before judging clicks.",
            )
        if cpc_change is not None and cpc_change >= 0.25:
            add(
                "click_cost_increase",
                f"Investigate higher click costs: {campaign.name}",
                f"Average cost per click rose {cpc_change:.0%} between complete 28-day periods; "
                "each period has at least 1,000 impressions and 50 clicks.",
                "Review audience, placement, auction and campaign changes. Check available "
                "outcome quality before deciding whether the higher click cost is acceptable.",
            )
    return items


def build_available_evidence(
    session: Session, workspace_id: int, as_of: datetime
) -> dict[str, Any]:
    """Return independently usable evidence, never requiring an unrelated integration.

    ``attributed_outcomes`` deliberately stays unready here: IntelligenceService replaces
    it with UnifiedOutcomeService's authoritative readiness and blocking reasons.
    """
    now = as_of.replace(tzinfo=UTC) if as_of.tzinfo is None else as_of.astimezone(UTC)
    accounts = list(
        session.scalars(
            select(AdvertisingAccount)
            .where(AdvertisingAccount.workspace_id == workspace_id)
            .order_by(AdvertisingAccount.platform, AdvertisingAccount.id)
        )
    )
    campaigns = list(
        session.scalars(
            select(Campaign)
            .join(AdvertisingAccount, Campaign.account_id == AdvertisingAccount.id)
            .where(AdvertisingAccount.workspace_id == workspace_id)
            .order_by(Campaign.id)
        )
    )
    # Only the canonical campaign grain contributes. Adding ad groups or keywords
    # cannot increase account spend, impressions, or clicks a second time.
    rows = list(
        session.scalars(
            select(DailyMetric)
            .join(
                Campaign,
                and_(
                    DailyMetric.campaign_id == Campaign.id,
                    DailyMetric.platform == Campaign.platform,
                ),
            )
            .join(AdvertisingAccount, Campaign.account_id == AdvertisingAccount.id)
            .where(
                AdvertisingAccount.workspace_id == workspace_id,
                DailyMetric.entity_type == "campaign",
                DailyMetric.entity_id == Campaign.id,
                DailyMetric.metric_date >= now.date() - timedelta(days=57),
                DailyMetric.metric_date <= now.date(),
            )
            .order_by(DailyMetric.campaign_id, DailyMetric.metric_date)
        )
    )
    by_campaign: dict[int, list[DailyMetric]] = defaultdict(list)
    for row in rows:
        by_campaign[row.campaign_id].append(row)
    by_account: dict[int, list[Campaign]] = defaultdict(list)
    for campaign in campaigns:
        by_account[campaign.account_id].append(campaign)
    account_reports: list[dict[str, Any]] = []
    recommendations: list[dict[str, Any]] = []
    meta_connections = {
        row.account_id: row
        for row in session.execute(
            select(
                MetaConnection.account_id,
                MetaConnection.conversion_action_type,
                MetaConnection.last_sync_at,
                MetaConnection.covered_from,
                MetaConnection.covered_through,
                MetaConnection.status,
                MetaConnection.error_code,
                MetaConnection.window_end,
            ).where(MetaConnection.workspace_id == workspace_id)
        )
    }
    for account in accounts:
        timezone_known = bool(account.time_zone)
        try:
            zone = ZoneInfo(account.time_zone or "UTC")
        except ZoneInfoNotFoundError:
            zone, timezone_known = ZoneInfo("UTC"), False
        today = now.astimezone(zone).date()
        end, start = today - timedelta(days=1), today - timedelta(days=WINDOW_DAYS)
        previous_start = start - timedelta(days=WINDOW_DAYS)
        previous_end = start - timedelta(days=1)
        owned = by_account[account.id]
        owned_rows = [row for campaign in owned for row in by_campaign[campaign.id]]
        meta = meta_connections.get(account.id)
        current_covered = _meta_covers(meta, start, end, now)
        previous_covered = _meta_covers(meta, previous_start, previous_end, now)
        current_conversions = account.platform == AdvertisingPlatform.GOOGLE_ADS or bool(
            current_covered and meta and meta.conversion_action_type
        )
        previous_conversions = account.platform == AdvertisingPlatform.GOOGLE_ADS or bool(
            previous_covered and meta and meta.conversion_action_type
        )
        value_available = account.platform == AdvertisingPlatform.GOOGLE_ADS or bool(
            meta and meta.conversion_action_type in PURCHASE_ACTIONS
        )
        import_fresh = not meta or bool(
            meta.status == "connected"
            and not meta.error_code
            and meta.last_sync_at
            and timedelta(0)
            <= now - meta.last_sync_at.replace(tzinfo=UTC)
            <= timedelta(days=FRESHNESS_DAYS)
        )
        current = _snapshot(
            owned_rows,
            start,
            end,
            len(owned),
            current_conversions,
            current_covered,
            value_available,
        )
        previous = _snapshot(
            owned_rows,
            previous_start,
            previous_end,
            len(owned),
            previous_conversions,
            previous_covered,
            value_available,
        )
        campaign_reports: list[dict[str, Any]] = []
        for campaign in owned:
            campaign_rows = by_campaign[campaign.id]
            # Account coverage proves total zero delivery. Campaign age is not stored;
            # never invent a pre-launch comparison period for a newly seen campaign.
            existed_current = any(row.metric_date <= end for row in campaign_rows)
            existed_previous = any(row.metric_date <= previous_end for row in campaign_rows)
            recent = _snapshot(
                campaign_rows,
                start,
                end,
                1,
                current_conversions,
                current_covered and existed_current,
                value_available,
            )
            old = _snapshot(
                campaign_rows,
                previous_start,
                previous_end,
                1,
                previous_conversions,
                previous_covered and existed_previous,
                value_available,
            )
            fresh = _fresh(recent, today) and import_fresh
            comparison = _comparison(recent, old, fresh and timezone_known)
            if not existed_previous:
                comparison["reason"] = (
                    "No previous campaign delivery is observed; campaign age and comparable "
                    "exposure are unknown."
                )
            campaign_reports.append(
                {
                    "id": campaign.id,
                    "name": campaign.name,
                    "status": "missing" if recent is None else "ready" if fresh else "stale",
                    "current": recent,
                    "previous": old,
                    "comparison": comparison,
                }
            )
            recommendations.extend(
                _campaign_suggestions(
                    account, campaign, recent, comparison, fresh and timezone_known, today
                )
            )
        any_fresh = (current_covered and _fresh(current, today) and import_fresh) or any(
            row["status"] == "ready" for row in campaign_reports
        )
        all_fresh = (current_covered and _fresh(current, today) and import_fresh) or (
            bool(campaign_reports) and all(row["status"] == "ready" for row in campaign_reports)
        )
        limitations = [
            "Platform conversions are not used as verified customers or sales.",
            "Missing dates remain unknown unless a complete Meta import certifies zero delivery.",
            "Calendar-window comparisons do not establish equal campaign age or exposure.",
        ]
        if meta and meta.window_end:
            limitations.append(
                "A refresh is in progress; figures use the previous completed import."
            )
        if current and not current["complete"]:
            limitations.append("Some campaign-days are missing; period comparisons are withheld.")
        if current and not all_fresh:
            limitations.append("Some campaigns need fresh data; fresh campaigns remain usable.")
        if not timezone_known:
            limitations.append(
                "Account time zone is unavailable; dates use UTC and directional suggestions "
                "are withheld until the time zone is known."
            )
        account_reports.append(
            {
                "id": account.id,
                "name": account.name,
                "platform": account.platform.value,
                "currency_code": account.currency_code,
                "time_zone": str(zone),
                "time_zone_known": timezone_known,
                "conversion_action_type": meta.conversion_action_type if meta else None,
                "window": {
                    "start": start.isoformat(),
                    "end": end.isoformat(),
                    "previous_start": previous_start.isoformat(),
                    "previous_end": previous_end.isoformat(),
                },
                "status": "missing" if current is None else "ready" if any_fresh else "stale",
                "current": current,
                "previous": previous,
                "comparison": _comparison(current, previous, all_fresh and timezone_known),
                "campaigns": campaign_reports,
                "limitations": limitations,
            }
        )
    commerce = sales_report(session, workspace_id, now=now)
    contract = session.scalar(
        select(MeasurementContract).where(MeasurementContract.workspace_id == workspace_id)
    )
    platform_ready = any(row["status"] == "ready" for row in account_reports)
    has_platform_data = any(row["current"] is not None for row in account_reports)
    capabilities = {
        "planning": _capability(
            True, "ready", "Goals, budgets, events and manual planning work without a connection."
        ),
        "platform_performance": _capability(
            platform_ready,
            "ready" if platform_ready else "stale" if has_platform_data else "missing",
            "Analyze each available advertising account independently; CRM is optional."
            if platform_ready
            else "Import or refresh one advertising account to analyze its delivery metrics.",
        ),
        "commerce": _capability(
            bool(commerce["ready"]),
            "ready" if commerce["ready"] else "partial" if commerce["connected"] else "missing",
            "Store sales can be analyzed without advertising or CRM connections."
            if commerce["ready"]
            else "Connect or refresh Shopify only when store sales analysis is needed.",
        ),
        "attributed_outcomes": _capability(
            False,
            "configured" if contract and contract.status == "active" else "missing",
            "Business attribution has its own measurement and evidence checks; "
            "it does not block platform or store analysis.",
        ),
    }
    return {
        "workspace_id": workspace_id,
        "as_of": now.isoformat(),
        "window": {"days": WINDOW_DAYS, "basis": "Completed account-local calendar days."},
        "analysis_ready": platform_ready or bool(commerce["ready"]),
        "capabilities": capabilities,
        "accounts": account_reports,
        "commerce": commerce,
        "recommendations": recommendations,
        "limitations": [
            "Each capability uses its own evidence; optional missing connections are not blockers.",
            "Providers, accounts and currencies remain separate without currency conversion.",
            "Directional platform suggestions require fresh data and minimum sample sizes.",
            "Business CPA, revenue ROAS, profit and lift require verified business evidence.",
        ],
        "thresholds": {
            "freshness_days": FRESHNESS_DAYS,
            "minimum_observed_days": MIN_OBSERVED_DAYS,
            "minimum_impressions": MIN_IMPRESSIONS,
            "minimum_clicks_per_comparison_period": MIN_CLICKS,
        },
    }
