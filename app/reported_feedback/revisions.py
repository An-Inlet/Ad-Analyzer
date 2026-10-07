"""Workspace-serialized immutable revisions; a missing pointer never revives history."""

from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.reported_feedback.models import ReportedFeedbackCurrent, ReportedFeedbackSlot

GROUP = ("workspace_id", "environment", "original_attempt_id", "policy_family", "cohort_digest")
OWNED = (*GROUP, "account_id", "campaign_id", "opportunity_digest")
MAX_RETAINED_REVISIONS = 128


def current_slot(db: Session, proposed: ReportedFeedbackSlot) -> ReportedFeedbackSlot | None:
    pointer = db.scalar(
        select(ReportedFeedbackCurrent)
        .where(*(getattr(ReportedFeedbackCurrent, f) == getattr(proposed, f) for f in GROUP))
        .execution_options(populate_existing=True)
    )
    if pointer is None:
        if (
            db.scalar(
                select(ReportedFeedbackSlot.id)
                .where(*(getattr(ReportedFeedbackSlot, f) == getattr(proposed, f) for f in GROUP))
                .limit(1)
            )
            is not None
        ):
            raise HTTPException(409, "reported_feedback_current_pointer_unavailable")
        return None
    row = db.get(ReportedFeedbackSlot, pointer.slot_id, populate_existing=True)
    if (
        row is None
        or any(getattr(pointer, f) != getattr(row, f) for f in OWNED)
        or pointer.revision != row.revision
    ):
        raise HTTPException(409, "reported_feedback_current_pointer_changed")
    return row


def require_current_slot(db: Session, row: ReportedFeedbackSlot) -> None:
    current = current_slot(db, row)
    if current is None or current.id != row.id:
        raise HTTPException(409, "reported_feedback_preview_superseded")


def append_revision(db: Session, saved: ReportedFeedbackSlot) -> None:
    ids = list(
        db.scalars(
            select(ReportedFeedbackSlot.id)
            .where(*(getattr(ReportedFeedbackSlot, f) == getattr(saved, f) for f in GROUP))
            .limit(MAX_RETAINED_REVISIONS)
        )
    )
    if len(ids) >= MAX_RETAINED_REVISIONS:
        raise HTTPException(409, "reported_feedback_revision_capacity_reached")
    pointer = db.scalar(
        select(ReportedFeedbackCurrent)
        .where(*(getattr(ReportedFeedbackCurrent, f) == getattr(saved, f) for f in GROUP))
        .execution_options(populate_existing=True)
    )
    db.add(saved)
    db.flush()
    if pointer is None:
        db.add(
            ReportedFeedbackCurrent(
                id=uuid4().hex,
                slot_id=saved.id,
                revision=saved.revision,
                **{f: getattr(saved, f) for f in OWNED},
            )
        )
    else:
        pointer.slot_id, pointer.revision = saved.id, saved.revision
    db.flush()
