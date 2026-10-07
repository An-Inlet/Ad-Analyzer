"""Customer API: never accepts operator tokens, IAP headers, or email membership."""

import time
from secrets import token_urlsafe
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field, SecretStr
from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError

from app.customers.access import (
    CSRF_COOKIE,
    SESSION_COOKIE,
    TTL_SECONDS,
    Database,
    MutationPrincipal,
    Principal,
    Provider,
    customer_workspace,
    customer_workspaces,
    digest,
    require_origin,
)
from app.customers.identity import denied
from app.customers.models import CustomerSession, CustomerTokenExchange, CustomerUser
from app.customers.provisioning import WorkspaceSignupRequest, provision_workspace

router = APIRouter(prefix="/api/customer/v1", tags=["customer"])


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id_token: SecretStr = Field(min_length=1, max_length=16384)


class SessionResponse(BaseModel):
    user_id: str
    email: str
    expires_at: int


class WorkspaceResponse(BaseModel):
    id: int
    slug: str
    name: str
    role: str


@router.post("/session", response_model=SessionResponse)
def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    db: Database,
    provider: Provider,
    _origin: Annotated[None, Depends(require_origin)],
) -> SessionResponse:
    if request.headers.getlist("x-inlet-request") != ["1"]:
        raise HTTPException(status_code=403, detail="request rejected")
    identity = provider.verify(body.id_token.get_secret_value())
    now = int(time.time())
    receipt = digest(body.id_token.get_secret_value())
    if db.get(CustomerTokenExchange, receipt) is not None:
        raise denied()
    user = db.scalar(
        select(CustomerUser).where(
            CustomerUser.issuer == identity.issuer, CustomerUser.subject == identity.subject
        )
    )
    if user is None:
        user = CustomerUser(
            id=uuid4().hex,
            issuer=identity.issuer,
            subject=identity.subject,
            email=identity.email,
            status="active",
        )
        db.add(user)
    if user.status != "active":
        raise denied()
    user.email = identity.email  # Contact data only; never used to claim memberships.
    secret, csrf = token_urlsafe(32), token_urlsafe(32)
    row = CustomerSession(
        digest=digest(secret),
        user_id=user.id,
        csrf_digest=digest(csrf),
        created_at=now,
        expires_at=now + TTL_SECONDS,
        authenticated_at=identity.authenticated_at,
    )
    try:
        db.flush()
        db.execute(delete(CustomerTokenExchange).where(CustomerTokenExchange.expires_at <= now))
        db.add(CustomerTokenExchange(digest=receipt, expires_at=identity.expires_at))
        # Rotate any session presented during login, even when switching identities.
        old = request.cookies.get(SESSION_COOKIE)
        if old:
            db.execute(
                update(CustomerSession)
                .where(CustomerSession.digest == digest(old))
                .values(revoked_at=now)
            )
        db.add(row)
        db.commit()
    except IntegrityError:
        db.rollback()
        # Concurrent replay/user creation fails closed; client retries with a fresh token.
        raise denied() from None
    for name, value, http_only in [(SESSION_COOKIE, secret, True), (CSRF_COOKIE, csrf, False)]:
        response.set_cookie(
            name,
            value,
            max_age=TTL_SECONDS,
            secure=True,
            httponly=http_only,
            samesite="strict",
            path="/",
        )
    response.headers["Cache-Control"] = "no-store"
    return SessionResponse(user_id=user.id, email=user.email, expires_at=row.expires_at)


@router.get("/session", response_model=SessionResponse)
def session_status(principal: Principal, response: Response) -> SessionResponse:
    response.headers["Cache-Control"] = "no-store"
    return SessionResponse(
        user_id=principal.user.id,
        email=principal.user.email,
        expires_at=principal.session.expires_at,
    )


@router.delete("/session", status_code=204)
def logout(principal: MutationPrincipal, db: Database, response: Response) -> None:
    principal.session.revoked_at = int(time.time())
    db.commit()
    for name in (SESSION_COOKIE, CSRF_COOKIE):
        response.delete_cookie(name, path="/", secure=True, samesite="strict")
    response.headers["Cache-Control"] = "no-store"


@router.get("/workspaces", response_model=list[WorkspaceResponse])
def list_workspaces(principal: Principal, db: Database) -> list[WorkspaceResponse]:
    return [
        WorkspaceResponse(id=w.id, slug=w.slug, name=w.name, role=role)
        for w, role in customer_workspaces(db, principal.user.id)
    ]


@router.get("/workspaces/{workspace_id}", response_model=WorkspaceResponse)
def get_workspace(workspace_id: int, principal: Principal, db: Database) -> WorkspaceResponse:
    workspace, role = customer_workspace(db, principal.user.id, workspace_id)
    return WorkspaceResponse(id=workspace.id, slug=workspace.slug, name=workspace.name, role=role)


@router.post("/workspaces", response_model=WorkspaceResponse, status_code=201)
def signup_workspace(
    body: WorkspaceSignupRequest,
    request: Request,
    response: Response,
    principal: MutationPrincipal,
    db: Database,
) -> WorkspaceResponse:
    keys = request.headers.getlist("idempotency-key")
    if len(keys) != 1:
        raise HTTPException(422, "invalid idempotency key")
    workspace, created = provision_workspace(db, principal, keys[0], body)
    response.status_code = 201 if created else 200
    return WorkspaceResponse(
        id=workspace.id, slug=workspace.slug, name=workspace.name, role="owner"
    )
