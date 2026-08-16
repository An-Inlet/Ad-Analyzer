from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

from app.ads.enums import AdvertisingPlatform, JobRunStatus, MetricEntityType
from app.ads.models import (
    AdGroup,
    AdvertisingAccount,
    Campaign,
    DailyMetric,
    JobRun,
    Keyword,
    SearchTerm,
)
from app.api.repository import ReadOnlyAdsRepository
from app.optimizer.analytics import MetricWindow, inclusive_window_days, percent_delta
from app.optimizer.recommendations import Finding
from sqlalchemy import Select, and_, func, select
from sqlalchemy.orm import Session

MIN_COMPLETE_DAYS = 3
MIN_IMPRESSIONS = 500
MIN_CLICKS = 30
MIN_SPEND_MICROS = 2_000_000
LOW_CTR = Decimal("0.02")
MATERIAL_CHANGE = Decimal("0.50")
MAJOR_CHANGE = Decimal("1.00")
STALE_AFTER_DAYS = 3
_PAGE_SIZE = 200


@dataclass(frozen=True)
class QueryPerformanceSnapshot:
    workspace_id: int
    platform: AdvertisingPlatform
    account_id: int
    account_name: str
    campaign_id: int
    campaign_name: str
    ad_group_id: int
    ad_group_name: str
    entity_type: MetricEntityType
    entity_id: int
    display_label: str
    source_text_redacted: bool
    match_type: str | None
    status: str | None
    current: MetricWindow
    comparison: MetricWindow
    findings: tuple[Finding, ...]


@dataclass(frozen=True)
class QueryFindingCounts:
    findings_count: int
    high_severity_findings_count: int
    keyword_findings_count: int
    search_term_findings_count: int


@dataclass(frozen=True)
class _QueryScope:
    workspace_id: int
    platform: AdvertisingPlatform
    account_id: int
    account_name: str
    campaign_id: int
    campaign_name: str
    ad_group_id: int
    ad_group_name: str
    entity_type: MetricEntityType
    entity_id: int
    display_label: str
    source_text_redacted: bool
    match_type: str | None
    status: str | None


def _empty_totals() -> dict[str, Any]:
    return {
        "days_with_metrics": 0,
        "impressions": 0,
        "clicks": 0,
        "cost_micros": 0,
        "conversions": Decimal("0"),
        "conversion_value_micros": 0,
    }


def _window(start: date, end: date, totals: dict[str, Any] | None) -> MetricWindow:
    values = totals or _empty_totals()
    return MetricWindow(
        date_from=start,
        date_to=end,
        window_days=inclusive_window_days(start, end),
        days_with_metric_rows=int(values["days_with_metrics"]),
        impressions=int(values["impressions"]),
        clicks=int(values["clicks"]),
        cost_micros=int(values["cost_micros"]),
        conversions=Decimal(values["conversions"]),
        conversion_value_micros=int(values["conversion_value_micros"]),
    )


def _comparison_dates(start: date, end: date) -> tuple[date, date]:
    span = inclusive_window_days(start, end)
    comparison_end = start - timedelta(days=1)
    return comparison_end - timedelta(days=span - 1), comparison_end


def _has_complete_days(window: MetricWindow) -> bool:
    return window.days_with_metric_rows >= min(MIN_COMPLETE_DAYS, window.window_days)


def _change_severity(delta: Decimal) -> str:
    return "medium" if abs(delta) >= MAJOR_CHANGE else "low"


def generate_query_findings(
    entity_type: MetricEntityType,
    current: MetricWindow,
    comparison: MetricWindow,
    *,
    last_success_at: datetime | None,
    now: datetime | None = None,
) -> list[Finding]:
    """Return numeric, deterministic findings without exposing keyword or query text."""
    resolved_now = now or datetime.now(UTC)
    if last_success_at is not None and last_success_at.tzinfo is None:
        last_success_at = last_success_at.replace(tzinfo=UTC)
    findings: list[Finding] = []
    if last_success_at is None or last_success_at < resolved_now - timedelta(
        days=STALE_AFTER_DAYS
    ):
        findings.append(
            Finding(
                "stale_data",
                "high",
                "Latest successful sync is stale or unavailable.",
                {"last_success_at": str(last_success_at)},
            )
        )
    if not _has_complete_days(current):
        findings.append(
            Finding(
                "insufficient_data",
                "medium",
                "Current window has insufficient lower-level metric coverage.",
                {
                    "window_days": str(current.window_days),
                    "days_with_metric_rows": str(current.days_with_metric_rows),
                    "minimum_complete_days": str(
                        min(MIN_COMPLETE_DAYS, current.window_days)
                    ),
                },
            )
        )
        return findings

    scope_name = "Search-term record" if entity_type is MetricEntityType.SEARCH_TERM else "Keyword"
    if (
        current.clicks >= MIN_CLICKS
        and current.cost_micros >= MIN_SPEND_MICROS
        and current.conversions == 0
    ):
        findings.append(
            Finding(
                "spend_without_platform_conversions",
                "high",
                f"{scope_name} has material spend and clicks without platform conversions.",
                {
                    "clicks": str(current.clicks),
                    "cost_micros": str(current.cost_micros),
                    "platform_conversions": str(current.conversions),
                },
            )
        )
    if current.impressions >= MIN_IMPRESSIONS and current.ctr < LOW_CTR:
        findings.append(
            Finding(
                "low_ctr",
                "medium",
                f"{scope_name} click-through rate is below the deterministic threshold.",
                {
                    "impressions": str(current.impressions),
                    "clicks": str(current.clicks),
                    "ctr": str(current.ctr),
                },
            )
        )
    if not _has_complete_days(comparison):
        return findings

    spend_delta = percent_delta(
        Decimal(current.cost_micros),
        Decimal(comparison.cost_micros),
    )
    if (
        current.cost_micros >= MIN_SPEND_MICROS
        and comparison.cost_micros >= MIN_SPEND_MICROS
        and spend_delta is not None
        and abs(spend_delta) >= MATERIAL_CHANGE
    ):
        findings.append(
            Finding(
                "unusual_spend_change",
                _change_severity(spend_delta),
                f"{scope_name} spend changed materially versus the comparison window.",
                {
                    "current_cost_micros": str(current.cost_micros),
                    "comparison_cost_micros": str(comparison.cost_micros),
                    "relative_change": str(spend_delta),
                },
            )
        )
    impression_delta = percent_delta(
        Decimal(current.impressions),
        Decimal(comparison.impressions),
    )
    if (
        current.impressions >= MIN_IMPRESSIONS
        and comparison.impressions >= MIN_IMPRESSIONS
        and impression_delta is not None
        and abs(impression_delta) >= MATERIAL_CHANGE
    ):
        findings.append(
            Finding(
                "unusual_traffic_change",
                _change_severity(impression_delta),
                f"{scope_name} impressions changed materially versus the comparison window.",
                {
                    "current_impressions": str(current.impressions),
                    "comparison_impressions": str(comparison.impressions),
                    "relative_change": str(impression_delta),
                },
            )
        )
    return findings


class QueryPerformanceService:
    """Analyze local keyword/query metrics without external calls or advertising mutations."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.repository = ReadOnlyAdsRepository(session)

    def analyze_keywords(
        self,
        ad_group_id: int,
        date_from: date,
        date_to: date,
        *,
        limit: int,
        offset: int,
        now: datetime | None = None,
    ) -> tuple[list[QueryPerformanceSnapshot], int]:
        scopes, total = self._scope_page(
            MetricEntityType.KEYWORD,
            date_from,
            date_to,
            ad_group_id=ad_group_id,
            limit=limit,
            offset=offset,
        )
        return self._analyze_scopes(scopes, date_from, date_to, now=now), total

    def analyze_search_terms(
        self,
        ad_group_id: int,
        date_from: date,
        date_to: date,
        *,
        limit: int,
        offset: int,
        now: datetime | None = None,
    ) -> tuple[list[QueryPerformanceSnapshot], int]:
        scopes, total = self._scope_page(
            MetricEntityType.SEARCH_TERM,
            date_from,
            date_to,
            ad_group_id=ad_group_id,
            limit=limit,
            offset=offset,
        )
        return self._analyze_scopes(scopes, date_from, date_to, now=now), total

    def count_workspace_findings(
        self,
        workspace_id: int,
        date_from: date,
        date_to: date,
        *,
        account_id: int | None = None,
        now: datetime | None = None,
    ) -> QueryFindingCounts:
        total_count = 0
        high_count = 0
        keyword_count = 0
        search_term_count = 0
        for entity_type in (MetricEntityType.KEYWORD, MetricEntityType.SEARCH_TERM):
            offset = 0
            while True:
                scopes, _ = self._scope_page(
                    entity_type,
                    date_from,
                    date_to,
                    workspace_id=workspace_id,
                    account_id=account_id,
                    limit=_PAGE_SIZE,
                    offset=offset,
                )
                if not scopes:
                    break
                rows = self._analyze_scopes(scopes, date_from, date_to, now=now)
                scoped_count = sum(len(row.findings) for row in rows)
                total_count += scoped_count
                high_count += sum(
                    finding.severity == "high" for row in rows for finding in row.findings
                )
                if entity_type is MetricEntityType.KEYWORD:
                    keyword_count += scoped_count
                else:
                    search_term_count += scoped_count
                if len(scopes) < _PAGE_SIZE:
                    break
                offset += _PAGE_SIZE
        return QueryFindingCounts(
            findings_count=total_count,
            high_severity_findings_count=high_count,
            keyword_findings_count=keyword_count,
            search_term_findings_count=search_term_count,
        )

    def _analyze_scopes(
        self,
        scopes: list[_QueryScope],
        date_from: date,
        date_to: date,
        *,
        now: datetime | None,
    ) -> list[QueryPerformanceSnapshot]:
        if not scopes:
            return []
        comparison_from, comparison_to = _comparison_dates(date_from, date_to)
        entity_type = scopes[0].entity_type
        entity_ids = [scope.entity_id for scope in scopes]
        current_totals = self.repository.entity_metric_totals(
            entity_type,
            entity_ids,
            date_from,
            date_to,
        )
        comparison_totals = self.repository.entity_metric_totals(
            entity_type,
            entity_ids,
            comparison_from,
            comparison_to,
        )
        last_success = self._last_success_by_account({scope.account_id for scope in scopes})
        resolved_now = now or datetime.now(UTC)
        rows: list[QueryPerformanceSnapshot] = []
        for scope in scopes:
            current = _window(date_from, date_to, current_totals.get(scope.entity_id))
            comparison = _window(
                comparison_from,
                comparison_to,
                comparison_totals.get(scope.entity_id),
            )
            rows.append(
                QueryPerformanceSnapshot(
                    **scope.__dict__,
                    current=current,
                    comparison=comparison,
                    findings=tuple(
                        generate_query_findings(
                            scope.entity_type,
                            current,
                            comparison,
                            last_success_at=last_success.get(scope.account_id),
                            now=resolved_now,
                        )
                    ),
                )
            )
        return rows

    def _last_success_by_account(self, account_ids: set[int]) -> dict[int, datetime]:
        if not account_ids:
            return {}
        return {
            int(account_id): finished_at
            for account_id, finished_at in self.session.execute(
                select(JobRun.account_id, func.max(JobRun.finished_at))
                .where(
                    JobRun.account_id.in_(account_ids),
                    JobRun.status == JobRunStatus.SUCCEEDED,
                )
                .group_by(JobRun.account_id)
            ).all()
            if account_id is not None and finished_at is not None
        }

    def _scope_page(
        self,
        entity_type: MetricEntityType,
        date_from: date,
        date_to: date,
        *,
        ad_group_id: int | None = None,
        workspace_id: int | None = None,
        account_id: int | None = None,
        limit: int,
        offset: int,
    ) -> tuple[list[_QueryScope], int]:
        if entity_type not in {MetricEntityType.KEYWORD, MetricEntityType.SEARCH_TERM}:
            raise ValueError("unsupported lower-level metric scope")
        spend = (
            select(
                DailyMetric.entity_id.label("entity_id"),
                func.sum(DailyMetric.cost_micros).label("cost_micros"),
            )
            .where(
                DailyMetric.entity_type == entity_type.value,
                DailyMetric.metric_date >= date_from,
                DailyMetric.metric_date <= date_to,
            )
            .group_by(DailyMetric.entity_id)
            .subquery()
        )
        if entity_type is MetricEntityType.KEYWORD:
            statement: Select[Any] = (
                select(
                    AdvertisingAccount.workspace_id,
                    Keyword.platform,
                    AdvertisingAccount.id,
                    AdvertisingAccount.name,
                    Campaign.id,
                    Campaign.name,
                    AdGroup.id,
                    AdGroup.name,
                    Keyword.id,
                    Keyword.text,
                    Keyword.match_type,
                    Keyword.status,
                )
                .select_from(Keyword)
                .join(
                    AdGroup,
                    and_(
                        AdGroup.id == Keyword.ad_group_id,
                        AdGroup.platform == Keyword.platform,
                    ),
                )
                .join(Campaign, Campaign.id == AdGroup.campaign_id)
                .join(AdvertisingAccount, AdvertisingAccount.id == Campaign.account_id)
                .outerjoin(spend, spend.c.entity_id == Keyword.id)
                .order_by(func.coalesce(spend.c.cost_micros, 0).desc(), Keyword.id.asc())
            )
        else:
            statement = (
                select(
                    AdvertisingAccount.workspace_id,
                    SearchTerm.platform,
                    AdvertisingAccount.id,
                    AdvertisingAccount.name,
                    Campaign.id,
                    Campaign.name,
                    AdGroup.id,
                    AdGroup.name,
                    SearchTerm.id,
                    SearchTerm.match_type,
                )
                .select_from(SearchTerm)
                .join(
                    AdGroup,
                    and_(
                        AdGroup.id == SearchTerm.ad_group_id,
                        AdGroup.platform == SearchTerm.platform,
                    ),
                )
                .join(Campaign, Campaign.id == AdGroup.campaign_id)
                .join(AdvertisingAccount, AdvertisingAccount.id == Campaign.account_id)
                .outerjoin(spend, spend.c.entity_id == SearchTerm.id)
                .order_by(func.coalesce(spend.c.cost_micros, 0).desc(), SearchTerm.id.asc())
            )
        if ad_group_id is not None:
            statement = statement.where(AdGroup.id == ad_group_id)
        if workspace_id is not None:
            statement = statement.where(AdvertisingAccount.workspace_id == workspace_id)
        if account_id is not None:
            statement = statement.where(AdvertisingAccount.id == account_id)
        total = self.session.scalar(
            select(func.count()).select_from(statement.order_by(None).subquery())
        ) or 0
        result = self.session.execute(statement.limit(limit).offset(offset)).all()
        scopes: list[_QueryScope] = []
        for row in result:
            if entity_type is MetricEntityType.KEYWORD:
                (
                    row_workspace_id,
                    platform,
                    row_account_id,
                    account_name,
                    campaign_id,
                    campaign_name,
                    row_ad_group_id,
                    ad_group_name,
                    entity_id,
                    display_label,
                    match_type,
                    status,
                ) = row
                source_text_redacted = False
            else:
                (
                    row_workspace_id,
                    platform,
                    row_account_id,
                    account_name,
                    campaign_id,
                    campaign_name,
                    row_ad_group_id,
                    ad_group_name,
                    entity_id,
                    match_type,
                ) = row
                display_label = f"Search term #{entity_id}"
                source_text_redacted = True
                status = None
            scopes.append(
                _QueryScope(
                    workspace_id=int(row_workspace_id),
                    platform=AdvertisingPlatform(platform),
                    account_id=int(row_account_id),
                    account_name=str(account_name),
                    campaign_id=int(campaign_id),
                    campaign_name=str(campaign_name),
                    ad_group_id=int(row_ad_group_id),
                    ad_group_name=str(ad_group_name),
                    entity_type=entity_type,
                    entity_id=int(entity_id),
                    display_label=str(display_label),
                    source_text_redacted=source_text_redacted,
                    match_type=str(match_type) if match_type is not None else None,
                    status=str(status) if status is not None else None,
                )
            )
        return scopes, int(total)
