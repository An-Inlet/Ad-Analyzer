import socket
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from enum import StrEnum
from weakref import WeakKeyDictionary

from sqlalchemy import select
from sqlalchemy.exc import DBAPIError, OperationalError
from sqlalchemy.orm import Session

from app.ads.enums import JobRunStatus
from app.ads.models import AdvertisingAccount, DailyMetric, JobRun
from app.ads.repository import AdvertisingMetricsRepository
from app.ads.schemas import AdvertisingAccountCreate, NormalizedMetricsBatch
from app.collectors import google_ads
from app.collectors.google_ads import (
    GoogleAdsAuthenticationError,
    GoogleAdsIntegrationError,
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
        lock_lost: bool = False,
    ) -> None:
        super().__init__(message[:120])
        self.classification = classification
        self.lock_lost = lock_lost


_WORKER_REQUIRED_ERROR = "Google Ads synchronization must be run through the Phase 7 worker."
_CAPABILITY_INTERRUPTED_ERROR = "Google Ads synchronization interrupted before retry."
_CAPABILITY_LOCK_LOST_ERROR = "Google Ads synchronization lost advisory-lock ownership."


@dataclass
class _Phase7SyncCapabilityState:
    lock: object
    connection: object
    session: Session
    lock_key: int
    backend_pid: int | None
    stop_requested: Callable[[], bool]
    valid: bool = True


class Phase7SyncCapability:
    """Opaque worker-owned capability tying collector access to one locked cycle."""

    __slots__ = ("__weakref__",)

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        raise RuntimeError(_WORKER_REQUIRED_ERROR)

    def invalidate(self) -> None:
        state = _CAPABILITY_STATES.get(self)
        if state is not None:
            state.valid = False

    def validate(self, session: Session) -> None:
        state = _CAPABILITY_STATES.get(self)
        if state is None or not state.valid:
            raise GoogleAdsSyncError(
                _WORKER_REQUIRED_ERROR,
                classification=SyncFailureClassification.PERMANENT_CONFIGURATION,
            )
        if session is not state.session:
            raise GoogleAdsSyncError(
                _WORKER_REQUIRED_ERROR,
                classification=SyncFailureClassification.PERMANENT_CONFIGURATION,
            )
        if state.stop_requested():
            self.invalidate()
            raise GoogleAdsSyncError(
                _CAPABILITY_INTERRUPTED_ERROR,
                classification=SyncFailureClassification.PERMANENT_CONFIGURATION,
            )
        if getattr(state.connection, "invalidated", False):
            self.invalidate()
            raise GoogleAdsSyncError(
                _CAPABILITY_LOCK_LOST_ERROR,
                classification=SyncFailureClassification.TRANSIENT_DATABASE,
                lock_lost=True,
            )
        lock = state.lock
        if getattr(lock, "key", None) != state.lock_key:
            raise GoogleAdsSyncError(
                _WORKER_REQUIRED_ERROR,
                classification=SyncFailureClassification.PERMANENT_CONFIGURATION,
            )
        if getattr(lock, "backend_pid", None) != state.backend_pid:
            self.invalidate()
            raise GoogleAdsSyncError(
                _CAPABILITY_LOCK_LOST_ERROR,
                classification=SyncFailureClassification.TRANSIENT_DATABASE,
                lock_lost=True,
            )
        owns_current_session = getattr(lock, "owns_current_session", None)
        if not callable(owns_current_session) or not bool(owns_current_session(session)):
            self.invalidate()
            raise GoogleAdsSyncError(
                _CAPABILITY_LOCK_LOST_ERROR,
                classification=SyncFailureClassification.TRANSIENT_DATABASE,
                lock_lost=True,
            )


_CAPABILITY_STATES: WeakKeyDictionary[
    Phase7SyncCapability, _Phase7SyncCapabilityState
] = WeakKeyDictionary()


def _new_phase7_sync_capability(
    *,
    lock: object,
    connection: object,
    session: Session,
    lock_key: int,
    backend_pid: int | None,
    stop_requested: Callable[[], bool],
) -> Phase7SyncCapability:
    capability = object.__new__(Phase7SyncCapability)
    _CAPABILITY_STATES[capability] = _Phase7SyncCapabilityState(
        lock=lock,
        connection=connection,
        session=session,
        lock_key=lock_key,
        backend_pid=backend_pid,
        stop_requested=stop_requested,
    )
    return capability


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
        _ = date_range
        raise GoogleAdsSyncError(
            _WORKER_REQUIRED_ERROR,
            classification=SyncFailureClassification.PERMANENT_CONFIGURATION,
        )

    def sync_authoritative_job_run(
        self,
        job_run: JobRun,
        *,
        date_range: google_ads.GoogleAdsDateRange = google_ads.GoogleAdsDateRange.LAST_7_DAYS,
        capability: Phase7SyncCapability,
    ) -> GoogleAdsSyncResult:
        success_commit_started = False
        try:
            result = self._collect_and_persist(
                job_run, date_range=date_range, capability=capability
            )
            capability.validate(self.session)
            success_commit_started = True
            self.session.commit()
            return result
        except GoogleAdsSyncError:
            raise
        except Exception as exc:
            if type(exc).__name__ in {"SyncShutdownRequested", "AdvisoryLockLostError"}:
                raise
            with suppress(Exception):
                self.session.rollback()
            if success_commit_started:
                raise GoogleAdsSyncError(
                    UNKNOWN_COMMIT_OUTCOME_ERROR,
                    classification=SyncFailureClassification.UNKNOWN_COMMIT_OUTCOME,
                    lock_lost=self._is_lock_lost_failure(exc),
                ) from None
            classification = self._classify_failure(exc)
            raise GoogleAdsSyncError(
                self._sanitize_error(exc),
                classification=classification,
                lock_lost=self._is_lock_lost_failure(exc),
            ) from None

    def _check_before_collector(self, capability: Phase7SyncCapability) -> None:
        if not isinstance(capability, Phase7SyncCapability):
            raise GoogleAdsSyncError(
                _WORKER_REQUIRED_ERROR,
                classification=SyncFailureClassification.PERMANENT_CONFIGURATION,
            )
        capability.validate(self.session)

    def _collect_and_persist(
        self,
        job_run: JobRun,
        *,
        date_range: google_ads.GoogleAdsDateRange,
        capability: Phase7SyncCapability,
    ) -> GoogleAdsSyncResult:
        records_processed = 0
        self._last_records_processed = records_processed
        self._check_before_collector(capability)
        resolved_account = google_ads.collect_account()
        self._last_resolved_account = resolved_account
        account = self.repository.upsert_account(resolved_account)
        job_run.account_id = account.id
        records_processed += 1
        self._last_records_processed = records_processed

        self._check_before_collector(capability)
        campaigns = [
            self.repository.upsert_campaign(campaign)
            for campaign in google_ads.collect_campaigns(account.id)
        ]
        records_processed += len(campaigns)
        self._last_records_processed = records_processed
        campaign_ids_by_external_id = {
            campaign.external_campaign_id: campaign.id for campaign in campaigns
        }

        self._check_before_collector(capability)
        ad_groups = [
            self.repository.upsert_ad_group(ad_group)
            for ad_group in google_ads.collect_ad_groups(campaign_ids_by_external_id)
        ]
        records_processed += len(ad_groups)
        self._last_records_processed = records_processed
        ad_group_ids_by_external_id = {
            ad_group.external_ad_group_id: ad_group.id for ad_group in ad_groups
        }

        self._check_before_collector(capability)
        ads = [
            self.repository.upsert_ad(ad)
            for ad in google_ads.collect_ads(ad_group_ids_by_external_id)
        ]
        records_processed += len(ads)
        self._last_records_processed = records_processed

        self._check_before_collector(capability)
        keywords = [
            self.repository.upsert_keyword(keyword)
            for keyword in google_ads.collect_keywords(ad_group_ids_by_external_id)
        ]
        records_processed += len(keywords)
        self._last_records_processed = records_processed

        self._check_before_collector(capability)
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
            self._check_before_collector(capability)
            metrics = google_ads.collect_metrics(campaign_ids_by_external_id, date_range).metrics
        else:
            metrics = []
        self._check_before_collector(capability)
        daily_metrics = [self.repository.upsert_daily_metric(metric) for metric in metrics]
        records_processed += len(daily_metrics)
        self._last_records_processed = records_processed

        self._check_before_collector(capability)
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
        collector_classification = getattr(exc, "retry_classification", None)
        if isinstance(collector_classification, str):
            with suppress(ValueError):
                return SyncFailureClassification(collector_classification)
        if isinstance(exc, GoogleAdsRateLimitError):
            return SyncFailureClassification.TRANSIENT_RATE_LIMIT
        if isinstance(exc, GoogleAdsIntegrationError):
            return SyncFailureClassification.UNKNOWN_PERMANENT
        if isinstance(exc, (TimeoutError, ConnectionError, socket.gaierror)):
            return SyncFailureClassification.TRANSIENT_NETWORK
        if self._is_lock_lost_failure(exc):
            return SyncFailureClassification.TRANSIENT_DATABASE
        if isinstance(exc, OperationalError):
            code = getattr(getattr(exc, "orig", None), "pgcode", None) or getattr(
                getattr(exc, "orig", None), "sqlstate", None
            )
            if code in {"40001", "40P01", "57014"}:
                return SyncFailureClassification.TRANSIENT_DATABASE
            if code in {"08000", "08003", "08006"}:
                return SyncFailureClassification.UNKNOWN_COMMIT_OUTCOME
        if isinstance(exc, GoogleAdsAuthenticationError):
            return SyncFailureClassification.PERMANENT_AUTH
        if isinstance(exc, (ValueError, TypeError)):
            return SyncFailureClassification.PERMANENT_VALIDATION
        return SyncFailureClassification.UNKNOWN_PERMANENT

    def _is_lock_lost_failure(self, exc: BaseException) -> bool:
        return isinstance(exc, DBAPIError) and exc.connection_invalidated

    def _lock_lost_from_classification(self, classification: SyncFailureClassification) -> bool:
        return classification == SyncFailureClassification.UNKNOWN_COMMIT_OUTCOME

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
