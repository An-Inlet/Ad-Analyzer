"""Serialize native Meta changes with workspace-first mandate and campaign review."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.workspaces.models import Workspace


def lock_workspace(db: Session, workspace_id: int, *, skip_locked: bool = False) -> bool:
    # NO KEY UPDATE serializes competing owners without blocking foreign-key KEY
    # SHARE locks. Do not reject suspended workspaces here: disconnect remains
    # available, and imports retain their existing ownership/status checks.
    return (
        db.scalar(
            select(Workspace.id)
            .where(Workspace.id == workspace_id)
            .with_for_update(key_share=True, skip_locked=skip_locked)
        )
        is not None
    )
