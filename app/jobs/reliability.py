"""Reliable, separate-process execution primitives for Google Ads synchronization."""

import logging
import math
import random
import socket
import time
from collections.abc import Callable
from contextlib import suppress
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
    FAILED_JOB_RUN_UNKNOWN_COMMIT_OUTCOME_ERROR,
    GoogleAdsSyncError,
    GoogleAdsSyncResult,
    GoogleAdsSyncService,
    Phase7SyncCapability,
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
INTERRUPTED_SYNC_ERROR = "Google Ads synchronization interrupted before retry."
LOCK_LOST_SYNC_ERROR = "Google Ads synchronization lost advisory-lock ownership."


class SyncOverlapSkipped(RuntimeError):
    """Raised internally when another worker owns the PostgreSQL lock."""


class SyncShutdownRequested(RuntimeError):
    """Raised after shutdown is requested during retry backoff."""


class AdvisoryLockLostError(RuntimeError):
    """Raised when the physical backend that owned the advisory lock is lost."""



def _advisory_lock_key_parts(key: int) -> tuple[int, int]:
    if key < -(2**63) or key > 2**63 - 1:
        raise ValueError("PostgreSQL advisory lock key must be a signed 64-bit integer")
    unsigned = key & ((1 << 64) - 1)
    return unsigned >> 32, unsigned & 0xFFFFFFFF


def _owns_advisory_lock_sql() -> str:
    return (
        "SELECT EXISTS ("
        "SELECT 1 FROM pg_locks "
        "WHERE locktype = 'advisory' "
        "AND pid = :pid "
        "AND classid = :classid "
        "AND objid = :objid "
        "AND objsubid = 1 "
        "AND mode = 'ExclusiveLock' "
        "AND granted)"
    )

class PostgreSQLAdvisoryLock:
    """A session-level lock held by exactly one pinned physical connection."""

    def __init__(self, connection: Connection, key: int) -> None:
        self.connection, self.key, self.acquired = connection, key, False
        self.backend_pid: int | None = None

    def _end_raw_transaction(self, *, commit: bool) -> None:
        if not self.connection.in_transaction():
            return
        if commit:
            self.connection.commit()
        else:
            self.connection.rollback()
        if self.connection.in_transaction():
            raise RuntimeError("raw advisory-lock transaction remained active")

    def try_acquire(self) -> bool:
        if self.connection.dialect.name != "postgresql":
            raise RuntimeError("Google Ads scheduler requires PostgreSQL advisory locks")
        try:
            self.acquired = bool(
                self.connection.scalar(
                    text("SELECT pg_try_advisory_lock(:key)"), {"key": self.key}
                )
            )
            if self.acquired:
                self.backend_pid = int(self.connection.scalar(text("SELECT pg_backend_pid()")))
            self._end_raw_transaction(commit=True)
        except BaseException:
            if self.acquired and not self.connection.invalidated:
                with suppress(BaseException):
                    self._end_raw_transaction(commit=False)
                with suppress(BaseException):
                    self.release()
            if self.acquired or self.connection.invalidated or self.connection.in_transaction():
                self.connection.invalidate()
            raise
        if self.connection.in_transaction():
            raise RuntimeError("advisory-lock acquisition transaction is still active")
        return self.acquired

    def owns_current_session(self, session: Session) -> bool:
        if not self.acquired or self.connection.invalidated:
            return False
        if self.connection.dialect.name != "postgresql":
            return True
        classid, objid = _advisory_lock_key_parts(self.key)
        params = {"pid": self.backend_pid, "classid": classid, "objid": objid}
        backend_pid = int(session.scalar(text("SELECT pg_backend_pid()")))
        owns_lock = bool(session.scalar(text(_owns_advisory_lock_sql()), params))
        return backend_pid == self.backend_pid and owns_lock

    def owns_current_connection(self) -> bool:
        if self.connection.in_transaction():
            raise RuntimeError("raw advisory-lock ownership checks require no active transaction")
        if not self.acquired or self.connection.invalidated:
            return False
        if self.connection.dialect.name != "postgresql":
            return True
        classid, objid = _advisory_lock_key_parts(self.key)
        params = {"pid": self.backend_pid, "classid": classid, "objid": objid}
        try:
            backend_pid = int(self.connection.scalar(text("SELECT pg_backend_pid()")))
            owns_lock = bool(self.connection.scalar(text(_owns_advisory_lock_sql()), params))
            return backend_pid == self.backend_pid and owns_lock
        finally:
            if not self.connection.invalidated and self.connection.in_transaction():
                self._end_raw_transaction(commit=True)

    def release(self) -> None:
        if not self.acquired or self.connection.invalidated:
            return
        try:
            unlocked = bool(
                self.connection.scalar(
                    text("SELECT pg_advisory_unlock(:key)"), {"key": self.key}
                )
            )
            if not unlocked:
                raise RuntimeError("PostgreSQL advisory lock release failed")
            self._end_raw_transaction(commit=True)
        except BaseException:
            with suppress(BaseException):
                self._end_raw_transaction(commit=False)
            self.connection.invalidate()
            raise
        finally:
            self.acquired = False


def lock_ownership_lost(exc: BaseException) -> bool:
    """Return true when the pinned backend session can no longer own the lock."""
    return (
        isinstance(exc, AdvisoryLockLostError)
        or (isinstance(exc, DBAPIError) and exc.connection_invalidated)
        or bool(getattr(exc, "lock_lost", False))
    )


def unknown_commit_outcome(exc: BaseException) -> bool:
    return isinstance(exc, GoogleAdsSyncError) and (
        exc.classification == SyncFailureClassification.UNKNOWN_COMMIT_OUTCOME
    )


def is_transient_failure(exc: BaseException) -> bool:
    """Conservative classification: unknown, lock-loss, and commit outcomes never retry."""
    if lock_ownership_lost(exc) or unknown_commit_outcome(exc):
        return False
    if isinstance(exc, GoogleAdsSyncError):
        return exc.classification in _TRANSIENT_CLASSIFICATIONS
    if isinstance(exc, (TimeoutError, ConnectionError, socket.gaierror)):
        return True
    if isinstance(exc, GoogleAdsRateLimitError):
        return True
    if isinstance(exc, DBAPIError) and exc.connection_invalidated:
        return False
    if isinstance(exc, OperationalError):
        code = getattr(getattr(exc, "orig", None), "pgcode", None) or getattr(
            getattr(exc, "orig", None), "sqlstate", None
        )
        return code in {"40001", "40P01", "57014"}
    code = getattr(exc, "code", None)
    return code in {429, 500, 502, 503, 504}


def _safe_jitter(random_value: Callable[[], Any]) -> float:
    raw = random_value()
    if isinstance(raw, bool) or not isinstance(raw, int | float) or not math.isfinite(raw):
        return 0.0
    return min(1.0, max(0.0, float(raw)))


_CAPABILITY_INTERRUPTED_ERROR = "Google Ads synchronization interrupted before retry."
_CAPABILITY_LOCK_LOST_ERROR = "Google Ads synchronization lost advisory-lock ownership."


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
    commit_started = False
    try:
        session.flush()
        commit_started = True
        session.commit()
    except Exception as exc:
        with suppress(Exception):
            session.rollback()
        if commit_started:
            raise GoogleAdsSyncError(
                (
                    "Google Ads sync commit outcome is unknown; "
                    "verify the latest job run before retrying"
                ),
                classification=SyncFailureClassification.UNKNOWN_COMMIT_OUTCOME,
                lock_lost=lock_ownership_lost(exc),
            ) from None
        raise
    return job_run


def _safe_failure_summary(exc: BaseException, attempts: int) -> str:
    if isinstance(exc, SyncShutdownRequested):
        return INTERRUPTED_SYNC_ERROR
    if isinstance(exc, AdvisoryLockLostError) or lock_ownership_lost(exc):
        return LOCK_LOST_SYNC_ERROR
    if isinstance(exc, GoogleAdsSyncError):
        return f"{str(exc)}; attempts={attempts}"[:120]
    return f"Google Ads read-only sync failed ({type(exc).__name__}; attempts={attempts})"[:120]


def _finalize_failed_job_run(
    session: Session, job_run: JobRun, exc: BaseException, attempts: int
) -> None:
    commit_started = False
    try:
        session.rollback()
        job_run = session.merge(job_run)
        AdvertisingMetricsRepository(session).finish_job_run(
            job_run,
            status=JobRunStatus.FAILED,
            records_processed=0,
            error_message=_safe_failure_summary(exc, attempts),
        )
        session.flush()
        commit_started = True
        session.commit()
    except Exception as finalize_exc:
        with suppress(Exception):
            session.rollback()
        if commit_started:
            raise GoogleAdsSyncError(
                FAILED_JOB_RUN_UNKNOWN_COMMIT_OUTCOME_ERROR,
                classification=SyncFailureClassification.UNKNOWN_COMMIT_OUTCOME,
                lock_lost=lock_ownership_lost(finalize_exc),
            ) from None
        raise



def _finalize_failed_job_run_on_engine(
    engine: Engine, job_run_id: int, exc: BaseException, attempts: int
) -> None:
    with engine.connect() as connection:
        session = sessionmaker(
            bind=connection,
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
        )()
        try:
            job_run = session.get(JobRun, job_run_id)
            if job_run is not None:
                _finalize_failed_job_run(session, job_run, exc, attempts)
        finally:
            session.close()

def _wait_for_retry(delay: float, wait: Callable[[float], bool | None]) -> None:
    if wait(delay):
        raise SyncShutdownRequested(INTERRUPTED_SYNC_ERROR)


def _stop_requested(stop_requested: Callable[[], bool] | None) -> bool:
    return bool(stop_requested and stop_requested())


def _raise_if_stop_requested(stop_requested: Callable[[], bool] | None) -> None:
    if _stop_requested(stop_requested):
        raise SyncShutdownRequested(INTERRUPTED_SYNC_ERROR)


def _make_pre_collector_check(
    lock: PostgreSQLAdvisoryLock,
    connection: Connection,
    session: Session,
    stop_requested: Callable[[], bool] | None,
) -> Callable[[], None]:
    def check() -> None:
        _raise_if_stop_requested(stop_requested)
        try:
            owns_lock = lock.owns_current_session(session)
        except BaseException:
            connection.invalidate()
            raise AdvisoryLockLostError(LOCK_LOST_SYNC_ERROR) from None
        if not owns_lock:
            connection.invalidate()
            raise AdvisoryLockLostError(LOCK_LOST_SYNC_ERROR)

    return check


def run_cycle(
    settings: Settings,
    engine: Engine,
    *,
    sleep: Callable[[float], None] = time.sleep,
    wait: Callable[[float], bool | None] | None = None,
    stop_requested: Callable[[], bool] | None = None,
    random_value: Callable[[], Any] = random.random,
) -> CycleOutcome:
    """Run one locked cycle; all retries retain the same advisory-lock connection."""
    connection = engine.connect()
    lock = PostgreSQLAdvisoryLock(connection, settings.sync_lock_key)
    session: Session | None = None
    job_run: JobRun | None = None
    last_attempt = 0
    finalization_completed = False
    finalization_outcome_unknown = False
    primary_error: BaseException | None = None
    capability: Phase7SyncCapability | None = None
    class _CyclePhase7SyncCapability(Phase7SyncCapability):
        """Function-local capability bound to this run_cycle invocation."""

        __slots__ = (
            "_lock",
            "_connection",
            "_session",
            "_lock_key",
            "_backend_pid",
            "_stop_requested",
            "_valid",
        )

        def __init__(
            self,
            *,
            lock: object,
            connection: object,
            session: Session,
            lock_key: int,
            backend_pid: int | None,
            stop_requested: Callable[[], bool],
        ) -> None:
            self._lock = lock
            self._connection = connection
            self._session = session
            self._lock_key = lock_key
            self._backend_pid = backend_pid
            self._stop_requested = stop_requested
            self._valid = True

        def invalidate(self) -> None:
            self._valid = False

        def validate(self, session: Session) -> None:
            if not self._valid:
                raise GoogleAdsSyncError(
                    "Google Ads synchronization must be run through the Phase 7 worker.",
                    classification=SyncFailureClassification.PERMANENT_CONFIGURATION,
                )
            if session is not self._session:
                raise GoogleAdsSyncError(
                    "Google Ads synchronization must be run through the Phase 7 worker.",
                    classification=SyncFailureClassification.PERMANENT_CONFIGURATION,
                )
            if self._stop_requested():
                self.invalidate()
                raise GoogleAdsSyncError(
                    _CAPABILITY_INTERRUPTED_ERROR,
                    classification=SyncFailureClassification.PERMANENT_CONFIGURATION,
                )
            if getattr(self._connection, "invalidated", False):
                self.invalidate()
                raise GoogleAdsSyncError(
                    _CAPABILITY_LOCK_LOST_ERROR,
                    classification=SyncFailureClassification.TRANSIENT_DATABASE,
                    lock_lost=True,
                )
            if getattr(self._lock, "key", None) != self._lock_key:
                raise GoogleAdsSyncError(
                    "Google Ads synchronization must be run through the Phase 7 worker.",
                    classification=SyncFailureClassification.PERMANENT_CONFIGURATION,
                )
            if getattr(self._lock, "backend_pid", None) != self._backend_pid:
                self.invalidate()
                raise GoogleAdsSyncError(
                    _CAPABILITY_LOCK_LOST_ERROR,
                    classification=SyncFailureClassification.TRANSIENT_DATABASE,
                    lock_lost=True,
                )
            owns_current_session = getattr(self._lock, "owns_current_session", None)
            if not callable(owns_current_session) or not bool(owns_current_session(session)):
                self.invalidate()
                raise GoogleAdsSyncError(
                    _CAPABILITY_LOCK_LOST_ERROR,
                    classification=SyncFailureClassification.TRANSIENT_DATABASE,
                    lock_lost=True,
                )

    retry_wait: Callable[[float], bool | None]
    if wait is None:
        def retry_wait(delay: float) -> bool:
            sleep(delay)
            return False
    else:
        retry_wait = wait

    def handle_failed_finalization_error(
        finalize_exc: BaseException,
        original_exc: BaseException,
        attempts: int,
    ) -> None:
        nonlocal finalization_completed, finalization_outcome_unknown, primary_error
        if unknown_commit_outcome(finalize_exc):
            finalization_outcome_unknown = True
            primary_error = finalize_exc
            if lock_ownership_lost(finalize_exc):
                lock.acquired = False
                connection.invalidate()
            raise finalize_exc
        if lock_ownership_lost(finalize_exc):
            if job_run is None:
                raise finalize_exc
            lock.acquired = False
            connection.invalidate()
            if capability is not None:
                capability.invalidate()
            if session is not None:
                session.close()
            try:
                _finalize_failed_job_run_on_engine(engine, job_run.id, original_exc, attempts)
                finalization_completed = True
            except BaseException as replacement_exc:
                if unknown_commit_outcome(replacement_exc):
                    finalization_outcome_unknown = True
                    primary_error = replacement_exc
                    if lock_ownership_lost(replacement_exc):
                        connection.invalidate()
                    raise replacement_exc
                raise
            return
        raise finalize_exc

    try:
        _raise_if_stop_requested(stop_requested)
        if not lock.try_acquire():
            logger.info("google_ads_sync_overlap_skipped")
            return CycleOutcome(skipped=True, result=None, attempts=0)
        if connection.in_transaction():
            raise RuntimeError("advisory-lock acquisition transaction is still active")
        session_factory = sessionmaker(
            bind=connection,
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
        )
        session = session_factory()
        job_run = _create_authoritative_job_run(session)
        try:
            _raise_if_stop_requested(stop_requested)
        except BaseException as stop_exc:
            try:
                _finalize_failed_job_run(session, job_run, stop_exc, 0)
                finalization_completed = True
            except BaseException as finalize_exc:
                handle_failed_finalization_error(finalize_exc, stop_exc, 0)
            raise
        for attempt in range(1, settings.sync_max_attempts + 1):
            try:
                _raise_if_stop_requested(stop_requested)
                last_attempt = attempt
                capability = _CyclePhase7SyncCapability(
                    lock=lock,
                    connection=connection,
                    session=session,
                    lock_key=settings.sync_lock_key,
                    backend_pid=lock.backend_pid,
                    stop_requested=stop_requested or (lambda: False),
                )
                result = GoogleAdsSyncService(session).sync_authoritative_job_run(
                    job_run,
                    capability=capability,
                )
                logger.info(
                    "google_ads_sync_succeeded run_id=%s attempt=%s", result.job_run_id, attempt
                )
                return CycleOutcome(skipped=False, result=result, attempts=attempt)
            except BaseException as exc:
                if unknown_commit_outcome(exc):
                    primary_error = exc
                    if lock_ownership_lost(exc):
                        lock.acquired = False
                        connection.invalidate()
                    logger.error(
                        "google_ads_sync_unknown_commit_outcome run_id=%s attempt=%s",
                        job_run.id,
                        attempt,
                    )
                    raise
                if lock_ownership_lost(exc):
                    lock.acquired = False
                    connection.invalidate()
                    session.close()
                    _finalize_failed_job_run_on_engine(
                        engine, job_run.id, AdvisoryLockLostError(), attempt
                    )
                    finalization_completed = True
                    raise AdvisoryLockLostError(LOCK_LOST_SYNC_ERROR) from None
                retryable = isinstance(exc, Exception) and is_transient_failure(exc)
                if attempt >= settings.sync_max_attempts or not retryable:
                    try:
                        _finalize_failed_job_run(session, job_run, exc, attempt)
                        finalization_completed = True
                    except BaseException as finalize_exc:
                        handle_failed_finalization_error(finalize_exc, exc, attempt)
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
                try:
                    _raise_if_stop_requested(stop_requested)
                    _wait_for_retry(delay, retry_wait)
                    _raise_if_stop_requested(stop_requested)
                except BaseException as wait_exc:
                    if unknown_commit_outcome(wait_exc):
                        primary_error = wait_exc
                        raise
                    try:
                        _finalize_failed_job_run(session, job_run, wait_exc, attempt)
                        finalization_completed = True
                    except BaseException as finalize_exc:
                        handle_failed_finalization_error(finalize_exc, wait_exc, attempt)
                    raise
        raise AssertionError("unreachable")
    except BaseException as exc:
        if unknown_commit_outcome(exc):
            primary_error = exc
            if lock_ownership_lost(exc):
                lock.acquired = False
                connection.invalidate()
            raise
        if job_run is not None and not finalization_completed and not finalization_outcome_unknown:
            assert session is not None
            try:
                _finalize_failed_job_run(session, job_run, exc, last_attempt)
                finalization_completed = True
            except BaseException as finalize_exc:
                handle_failed_finalization_error(finalize_exc, exc, last_attempt)
        raise
    finally:
        release_error: BaseException | None = None
        try:
            if capability is not None:
                capability.invalidate()
            if session is not None:
                session.close()
        finally:
            try:
                lock.release()
            except BaseException as exc:
                release_error = exc
            finally:
                connection.close()
            if release_error is not None and not unknown_commit_outcome(
                primary_error or release_error
            ):
                raise release_error
