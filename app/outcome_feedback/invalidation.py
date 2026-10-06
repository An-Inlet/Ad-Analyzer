"""Delete whole derived documents under caller's workspace fence; never commit."""

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.outcome_feedback.models import V3Assessment


def erase_workspace_feedback(db: Session, workspace_id: int) -> None:
    db.execute(delete(V3Assessment).where(V3Assessment.workspace_id == workspace_id))


def erase_source_feedback(db: Session, workspace_id: int, store_id: str) -> None:
    db.execute(
        delete(V3Assessment).where(
            V3Assessment.workspace_id == workspace_id, V3Assessment.store_id == store_id
        )
    )


def erase_attempt_feedback(db: Session, workspace_id: int, attempt_id: str) -> None:
    db.execute(
        delete(V3Assessment).where(
            V3Assessment.workspace_id == workspace_id, V3Assessment.attempt_id == attempt_id
        )
    )
