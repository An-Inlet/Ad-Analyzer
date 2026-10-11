"""Shared transactional invalidation of snapshots; independent of workspace admission."""

from datetime import UTC, datetime

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.workspaces.models import Workspace


def _lock_workspace(db: Session, workspace_id: int) -> None:
    owned = db.scalar(
        select(Workspace.id).where(Workspace.id == workspace_id).with_for_update(key_share=True)
    )
    if owned is None:
        raise ValueError("privacy workspace unavailable")


def advance_workspace_export_revision(db: Session, workspace_id: int) -> None:
    """Internal counter-only fence after owned derived-data correction/deletion.

    This is not semantic privacy erasure. Callers preserving historical-as-observed
    data must delete obsolete derived results themselves. No commit/status filter;
    acquire workspace first, before native/store/product locks.
    """
    _lock_workspace(db, workspace_id)
    db.execute(
        update(Workspace)
        .where(Workspace.id == workspace_id)
        .values(export_privacy_revision=Workspace.export_privacy_revision + 1)
        .execution_options(synchronize_session=False)
    )


def bump_workspace_export_revision(db: Session, workspace_id: int) -> None:
    """Semantic privacy invalidation: erase derived data and fence exports.

    Call before native/store locks (or with this workspace already locked).
    No status filter: erasure/retention must work for closing or retained inactive
    workspaces. Caller owns commit; rollback restores both deletion and fence.
    Every destructive customer-data writer must join this contract.
    """
    _lock_workspace(db, workspace_id)
    from app.campaign_performance.presence_storage import erase_workspace_presence
    from app.campaign_performance.range_receipts import erase_workspace_range_receipts
    from app.campaign_performance.selected_storage import erase_workspace_selected
    from app.initial_planning.invalidation import erase_workspace_observations
    from app.meta.presence_staging import erase_workspace_staging
    from app.optimization_candidates.invalidation import erase_workspace_candidates
    from app.planning_documents.invalidation import erase_workspace_plans

    erase_workspace_range_receipts(db, workspace_id)
    erase_workspace_selected(db, workspace_id)
    erase_workspace_staging(db, workspace_id)
    erase_workspace_presence(db, workspace_id)
    erase_workspace_plans(db, workspace_id)
    erase_workspace_candidates(db, workspace_id)
    erase_workspace_observations(db, workspace_id)
    advance_workspace_export_revision(db, workspace_id)


def workspace_export_revision(db: Session, workspace_id: int) -> int:
    revision = db.scalar(
        select(Workspace.export_privacy_revision).where(Workspace.id == workspace_id)
    )
    if revision is None:
        raise ValueError("privacy workspace unavailable")
    return revision


def database_utc_now(db: Session) -> datetime:
    """Fresh database wallclock, not PostgreSQL's transaction-start timestamp."""
    if db.get_bind().dialect.name == "postgresql":
        value = db.scalar(select(func.clock_timestamp()))
    elif db.get_bind().dialect.name == "sqlite":
        raw = db.scalar(select(func.strftime("%Y-%m-%d %H:%M:%f", "now")))
        value = datetime.fromisoformat(raw) if isinstance(raw, str) else None
    else:
        raise ValueError("unsupported retention database")
    if not isinstance(value, datetime):
        raise ValueError("database retention clock unavailable")
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
