"""Session-bound Google setup. Runtime transport fails closed until separately released."""

from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import Field
from sqlalchemy import select

from app.customers.access import Database, MutationPrincipal, Principal, customer_workspace
from app.goals.schemas import StrictModel
from app.google_connections import service as s
from app.google_connections.contracts import GoogleReadTransport, get_transport
from app.google_connections.models import GoogleCustomerConnection

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
) -> dict[str, Any]:
    now = datetime.now(UTC)
    row = s.authorization(db, body.state, principal.session.digest, now)
    access(db, principal.user.id, row.workspace_id, response, write=True)
    row = s.finish(db, body.state, principal.session.digest, body.code, now, transport)
    return {"accounts": row.accounts, "workspace_id": row.workspace_id, "mode": "fixture"}


@router.post("/workspaces/{workspace_id}/google/select")
def choose(
    workspace_id: int,
    body: Selection,
    principal: MutationPrincipal,
    db: Database,
    response: Response,
) -> dict[str, Any]:
    access(db, principal.user.id, workspace_id, response, write=True)
    row = s.authorization(db, body.state, principal.session.digest, datetime.now(UTC))
    if row.workspace_id != workspace_id:
        raise HTTPException(404, "authorization unavailable")
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
    access(db, principal.user.id, workspace_id, response, write=True)
    row = s.owned(db, workspace_id, connection_id)
    s.disconnect(db, row)
    return s.view(row)


@router.get("/google/callback")
def browser_callback() -> Response:
    # The existing Strict session cookie is not sent on the cross-site redirect.
    # Relay from this same-origin document; POST checks session, Origin, CSRF and state.
    from fastapi.responses import HTMLResponse

    html = """<!doctype html><html lang="en"><meta charset="utf-8">
<title>Connect Google Ads — Inlet</title><h1>Connect Google Ads</h1>
<p id="result">Completing authorization…</p>
<script>
const params = new URLSearchParams(location.search);
history.replaceState(null, '', location.pathname);
sessionStorage.setItem('inlet-google-state', params.get('state') || '');
const csrf = document.cookie.split('; ').find(x => x.startsWith('__Host-inlet_csrf='));
fetch(location.pathname, {method:'POST', credentials:'same-origin',
  headers:{'Content-Type':'application/json','X-CSRF-Token':csrf ? csrf.split('=')[1] : ''},
  body:JSON.stringify({state:params.get('state'),code:params.get('code')})})
.then(async r => {const data = await r.json();
  document.getElementById('result').textContent = r.ok
    ? 'Authorization received. Return to Connections to select an account.'
    : 'Connection unavailable. Return to Connections and try again.';
}).catch(() => {
  document.getElementById('result').textContent='Connection unavailable. Please restart.';
});
</script></html>"""
    return HTMLResponse(
        html,
        headers={
            "Cache-Control": "no-store",
            "Referrer-Policy": "no-referrer",
            "X-Frame-Options": "DENY",
        },
    )


class PendingSelection(StrictModel):
    state: str = Field(pattern=r"^[A-Za-z0-9_-]{43}$")


@router.post("/google/accounts")
def accounts(
    body: PendingSelection, principal: MutationPrincipal, db: Database, response: Response
) -> dict[str, Any]:
    row = s.authorization(db, body.state, principal.session.digest, datetime.now(UTC))
    access(db, principal.user.id, row.workspace_id, response, write=True)
    if row.state != "select_account":
        raise HTTPException(409, "account selection unavailable")
    return {"accounts": row.accounts, "workspace_id": row.workspace_id, "mode": "fixture"}
