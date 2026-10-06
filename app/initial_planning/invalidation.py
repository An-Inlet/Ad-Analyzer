"""Caller holds workspace fence. No locks, commits or recursive privacy callbacks."""

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.initial_planning.models import CalibrationRow, ObservationRow


def erase_source_observations(db: Session, workspace_id: int, account_id: int) -> None:
    invalidate_account_calibrations(db, workspace_id, account_id)
    db.execute(
        delete(ObservationRow).where(
            ObservationRow.workspace_id == workspace_id,
            ObservationRow.account_id == account_id,
        )
    )


def erase_workspace_observations(db: Session, workspace_id: int) -> None:
    db.execute(delete(CalibrationRow).where(CalibrationRow.workspace_id == workspace_id))
    db.execute(delete(ObservationRow).where(ObservationRow.workspace_id == workspace_id))


def invalidate_account_calibrations(db: Session, workspace_id: int, account_id: int) -> None:
    # Historical captures remain explicitly historical; deletion triggers advance
    # export fence only. Next actual terminal completion captures that final fence.
    db.execute(
        delete(CalibrationRow).where(
            CalibrationRow.workspace_id == workspace_id,
            CalibrationRow.account_id == account_id,
        )
    )
