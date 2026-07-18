"""Reliable, separate-process execution primitives for Google Ads synchronization."""

import logging
import random
import socket
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import cast

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, OperationalError
from sqlalchemy.orm import Session

from app.ads.services import GoogleAdsSyncResult, GoogleAdsSyncService
from app.collectors.google_ads import GoogleAdsRateLimitError
from app.settings import Settings

logger = logging.getLogger(__name__)


class SyncOverlapSkipped(RuntimeError):
    """Raised internally when another worker owns the PostgreSQL lock."""


class PostgreSQLAdvisoryLock:
    """A session-scoped lock held by this one dedicated database connection."""

    def __init__(self, session: Session, key: int) -> None:
        self.session, self.key, self.acquired = session, key, False

    def try_acquire(self) -> bool:
        if self.session.get_bind().dialect.name != "postgresql":
            raise RuntimeError("Google Ads scheduler requires PostgreSQL advisory locks")
        self.acquired = bool(
            self.session.scalar(text("SELECT pg_try_advisory_lock(:key)"), {"key": self.key})
        )
        return self.acquired

    def release(self) -> None:
        if self.acquired:
            try:
                self.session.scalar(text("SELECT pg_advisory_unlock(:key)"), {"key": self.key})
            finally:
                self.acquired = False


def is_transient_failure(exc: Exception) -> bool:
    """Conservative classification: unknown and credential errors never retry."""
    if isinstance(exc, (TimeoutError, ConnectionError, socket.gaierror)):
        return True
    if isinstance(exc, GoogleAdsRateLimitError):
        return True
    if isinstance(exc, OperationalError):
        message = str(getattr(exc, "orig", "")).lower()
        return any(
            word in message for word in ("deadlock", "serialization", "timeout", "connection")
        )
    if isinstance(exc, DBAPIError) and exc.connection_invalidated:
        return True
    code = getattr(exc, "code", None)
    return code in {429, 500, 502, 503, 504}


def retry_delay(
    attempt: int, settings: Settings, random_value: Callable[[], float] = random.random
) -> float:
    """Exponential, capped delay with at most ten percent bounded jitter."""
    delay = min(
        settings.sync_retry_max_seconds, settings.sync_retry_base_seconds * (2 ** (attempt - 1))
    )
    return cast(float, min(settings.sync_retry_max_seconds, delay + delay * 0.1 * random_value()))


@dataclass(frozen=True)
class CycleOutcome:
    skipped: bool
    result: GoogleAdsSyncResult | None
    attempts: int


def run_cycle(
    settings: Settings,
    session_factory: Callable[[], Session],
    *,
    sleep: Callable[[float], None] = time.sleep,
    random_value: Callable[[], float] = random.random,
) -> CycleOutcome:
    """Run one locked cycle; all retries retain the same advisory-lock connection."""
    session = session_factory()
    lock = PostgreSQLAdvisoryLock(session, settings.sync_lock_key)
    try:
        if not lock.try_acquire():
            logger.info("google_ads_sync_overlap_skipped")
            return CycleOutcome(skipped=True, result=None, attempts=0)
        for attempt in range(1, settings.sync_max_attempts + 1):
            try:
                result = GoogleAdsSyncService(session).sync()
                logger.info(
                    "google_ads_sync_succeeded run_id=%s attempt=%s", result.job_run_id, attempt
                )
                return CycleOutcome(skipped=False, result=result, attempts=attempt)
            except Exception as exc:
                if attempt >= settings.sync_max_attempts or not is_transient_failure(exc):
                    logger.error(
                        "google_ads_sync_failed attempt=%s error_type=%s",
                        attempt,
                        type(exc).__name__,
                    )
                    raise
                delay = retry_delay(attempt, settings, random_value)
                logger.warning(
                    "google_ads_sync_retry attempt=%s delay_seconds=%.2f", attempt, delay
                )
                sleep(delay)
        raise AssertionError("unreachable")
    finally:
        try:
            lock.release()
        finally:
            session.close()
