import socket
from contextlib import suppress
from dataclasses import dataclass
from enum import StrEnum

from sqlalchemy import select
from sqlalchemy.exc import DBAPIError, OperationalError
from sqlalchemy.orm import Session

from app.ads.enums import AdvertisingPlatform, JobRunStatus
from app.ads.models import AdvertisingAccount, DailyMetric, JobRun
from app.ads.repository import AdvertisingMetricsRepository
from app.ads.schemas import AdvertisingAccountCreate, NormalizedMetricsBatch
from app.collectors import google_ads
from app.collectors.google_ads import (
    GoogleAdsAuthenticationError,
    GoogleAdsRateLimitError,
)

FAILED_JOB_RUN_PERSISTENCE_ERROR = (
    "Google Ads sync failed and the failure record could not be persisted"
)
FAILED_JOB_RUN_UNKNOWN_COMMIT_OUTCOME_ERROR = (
    "Google Ads sync failed; the failure-record commit outcome is unknown "
    "and must be verified before retrying"
)
UNKNOWN_COMMIT_OUTCOME_ERROR = (
    "Google Ads sync commit outcome is unknown; verify the latest job run before retrying"
)


class SyncFailureClassification(StrEnum):
    TRANSIENT_RATE_LIMIT = "TRANSIENT_RATE_LIMIT"
    TRANSIENT_NETWORK = "TRANSIENT_NETWORK"
    TRANSIENT_DATABASE = "TRANSIENT_DATABASE"
    PERMANENT_AUTH = "PERMANENT_AUTH"
    PERMANENT_CONFIGURATION = "PERMANENT_CONFIGURATION"
    PERMANENT_VALIDATION = "PERMANENT_VALIDATION"
    UNKNOWN_COMMIT_OUTCOME = "UNKNOWN_COMMIT_OUTCOME"
    UNKNOWN_PERMANENT = "UNKNOWN_PERMANENT"


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

    def __init__(
        self,
        message: str,
        *,
        classification: SyncFailureClassification = SyncFailureClassification.UNKNOWN_PERMANENT,
    ) -> None:
        super().__init__(message[:120])
        self.classification = classification


class GoogleAdsSyncService:
    """Persist read-only Google Ads collector data to the local database."""

    job_name = "google_ads_read_only_sync"

    def __init__(self, session: Session) -> None:
        self.session = session
        self.repository = AdvertisingMetricsRepository(session)
        self._last_records_processed = 0
        self._last_resolved_account: AdvertisingAccountCreate | None = None

    def sync(
        self,
        *,
        date_range: google_ads.GoogleAdsDateRange = google_ads.GoogleAdsDateRange.LAST_7_DAYS,
    ) -> GoogleAdsSyncResult:
        records_processed = 0
        resolved_account: AdvertisingAccountCreate | None = None
        sync_error_message: str | None = None
        failure_classification = SyncFailureClassification.UNKNOWN_PERMANENT
        success_commit_started = False
        try:
            job_run = self.repository.create_job_run(
                platform=AdvertisingPlatform.GOOGLE_ADS,
                job_name=self.job_name,
                status=JobRunStatus.RUNNING,
            )
            self.session.flush()
            result = self._collect_and_persist(job_run, date_range=date_range)
            success_commit_started = True
            self.session.commit()
            return result
        except Exception as exc:
            if success_commit_started:
                with suppress(Exception):
                    self.session.rollback()
                sync_error_message = UNKNOWN_COMMIT_OUTCOME_ERROR
                failure_classification = SyncFailureClassification.UNKNOWN_COMMIT_OUTCOME
            else:
                records_processed = self._last_records_processed
                resolved_account = self._last_resolved_account
                sanitized_error_message = self._sanitize_error(exc)
                failure_classification = self._classify_failure(exc)
                failed_job_run_commit_started = False
                try:
                    self.session.rollback()
                    failed_account_id = self._resolve_durable_failed_run_account_id(
                        resolved_account
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
                    self.session.flush()
                    failed_job_run_commit_started = True
                    self.session.commit()
                    sync_error_message = sanitized_error_message
                except Exception:
                    with suppress(Exception):
                        self.session.rollback()
                    sync_error_message = (
                        FAILED_JOB_RUN_UNKNOWN_COMMIT_OUTCOME_ERROR
                        if failed_job_run_commit_started
                        else FAILED_JOB_RUN_PERSISTENCE_ERROR
                    )
                    failure_classification = SyncFailureClassification.UNKNOWN_COMMIT_OUTCOME
        if sync_error_message is not None:
            raise GoogleAdsSyncError(
                sync_error_message, classification=failure_classification
            ) from None
        raise GoogleAdsSyncError(FAILED_JOB_RUN_PERSISTENCE_ERROR) from None

    def sync_authoritative_job_run(
        self,
        job_run: JobRun,
        *,
        date_range: google_ads.GoogleAdsDateRange = google_ads.GoogleAdsDateRange.LAST_7_DAYS,
    ) -> GoogleAdsSyncResult:
        try:
            result = self._collect_and_persist(job_run, date_range=date_range)
            self.session.commit()
            return result
        except GoogleAdsSyncError:
            raise
        except Exception as exc:
            with suppress(Exception):
                self.session.rollback()
            raise GoogleAdsSyncError(
                self._sanitize_error(exc), classification=self._classify_failure(exc)
            ) from None

    def _collect_and_persist(
        self,
        job_run: JobRun,
        *,
        date_range: google_ads.GoogleAdsDateRange,
    ) -> GoogleAdsSyncResult:
        records_processed = 0
        self._last_records_processed = records_processed
        resolved_account = google_ads.collect_account()
        self._last_resolved_account = resolved_account
        account = self.repository.upsert_account(resolved_account)
        job_run.account_id = account.id
        records_processed += 1
        self._last_records_processed = records_processed

        campaigns = [
            self.repository.upsert_campaign(campaign)
            for campaign in google_ads.collect_campaigns(account.id)
        ]
        records_processed += len(campaigns)
        self._last_records_processed = records_processed
        campaign_ids_by_external_id = {
            campaign.external_campaign_id: campaign.id for campaign in campaigns
        }

        ad_groups = [
            self.repository.upsert_ad_group(ad_group)
            for ad_group in google_ads.collect_ad_groups(campaign_ids_by_external_id)
        ]
        records_processed += len(ad_groups)
        self._last_records_processed = records_processed
        ad_group_ids_by_external_id = {
            ad_group.external_ad_group_id: ad_group.id for ad_group in ad_groups
        }

        ads = [
            self.repository.upsert_ad(ad)
            for ad in google_ads.collect_ads(ad_group_ids_by_external_id)
        ]
        records_processed += len(ads)
        self._last_records_processed = records_processed

        keywords = [
            self.repository.upsert_keyword(keyword)
            for keyword in google_ads.collect_keywords(ad_group_ids_by_external_id)
        ]
        records_processed += len(keywords)
        self._last_records_processed = records_processed

        search_terms = [
            self.repository.upsert_search_term(search_term)
            for search_term in google_ads.collect_search_terms(
                ad_group_ids_by_external_id,
                date_range,
            )
        ]
        records_processed += len(search_terms)
        self._last_records_processed = records_processed

        if campaign_ids_by_external_id:
            metrics = google_ads.collect_metrics(campaign_ids_by_external_id, date_range).metrics
        else:
            metrics = []
        daily_metrics = [self.repository.upsert_daily_metric(metric) for metric in metrics]
        records_processed += len(daily_metrics)
        self._last_records_processed = records_processed

        self.repository.finish_job_run(
            job_run,
            status=JobRunStatus.SUCCEEDED,
            records_processed=records_processed,
        )
        self.session.flush()
        return GoogleAdsSyncResult(
            job_run_id=job_run.id,
            records_processed=records_processed,
            status=JobRunStatus.SUCCEEDED,
        )

    def _sanitize_error(self, exc: BaseException) -> str:
        return f"Google Ads read-only sync failed ({type(exc).__name__})"[:120]

    def _classify_failure(self, exc: BaseException) -> SyncFailureClassification:
        if isinstance(exc, GoogleAdsRateLimitError):
            return SyncFailureClassification.TRANSIENT_RATE_LIMIT
        if isinstance(exc, (TimeoutError, ConnectionError, socket.gaierror)):
            return SyncFailureClassification.TRANSIENT_NETWORK
        if isinstance(exc, DBAPIError) and exc.connection_invalidated:
            return SyncFailureClassification.TRANSIENT_DATABASE
        if isinstance(exc, OperationalError):
            code = getattr(getattr(exc, "orig", None), "pgcode", None) or getattr(
                getattr(exc, "orig", None), "sqlstate", None
            )
            if code in {"40001", "40P01", "57014", "08000", "08003", "08006"}:
                return SyncFailureClassification.TRANSIENT_DATABASE
        if isinstance(exc, GoogleAdsAuthenticationError):
            return SyncFailureClassification.PERMANENT_AUTH
        if isinstance(exc, (ValueError, TypeError)):
            return SyncFailureClassification.PERMANENT_VALIDATION
        return SyncFailureClassification.UNKNOWN_PERMANENT

    def _resolve_durable_failed_run_account_id(
        self,
        account: AdvertisingAccountCreate | None,
    ) -> int | None:
        if account is None:
            return None
        return self.session.scalar(
            select(AdvertisingAccount.id).where(
                AdvertisingAccount.platform == account.platform,
                AdvertisingAccount.external_account_id == account.external_account_id,
            )
        )
