"""Bounded DB-expired initial evidence cleanup; consumed semantic identity survives."""

from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy import ColumnElement, delete, select, union
from sqlalchemy.orm import Session

from app.initial_planning.automatic_models import (
    InitialRuleAdmissionOrigin,
    InitialRuleCandidateDependency,
    InitialRuleOpportunity,
)
from app.lifecycle.privacy import database_utc_now
from app.workspaces.models import Workspace


def unconsumed() -> ColumnElement[bool]:
    return (
        ~select(InitialRuleAdmissionOrigin.admission_id)
        .where(
            InitialRuleAdmissionOrigin.opportunity_id == InitialRuleOpportunity.id,
        )
        .exists()
    )


def purge_expired_initial_rules(
    session_factory: Callable[[], Session],
    *,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    batch_limit: int = 20,
) -> int:
    if isinstance(batch_limit, bool) or not 1 <= batch_limit <= 100:
        raise ValueError("initial rule retention batch limit required")
    with session_factory() as db:
        now = min(clock(), database_utc_now(db))
        candidates = union(
            select(InitialRuleCandidateDependency.workspace_id).where(
                InitialRuleCandidateDependency.expires_at <= now,
            ),
            select(InitialRuleOpportunity.workspace_id).where(
                InitialRuleOpportunity.pending_expires_at <= now,
                unconsumed(),
            ),
        ).subquery()
        ids = list(
            db.scalars(
                select(candidates.c.workspace_id)
                .order_by(candidates.c.workspace_id)
                .limit(batch_limit)
            )
        )
    count = 0
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
            db.execute(
                delete(InitialRuleCandidateDependency).where(
                    InitialRuleCandidateDependency.workspace_id == wid,
                    InitialRuleCandidateDependency.expires_at <= now,
                )
            )
            db.execute(
                delete(InitialRuleOpportunity).where(
                    InitialRuleOpportunity.workspace_id == wid,
                    InitialRuleOpportunity.pending_expires_at <= now,
                    unconsumed(),
                )
            )
            db.commit()
            count += 1
    return count


def erase_unused_initial_origins(db: Session, workspace_id: int) -> None:
    """Semantic erasure: caller owns workspace fence, protected admissions remain."""
    db.execute(
        delete(InitialRuleCandidateDependency).where(
            InitialRuleCandidateDependency.workspace_id == workspace_id,
        )
    )
    db.execute(
        delete(InitialRuleOpportunity).where(
            InitialRuleOpportunity.workspace_id == workspace_id,
            unconsumed(),
        )
    )
