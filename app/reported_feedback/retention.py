"""Bounded persisted-deadline cleanup, even with capture disabled or workspace closing."""

from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy import Engine, delete, select, union
from sqlalchemy.orm import Session

from app.lifecycle.privacy import database_utc_now
from app.reported_feedback.models import (
    ReportedActionComparison,
    ReportedFeedbackJob,
    ReportedFeedbackSlot,
    ReportedWindowCapsule,
)
from app.workspaces.models import Workspace

EXPIRING = (
    ReportedFeedbackSlot,
    ReportedActionComparison,
    ReportedWindowCapsule,
    ReportedFeedbackJob,
)


def purge_expired_feedback(
    session_factory: Callable[[], Session],
    *,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    batch_limit: int = 20,
) -> int:
    if isinstance(batch_limit, bool) or not 1 <= batch_limit <= 100:
        raise ValueError("retention batch limit must be between one and one hundred")
    with session_factory() as db:
        candidates = union(
            *[select(model.workspace_id).where(model.expires_at <= clock()) for model in EXPIRING]
        ).subquery()
        ids = list(
            db.scalars(
                select(candidates.c.workspace_id)
                .order_by(candidates.c.workspace_id)
                .limit(batch_limit)
            )
        )
    purged = 0
    for wid in ids:
        with session_factory() as db:
            if (
                db.scalar(
                    select(Workspace.id).where(Workspace.id == wid).with_for_update(key_share=True)
                )
                is None
            ):
                continue
            now = min(clock(), database_utc_now(db))
            changed = False
            for model in EXPIRING:
                if (
                    db.scalar(
                        select(model.id)
                        .where(model.workspace_id == wid, model.expires_at <= now)
                        .limit(1)
                    )
                    is not None
                ):
                    if model is ReportedWindowCapsule:
                        # A missing retained observation cannot leave its acquisition
                        # request schedulable or dependent numeric graph recoverable.
                        jobs = select(ReportedWindowCapsule.job_id).where(
                            ReportedWindowCapsule.workspace_id == wid,
                            ReportedWindowCapsule.expires_at <= now,
                        )
                        db.execute(
                            delete(ReportedFeedbackJob).where(
                                ReportedFeedbackJob.workspace_id == wid,
                                ReportedFeedbackJob.id.in_(jobs),
                            )
                        )
                    else:
                        db.execute(
                            delete(model).where(model.workspace_id == wid, model.expires_at <= now)
                        )
                    changed = True
            db.commit()
            purged += int(changed)
    return purged


def run_reported_retention_tick(engine: Engine) -> int:
    return purge_expired_feedback(lambda: Session(engine))
