import hashlib
import re
import time
from dataclasses import dataclass
from typing import Annotated
from urllib.parse import urlsplit

from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.customers.identity import IdentityProvider, denied, get_identity_provider, unavailable
from app.customers.models import CustomerMembership, CustomerSession, CustomerUser
from app.database.session import get_db
from app.settings import settings
from app.workspaces.models import Workspace

SESSION_COOKIE = "__Host-inlet_session"
CSRF_COOKIE = "__Host-inlet_csrf"
TTL_SECONDS = 8 * 60 * 60


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def valid_secret(value: str | None) -> bool:
    return value is not None and re.fullmatch(r"[A-Za-z0-9_-]{43}", value) is not None


def require_origin(request: Request) -> None:
    origin = settings.customer_app_origin
    parsed = urlsplit(origin)
    if (
        not origin
        or parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.path
        or parsed.query
        or parsed.fragment
    ):
        raise unavailable()
    if request.url.scheme != "https":
        raise HTTPException(status_code=403, detail="request rejected")
    if request.headers.getlist("origin") != [origin]:
        raise HTTPException(status_code=403, detail="request rejected")


@dataclass(frozen=True)
class CustomerPrincipal:
    user: CustomerUser
    session: CustomerSession


Database = Annotated[Session, Depends(get_db)]
Provider = Annotated[IdentityProvider, Depends(get_identity_provider)]


def require_customer(request: Request, db: Database, provider: Provider) -> CustomerPrincipal:
    presented = request.cookies.get(SESSION_COOKIE)
    if request.url.scheme != "https" or not valid_secret(presented):
        raise denied()
    row = db.get(CustomerSession, digest(presented or ""))
    if row is None or row.revoked_at is not None or row.expires_at <= int(time.time()):
        raise denied()
    user = db.get(CustomerUser, row.user_id)
    if user is None or user.status != "active" or user.issuer != provider.issuer:
        raise denied()
    # No authorization cache: provider suspension/revocation is checked on every request.
    provider.check_active(user.subject, row.authenticated_at)
    return CustomerPrincipal(user, row)


Principal = Annotated[CustomerPrincipal, Depends(require_customer)]


def require_customer_mutation(request: Request, principal: Principal) -> CustomerPrincipal:
    require_origin(request)
    supplied = request.headers.getlist("x-csrf-token")
    cookie = request.cookies.get(CSRF_COOKIE)
    if (
        len(supplied) != 1
        or not valid_secret(cookie)
        or supplied[0] != cookie
        or digest(supplied[0]) != principal.session.csrf_digest
    ):
        raise HTTPException(status_code=403, detail="request rejected")
    return principal


MutationPrincipal = Annotated[CustomerPrincipal, Depends(require_customer_mutation)]


def customer_workspaces(db: Session, user_id: str) -> list[tuple[Workspace, str]]:
    return list(
        db.execute(
            select(Workspace, CustomerMembership.role)
            .join(CustomerMembership, CustomerMembership.workspace_id == Workspace.id)
            .where(
                CustomerMembership.user_id == user_id,
                CustomerMembership.status == "active",
                Workspace.status == "active",
            )
            .order_by(Workspace.id)
        ).tuples()
    )


def customer_workspace(db: Session, user_id: str, workspace_id: int) -> tuple[Workspace, str]:
    result = (
        db.execute(
            select(Workspace, CustomerMembership.role)
            .join(CustomerMembership, CustomerMembership.workspace_id == Workspace.id)
            .where(
                Workspace.id == workspace_id,
                Workspace.status == "active",
                CustomerMembership.user_id == user_id,
                CustomerMembership.status == "active",
            )
        )
        .tuples()
        .one_or_none()
    )
    if result is None:
        raise HTTPException(status_code=404, detail="workspace not found")
    return result


def lock_customer_mutation(
    db: Session, principal: CustomerPrincipal, workspace_id: int, provider: IdentityProvider
) -> None:
    """Reauthorize at the mutation boundary, then fence local revocation until commit.

    Canonical order matches customer Shopify and login: workspace, user, session,
    membership. Call after receiving a body, before taking product/account locks.
    Never hold these locks while waiting for an untrusted request body.
    """
    db.scalar(
        select(Workspace)
        .where(Workspace.id == workspace_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    user = db.scalar(
        select(CustomerUser)
        .where(CustomerUser.id == principal.user.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    session = db.scalar(
        select(CustomerSession)
        .where(CustomerSession.digest == principal.session.digest)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if (
        user is None
        or user.status != "active"
        or user.issuer != provider.issuer
        or session is None
        or session.user_id != user.id
        or session.revoked_at is not None
        or session.expires_at <= int(time.time())
    ):
        raise denied()
    membership = db.scalar(
        select(CustomerMembership)
        .where(
            CustomerMembership.user_id == user.id,
            CustomerMembership.workspace_id == workspace_id,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if membership is None or membership.status != "active":
        raise HTTPException(404, "workspace not found")
    _, role = customer_workspace(db, user.id, workspace_id)
    if role not in {"owner", "admin"}:
        raise HTTPException(403, "insufficient role")
    provider.check_active(user.subject, session.authenticated_at)
    # Row locks fence revocation, but time can advance during lock/provider waits.
    if session.expires_at <= int(time.time()):
        raise denied()
