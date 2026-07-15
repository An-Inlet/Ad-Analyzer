from contextlib import suppress
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.ads.enums import AdvertisingPlatform, JobRunStatus
from app.ads.models import DailyMetric
from app.ads.repository import AdvertisingMetricsRepository
from app.ads.schemas import AdvertisingAccountCreate, NormalizedMetricsBatch
from app.collectors import google_ads

FAILED_JOB_RUN_PERSISTENCE_ERROR = (
    "Google Ads sync failed and the failure record could not be persisted"
)


class NormalizedMetricsService:
    """Stores normalized advertising metrics without contacting ad platforms."""

    def __init__(self, session: Session) -> None:
        self.repository = AdvertisingMetricsRepository(session)

    def store_batch(self, batch: NormalizedMetricsBatch) -> list[DailyMetric]:
        return self.repository.add_daily_metrics(batch.metrics)


@dataclass(frozen=True)
class GoogleAdsSyncResult:
    job_run_id: int
    records_processed: int
    status: JobRunStatus


class GoogleAdsSyncError(RuntimeError):
    """Raised when a Google Ads sync fails after sanitizing diagnostics."""


class GoogleAdsSyncService:
    """Persist read-only Google Ads collector data to the local database."""

    job_name = "google_ads_read_only_sync"

    def __init__(self, session: Session) -> None:
        self.session = session
        self.repository = AdvertisingMetricsRepository(session)

    def sync(
        self,
        *,
        date_range: google_ads.GoogleAdsDateRange = google_ads.GoogleAdsDateRange.LAST_7_DAYS,
    ) -> GoogleAdsSyncResult:
        records_processed = 0
        resolved_account: AdvertisingAccountCreate | None = None
        resolved_account_id: int | None = None
        sync_error_message: str | None = None
        try:
            job_run = self.repository.create_job_run(
                platform=AdvertisingPlatform.GOOGLE_ADS,
                job_name=self.job_name,
                status=JobRunStatus.RUNNING,
            )
            self.session.flush()
            resolved_account = google_ads.collect_account()
            account = self.repository.upsert_account(resolved_account)
            job_run.account_id = account.id
            resolved_account_id = account.id
            records_processed += 1

            campaigns = [
                self.repository.upsert_campaign(campaign)
                for campaign in google_ads.collect_campaigns(account.id)
            ]
            records_processed += len(campaigns)
            campaign_ids_by_external_id = {
                campaign.external_campaign_id: campaign.id for campaign in campaigns
            }

            ad_groups = [
                self.repository.upsert_ad_group(ad_group)
                for ad_group in google_ads.collect_ad_groups(campaign_ids_by_external_id)
            ]
            records_processed += len(ad_groups)
            ad_group_ids_by_external_id = {
                ad_group.external_ad_group_id: ad_group.id for ad_group in ad_groups
            }

            ads = [
                self.repository.upsert_ad(ad)
                for ad in google_ads.collect_ads(ad_group_ids_by_external_id)
            ]
            records_processed += len(ads)

            keywords = [
                self.repository.upsert_keyword(keyword)
                for keyword in google_ads.collect_keywords(ad_group_ids_by_external_id)
            ]
            records_processed += len(keywords)

            search_terms = [
                self.repository.upsert_search_term(search_term)
                for search_term in google_ads.collect_search_terms(
                    ad_group_ids_by_external_id,
                    date_range,
                )
            ]
            records_processed += len(search_terms)

            if campaign_ids_by_external_id:
                metrics = google_ads.collect_metrics(
                    campaign_ids_by_external_id, date_range
                ).metrics
            else:
                metrics = []
            daily_metrics = [self.repository.upsert_daily_metric(metric) for metric in metrics]
            records_processed += len(daily_metrics)

            self.repository.finish_job_run(
                job_run,
                status=JobRunStatus.SUCCEEDED,
                records_processed=records_processed,
            )
            self.session.flush()
            job_run_id = job_run.id
            result = GoogleAdsSyncResult(
                job_run_id=job_run_id,
                records_processed=records_processed,
                status=JobRunStatus.SUCCEEDED,
            )
            self.session.commit()
            return result
        except Exception as exc:
            sanitized_error_message = self._sanitize_error(exc)
            try:
                self.session.rollback()
                failed_account_id = self._restore_failed_run_account_id(
                    resolved_account,
                    resolved_account_id,
                )
                failed_job_run = self.repository.create_job_run(
                    platform=AdvertisingPlatform.GOOGLE_ADS,
                    job_name=self.job_name,
                    status=JobRunStatus.FAILED,
                    account_id=failed_account_id,
                )
                self.repository.finish_job_run(
                    failed_job_run,
                    status=JobRunStatus.FAILED,
                    records_processed=records_processed,
                    error_message=sanitized_error_message,
                )
                self.session.commit()
                sync_error_message = sanitized_error_message
            except Exception:
                with suppress(Exception):
                    self.session.rollback()
                sync_error_message = FAILED_JOB_RUN_PERSISTENCE_ERROR
        if sync_error_message is not None:
            raise GoogleAdsSyncError(sync_error_message) from None
        raise GoogleAdsSyncError(FAILED_JOB_RUN_PERSISTENCE_ERROR) from None

    def _sanitize_error(self, exc: Exception) -> str:
        return f"Google Ads read-only sync failed ({type(exc).__name__})"[:120]

    def _restore_failed_run_account_id(
        self,
        account: AdvertisingAccountCreate | None,
        original_account_id: int | None,
    ) -> int | None:
        if account is None or original_account_id is None:
            return None
        restored_account = self.repository.upsert_account(account)
        self.session.flush()
        return restored_account.id
