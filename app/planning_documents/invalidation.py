"""Semantic erasure removes the complete owned graph; caller holds workspace lock."""

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.planning_documents.models import (
    PlanDependencyRow,
    PlanEventRow,
    PlanInputRow,
    PlanRequestRow,
    PlanRow,
    PlanVersionRow,
)


def erase_workspace_plans(db: Session, workspace_id: int) -> None:
    db.execute(delete(PlanRequestRow).where(PlanRequestRow.workspace_id == workspace_id))
    # Reverse chain order satisfies immediate RESTRICT semantics on both databases.
    events = db.execute(
        select(PlanEventRow.plan_id, PlanEventRow.sequence)
        .where(PlanEventRow.workspace_id == workspace_id)
        .order_by(PlanEventRow.sequence.desc())
    ).all()
    for plan_id, sequence in events:
        db.execute(
            delete(PlanEventRow).where(
                PlanEventRow.workspace_id == workspace_id,
                PlanEventRow.plan_id == plan_id,
                PlanEventRow.sequence == sequence,
            )
        )
    for model in (PlanDependencyRow, PlanVersionRow, PlanInputRow, PlanRow):
        db.execute(delete(model).where(model.workspace_id == workspace_id))
