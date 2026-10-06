"""Transactional derived-data erasure; callers already hold the workspace lock.

No financial/service imports, commits, new locks, authority or receipt deletion.
"""

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.commerce.models import CommerceMeasurementPublication
from app.optimization_candidates.models import CandidateJob


def erase_workspace_candidates(db: Session, workspace_id: int) -> None:
    db.execute(delete(CandidateJob).where(CandidateJob.workspace_id == workspace_id))


def erase_source_candidates(db: Session, workspace_id: int, store_id: str) -> None:
    publications = select(CommerceMeasurementPublication.id).where(
        CommerceMeasurementPublication.workspace_id == workspace_id,
        CommerceMeasurementPublication.store_id == store_id,
    )
    db.execute(
        delete(CandidateJob).where(
            CandidateJob.workspace_id == workspace_id, CandidateJob.publication_id.in_(publications)
        )
    )


def erase_attempt_candidates(db: Session, workspace_id: int, attempt_id: str) -> None:
    db.execute(
        delete(CandidateJob).where(
            CandidateJob.workspace_id == workspace_id, CandidateJob.attempt_id == attempt_id
        )
    )
