"""Read-only, bounded operational status for the Google Ads sync worker."""

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ads.enums import AdvertisingPlatform, JobRunStatus
from app.ads.models import JobRun
from app.settings import Settings


@dataclass(frozen=True)
class SyncHealth:
    status: str
    stale: bool
    running: bool
    last_attempt_at: datetime | None
    last_success_at: datetime | None
    last_failure_at: datetime | None
    last_failure_summary: str | None
    success_age_seconds: int | None
    stale_after_seconds: int


def sync_health(session: Session, settings: Settings, now: datetime | None = None) -> SyncHealth:
    """Use three indexed scalar queries, never collectors or mutations."""
    current = now or datetime.now(UTC)
    base = select(JobRun).where(
        JobRun.platform == AdvertisingPlatform.GOOGLE_ADS,
        JobRun.job_name == "google_ads_read_only_sync",
    )
    latest = session.scalars(
        base.order_by(JobRun.started_at.desc(), JobRun.id.desc()).limit(1)
    ).first()
    successful = session.scalars(
        base.where(JobRun.status == JobRunStatus.SUCCEEDED)
        .order_by(JobRun.finished_at.desc(), JobRun.id.desc())
        .limit(1)
    ).first()
    failure = session.scalars(
        base.where(JobRun.status == JobRunStatus.FAILED)
        .order_by(JobRun.finished_at.desc(), JobRun.id.desc())
        .limit(1)
    ).first()
    success_at = successful.finished_at if successful else None
    age = (
        max(0, int((current - success_at.astimezone(UTC)).total_seconds())) if success_at else None
    )
    stale_after = settings.sync_stale_after_minutes * 60
    running = latest is not None and latest.status == JobRunStatus.RUNNING
    stale = success_at is None or (age is not None and age > stale_after)
    if running:
        status = "Running"
    elif success_at is None and failure is None:
        status = "Never Synced"
    elif latest is not None and latest.status == JobRunStatus.FAILED:
        status = "Failed"
    elif stale:
        status = "Stale"
    else:
        status = "Healthy"
    summary = failure.error_message[:120] if failure and failure.error_message else None
    return SyncHealth(
        status,
        stale,
        running,
        latest.started_at if latest else None,
        success_at,
        failure.finished_at if failure else None,
        summary,
        age,
        stale_after,
    )
