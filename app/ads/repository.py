from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any, TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ads.enums import AdvertisingPlatform, JobRunStatus
from app.ads.models import (
    Ad,
    AdGroup,
    AdvertisingAccount,
    Campaign,
    DailyMetric,
    JobRun,
    Keyword,
    SearchTerm,
)
from app.ads.schemas import (
    AdCreate,
    AdGroupCreate,
    AdvertisingAccountCreate,
    CampaignCreate,
    DailyMetricCreate,
    KeywordCreate,
    SearchTermCreate,
)

ModelT = TypeVar("ModelT")


class AdvertisingMetricsRepository:
    """Repository for local, normalized, read-only advertising data storage."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def add_daily_metric(self, metric: DailyMetricCreate) -> DailyMetric:
        db_metric = DailyMetric(**metric.model_dump())
        self.session.add(db_metric)
        return db_metric

    def add_daily_metrics(self, metrics: Sequence[DailyMetricCreate]) -> list[DailyMetric]:
        return [self.add_daily_metric(metric) for metric in metrics]

    def upsert_account(self, account: AdvertisingAccountCreate) -> AdvertisingAccount:
        db_account = self.session.scalar(
            select(AdvertisingAccount).where(
                AdvertisingAccount.platform == account.platform,
                AdvertisingAccount.external_account_id == account.external_account_id,
            )
        )
        return self._upsert(db_account, AdvertisingAccount, account.model_dump())

    def upsert_campaign(self, campaign: CampaignCreate) -> Campaign:
        db_campaign = self.session.scalar(
            select(Campaign).where(
                Campaign.account_id == campaign.account_id,
                Campaign.platform == campaign.platform,
                Campaign.external_campaign_id == campaign.external_campaign_id,
            )
        )
        return self._upsert(db_campaign, Campaign, campaign.model_dump())

    def upsert_ad_group(self, ad_group: AdGroupCreate) -> AdGroup:
        db_ad_group = self.session.scalar(
            select(AdGroup).where(
                AdGroup.campaign_id == ad_group.campaign_id,
                AdGroup.platform == ad_group.platform,
                AdGroup.external_ad_group_id == ad_group.external_ad_group_id,
            )
        )
        return self._upsert(db_ad_group, AdGroup, ad_group.model_dump())

    def upsert_ad(self, ad: AdCreate) -> Ad:
        db_ad = self.session.scalar(
            select(Ad).where(
                Ad.platform == ad.platform,
                Ad.external_ad_id == ad.external_ad_id,
            )
        )
        return self._upsert(db_ad, Ad, ad.model_dump())

    def upsert_keyword(self, keyword: KeywordCreate) -> Keyword:
        db_keyword = self.session.scalar(
            select(Keyword).where(
                Keyword.ad_group_id == keyword.ad_group_id,
                Keyword.platform == keyword.platform,
                Keyword.external_keyword_id == keyword.external_keyword_id,
            )
        )
        return self._upsert(db_keyword, Keyword, keyword.model_dump())

    def upsert_search_term(self, search_term: SearchTermCreate) -> SearchTerm:
        db_search_term = self.session.scalar(
            select(SearchTerm).where(
                SearchTerm.ad_group_id == search_term.ad_group_id,
                SearchTerm.platform == search_term.platform,
                SearchTerm.term == search_term.term,
            )
        )
        return self._upsert(db_search_term, SearchTerm, search_term.model_dump())

    def upsert_daily_metric(self, metric: DailyMetricCreate) -> DailyMetric:
        db_metric = self.session.scalar(
            select(DailyMetric).where(
                DailyMetric.platform == metric.platform,
                DailyMetric.metric_date == metric.metric_date,
                DailyMetric.entity_type == metric.entity_type,
                DailyMetric.entity_id == metric.entity_id,
            )
        )
        return self._upsert(db_metric, DailyMetric, metric.model_dump())

    def create_job_run(
        self,
        *,
        platform: AdvertisingPlatform,
        job_name: str,
        status: JobRunStatus,
        account_id: int | None = None,
    ) -> JobRun:
        job_run = JobRun(
            platform=platform,
            account_id=account_id,
            job_name=job_name,
            status=status,
            started_at=datetime.now(UTC),
        )
        self.session.add(job_run)
        return job_run

    def finish_job_run(
        self,
        job_run: JobRun,
        *,
        status: JobRunStatus,
        records_processed: int,
        error_message: str | None = None,
    ) -> JobRun:
        job_run.status = status
        job_run.finished_at = datetime.now(UTC)
        job_run.records_processed = records_processed
        job_run.error_message = error_message
        return job_run

    def _upsert(
        self,
        instance: ModelT | None,
        model: type[ModelT],
        values: dict[str, Any],
    ) -> ModelT:
        if instance is None:
            instance = model(**values)
            self.session.add(instance)
        else:
            for key, value in values.items():
                setattr(instance, key, value)
        self.session.flush()
        return instance
