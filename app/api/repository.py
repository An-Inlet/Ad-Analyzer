from datetime import date
from decimal import Decimal
from typing import Any, cast

from sqlalchemy import Select, and_, func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.ads.enums import AdvertisingPlatform, JobRunStatus
from app.ads.models import AdGroup, AdvertisingAccount, Campaign, DailyMetric, JobRun


class ReadOnlyAdsRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def _page(self, stmt: Select[Any], limit: int, offset: int) -> tuple[list[Any], int]:
        total = self.session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        items = list(self.session.scalars(stmt.limit(limit).offset(offset)).all())
        return items, total

    def list_accounts(
        self, platform: AdvertisingPlatform | None, limit: int, offset: int
    ) -> tuple[list[AdvertisingAccount], int]:
        stmt = select(AdvertisingAccount)
        if platform is not None:
            stmt = stmt.where(AdvertisingAccount.platform == platform)
        return cast(
            tuple[list[AdvertisingAccount], int],
            self._page(stmt.order_by(AdvertisingAccount.id.asc()), limit, offset),
        )

    def get_account(self, account_id: int) -> AdvertisingAccount | None:
        return self.session.get(AdvertisingAccount, account_id)

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

    def list_campaign_ad_groups(
        self, campaign_id: int, limit: int, offset: int
    ) -> tuple[list[AdGroup], int]:
        stmt = select(AdGroup).where(AdGroup.campaign_id == campaign_id).order_by(AdGroup.id.asc())
        return cast(tuple[list[AdGroup], int], self._page(stmt, limit, offset))

    def list_campaign_metrics(
        self, campaign_id: int, date_from: date, date_to: date
    ) -> list[DailyMetric]:
        stmt = (
            select(DailyMetric)
            .where(
                DailyMetric.campaign_id == campaign_id,
                DailyMetric.metric_date >= date_from,
                DailyMetric.metric_date <= date_to,
            )
            .order_by(DailyMetric.metric_date.asc(), DailyMetric.id.asc())
        )
        return list(self.session.scalars(stmt).all())

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
        }

    def list_job_runs(
        self,
        platform: AdvertisingPlatform | None,
        account_id: int | None,
        status: JobRunStatus | None,
        limit: int,
        offset: int,
    ) -> tuple[list[JobRun], int]:
        stmt = select(JobRun)
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

    def sync_status(self) -> list[tuple[AdvertisingAccount, JobRun | None, Any]]:
        latest_id = (
            select(func.max(JobRun.id))
            .where(
                or_(
                    JobRun.account_id == AdvertisingAccount.id,
                    and_(
                        JobRun.account_id.is_(None), JobRun.platform == AdvertisingAccount.platform
                    ),
                )
            )
            .correlate(AdvertisingAccount)
            .scalar_subquery()
        )
        success_at = (
            select(func.max(JobRun.finished_at))
            .where(
                JobRun.account_id == AdvertisingAccount.id, JobRun.status == JobRunStatus.SUCCEEDED
            )
            .correlate(AdvertisingAccount)
            .scalar_subquery()
        )
        stmt = (
            select(AdvertisingAccount, JobRun, success_at)
            .outerjoin(JobRun, JobRun.id == latest_id)
            .order_by(AdvertisingAccount.id.asc())
        )
        return cast(
            list[tuple[AdvertisingAccount, JobRun | None, Any]], self.session.execute(stmt).all()
        )
