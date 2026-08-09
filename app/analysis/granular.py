from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

from app.ads.enums import AdvertisingPlatform, JobRunStatus, MetricEntityType
from app.ads.models import AdGroup, AdvertisingAccount, Campaign, JobRun
from app.api.repository import ReadOnlyAdsRepository
from app.optimizer.analytics import MetricWindow, inclusive_window_days
from app.optimizer.recommendations import Finding, generate_findings
from sqlalchemy import Select, and_, func, select
from sqlalchemy.orm import Session

_PAGE_SIZE = 200


@dataclass(frozen=True)
class PerformanceScopeSnapshot:
    workspace_id: int
    platform: AdvertisingPlatform
    account_id: int
    account_name: str
    campaign_id: int
    campaign_name: str
    entity_type: MetricEntityType
    entity_id: int
    entity_name: str
    status: str | None
    current: MetricWindow
    comparison: MetricWindow
    findings: tuple[Finding, ...]


@dataclass(frozen=True)
class GranularFindingCounts:
    findings_count: int
    high_severity_findings_count: int
    campaign_findings_count: int
    ad_group_findings_count: int


@dataclass(frozen=True)
class _Scope:
    workspace_id: int
    platform: AdvertisingPlatform
    account_id: int
    account_name: str
    campaign_id: int
    campaign_name: str
    entity_type: MetricEntityType
    entity_id: int
    entity_name: str
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


class GranularAnalysisService:
    """Analyze campaign and ad-group facts without external calls or mutations."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.repository = ReadOnlyAdsRepository(session)

    def analyze_campaigns(
        self,
        account_id: int,
        date_from: date,
        date_to: date,
        *,
        limit: int,
        offset: int,
        now: datetime | None = None,
    ) -> tuple[list[PerformanceScopeSnapshot], int]:
        account = self.repository.get_account(account_id)
        if account is None:
            return [], 0
        campaigns, total = self.repository.list_account_campaigns(
            account_id,
            None,
            limit,
            offset,
        )
        scopes = [
            _Scope(
                workspace_id=account.workspace_id,
                platform=campaign.platform,
                account_id=account.id,
                account_name=account.name,
                campaign_id=campaign.id,
                campaign_name=campaign.name,
                entity_type=MetricEntityType.CAMPAIGN,
                entity_id=campaign.id,
                entity_name=campaign.name,
                status=campaign.status,
            )
            for campaign in campaigns
        ]
        return self._analyze_scopes(scopes, date_from, date_to, now=now), total

    def analyze_campaign(
        self,
        campaign_id: int,
        date_from: date,
        date_to: date,
        *,
        now: datetime | None = None,
    ) -> PerformanceScopeSnapshot | None:
        campaign = self.repository.get_campaign(campaign_id)
        if campaign is None:
            return None
        scope = _Scope(
            workspace_id=campaign.account.workspace_id,
            platform=campaign.platform,
            account_id=campaign.account_id,
            account_name=campaign.account.name,
            campaign_id=campaign.id,
            campaign_name=campaign.name,
            entity_type=MetricEntityType.CAMPAIGN,
            entity_id=campaign.id,
            entity_name=campaign.name,
            status=campaign.status,
        )
        return self._analyze_scopes([scope], date_from, date_to, now=now)[0]

    def analyze_ad_groups(
        self,
        campaign_id: int,
        date_from: date,
        date_to: date,
        *,
        limit: int,
        offset: int,
        now: datetime | None = None,
    ) -> tuple[list[PerformanceScopeSnapshot], int]:
        campaign = self.repository.get_campaign(campaign_id)
        if campaign is None:
            return [], 0
        groups, total = self.repository.list_campaign_ad_groups(campaign_id, limit, offset)
        scopes = [
            _Scope(
                workspace_id=campaign.account.workspace_id,
                platform=group.platform,
                account_id=campaign.account_id,
                account_name=campaign.account.name,
                campaign_id=campaign.id,
                campaign_name=campaign.name,
                entity_type=MetricEntityType.AD_GROUP,
                entity_id=group.id,
                entity_name=group.name,
                status=group.status,
            )
            for group in groups
        ]
        return self._analyze_scopes(scopes, date_from, date_to, now=now), total

    def count_workspace_findings(
        self,
        workspace_id: int,
        date_from: date,
        date_to: date,
        *,
        account_id: int | None = None,
        now: datetime | None = None,
    ) -> GranularFindingCounts:
        total_count = 0
        high_count = 0
        campaign_count = 0
        ad_group_count = 0
        for entity_type in (MetricEntityType.CAMPAIGN, MetricEntityType.AD_GROUP):
            offset = 0
            while True:
                scopes = self._workspace_scope_page(
                    workspace_id,
                    entity_type,
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
                if entity_type is MetricEntityType.CAMPAIGN:
                    campaign_count += scoped_count
                else:
                    ad_group_count += scoped_count
                if len(scopes) < _PAGE_SIZE:
                    break
                offset += _PAGE_SIZE
        return GranularFindingCounts(
            findings_count=total_count,
            high_severity_findings_count=high_count,
            campaign_findings_count=campaign_count,
            ad_group_findings_count=ad_group_count,
        )

    def _analyze_scopes(
        self,
        scopes: list[_Scope],
        date_from: date,
        date_to: date,
        *,
        now: datetime | None,
    ) -> list[PerformanceScopeSnapshot]:
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
        rows: list[PerformanceScopeSnapshot] = []
        for scope in scopes:
            current = _window(date_from, date_to, current_totals.get(scope.entity_id))
            comparison = _window(
                comparison_from,
                comparison_to,
                comparison_totals.get(scope.entity_id),
            )
            findings = tuple(
                generate_findings(
                    current,
                    comparison,
                    last_success_at=last_success.get(scope.account_id),
                    now=resolved_now,
                )
            )
            rows.append(
                PerformanceScopeSnapshot(
                    workspace_id=scope.workspace_id,
                    platform=scope.platform,
                    account_id=scope.account_id,
                    account_name=scope.account_name,
                    campaign_id=scope.campaign_id,
                    campaign_name=scope.campaign_name,
                    entity_type=scope.entity_type,
                    entity_id=scope.entity_id,
                    entity_name=scope.entity_name,
                    status=scope.status,
                    current=current,
                    comparison=comparison,
                    findings=findings,
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

    def _workspace_scope_page(
        self,
        workspace_id: int,
        entity_type: MetricEntityType,
        *,
        account_id: int | None,
        limit: int,
        offset: int,
    ) -> list[_Scope]:
        if entity_type is MetricEntityType.CAMPAIGN:
            statement: Select[Any] = (
                select(
                    AdvertisingAccount.workspace_id,
                    Campaign.platform,
                    AdvertisingAccount.id,
                    AdvertisingAccount.name,
                    Campaign.id,
                    Campaign.name,
                    Campaign.status,
                )
                .join(Campaign, Campaign.account_id == AdvertisingAccount.id)
                .where(AdvertisingAccount.workspace_id == workspace_id)
                .order_by(AdvertisingAccount.id.asc(), Campaign.id.asc())
            )
        else:
            statement = (
                select(
                    AdvertisingAccount.workspace_id,
                    AdGroup.platform,
                    AdvertisingAccount.id,
                    AdvertisingAccount.name,
                    Campaign.id,
                    Campaign.name,
                    AdGroup.id,
                    AdGroup.name,
                    AdGroup.status,
                )
                .join(Campaign, Campaign.account_id == AdvertisingAccount.id)
                .join(
                    AdGroup,
                    and_(
                        AdGroup.campaign_id == Campaign.id,
                        AdGroup.platform == Campaign.platform,
                    ),
                )
                .where(AdvertisingAccount.workspace_id == workspace_id)
                .order_by(AdvertisingAccount.id.asc(), Campaign.id.asc(), AdGroup.id.asc())
            )
        if account_id is not None:
            statement = statement.where(AdvertisingAccount.id == account_id)
        rows = self.session.execute(statement.limit(limit).offset(offset)).all()
        if entity_type is MetricEntityType.CAMPAIGN:
            return [
                _Scope(
                    workspace_id=int(row[0]),
                    platform=row[1],
                    account_id=int(row[2]),
                    account_name=str(row[3]),
                    campaign_id=int(row[4]),
                    campaign_name=str(row[5]),
                    entity_type=entity_type,
                    entity_id=int(row[4]),
                    entity_name=str(row[5]),
                    status=row[6],
                )
                for row in rows
            ]
        return [
            _Scope(
                workspace_id=int(row[0]),
                platform=row[1],
                account_id=int(row[2]),
                account_name=str(row[3]),
                campaign_id=int(row[4]),
                campaign_name=str(row[5]),
                entity_type=entity_type,
                entity_id=int(row[6]),
                entity_name=str(row[7]),
                status=row[8],
            )
            for row in rows
        ]
