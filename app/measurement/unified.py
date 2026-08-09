from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal
from statistics import median
from typing import Any

from app.ads.enums import MetricEntityType
from app.ads.models import AdGroup, AdvertisingAccount, Campaign, DailyMetric
from app.crm.models import CrmConnection, CrmEventRecord
from app.measurement.enums import (
    CustomerValueMode,
    MeasurementAuthority,
    MeasurementValueBehavior,
    PaidClickIdKind,
)
from app.measurement.identifiers import identifier_digest
from app.measurement.models import WebAnalyticsEvent
from app.measurement.repository import MeasurementContractSnapshot, MeasurementRepository
from app.measurement.service import evaluate_measurement_readiness
from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session


@dataclass(frozen=True)
class UnifiedSourceCoverage:
    advertising_metric_days: int
    ad_group_metric_days: int
    ga4_event_count: int
    paid_session_count: int
    crm_event_count: int
    mapped_crm_event_count: int
    attributed_journey_count: int
    unattributed_journey_count: int
    attribution_rate: Decimal | None
    ad_group_attributed_journey_count: int
    ad_group_unattributed_journey_count: int
    ad_group_attribution_rate: Decimal | None
    currency_mismatch_count: int


@dataclass(frozen=True)
class OutcomeMetricsSnapshot:
    advertising_metric_days: int
    metric_coverage_ratio: Decimal
    impressions: int
    clicks: int
    cost_micros: int
    platform_conversion_count: Decimal
    platform_conversion_value_micros: int
    ga4_event_count: int
    paid_session_count: int
    lead_count: int
    optimization_outcome_count: int
    business_outcome_count: int
    cancelled_outcome_count: int
    observed_revenue_micros: int
    click_through_rate: Decimal | None
    platform_conversion_rate: Decimal | None
    click_to_paid_session_rate: Decimal | None
    paid_session_to_lead_rate: Decimal | None
    optimization_outcome_rate: Decimal | None
    business_outcome_rate: Decimal | None
    lead_to_business_outcome_rate: Decimal | None
    funnel_drop_off_rate: Decimal | None
    cancellation_rate: Decimal | None
    revenue_per_click_micros: int | None
    revenue_per_paid_session_micros: int | None
    revenue_per_lead_micros: int | None
    revenue_per_optimization_outcome_micros: int | None
    revenue_per_business_outcome_micros: int | None
    cost_per_lead_micros: int | None
    cost_per_optimization_outcome_micros: int | None
    cost_per_business_outcome_micros: int | None
    observed_roas: Decimal | None
    median_outcome_lag_days: Decimal | None


@dataclass(frozen=True)
class AdGroupOutcomeSnapshot:
    ad_group_id: int
    ad_group_name: str
    metrics: OutcomeMetricsSnapshot


@dataclass(frozen=True)
class CampaignOutcomeSnapshot:
    account_id: int
    campaign_id: int
    platform: str
    campaign_name: str
    metrics: OutcomeMetricsSnapshot
    ad_groups: tuple[AdGroupOutcomeSnapshot, ...]


@dataclass(frozen=True)
class UnifiedOutcomeSnapshot:
    workspace_id: int
    cohort_date_from: date
    cohort_date_to: date
    mature_through: date | None
    as_of: datetime
    contract_version: int | None
    currency_code: str | None
    optimization_goal_stage_key: str | None
    business_value_stage_key: str | None
    analysis_ready: bool
    blocking_reasons: tuple[str, ...]
    ad_group_analysis_ready: bool
    ad_group_blocking_reasons: tuple[str, ...]
    source_coverage: UnifiedSourceCoverage
    totals: OutcomeMetricsSnapshot | None
    campaigns: tuple[CampaignOutcomeSnapshot, ...]


@dataclass
class _MutableMetrics:
    advertising_metric_days: int = 0
    impressions: int = 0
    clicks: int = 0
    cost_micros: int = 0
    platform_conversions: Decimal = Decimal("0")
    platform_conversion_value_micros: int = 0
    ga4_event_count: int = 0
    paid_sessions: set[str] = field(default_factory=set)
    leads: set[str] = field(default_factory=set)
    optimization_outcomes: set[str] = field(default_factory=set)
    business_outcomes: set[str] = field(default_factory=set)
    cancelled_outcomes: set[str] = field(default_factory=set)
    observed_revenue_by_journey: dict[str, int] = field(default_factory=dict)
    outcome_lag_days: list[int] = field(default_factory=list)


@dataclass
class _JourneyState:
    touchpoint: WebAnalyticsEvent | None = None
    stage_keys: set[str] = field(default_factory=set)
    observed_revenue_micros: int = 0
    cancelled: bool = False
    outcome_lag_days: list[int] = field(default_factory=list)
    currency_mismatch_count: int = 0


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _day_start(value: date) -> datetime:
    return datetime.combine(value, time.min, tzinfo=UTC)


def _day_after(value: date) -> datetime:
    return _day_start(value + timedelta(days=1))


def _ratio(numerator: int, denominator: int) -> Decimal | None:
    if denominator == 0:
        return None
    return (Decimal(numerator) / Decimal(denominator)).quantize(
        Decimal("0.000001"), rounding=ROUND_HALF_UP
    )


def _decimal_ratio(numerator: Decimal, denominator: int) -> Decimal | None:
    if denominator == 0:
        return None
    return (numerator / Decimal(denominator)).quantize(
        Decimal("0.000001"), rounding=ROUND_HALF_UP
    )


def _micros_per(numerator: int, denominator: int) -> int | None:
    if denominator == 0:
        return None
    return int(
        (Decimal(numerator) / Decimal(denominator)).quantize(
            Decimal("1"), rounding=ROUND_HALF_UP
        )
    )


def _money_to_micros(value: object) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        amount = Decimal(str(value))
    except Exception:
        return None
    if not amount.is_finite() or amount < 0:
        return None
    return int((amount * Decimal("1000000")).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _finalize(bucket: _MutableMetrics, window_days: int) -> OutcomeMetricsSnapshot:
    lead_count = len(bucket.leads)
    optimization_count = len(bucket.optimization_outcomes)
    business_count = len(bucket.business_outcomes)
    revenue = sum(bucket.observed_revenue_by_journey.values())
    lag = (
        Decimal(str(median(bucket.outcome_lag_days))).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        if bucket.outcome_lag_days
        else None
    )
    business_per_lead = _ratio(business_count, lead_count)
    completed_outcomes = business_count + len(bucket.cancelled_outcomes)
    return OutcomeMetricsSnapshot(
        advertising_metric_days=bucket.advertising_metric_days,
        metric_coverage_ratio=(
            Decimal(bucket.advertising_metric_days) / Decimal(window_days)
        ).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP),
        impressions=bucket.impressions,
        clicks=bucket.clicks,
        cost_micros=bucket.cost_micros,
        platform_conversion_count=bucket.platform_conversions,
        platform_conversion_value_micros=bucket.platform_conversion_value_micros,
        ga4_event_count=bucket.ga4_event_count,
        paid_session_count=len(bucket.paid_sessions),
        lead_count=lead_count,
        optimization_outcome_count=optimization_count,
        business_outcome_count=business_count,
        cancelled_outcome_count=len(bucket.cancelled_outcomes),
        observed_revenue_micros=revenue,
        click_through_rate=_ratio(bucket.clicks, bucket.impressions),
        platform_conversion_rate=_decimal_ratio(bucket.platform_conversions, bucket.clicks),
        click_to_paid_session_rate=_ratio(len(bucket.paid_sessions), bucket.clicks),
        paid_session_to_lead_rate=_ratio(lead_count, len(bucket.paid_sessions)),
        optimization_outcome_rate=_ratio(optimization_count, lead_count),
        business_outcome_rate=_ratio(business_count, optimization_count),
        lead_to_business_outcome_rate=business_per_lead,
        funnel_drop_off_rate=(
            Decimal("1") - business_per_lead if business_per_lead is not None else None
        ),
        cancellation_rate=_ratio(len(bucket.cancelled_outcomes), completed_outcomes),
        revenue_per_click_micros=_micros_per(revenue, bucket.clicks),
        revenue_per_paid_session_micros=_micros_per(revenue, len(bucket.paid_sessions)),
        revenue_per_lead_micros=_micros_per(revenue, lead_count),
        revenue_per_optimization_outcome_micros=_micros_per(revenue, optimization_count),
        revenue_per_business_outcome_micros=_micros_per(revenue, business_count),
        cost_per_lead_micros=_micros_per(bucket.cost_micros, lead_count),
        cost_per_optimization_outcome_micros=_micros_per(
            bucket.cost_micros, optimization_count
        ),
        cost_per_business_outcome_micros=_micros_per(bucket.cost_micros, business_count),
        observed_roas=(
            _ratio(revenue, bucket.cost_micros) if bucket.cost_micros else None
        ),
        median_outcome_lag_days=lag,
    )


def _empty_coverage() -> UnifiedSourceCoverage:
    return UnifiedSourceCoverage(
        advertising_metric_days=0,
        ad_group_metric_days=0,
        ga4_event_count=0,
        paid_session_count=0,
        crm_event_count=0,
        mapped_crm_event_count=0,
        attributed_journey_count=0,
        unattributed_journey_count=0,
        attribution_rate=None,
        ad_group_attributed_journey_count=0,
        ad_group_unattributed_journey_count=0,
        ad_group_attribution_rate=None,
        currency_mismatch_count=0,
    )


class UnifiedOutcomeService:
    """Correlate local ad, GA4, and CRM facts without contacting external systems."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def report(
        self,
        workspace_id: int,
        cohort_date_from: date,
        cohort_date_to: date,
        *,
        as_of: datetime | None = None,
    ) -> UnifiedOutcomeSnapshot:
        if cohort_date_to < cohort_date_from:
            raise ValueError("invalid cohort date range")
        resolved_as_of = _utc(as_of or datetime.now(UTC))
        snapshot = MeasurementRepository(self.session).get_for_workspace(workspace_id)
        if snapshot is None:
            return UnifiedOutcomeSnapshot(
                workspace_id=workspace_id,
                cohort_date_from=cohort_date_from,
                cohort_date_to=cohort_date_to,
                mature_through=None,
                as_of=resolved_as_of,
                contract_version=None,
                currency_code=None,
                optimization_goal_stage_key=None,
                business_value_stage_key=None,
                analysis_ready=False,
                blocking_reasons=("measurement_contract_missing",),
                ad_group_analysis_ready=False,
                ad_group_blocking_reasons=("measurement_contract_missing",),
                source_coverage=_empty_coverage(),
                totals=None,
                campaigns=(),
            )
        readiness = evaluate_measurement_readiness(snapshot)
        contract = snapshot.contract
        contract_reasons = list(readiness.blocking_reasons)
        if contract.customer_value_mode != CustomerValueMode.OBSERVED_REVENUE_ONLY.value:
            contract_reasons.append("customer_value_mode_not_supported")
        if contract.engaged_view_lookback_days != 0:
            contract_reasons.append("engaged_view_attribution_not_supported")
        maturity_cutoff = resolved_as_of.date() - timedelta(days=contract.outcome_maturity_days)
        mature_through = min(cohort_date_to, maturity_cutoff)
        if contract_reasons:
            return self._contract_blocked_report(
                workspace_id,
                cohort_date_from,
                cohort_date_to,
                mature_through,
                resolved_as_of,
                snapshot,
                tuple(contract_reasons),
            )
        if mature_through < cohort_date_from:
            return self._contract_blocked_report(
                workspace_id,
                cohort_date_from,
                cohort_date_to,
                None,
                resolved_as_of,
                snapshot,
                ("no_mature_cohort",),
            )
        return self._build_ready_report(
            workspace_id,
            cohort_date_from,
            cohort_date_to,
            mature_through,
            resolved_as_of,
            snapshot,
        )

    def _contract_blocked_report(
        self,
        workspace_id: int,
        cohort_date_from: date,
        cohort_date_to: date,
        mature_through: date | None,
        as_of: datetime,
        snapshot: MeasurementContractSnapshot,
        reasons: tuple[str, ...],
    ) -> UnifiedOutcomeSnapshot:
        contract = snapshot.contract
        return UnifiedOutcomeSnapshot(
            workspace_id=workspace_id,
            cohort_date_from=cohort_date_from,
            cohort_date_to=cohort_date_to,
            mature_through=mature_through,
            as_of=as_of,
            contract_version=contract.version,
            currency_code=contract.currency_code,
            optimization_goal_stage_key=contract.optimization_goal_stage_key,
            business_value_stage_key=contract.business_value_stage_key,
            analysis_ready=False,
            blocking_reasons=reasons,
            ad_group_analysis_ready=False,
            ad_group_blocking_reasons=reasons,
            source_coverage=_empty_coverage(),
            totals=None,
            campaigns=(),
        )

    def _build_ready_report(
        self,
        workspace_id: int,
        cohort_date_from: date,
        cohort_date_to: date,
        mature_through: date,
        as_of: datetime,
        snapshot: MeasurementContractSnapshot,
    ) -> UnifiedOutcomeSnapshot:
        contract = snapshot.contract
        start_at = _day_start(cohort_date_from)
        mature_end = _day_after(mature_through)
        outcome_end = min(
            as_of,
            _day_after(mature_through + timedelta(days=contract.customer_value_horizon_days)),
        )
        metric_window_days = (mature_through - cohort_date_from).days + 1
        campaign_metadata = self._campaign_metadata(workspace_id)
        ad_group_metadata = self._ad_group_metadata(workspace_id)
        campaign_buckets: defaultdict[int, _MutableMetrics] = defaultdict(_MutableMetrics)
        ad_group_buckets: defaultdict[int, _MutableMetrics] = defaultdict(_MutableMetrics)
        total_bucket = _MutableMetrics()
        metric_days, ad_group_metric_days = self._apply_ad_metrics(
            workspace_id,
            cohort_date_from,
            mature_through,
            campaign_buckets,
            ad_group_buckets,
            total_bucket,
        )
        web_events = list(
            self.session.scalars(
                select(WebAnalyticsEvent)
                .where(
                    WebAnalyticsEvent.workspace_id == workspace_id,
                    WebAnalyticsEvent.occurred_at >= start_at,
                    WebAnalyticsEvent.occurred_at < mature_end,
                )
                .order_by(WebAnalyticsEvent.occurred_at.asc(), WebAnalyticsEvent.id.asc())
            ).all()
        )
        touchpoints = self._apply_web_events(
            web_events,
            campaign_buckets,
            ad_group_buckets,
            total_bucket,
        )
        crm_records = list(
            self.session.scalars(
                select(CrmEventRecord)
                .join(CrmConnection, CrmConnection.id == CrmEventRecord.connection_id)
                .where(
                    CrmConnection.workspace_id == workspace_id,
                    CrmEventRecord.occurred_at >= start_at,
                    CrmEventRecord.occurred_at <= outcome_end,
                )
                .order_by(
                    CrmEventRecord.connection_id.asc(),
                    CrmEventRecord.crm_lead_id.asc(),
                    CrmEventRecord.occurred_at.asc(),
                    CrmEventRecord.id.asc(),
                )
            ).all()
        )
        journey_result = self._apply_crm_journeys(
            workspace_id,
            crm_records,
            touchpoints,
            snapshot,
            campaign_buckets,
            ad_group_buckets,
            total_bucket,
        )
        (
            mapped_count,
            attributed_count,
            unattributed_count,
            ad_group_attributed_count,
            ad_group_unattributed_count,
            currency_mismatches,
        ) = journey_result
        reasons: list[str] = []
        if metric_days == 0:
            reasons.append("advertising_metrics_missing")
        if not touchpoints:
            reasons.append("ga4_paid_touchpoints_missing")
        if not crm_records:
            reasons.append("crm_events_missing")
        elif mapped_count == 0:
            reasons.append("mapped_crm_outcomes_missing")
        elif attributed_count == 0:
            reasons.append("crm_attribution_missing")
        if currency_mismatches:
            reasons.append("crm_currency_mismatch")
        ad_group_reasons: list[str] = []
        if ad_group_metric_days == 0:
            ad_group_reasons.append("ad_group_metrics_missing")
        if not any(item.ad_group_id is not None for item in touchpoints):
            ad_group_reasons.append("ad_group_paid_touchpoints_missing")
        if not crm_records:
            ad_group_reasons.append("crm_events_missing")
        elif mapped_count == 0:
            ad_group_reasons.append("mapped_crm_outcomes_missing")
        elif ad_group_attributed_count == 0:
            ad_group_reasons.append("ad_group_crm_attribution_missing")
        if ad_group_unattributed_count:
            ad_group_reasons.append("ad_group_attribution_incomplete")
        if currency_mismatches:
            ad_group_reasons.append("crm_currency_mismatch")
        campaign_rows = tuple(
            CampaignOutcomeSnapshot(
                account_id=campaign_metadata[campaign_id][0],
                campaign_id=campaign_id,
                platform=campaign_metadata[campaign_id][1],
                campaign_name=campaign_metadata[campaign_id][2],
                metrics=_finalize(bucket, metric_window_days),
                ad_groups=tuple(
                    AdGroupOutcomeSnapshot(
                        ad_group_id=ad_group_id,
                        ad_group_name=ad_group_metadata[ad_group_id][1],
                        metrics=_finalize(ad_group_bucket, metric_window_days),
                    )
                    for ad_group_id, ad_group_bucket in sorted(
                        ad_group_buckets.items(),
                        key=lambda item: (
                            ad_group_metadata.get(item[0], (0, ""))[1].lower(),
                            item[0],
                        ),
                    )
                    if ad_group_id in ad_group_metadata
                    and ad_group_metadata[ad_group_id][0] == campaign_id
                ),
            )
            for campaign_id, bucket in sorted(
                campaign_buckets.items(),
                key=lambda item: (
                    campaign_metadata.get(item[0], (0, "", ""))[2].lower(),
                    item[0],
                ),
            )
            if campaign_id in campaign_metadata
        )
        journey_total = attributed_count + unattributed_count
        coverage = UnifiedSourceCoverage(
            advertising_metric_days=metric_days,
            ad_group_metric_days=ad_group_metric_days,
            ga4_event_count=len(web_events),
            paid_session_count=len(touchpoints),
            crm_event_count=len(crm_records),
            mapped_crm_event_count=mapped_count,
            attributed_journey_count=attributed_count,
            unattributed_journey_count=unattributed_count,
            attribution_rate=_ratio(attributed_count, journey_total),
            ad_group_attributed_journey_count=ad_group_attributed_count,
            ad_group_unattributed_journey_count=ad_group_unattributed_count,
            ad_group_attribution_rate=_ratio(ad_group_attributed_count, journey_total),
            currency_mismatch_count=currency_mismatches,
        )
        return UnifiedOutcomeSnapshot(
            workspace_id=workspace_id,
            cohort_date_from=cohort_date_from,
            cohort_date_to=cohort_date_to,
            mature_through=mature_through,
            as_of=as_of,
            contract_version=contract.version,
            currency_code=contract.currency_code,
            optimization_goal_stage_key=contract.optimization_goal_stage_key,
            business_value_stage_key=contract.business_value_stage_key,
            analysis_ready=not reasons,
            blocking_reasons=tuple(reasons),
            ad_group_analysis_ready=not ad_group_reasons,
            ad_group_blocking_reasons=tuple(ad_group_reasons),
            source_coverage=coverage,
            totals=_finalize(total_bucket, metric_window_days),
            campaigns=campaign_rows,
        )

    def _campaign_metadata(self, workspace_id: int) -> dict[int, tuple[int, str, str]]:
        rows = self.session.execute(
            select(Campaign.id, Campaign.account_id, AdvertisingAccount.platform, Campaign.name)
            .join(AdvertisingAccount, AdvertisingAccount.id == Campaign.account_id)
            .where(AdvertisingAccount.workspace_id == workspace_id)
        ).all()
        return {
            int(campaign_id): (
                int(account_id),
                platform.value if hasattr(platform, "value") else str(platform),
                str(name),
            )
            for campaign_id, account_id, platform, name in rows
        }

    def _ad_group_metadata(self, workspace_id: int) -> dict[int, tuple[int, str]]:
        rows = self.session.execute(
            select(AdGroup.id, AdGroup.campaign_id, AdGroup.name)
            .join(Campaign, Campaign.id == AdGroup.campaign_id)
            .join(AdvertisingAccount, AdvertisingAccount.id == Campaign.account_id)
            .where(AdvertisingAccount.workspace_id == workspace_id)
        ).all()
        return {
            int(ad_group_id): (int(campaign_id), str(name))
            for ad_group_id, campaign_id, name in rows
        }

    def _apply_ad_metrics(
        self,
        workspace_id: int,
        date_from: date,
        date_to: date,
        campaign_buckets: defaultdict[int, _MutableMetrics],
        ad_group_buckets: defaultdict[int, _MutableMetrics],
        total: _MutableMetrics,
    ) -> tuple[int, int]:
        campaign_rows = self.session.execute(
            select(
                DailyMetric.campaign_id,
                func.count(func.distinct(DailyMetric.metric_date)),
                func.coalesce(func.sum(DailyMetric.impressions), 0),
                func.coalesce(func.sum(DailyMetric.clicks), 0),
                func.coalesce(func.sum(DailyMetric.cost_micros), 0),
                func.coalesce(func.sum(DailyMetric.conversions), 0),
                func.coalesce(func.sum(DailyMetric.conversion_value_micros), 0),
            )
            .join(
                Campaign,
                and_(
                    Campaign.id == DailyMetric.campaign_id,
                    Campaign.platform == DailyMetric.platform,
                ),
            )
            .join(AdvertisingAccount, AdvertisingAccount.id == Campaign.account_id)
            .where(
                AdvertisingAccount.workspace_id == workspace_id,
                DailyMetric.entity_type == MetricEntityType.CAMPAIGN.value,
                DailyMetric.entity_id == Campaign.id,
                DailyMetric.metric_date >= date_from,
                DailyMetric.metric_date <= date_to,
            )
            .group_by(DailyMetric.campaign_id)
        ).all()
        for (
            campaign_id,
            metric_days,
            impressions,
            clicks,
            cost_micros,
            conversions,
            conversion_value_micros,
        ) in campaign_rows:
            if campaign_id is None:
                continue
            bucket = campaign_buckets[int(campaign_id)]
            bucket.advertising_metric_days = int(metric_days)
            bucket.impressions += int(impressions)
            bucket.clicks += int(clicks)
            bucket.cost_micros += int(cost_micros)
            bucket.platform_conversions += Decimal(str(conversions))
            bucket.platform_conversion_value_micros += int(conversion_value_micros)
            total.impressions += int(impressions)
            total.clicks += int(clicks)
            total.cost_micros += int(cost_micros)
            total.platform_conversions += Decimal(str(conversions))
            total.platform_conversion_value_micros += int(conversion_value_micros)
        campaign_metric_days = int(
            self.session.scalar(
                select(func.count(func.distinct(DailyMetric.metric_date)))
                .join(
                    Campaign,
                    and_(
                        Campaign.id == DailyMetric.campaign_id,
                        Campaign.platform == DailyMetric.platform,
                    ),
                )
                .join(AdvertisingAccount, AdvertisingAccount.id == Campaign.account_id)
                .where(
                    AdvertisingAccount.workspace_id == workspace_id,
                    DailyMetric.entity_type == MetricEntityType.CAMPAIGN.value,
                    DailyMetric.entity_id == Campaign.id,
                    DailyMetric.metric_date >= date_from,
                    DailyMetric.metric_date <= date_to,
                )
            )
            or 0
        )
        total.advertising_metric_days = campaign_metric_days
        ad_group_rows = self.session.execute(
            select(
                DailyMetric.campaign_id,
                DailyMetric.ad_group_id,
                func.count(func.distinct(DailyMetric.metric_date)),
                func.coalesce(func.sum(DailyMetric.impressions), 0),
                func.coalesce(func.sum(DailyMetric.clicks), 0),
                func.coalesce(func.sum(DailyMetric.cost_micros), 0),
                func.coalesce(func.sum(DailyMetric.conversions), 0),
                func.coalesce(func.sum(DailyMetric.conversion_value_micros), 0),
            )
            .join(
                AdGroup,
                and_(
                    AdGroup.id == DailyMetric.ad_group_id,
                    AdGroup.campaign_id == DailyMetric.campaign_id,
                    AdGroup.platform == DailyMetric.platform,
                ),
            )
            .join(Campaign, Campaign.id == AdGroup.campaign_id)
            .join(AdvertisingAccount, AdvertisingAccount.id == Campaign.account_id)
            .where(
                AdvertisingAccount.workspace_id == workspace_id,
                DailyMetric.entity_type == MetricEntityType.AD_GROUP.value,
                DailyMetric.entity_id == AdGroup.id,
                DailyMetric.metric_date >= date_from,
                DailyMetric.metric_date <= date_to,
            )
            .group_by(DailyMetric.campaign_id, DailyMetric.ad_group_id)
        ).all()
        for (
            campaign_id,
            ad_group_id,
            metric_days,
            impressions,
            clicks,
            cost_micros,
            conversions,
            conversion_value_micros,
        ) in ad_group_rows:
            if campaign_id is None or ad_group_id is None:
                continue
            campaign_buckets[int(campaign_id)]
            bucket = ad_group_buckets[int(ad_group_id)]
            bucket.advertising_metric_days = int(metric_days)
            bucket.impressions += int(impressions)
            bucket.clicks += int(clicks)
            bucket.cost_micros += int(cost_micros)
            bucket.platform_conversions += Decimal(str(conversions))
            bucket.platform_conversion_value_micros += int(conversion_value_micros)
        ad_group_metric_days = int(
            self.session.scalar(
                select(func.count(func.distinct(DailyMetric.metric_date)))
                .join(
                    AdGroup,
                    and_(
                        AdGroup.id == DailyMetric.ad_group_id,
                        AdGroup.campaign_id == DailyMetric.campaign_id,
                        AdGroup.platform == DailyMetric.platform,
                    ),
                )
                .join(Campaign, Campaign.id == AdGroup.campaign_id)
                .join(AdvertisingAccount, AdvertisingAccount.id == Campaign.account_id)
                .where(
                    AdvertisingAccount.workspace_id == workspace_id,
                    DailyMetric.entity_type == MetricEntityType.AD_GROUP.value,
                    DailyMetric.entity_id == AdGroup.id,
                    DailyMetric.metric_date >= date_from,
                    DailyMetric.metric_date <= date_to,
                )
            )
            or 0
        )
        return campaign_metric_days, ad_group_metric_days

    def _apply_web_events(
        self,
        events: list[WebAnalyticsEvent],
        campaign_buckets: defaultdict[int, _MutableMetrics],
        ad_group_buckets: defaultdict[int, _MutableMetrics],
        total: _MutableMetrics,
    ) -> tuple[WebAnalyticsEvent, ...]:
        session_touchpoints: dict[str, WebAnalyticsEvent] = {}
        for event in events:
            if event.campaign_id is not None:
                campaign_buckets[event.campaign_id].ga4_event_count += 1
                total.ga4_event_count += 1
            if event.ad_group_id is not None:
                ad_group_buckets[event.ad_group_id].ga4_event_count += 1
            if not event.is_paid_touchpoint or event.campaign_id is None:
                continue
            previous = session_touchpoints.get(event.session_id_digest)
            if previous is None or (_utc(event.occurred_at), event.id) > (
                _utc(previous.occurred_at),
                previous.id,
            ):
                session_touchpoints[event.session_id_digest] = event
        for session_digest, touchpoint in session_touchpoints.items():
            if touchpoint.campaign_id is None:
                continue
            campaign_buckets[touchpoint.campaign_id].paid_sessions.add(session_digest)
            total.paid_sessions.add(session_digest)
            if touchpoint.ad_group_id is not None:
                ad_group_buckets[touchpoint.ad_group_id].paid_sessions.add(session_digest)
        return tuple(
            sorted(
                session_touchpoints.values(),
                key=lambda item: (_utc(item.occurred_at), item.id),
            )
        )

    def _apply_crm_journeys(
        self,
        workspace_id: int,
        records: list[CrmEventRecord],
        touchpoints: tuple[WebAnalyticsEvent, ...],
        snapshot: MeasurementContractSnapshot,
        campaign_buckets: defaultdict[int, _MutableMetrics],
        ad_group_buckets: defaultdict[int, _MutableMetrics],
        total: _MutableMetrics,
    ) -> tuple[int, int, int, int, int, int]:
        contract = snapshot.contract
        mappings = {
            mapping.source_event_type: mapping
            for mapping in snapshot.mappings
            if mapping.event_source == contract.source_of_truth
            and mapping.authority == MeasurementAuthority.AUTHORITATIVE.value
        }
        lead_stage_key = next(
            (
                stage.stage_key
                for stage in sorted(snapshot.stages, key=lambda item: (item.position, item.id))
                if stage.counts_toward_funnel
            ),
            "lead",
        )
        by_subject: defaultdict[str, list[WebAnalyticsEvent]] = defaultdict(list)
        by_click: defaultdict[str, list[WebAnalyticsEvent]] = defaultdict(list)
        for touchpoint in touchpoints:
            if touchpoint.subject_id_digest is not None:
                by_subject[touchpoint.subject_id_digest].append(touchpoint)
            if touchpoint.click_id_digest is not None:
                by_click[touchpoint.click_id_digest].append(touchpoint)
        grouped: defaultdict[tuple[int, str], list[CrmEventRecord]] = defaultdict(list)
        for record in records:
            grouped[(record.connection_id, record.crm_lead_id)].append(record)
        mapped_event_count = 0
        attributed_count = 0
        unattributed_count = 0
        ad_group_attributed_count = 0
        ad_group_unattributed_count = 0
        currency_mismatch_count = 0
        for (connection_id, crm_lead_id), journey_records in grouped.items():
            journey_key = identifier_digest(
                workspace_id,
                "crm_journey",
                f"{connection_id}:{crm_lead_id}",
            )
            if journey_key is None:
                continue
            state = _JourneyState()
            journey_mapped = 0
            for record in journey_records:
                mapping = mappings.get(record.event_type)
                if mapping is None:
                    continue
                if state.touchpoint is None:
                    state.touchpoint = self._match_touchpoint(
                        workspace_id,
                        record,
                        by_subject,
                        by_click,
                        contract.click_lookback_days,
                    )
                if state.touchpoint is not None and _utc(record.occurred_at) > _utc(
                    state.touchpoint.occurred_at
                ) + timedelta(days=contract.customer_value_horizon_days):
                    continue
                journey_mapped += 1
                mapped_event_count += 1
                state.stage_keys.add(mapping.stage_key)
                if (
                    state.touchpoint is not None
                    and mapping.stage_key == contract.business_value_stage_key
                ):
                    lag = (_utc(record.occurred_at) - _utc(state.touchpoint.occurred_at)).days
                    if lag >= 0:
                        state.outcome_lag_days.append(lag)
                self._apply_value_event(
                    state,
                    record,
                    mapping.value_behavior,
                    contract.currency_code,
                )
            if journey_mapped == 0:
                continue
            currency_mismatch_count += state.currency_mismatch_count
            if state.touchpoint is None or state.touchpoint.campaign_id is None:
                unattributed_count += 1
                ad_group_unattributed_count += 1
                continue
            attributed_count += 1
            bucket = campaign_buckets[state.touchpoint.campaign_id]
            self._apply_journey_metrics(
                bucket,
                journey_key,
                state,
                lead_stage_key,
                contract.optimization_goal_stage_key,
                contract.business_value_stage_key,
            )
            self._apply_journey_metrics(
                total,
                journey_key,
                state,
                lead_stage_key,
                contract.optimization_goal_stage_key,
                contract.business_value_stage_key,
            )
            if state.touchpoint.ad_group_id is None:
                ad_group_unattributed_count += 1
            else:
                ad_group_attributed_count += 1
                self._apply_journey_metrics(
                    ad_group_buckets[state.touchpoint.ad_group_id],
                    journey_key,
                    state,
                    lead_stage_key,
                    contract.optimization_goal_stage_key,
                    contract.business_value_stage_key,
                )
        return (
            mapped_event_count,
            attributed_count,
            unattributed_count,
            ad_group_attributed_count,
            ad_group_unattributed_count,
            currency_mismatch_count,
        )

    def _match_touchpoint(
        self,
        workspace_id: int,
        record: CrmEventRecord,
        by_subject: dict[str, list[WebAnalyticsEvent]],
        by_click: dict[str, list[WebAnalyticsEvent]],
        lookback_days: int,
    ) -> WebAnalyticsEvent | None:
        payload = record.normalized_payload
        subject_value = payload.get("analytics_pseudonymous_id")
        if not isinstance(subject_value, str):
            subject_value = record.crm_lead_id
        subject_digest = identifier_digest(workspace_id, "subject", subject_value)
        candidates: dict[int, WebAnalyticsEvent] = {}
        if subject_digest is not None:
            candidates.update({item.id: item for item in by_subject.get(subject_digest, [])})
        for kind in PaidClickIdKind:
            click_value = payload.get(kind.value)
            if not isinstance(click_value, str):
                continue
            click_digest = identifier_digest(
                workspace_id,
                f"paid_click:{kind.value}",
                click_value,
            )
            if click_digest is not None:
                candidates.update({item.id: item for item in by_click.get(click_digest, [])})
        occurred_at = _utc(record.occurred_at)
        earliest = occurred_at - timedelta(days=lookback_days)
        eligible = [
            item
            for item in candidates.values()
            if earliest <= _utc(item.occurred_at) <= occurred_at
        ]
        if not eligible:
            return None
        return max(eligible, key=lambda item: (_utc(item.occurred_at), item.id))

    def _apply_value_event(
        self,
        state: _JourneyState,
        record: CrmEventRecord,
        value_behavior: str,
        currency_code: str,
    ) -> None:
        payload: dict[str, Any] = record.normalized_payload
        currency = payload.get("currency")
        value_micros = _money_to_micros(payload.get("value"))
        if value_micros is not None and currency != currency_code:
            state.currency_mismatch_count += 1
            value_micros = None
        if value_behavior == MeasurementValueBehavior.SET.value:
            if value_micros is not None:
                state.observed_revenue_micros = value_micros
            state.cancelled = False
        elif value_behavior == MeasurementValueBehavior.ADJUST.value:
            if record.event_type == "sale_cancelled":
                state.observed_revenue_micros = 0
                state.cancelled = True
            elif value_micros is not None:
                state.observed_revenue_micros = value_micros

    @staticmethod
    def _apply_journey_metrics(
        bucket: _MutableMetrics,
        journey_key: str,
        state: _JourneyState,
        lead_stage_key: str,
        optimization_stage_key: str,
        business_stage_key: str,
    ) -> None:
        if lead_stage_key in state.stage_keys:
            bucket.leads.add(journey_key)
        if optimization_stage_key in state.stage_keys:
            bucket.optimization_outcomes.add(journey_key)
        if business_stage_key in state.stage_keys and not state.cancelled:
            bucket.business_outcomes.add(journey_key)
        if state.cancelled:
            bucket.cancelled_outcomes.add(journey_key)
        bucket.observed_revenue_by_journey[journey_key] = state.observed_revenue_micros
        bucket.outcome_lag_days.extend(state.outcome_lag_days)
