import re
from datetime import UTC, datetime
from secrets import token_urlsafe
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.dashboard.auth import require_dashboard_session, validate_csrf
from app.dashboard.intelligence import _workspace
from app.dashboard.router import page_context, templates
from app.database.session import get_db
from app.meta.reporting import connection_report
from app.meta.security import CONVERSION_ACTIONS, MetaError, callback_values, configuration_ready
from app.meta.service import ConnectionService
from app.meta.sync import MetaSyncService, syncing_allowed
from app.settings import settings
from app.workspaces.access import require_workspace_review
from app.workspaces.models import Workspace

router = APIRouter(prefix="/dashboard", dependencies=[Depends(require_dashboard_session)])
FLOW_COOKIE = "__Host-ad_analyzer_meta_oauth"
MESSAGES = {
    "authorized": "Meta authorization succeeded. Choose the client account and "
    "reporting event below.",
    "connected": "Meta account connected. Start the first import below; other data "
    "connections are optional.",
    "accounts": "Showing the next page of Meta ad accounts available to this authorization.",
    "disconnected": "Meta authorization removed. Previously imported metrics remain as "
    "historical snapshots. You can also revoke this app in Meta's "
    "business integrations settings.",
    "complete": "Meta import completed. The latest complete performance snapshot is available.",
    "syncing": "This import page is saved. Continue below or let the scheduled "
    "worker finish the remaining pages.",
    "disabled": "Meta imports are paused. Review the integration setup and "
    "workspace automation controls.",
    "up_to_date": "Meta data is already up to date.",
    "retry_later": "Meta import is waiting to retry. Check the connection status below.",
    "not_connected_or_busy": "This account needs a connection or another import is already "
    "running.",
    "refresh_failed": "Meta could not complete this refresh. Previous data is retained; "
    "review the connection status below.",
}


def _identity(request: Request) -> str:
    return str(getattr(request.state, "dashboard_identity", "local-operator")).casefold()


def _actor(request: Request) -> str:
    flow = request.cookies.get(FLOW_COOKIE, "")
    if not re.fullmatch(r"[A-Za-z0-9_-]{43}", flow):
        raise MetaError("invalid_oauth_state")
    return _identity(request) + "\0" + flow


async def _form(request: Request) -> dict[str, Any]:
    values = dict(await request.form(max_fields=8, max_files=0))
    request.scope["_form"] = values
    validate_csrf(request)
    return values


def _redirect(slug: str, notice: str) -> RedirectResponse:
    return RedirectResponse(f"/dashboard/workspaces/{slug}/meta?notice={notice}", status_code=303)


@router.get("/workspaces/{workspace_slug}/meta", response_class=HTMLResponse)
def overview(
    request: Request, workspace_slug: str, db: Annotated[Session, Depends(get_db)]
) -> HTMLResponse:
    workspace, role = _workspace(request, db, workspace_slug)
    editable = role in {"platform_admin", "owner", "admin"}
    configured = configuration_ready(settings)
    grant = (
        ConnectionService(db, settings).grant(workspace.id, _actor(request), datetime.now(UTC))
        if editable
        and configured
        and re.fullmatch(r"[A-Za-z0-9_-]{43}", request.cookies.get(FLOW_COOKIE, ""))
        else None
    )
    return templates.TemplateResponse(
        request,
        "meta.html",
        page_context(
            request,
            title=f"{workspace.name} · Meta ads",
            workspace=workspace,
            report=connection_report(db, workspace.id),
            configured=configured,
            can_edit=editable,
            enabled=syncing_allowed(db, workspace.id),
            notice=MESSAGES.get(request.query_params.get("notice", "")),
            accounts=grant.accounts if grant else [],
            accounts_pending=grant is not None,
            accounts_more=bool(grant and grant.cursor),
            conversion_actions=CONVERSION_ACTIONS,
        ),
    )


@router.post("/workspaces/{workspace_slug}/meta/connect")
async def connect(
    request: Request, workspace_slug: str, db: Annotated[Session, Depends(get_db)]
) -> HTMLResponse:
    workspace, _role = _workspace(request, db, workspace_slug, edit=True)
    await _form(request)
    flow = token_urlsafe(32)
    try:
        location = ConnectionService(db, settings).begin(
            workspace.id, _identity(request) + "\0" + flow, datetime.now(UTC)
        )
    except MetaError:
        raise HTTPException(
            422, "Unable to start Meta authorization. Check the integration setup."
        ) from None
    response = templates.TemplateResponse(
        request,
        "meta_authorize.html",
        page_context(
            request,
            title="Authorize Meta",
            workspace=workspace,
            authorization_url=location,
        ),
    )
    # The main dashboard session stays SameSite=Strict. This short-lived,
    # identity-bound cookie survives Meta's top-level OAuth return navigation.
    response.set_cookie(
        FLOW_COOKIE, flow, max_age=600, secure=True, httponly=True, samesite="lax", path="/"
    )
    return response


@router.get("/meta/callback")
def callback(request: Request, db: Annotated[Session, Depends(get_db)]) -> RedirectResponse:
    try:
        if not configuration_ready(settings):
            raise MetaError("meta_configuration_required")
        now = datetime.now(UTC)
        values = callback_values(request.query_params.multi_items())
        service = ConnectionService(db, settings)
        state = service.pending(values, _actor(request), now)
        role = require_workspace_review(request, db, state.workspace_id)
        workspace = db.get(Workspace, state.workspace_id)
        if workspace is None:
            raise MetaError("invalid_oauth_state")
        service.finish(state, values["code"], role, now)
        return _redirect(workspace.slug, "authorized")
    except MetaError:
        db.rollback()
        raise HTTPException(
            422, "Meta authorization could not be completed. Return to the workspace and reconnect."
        ) from None


@router.post("/workspaces/{workspace_slug}/meta/accounts/more")
async def more_accounts(
    request: Request, workspace_slug: str, db: Annotated[Session, Depends(get_db)]
) -> RedirectResponse:
    workspace, _role = _workspace(request, db, workspace_slug, edit=True)
    await _form(request)
    try:
        await run_in_threadpool(
            ConnectionService(db, settings).more_accounts,
            workspace.id,
            _actor(request),
            datetime.now(UTC),
        )
    except MetaError:
        db.rollback()
        raise HTTPException(
            422, "Unable to load more accounts. Return to Meta authorization and retry."
        ) from None
    return _redirect(workspace.slug, "accounts")


@router.post("/workspaces/{workspace_slug}/meta/select")
async def select_account(
    request: Request, workspace_slug: str, db: Annotated[Session, Depends(get_db)]
) -> RedirectResponse:
    workspace, role = _workspace(request, db, workspace_slug, edit=True)
    values = await _form(request)
    try:
        await run_in_threadpool(
            ConnectionService(db, settings).select_account,
            workspace.id,
            _actor(request),
            str(values.get("account_id", "")),
            str(values.get("conversion_action_type", "")),
            role,
            datetime.now(UTC),
        )
    except MetaError:
        db.rollback()
        raise HTTPException(
            422,
            "Unable to connect this account. Choose an authorized account not "
            "assigned to another workspace; disconnect an existing account "
            "before switching.",
        ) from None
    response = _redirect(workspace.slug, "connected")
    response.delete_cookie(FLOW_COOKIE, path="/", secure=True, httponly=True, samesite="lax")
    return response


@router.post("/workspaces/{workspace_slug}/meta/sync")
async def sync(
    request: Request, workspace_slug: str, db: Annotated[Session, Depends(get_db)]
) -> RedirectResponse:
    workspace, _role = _workspace(request, db, workspace_slug, edit=True)
    await _form(request)
    result = await run_in_threadpool(MetaSyncService(db, settings).page, workspace.id, manual=True)
    notice = result["status"] if result["status"] in MESSAGES else "refresh_failed"
    return _redirect(workspace.slug, notice)


@router.post("/workspaces/{workspace_slug}/meta/disconnect")
async def disconnect(
    request: Request, workspace_slug: str, db: Annotated[Session, Depends(get_db)]
) -> RedirectResponse:
    workspace, role = _workspace(request, db, workspace_slug, edit=True)
    await _form(request)
    ConnectionService(db, settings).disconnect(workspace.id, role)
    return _redirect(workspace.slug, "disconnected")
