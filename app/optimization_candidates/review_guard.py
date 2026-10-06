"""Mandatory forward-only guard; historical evidence and settlement do not call it."""

from collections.abc import Callable
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.publication.execution_models import ProviderExecutionReview
from app.publication.optimization_execution_contracts import OptimizationRuntime


def check(
    db: Session,
    row: ProviderExecutionReview,
    actor: str,
    runtime: OptimizationRuntime,
    clock: Callable[[], datetime],
) -> None:
    if not row.candidate_provenance_required:
        return
    if runtime.candidate_review_guard is None:
        raise HTTPException(409, "candidate review authority unavailable")
    runtime.candidate_review_guard(db, row.workspace_id, row.id, actor, clock)


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
        raise HTTPException(404, "candidate review unavailable")
    check(db, row, actor, runtime, clock)
