"""Canonical first lock for workspace-owned mutations and closure."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.workspaces.models import Workspace


def lock_workspace_row(db: Session, workspace_id: int) -> Workspace | None:
    """Refresh authority without flushing pending product writes or changing status.

    NO KEY UPDATE serializes closure with local writers without conflicting with
    foreign-key KEY SHARE locks. Call before acquiring owned product row locks.
    """
    with db.no_autoflush:
        return db.scalar(
            select(Workspace)
            .where(Workspace.id == workspace_id)
            .with_for_update(key_share=True)
            .execution_options(populate_existing=True)
        )


def require_active_workspace(db: Session, workspace_id: int) -> Workspace:
    workspace = lock_workspace_row(db, workspace_id)
    if workspace is None or workspace.status != "active":
        raise ValueError("workspace unavailable")
    return workspace
