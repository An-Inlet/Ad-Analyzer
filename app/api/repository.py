from collections.abc import Sequence
from datetime import date
from decimal import Decimal
from typing import Any, cast

from sqlalchemy import Select, and_, func, select
from sqlalchemy.orm import Session, joinedload

from app.ads.enums import AdvertisingPlatform, JobRunStatus, MetricEntityType
from app.ads.models import AdGroup, AdvertisingAccount, Campaign, DailyMetric, JobRun


class ReadOnlyAdsRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def _page(self, stmt: Select[Any], limit: int, offset: int) -> tuple[list[Any], int]:
        total = self.session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        items = list(self.session.scalars(stmt.limit(limit).offset(offset)).all())
        return items, total

    def list_accounts(
        self,
        platform: AdvertisingPlatform | None,
        limit: int,
        offset: int,
        workspace_id: int | None = None,
    ) -> tuple[list[AdvertisingAccount], int]:
        stmt = select(AdvertisingAccount)
        if workspace_id is not None:
            stmt = stmt.where(AdvertisingAccount.workspace_id == workspace_id)
        if platform is not None:
            stmt = stmt.where(AdvertisingAccount.platform == platform)
        return cast(
            tuple[list[AdvertisingAccount], int],
            self._page(stmt.order_by(AdvertisingAccount.id.asc()), limit, offset),
        )

    def get_account(self, account_id: int) -> AdvertisingAccount | None:
        return self.session.get(AdvertisingAccount, account_id)

    def dashboard_accounts(
        self,
        limit: int,
        offset: int,
    ) -> tuple[list[tuple[AdvertisingAccount, int, JobRun | None, Any]], int]:
        """Return overview rows in bounded queries, without loading campaigns per account."""
        page_accounts = (
            select(AdvertisingAccount.id.label("id"), AdvertisingAccount.platform.label("platform"))
            .order_by(AdvertisingAccount.id.asc())
            .limit(limit)
            .offset(offset)
            .subquery()
        )
        campaign_counts = (
            select(
                Campaign.account_id.label("account_id"),
                func.count(Campaign.id).label("campaign_count"),
            )
            .join(page_accounts, page_accounts.c.id == Campaign.account_id)
            .group_by(Campaign.account_id)
            .subquery()
        )
        latest_rank = func.row_number().over(
            partition_by=(JobRun.account_id, JobRun.platform),
            order_by=(JobRun.started_at.desc(), JobRun.id.desc()),
        )
        ranked = (
            select(
                JobRun.id.label("id"),
                JobRun.account_id.label("account_id"),
                JobRun.platform.label("platform"),
                latest_rank.label("rank"),
            )
            .join(
                page_accounts,
                and_(
                    page_accounts.c.id == JobRun.account_id,
                    page_accounts.c.platform == JobRun.platform,
                ),
            )
            .subquery()
        )
        latest = select(ranked).where(ranked.c.rank == 1).subquery()
        last_success = (
            select(JobRun.account_id.label("account_id"), func.max(JobRun.finished_at).label("at"))
            .join(
                page_accounts,
                and_(
                    page_accounts.c.id == JobRun.account_id,
                    page_accounts.c.platform == JobRun.platform,
                ),
            )
            .where(JobRun.status == JobRunStatus.SUCCEEDED)
            .group_by(JobRun.account_id)
            .subquery()
        )
        stmt = (
            select(
                AdvertisingAccount,
                func.coalesce(campaign_counts.c.campaign_count, 0),
                JobRun,
                last_success.c.at,
            )
            .join(page_accounts, page_accounts.c.id == AdvertisingAccount.id)
            .outerjoin(campaign_counts, campaign_counts.c.account_id == AdvertisingAccount.id)
            .outerjoin(
                latest,
                and_(
                    latest.c.account_id == AdvertisingAccount.id,
                    latest.c.platform == AdvertisingAccount.platform,
                ),
            )
            .outerjoin(JobRun, JobRun.id == latest.c.id)
            .outerjoin(last_success, last_success.c.account_id == AdvertisingAccount.id)
            .order_by(AdvertisingAccount.id.asc())
        )
        total = self.session.scalar(select(func.count()).select_from(AdvertisingAccount)) or 0
        return cast(
            list[tuple[AdvertisingAccount, int, JobRun | None, Any]],
            self.session.execute(stmt).all(),
        ), total

    def account_sync_status(self, account_id: int) -> tuple[JobRun | None, Any]:
        latest = self.latest_job_run(None, account_id)
        successful = self.session.scalar(
            select(func.max(JobRun.finished_at)).where(
                JobRun.account_id == account_id, JobRun.status == JobRunStatus.SUCCEEDED
            )
        )
        return latest, successful

    def list_account_campaigns(
        self, account_id: int, status: str | None, limit: int, offset: int
    ) -> tuple[list[Campaign], int]:
        stmt = select(Campaign).where(Campaign.account_id == account_id)
        if status is not None:
            stmt = stmt.where(Campaign.status == status)
        return cast(
            tuple[list[Campaign], int], self._page(stmt.order_by(Campaign.id.asc()), limit, offset)
        )

    def get_campaign(self, campaign_id: int) -> Campaign | None:
        stmt = (
            select(Campaign).options(joinedload(Campaign.account)).where(Campaign.id == campaign_id)
        )
        return self.session.scalars(stmt).first()

    def get_ad_group(self, ad_group_id: int) -> AdGroup | None:
        stmt = (
            select(AdGroup)
            .options(joinedload(AdGroup.campaign).joinedload(Campaign.account))
            .where(AdGroup.id == ad_group_id)
        )
        return self.session.scalars(stmt).first()

    def list_campaign_ad_groups(
        self, campaign_id: int, limit: int, offset: int
    ) -> tuple[list[AdGroup], int]:
        stmt = select(AdGroup).where(AdGroup.campaign_id == campaign_id).order_by(AdGroup.id.asc())
        return cast(tuple[list[AdGroup], int], self._page(stmt, limit, offset))

    def list_campaign_metrics(
        self, campaign_id: int, date_from: date, date_to: date, limit: int, offset: int
    ) -> tuple[list[DailyMetric], int]:
        stmt = (
            select(DailyMetric)
            .where(
                DailyMetric.campaign_id == campaign_id,
                DailyMetric.entity_type == "campaign",
                DailyMetric.entity_id == campaign_id,
                DailyMetric.metric_date >= date_from,
                DailyMetric.metric_date <= date_to,
            )
            .order_by(DailyMetric.metric_date.asc(), DailyMetric.id.asc())
        )
        return cast(tuple[list[DailyMetric], int], self._page(stmt, limit, offset))

    def account_metric_totals(
        self, account_id: int, date_from: date, date_to: date
    ) -> dict[str, Any]:
        stmt = (
            select(
                func.coalesce(func.sum(DailyMetric.impressions), 0),
                func.coalesce(func.sum(DailyMetric.clicks), 0),
                func.coalesce(func.sum(DailyMetric.cost_micros), 0),
                func.coalesce(func.sum(DailyMetric.conversions), Decimal("0")),
                func.coalesce(func.sum(DailyMetric.conversion_value_micros), 0),
                func.count(func.distinct(DailyMetric.metric_date)),
            )
            .join(
                Campaign,
                and_(
                    Campaign.id == DailyMetric.campaign_id,
                    Campaign.platform == DailyMetric.platform,
                ),
            )
            .where(
                Campaign.account_id == account_id,
                DailyMetric.entity_type == "campaign",
                DailyMetric.entity_id == Campaign.id,
                DailyMetric.metric_date >= date_from,
                DailyMetric.metric_date <= date_to,
            )
        )
        row = self.session.execute(stmt).one()
        return {
            "impressions": row[0],
            "clicks": row[1],
            "cost_micros": row[2],
            "conversions": row[3],
            "conversion_value_micros": row[4],
            "days_with_metrics": row[5],
        }

    def entity_metric_totals(
        self,
        entity_type: MetricEntityType,
        entity_ids: Sequence[int],
        date_from: date,
        date_to: date,
    ) -> dict[int, dict[str, Any]]:
        if not entity_ids:
            return {}
        rows = self.session.execute(
            select(
                DailyMetric.entity_id,
                func.coalesce(func.sum(DailyMetric.impressions), 0),
                func.coalesce(func.sum(DailyMetric.clicks), 0),
                func.coalesce(func.sum(DailyMetric.cost_micros), 0),
                func.coalesce(func.sum(DailyMetric.conversions), Decimal("0")),
                func.coalesce(func.sum(DailyMetric.conversion_value_micros), 0),
                func.count(func.distinct(DailyMetric.metric_date)),
            )
            .where(
                DailyMetric.entity_type == entity_type.value,
                DailyMetric.entity_id.in_(entity_ids),
                DailyMetric.metric_date >= date_from,
                DailyMetric.metric_date <= date_to,
            )
            .group_by(DailyMetric.entity_id)
        ).all()
        return {
            int(row[0]): {
                "impressions": row[1],
                "clicks": row[2],
                "cost_micros": row[3],
                "conversions": row[4],
                "conversion_value_micros": row[5],
                "days_with_metrics": row[6],
            }
            for row in rows
        }

    def list_job_runs(
        self,
        platform: AdvertisingPlatform | None,
        account_id: int | None,
        status: JobRunStatus | None,
        limit: int,
        offset: int,
        workspace_id: int | None = None,
    ) -> tuple[list[JobRun], int]:
        stmt = select(JobRun)
        if workspace_id is not None:
            stmt = stmt.where(JobRun.workspace_id == workspace_id)
        if platform is not None:
            stmt = stmt.where(JobRun.platform == platform)
        if account_id is not None:
            stmt = stmt.where(JobRun.account_id == account_id)
        if status is not None:
            stmt = stmt.where(JobRun.status == status)
        return cast(
            tuple[list[JobRun], int],
            self._page(stmt.order_by(JobRun.started_at.desc(), JobRun.id.desc()), limit, offset),
        )

    def latest_job_run(
        self, platform: AdvertisingPlatform | None, account_id: int | None
    ) -> JobRun | None:
        stmt = select(JobRun)
        if platform is not None:
            stmt = stmt.where(JobRun.platform == platform)
        if account_id is not None:
            stmt = stmt.where(JobRun.account_id == account_id)
        return self.session.scalars(
            stmt.order_by(JobRun.started_at.desc(), JobRun.id.desc()).limit(1)
        ).first()

    def sync_status(
        self, limit: int, offset: int, workspace_id: int | None = None
    ) -> tuple[list[tuple[AdvertisingAccount, JobRun | None, Any]], int]:
        latest_rank = func.row_number().over(
            partition_by=(JobRun.account_id, JobRun.platform),
            order_by=(JobRun.started_at.desc(), JobRun.id.desc()),
        )
        ranked_runs = (
            select(
                JobRun.account_id.label("account_id"),
                JobRun.platform.label("platform"),
                JobRun.id.label("job_run_id"),
                latest_rank.label("rank"),
            )
            .where(JobRun.account_id.is_not(None))
            .subquery()
        )
        latest_runs = (
            select(ranked_runs.c.account_id, ranked_runs.c.platform, ranked_runs.c.job_run_id)
            .where(ranked_runs.c.rank == 1)
            .subquery()
        )
        last_success = (
            select(
                JobRun.account_id.label("account_id"),
                JobRun.platform.label("platform"),
                func.max(JobRun.finished_at).label("last_success_at"),
            )
            .where(JobRun.account_id.is_not(None), JobRun.status == JobRunStatus.SUCCEEDED)
            .group_by(JobRun.account_id, JobRun.platform)
            .subquery()
        )
        stmt = (
            select(AdvertisingAccount, JobRun, last_success.c.last_success_at)
            .outerjoin(
                latest_runs,
                and_(
                    latest_runs.c.account_id == AdvertisingAccount.id,
                    latest_runs.c.platform == AdvertisingAccount.platform,
                ),
            )
            .outerjoin(JobRun, JobRun.id == latest_runs.c.job_run_id)
            .outerjoin(
                last_success,
                and_(
                    last_success.c.account_id == AdvertisingAccount.id,
                    last_success.c.platform == AdvertisingAccount.platform,
                ),
            )
            .order_by(AdvertisingAccount.id.asc())
        )
        if workspace_id is not None:
            stmt = stmt.where(AdvertisingAccount.workspace_id == workspace_id)
        total_stmt = select(func.count()).select_from(AdvertisingAccount)
        if workspace_id is not None:
            total_stmt = total_stmt.where(AdvertisingAccount.workspace_id == workspace_id)
        total = self.session.scalar(total_stmt) or 0
        rows = self.session.execute(stmt.limit(limit).offset(offset)).all()
        return cast(tuple[list[tuple[AdvertisingAccount, JobRun | None, Any]], int], (rows, total))
