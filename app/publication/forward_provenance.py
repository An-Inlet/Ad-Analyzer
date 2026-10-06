"""Independent mandatory forward-only provenance; never historical settlement authority."""

from collections.abc import Callable
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.optimization_candidates import review_guard as candidates
from app.publication.execution_models import ProviderExecutionReview
from app.publication.optimization_execution_contracts import OptimizationRuntime


def check(
    db: Session,
    row: ProviderExecutionReview,
    actor: str,
    runtime: OptimizationRuntime,
    clock: Callable[[], datetime],
) -> None:
    current = db.get(ProviderExecutionReview, row.id, populate_existing=True)
    if current is None or current.workspace_id != row.workspace_id:
        raise HTTPException(409, "execution provenance unavailable")
    if current.initial_preview_provenance_required:
        if (
            not current.initial_preview_origin_id
            or current.candidate_provenance_required
            or current.automatic_authority_required
        ):
            raise HTTPException(409, "initial preview provenance inconsistent")
        if runtime.initial_preview_review_guard is None:
            raise HTTPException(409, "initial preview review authority unavailable")
        runtime.initial_preview_review_guard(db, current.workspace_id, current.id, actor, clock)
    elif current.initial_preview_origin_id is not None:
        raise HTTPException(409, "initial preview provenance inconsistent")
    candidates.check(db, current, actor, runtime, clock)


def check_id(
    db: Session,
    wid: int,
    review_id: str,
    actor: str,
    runtime: OptimizationRuntime,
    clock: Callable[[], datetime],
) -> None:
    row = db.get(ProviderExecutionReview, review_id, populate_existing=True)
    if row is None or row.workspace_id != wid:
        raise HTTPException(404, "execution review unavailable")
    check(db, row, actor, runtime, clock)
