from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any, TypeVar, cast

from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
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
    utc_now,
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
        return self._atomic_upsert(
            AdvertisingAccount,
            account.model_dump(),
            ("platform", "external_account_id"),
        )

    def upsert_campaign(self, campaign: CampaignCreate) -> Campaign:
        return self._atomic_upsert(
            Campaign,
            campaign.model_dump(),
            ("account_id", "platform", "external_campaign_id"),
        )

    def upsert_ad_group(self, ad_group: AdGroupCreate) -> AdGroup:
        return self._atomic_upsert(
            AdGroup,
            ad_group.model_dump(),
            ("campaign_id", "platform", "external_ad_group_id"),
        )

    def upsert_ad(self, ad: AdCreate) -> Ad:
        conflict_columns = (
            ("ad_group_id", "platform", "external_ad_id")
            if ad.ad_group_id is not None
            else ("ad_set_id", "platform", "external_ad_id")
        )
        return self._atomic_upsert(Ad, ad.model_dump(), conflict_columns)

    def upsert_keyword(self, keyword: KeywordCreate) -> Keyword:
        return self._atomic_upsert(
            Keyword,
            keyword.model_dump(),
            ("ad_group_id", "platform", "external_keyword_id"),
        )

    def upsert_search_term(self, search_term: SearchTermCreate) -> SearchTerm:
        return self._atomic_upsert(
            SearchTerm,
            search_term.model_dump(),
            ("ad_group_id", "platform", "term"),
        )

    def upsert_daily_metric(self, metric: DailyMetricCreate) -> DailyMetric:
        return self._atomic_upsert(
            DailyMetric,
            metric.model_dump(),
            ("platform", "metric_date", "entity_type", "entity_id"),
        )

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

    def _atomic_upsert(
        self,
        model: type[ModelT],
        values: dict[str, Any],
        conflict_columns: Sequence[str],
    ) -> ModelT:
        dialect_name = self.session.get_bind().dialect.name
        insert_statement: Any
        if dialect_name == "postgresql":
            insert_statement = postgresql_insert(model).values(**values)
        elif dialect_name == "sqlite":
            insert_statement = sqlite_insert(model).values(**values)
        else:
            raise RuntimeError(f"Atomic upsert is not supported for {dialect_name}")

        update_values = {
            key: getattr(insert_statement.excluded, key)
            for key in values
            if key not in {"id", "created_at"}
        }
        table = cast(Any, model).__table__
        if "updated_at" in table.c:
            update_values["updated_at"] = utc_now()

        statement = (
            insert_statement.on_conflict_do_update(
                index_elements=list(conflict_columns),
                set_=update_values,
            )
            .returning(model)
            .execution_options(populate_existing=True)
        )
        return cast(ModelT, self.session.scalars(statement).one())
