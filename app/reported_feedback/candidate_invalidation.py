"""Local transactional rule cache erasure; caller already owns the workspace fence."""

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.optimization_candidates.models import CandidateJob
from app.reported_feedback.candidate_models import ReportedRuleCandidateDependency


def erase_reported_candidates(db: Session, workspace_id: int, acquisition_job_id: str) -> None:
    jobs = select(ReportedRuleCandidateDependency.candidate_job_id).where(
        ReportedRuleCandidateDependency.workspace_id == workspace_id,
        ReportedRuleCandidateDependency.acquisition_job_id == acquisition_job_id,
    )
    db.execute(
        delete(CandidateJob).where(
            CandidateJob.workspace_id == workspace_id, CandidateJob.id.in_(jobs)
        )
    )
