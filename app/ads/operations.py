"""Read-only, bounded operational status for the Google Ads sync worker."""

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ads.enums import AdvertisingPlatform, JobRunStatus
from app.ads.models import JobRun
from app.settings import Settings

PUBLIC_SYNC_FAILURE_SUMMARY = "Google Ads synchronization failed."


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


def public_failure_summary(error_message: str | None) -> str | None:
    """Sanitize untrusted stored JobRun text for API and dashboard boundaries."""
    if not error_message:
        return None
    return PUBLIC_SYNC_FAILURE_SUMMARY


def _utc(value: datetime) -> datetime:
    """Treat timezone-naive database values as UTC for SQLite test parity."""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def sync_health(
    session: Session,
    settings: Settings,
    now: datetime | None = None,
    *,
    workspace_ids: set[int] | None = None,
) -> SyncHealth:
    """Use three indexed scalar queries, never collectors or mutations."""
    current = now or datetime.now(UTC)
    base = select(JobRun).where(
        JobRun.platform == AdvertisingPlatform.GOOGLE_ADS,
        JobRun.job_name == "google_ads_read_only_sync",
    )
    if workspace_ids is not None:
        if not workspace_ids:
            base = base.where(JobRun.workspace_id == -1)
        else:
            base = base.where(JobRun.workspace_id.in_(workspace_ids))
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
    age = max(0, int((_utc(current) - _utc(success_at)).total_seconds())) if success_at else None
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
    summary = public_failure_summary(failure.error_message if failure else None)
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
