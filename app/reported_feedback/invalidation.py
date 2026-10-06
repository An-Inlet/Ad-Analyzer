"""Caller owns workspace fence and transaction; never mutate protected finance."""

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.reported_feedback.models import ReportedActionComparison, ReportedFeedbackJob


def retract_account_comparisons(db: Session, workspace_id: int, account_id: int) -> None:
    db.execute(
        delete(ReportedActionComparison).where(
            ReportedActionComparison.workspace_id == workspace_id,
            ReportedActionComparison.account_id == account_id,
        )
    )


def erase_account_feedback(db: Session, workspace_id: int, account_id: int) -> None:
    db.execute(
        delete(ReportedFeedbackJob).where(
            ReportedFeedbackJob.workspace_id == workspace_id,
            ReportedFeedbackJob.account_id == account_id,
        )
    )


def erase_workspace_feedback(db: Session, workspace_id: int) -> None:
    db.execute(delete(ReportedFeedbackJob).where(ReportedFeedbackJob.workspace_id == workspace_id))


def erase_attempt_feedback(db: Session, workspace_id: int, attempt_id: str) -> None:
    db.execute(
        delete(ReportedFeedbackJob).where(
            ReportedFeedbackJob.workspace_id == workspace_id,
            ReportedFeedbackJob.original_attempt_id == attempt_id,
        )
    )
