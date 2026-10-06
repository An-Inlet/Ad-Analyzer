"""Session-bound Google setup. Runtime transport fails closed until separately released."""

from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import FileResponse
from pydantic import Field
from sqlalchemy import select

from app.customers.access import (
    Database,
    MutationPrincipal,
    Principal,
    Provider,
    customer_workspace,
    guard_customer_mutation,
)
from app.goals.schemas import StrictModel
from app.google_connections import service as s
from app.google_connections.contracts import GoogleReadTransport, get_transport
from app.google_connections.models import GoogleCustomerConnection
from app.settings import settings

router = APIRouter(prefix="/api/customer/v1", tags=["customer"])
Transport = Annotated[GoogleReadTransport, Depends(get_transport)]


class Callback(StrictModel):
    state: str = Field(pattern=r"^[A-Za-z0-9_-]{43}$")
    code: str = Field(min_length=1, max_length=4096)


class Selection(StrictModel):
    state: str = Field(pattern=r"^[A-Za-z0-9_-]{43}$")
    external_account_id: str = Field(pattern=r"^[0-9]{10}$")


def access(db: Database, uid: str, wid: int, response: Response, *, write: bool) -> None:
    _, role = customer_workspace(db, uid, wid)
    if write and role not in {"owner", "admin"}:
        raise HTTPException(403, "insufficient role")
    response.headers["Cache-Control"] = "no-store"


@router.post("/workspaces/{workspace_id}/google/authorize")
def authorize(
    workspace_id: int,
    principal: MutationPrincipal,
    db: Database,
    response: Response,
    transport: Transport,
) -> dict[str, Any]:
    guard_customer_mutation(db, principal, workspace_id)
    access(db, principal.user.id, workspace_id, response, write=True)
    return {
        "authorization_url": s.start(
            db, workspace_id, principal.session.digest, datetime.now(UTC), transport
        ),
        "live_verified": False,
    }


@router.post("/google/callback")
def callback(
    body: Callback,
    principal: MutationPrincipal,
    db: Database,
    response: Response,
    transport: Transport,
    provider: Provider,
) -> dict[str, Any]:
    now = datetime.now(UTC)
    row = s.authorization(db, body.state, principal.session.digest, now, lock=False)
    wid = row.workspace_id
    guard_customer_mutation(db, principal, wid)
    access(db, principal.user.id, row.workspace_id, response, write=True)

    def recheck() -> None:
        guard_customer_mutation(db, principal, wid)
        provider.check_active(principal.user.subject, principal.session.authenticated_at)
        s.authorization(db, body.state, principal.session.digest, datetime.now(UTC))

    row = s.finish(
        db, body.state, principal.session.digest, body.code, now, transport, before_persist=recheck
    )
    return {
        "accounts": row.accounts,
        "workspace_id": row.workspace_id,
        "mode": transport.mode,
        "live_verified": False,
    }


@router.post("/workspaces/{workspace_id}/google/select")
def choose(
    workspace_id: int,
    body: Selection,
    principal: MutationPrincipal,
    db: Database,
    response: Response,
) -> dict[str, Any]:
    access(db, principal.user.id, workspace_id, response, write=True)
    row = s.authorization(db, body.state, principal.session.digest, datetime.now(UTC), lock=False)
    if row.workspace_id != workspace_id:
        raise HTTPException(404, "authorization unavailable")
    guard_customer_mutation(db, principal, workspace_id)
    return s.view(
        s.choose(
            db, body.state, principal.session.digest, body.external_account_id, datetime.now(UTC)
        )
    )


@router.get("/workspaces/{workspace_id}/google/connections")
def listing(
    workspace_id: int, principal: Principal, db: Database, response: Response
) -> list[dict[str, Any]]:
    access(db, principal.user.id, workspace_id, response, write=False)
    return [
        s.view(row)
        for row in db.scalars(
            select(GoogleCustomerConnection).where(
                GoogleCustomerConnection.workspace_id == workspace_id
            )
        )
    ]


@router.delete("/workspaces/{workspace_id}/google/connections/{connection_id}")
def disconnect(
    workspace_id: int,
    connection_id: str,
    principal: MutationPrincipal,
    db: Database,
    response: Response,
) -> dict[str, Any]:
    guard_customer_mutation(db, principal, workspace_id)
    access(db, principal.user.id, workspace_id, response, write=True)
    row = s.owned(db, workspace_id, connection_id)
    s.disconnect(db, row)
    return s.view(row)


@router.get("/google/callback")
def browser_callback() -> Response:
    return FileResponse(
        Path(__file__).parents[1] / "portal" / "static" / "google-callback.html",
        media_type="text/html",
        headers={
            "Cache-Control": "no-store",
            "Referrer-Policy": "no-referrer",
            "X-Frame-Options": "DENY",
            "Content-Security-Policy": (
                "default-src 'none'; script-src 'self'; style-src 'self'; "
                "connect-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
            ),
        },
    )


class PendingSelection(StrictModel):
    state: str = Field(pattern=r"^[A-Za-z0-9_-]{43}$")


@router.post("/google/accounts")
def accounts(
    body: PendingSelection, principal: MutationPrincipal, db: Database, response: Response
) -> dict[str, Any]:
    row = s.authorization(db, body.state, principal.session.digest, datetime.now(UTC), lock=False)
    guard_customer_mutation(db, principal, row.workspace_id)
    row = s.authorization(db, body.state, principal.session.digest, datetime.now(UTC))
    access(db, principal.user.id, row.workspace_id, response, write=True)
    if row.state != "select_account":
        raise HTTPException(409, "account selection unavailable")
    return {"accounts": row.accounts, "workspace_id": row.workspace_id, "mode": "fixture"}


@router.get("/workspaces/{workspace_id}/google/setup")
def setup_status(
    workspace_id: int, principal: Principal, db: Database, transport: Transport, response: Response
) -> dict[str, Any]:
    _, role = customer_workspace(db, principal.user.id, workspace_id)
    response.headers["Cache-Control"] = "no-store"
    try:
        s.ready(transport)
        callback = s.redirect_uri()
        enabled = bool(settings.google_customer_client_id)
    except HTTPException:
        callback, enabled = "", False
    return {
        "enabled": enabled,
        "can_manage": role in {"owner", "admin"},
        "client_id": settings.google_customer_client_id if enabled else "",
        "redirect_uri": callback,
    }
