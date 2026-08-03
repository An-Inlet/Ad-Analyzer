from fastapi import HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.settings import settings
from app.workspaces.models import WorkspaceMembership

_REVIEW_ROLES = {"owner", "admin"}


def _identity(request: Request) -> str | None:
    value = getattr(request.state, "dashboard_identity", None)
    return value.casefold() if isinstance(value, str) and value else None


def is_platform_admin(request: Request) -> bool:
    if settings.app_env.casefold() != "production":
        return True
    identity = _identity(request)
    return identity is not None and identity in settings.dashboard_allowed_emails


def accessible_workspace_ids(request: Request, session: Session) -> set[int] | None:
    """Return None for a platform administrator, otherwise active workspace IDs."""
    if is_platform_admin(request):
        return None
    identity = _identity(request)
    if identity is None:
        return set()
    return set(
        session.scalars(
            select(WorkspaceMembership.workspace_id).where(
                WorkspaceMembership.principal == identity,
                WorkspaceMembership.status == "active",
            )
        ).all()
    )


def workspace_role(request: Request, session: Session, workspace_id: int) -> str | None:
    if is_platform_admin(request):
        return "platform_admin"
    identity = _identity(request)
    if identity is None:
        return None
    return session.scalar(
        select(WorkspaceMembership.role).where(
            WorkspaceMembership.workspace_id == workspace_id,
            WorkspaceMembership.principal == identity,
            WorkspaceMembership.status == "active",
        )
    )


def require_workspace_view(request: Request, session: Session, workspace_id: int) -> str:
    role = workspace_role(request, session, workspace_id)
    if role is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="workspace not found")
    return role


def require_workspace_review(request: Request, session: Session, workspace_id: int) -> str:
    role = require_workspace_view(request, session, workspace_id)
    if role != "platform_admin" and role not in _REVIEW_ROLES:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="access denied")
    return role
