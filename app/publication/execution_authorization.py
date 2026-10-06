"""Server-bound current authorization at each transaction's workspace-first boundary."""

from typing import Protocol

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.publication.service import owner
from app.workspaces.models import Workspace


class ExecutionAuthorizer(Protocol):
    def __call__(self, db: Session, workspace_id: int, actor: str, /) -> None:
        """API assembly binds its verified principal/session; never supplied by a customer."""
        ...


def owner_authorizer(db: Session, workspace_id: int, actor: str, /) -> None:
    """Internal offline default. Customer API runtimes must bind a fresh session guard.

    Lock order is workspace, user/session/membership (for API guards), then ledger,
    mandate and native account/source. The authorizer's locks live until commit.
    """
    if db.scalar(select(Workspace).where(Workspace.id == workspace_id).with_for_update()) is None:
        raise HTTPException(404, "workspace unavailable")
    owner(db, workspace_id, actor)
