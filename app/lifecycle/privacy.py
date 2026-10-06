"""Shared transactional invalidation of snapshots; independent of workspace admission."""

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.workspaces.models import Workspace


def bump_workspace_export_revision(db: Session, workspace_id: int) -> None:
    """Call before native/store locks (or with this workspace already locked).

    No status filter: erasure/retention must work for closing or retained inactive
    workspaces. The caller owns commit. Rollback rolls back both deletion and fence.
    Every future destructive customer-data writer must join this contract.
    """
    owned = db.scalar(
        select(Workspace.id).where(Workspace.id == workspace_id).with_for_update(key_share=True)
    )
    if owned is None:
        raise ValueError("privacy workspace unavailable")
    from app.optimization_candidates.invalidation import erase_workspace_candidates

    erase_workspace_candidates(db, workspace_id)
    db.execute(
        update(Workspace)
        .where(Workspace.id == workspace_id)
        .values(export_privacy_revision=Workspace.export_privacy_revision + 1)
        .execution_options(synchronize_session=False)
    )


def workspace_export_revision(db: Session, workspace_id: int) -> int:
    revision = db.scalar(
        select(Workspace.export_privacy_revision).where(Workspace.id == workspace_id)
    )
    if revision is None:
        raise ValueError("privacy workspace unavailable")
    return revision
