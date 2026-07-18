"""Reliable, separate-process execution primitives for Google Ads synchronization."""

import logging
import math
import random
import socket
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from sqlalchemy import Engine, text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import DBAPIError, OperationalError
from sqlalchemy.orm import Session, sessionmaker

from app.ads.enums import AdvertisingPlatform, JobRunStatus
from app.ads.models import JobRun
from app.ads.repository import AdvertisingMetricsRepository
from app.ads.services import (
    GoogleAdsSyncError,
    GoogleAdsSyncResult,
    GoogleAdsSyncService,
    SyncFailureClassification,
)
from app.collectors.google_ads import GoogleAdsRateLimitError
from app.settings import Settings

logger = logging.getLogger(__name__)

_TRANSIENT_CLASSIFICATIONS = {
    SyncFailureClassification.TRANSIENT_RATE_LIMIT,
    SyncFailureClassification.TRANSIENT_NETWORK,
    SyncFailureClassification.TRANSIENT_DATABASE,
}


class SyncOverlapSkipped(RuntimeError):
    """Raised internally when another worker owns the PostgreSQL lock."""


class PostgreSQLAdvisoryLock:
    """A session-level lock held by exactly one pinned physical connection."""

    def __init__(self, connection: Connection, key: int) -> None:
        self.connection, self.key, self.acquired = connection, key, False

    def try_acquire(self) -> bool:
        if self.connection.dialect.name != "postgresql":
            raise RuntimeError("Google Ads scheduler requires PostgreSQL advisory locks")
        self.acquired = bool(
            self.connection.scalar(text("SELECT pg_try_advisory_lock(:key)"), {"key": self.key})
        )
        return self.acquired

    def release(self) -> None:
        if not self.acquired:
            return
        unlocked = False
        try:
            unlocked = bool(
                self.connection.scalar(
                    text("SELECT pg_advisory_unlock(:key)"), {"key": self.key}
                )
            )
            if not unlocked:
                raise RuntimeError("PostgreSQL advisory lock release failed")
        except BaseException:
            self.connection.invalidate()
            raise
        finally:
            self.acquired = False


def is_transient_failure(exc: BaseException) -> bool:
    """Conservative classification: unknown and commit-outcome errors never retry."""
    if isinstance(exc, GoogleAdsSyncError):
        return exc.classification in _TRANSIENT_CLASSIFICATIONS
    if isinstance(exc, (TimeoutError, ConnectionError, socket.gaierror)):
        return True
    if isinstance(exc, GoogleAdsRateLimitError):
        return True
    if isinstance(exc, DBAPIError) and exc.connection_invalidated:
        return True
    if isinstance(exc, OperationalError):
        code = getattr(getattr(exc, "orig", None), "pgcode", None) or getattr(
            getattr(exc, "orig", None), "sqlstate", None
        )
        return code in {"40001", "40P01", "57014", "08000", "08003", "08006"}
    code = getattr(exc, "code", None)
    return code in {429, 500, 502, 503, 504}


def _safe_jitter(random_value: Callable[[], Any]) -> float:
    raw = random_value()
    if isinstance(raw, bool) or not isinstance(raw, int | float) or not math.isfinite(raw):
        return 0.0
    return min(1.0, max(0.0, float(raw)))


def retry_delay(
    attempt: int, settings: Settings, random_value: Callable[[], Any] = random.random
) -> float:
    """Exponential, capped delay with at most ten percent bounded jitter."""
    safe_attempt = max(1, min(attempt, 63))
    exponent = min(safe_attempt - 1, 30)
    base_delay = min(
        float(settings.sync_retry_max_seconds),
        float(settings.sync_retry_base_seconds) * float(2**exponent),
    )
    delay = base_delay + base_delay * 0.1 * _safe_jitter(random_value)
    return min(float(settings.sync_retry_max_seconds), max(0.0, delay))


@dataclass(frozen=True)
class CycleOutcome:
    skipped: bool
    result: GoogleAdsSyncResult | None
    attempts: int


def _create_authoritative_job_run(session: Session) -> JobRun:
    repository = AdvertisingMetricsRepository(session)
    job_run = repository.create_job_run(
        platform=AdvertisingPlatform.GOOGLE_ADS,
        job_name=GoogleAdsSyncService.job_name,
        status=JobRunStatus.RUNNING,
    )
    session.flush()
    session.commit()
    return job_run


def _finalize_failed_job_run(
    session: Session, job_run: JobRun, exc: BaseException, attempts: int
) -> None:
    with context_rollback(session):
        job_run = session.merge(job_run)
        AdvertisingMetricsRepository(session).finish_job_run(
            job_run,
            status=JobRunStatus.FAILED,
            records_processed=0,
            error_message=(
                f"Google Ads read-only sync failed ({type(exc).__name__}; attempts={attempts})"
            )[:120],
        )
        session.commit()


class context_rollback:
    def __init__(self, session: Session) -> None:
        self.session = session

    def __enter__(self) -> None:
        self.session.rollback()

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        if exc_type is not None:
            self.session.rollback()


def run_cycle(
    settings: Settings,
    engine: Engine,
    *,
    sleep: Callable[[float], None] = time.sleep,
    random_value: Callable[[], Any] = random.random,
) -> CycleOutcome:
    """Run one locked cycle; all retries retain the same advisory-lock connection."""
    connection = engine.connect()
    lock = PostgreSQLAdvisoryLock(connection, settings.sync_lock_key)
    session_factory = sessionmaker(bind=connection, autoflush=False, autocommit=False)
    session = session_factory()
    acquired = False
    job_run: JobRun | None = None
    last_attempt = 0
    try:
        if not lock.try_acquire():
            logger.info("google_ads_sync_overlap_skipped")
            return CycleOutcome(skipped=True, result=None, attempts=0)
        acquired = True
        job_run = _create_authoritative_job_run(session)
        for attempt in range(1, settings.sync_max_attempts + 1):
            last_attempt = attempt
            try:
                result = GoogleAdsSyncService(session).sync_authoritative_job_run(job_run)
                logger.info(
                    "google_ads_sync_succeeded run_id=%s attempt=%s", result.job_run_id, attempt
                )
                return CycleOutcome(skipped=False, result=result, attempts=attempt)
            except BaseException as exc:
                retryable = isinstance(exc, Exception) and is_transient_failure(exc)
                if attempt >= settings.sync_max_attempts or not retryable:
                    _finalize_failed_job_run(session, job_run, exc, attempt)
                    logger.error(
                        "google_ads_sync_failed run_id=%s attempt=%s error_type=%s",
                        job_run.id,
                        attempt,
                        type(exc).__name__,
                    )
                    raise
                delay = retry_delay(attempt, settings, random_value)
                logger.warning(
                    "google_ads_sync_retry run_id=%s attempt=%s delay_seconds=%.2f",
                    job_run.id,
                    attempt,
                    delay,
                )
                sleep(delay)
        raise AssertionError("unreachable")
    except BaseException as exc:
        if acquired and job_run is not None and last_attempt == 0:
            _finalize_failed_job_run(session, job_run, exc, last_attempt)
        raise
    finally:
        release_error: BaseException | None = None
        try:
            session.close()
        finally:
            try:
                lock.release()
            except BaseException as exc:
                release_error = exc
            finally:
                connection.close()
            if release_error is not None:
                raise release_error
