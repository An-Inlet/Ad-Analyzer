"""Revocable-session Meta onboarding, separate from operator authentication."""

from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import FileResponse
from pydantic import Field

from app.customers.access import (
    Database,
    MutationPrincipal,
    Principal,
    Provider,
    customer_workspace,
    guard_customer_mutation,
)
from app.goals.schemas import StrictModel
from app.meta import customer as flow
from app.meta.client import MetaClient
from app.meta.reporting import connection_report
from app.meta.security import API_VERSION, CONVERSION_ACTIONS, MetaError, configuration_ready
from app.meta.service import ConnectionService
from app.settings import Settings, settings

router = APIRouter(prefix="/api/customer/v1", tags=["customer"])


def configuration() -> Settings:
    parsed = urlsplit(settings.customer_app_origin)
    if (
        not settings.meta_customer_enabled
        or parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.path
        or parsed.query
        or parsed.fragment
    ):
        raise HTTPException(503, "Meta customer setup unavailable")
    result = settings.model_copy(
        update={
            "meta_redirect_uri": settings.customer_app_origin + "/api/customer/v1/meta/callback"
        }
    )
    if not configuration_ready(result, customer=True):
        raise HTTPException(503, "Meta customer setup unavailable")
    return result


def get_customer_meta_client() -> MetaClient:
    return MetaClient(configuration())


Client = Annotated[MetaClient, Depends(get_customer_meta_client)]


class State(StrictModel):
    state: str = Field(pattern=r"^[A-Za-z0-9_-]{43}$")


class Callback(State):
    code: str = Field(min_length=1, max_length=4096)


class Selection(State):
    external_account_id: str = Field(pattern=r"^[0-9]{1,32}$")
    conversion_action_type: str = Field(max_length=64)


def unavailable(error: MetaError) -> HTTPException:
    status = (
        409
        if error.code
        in {"invalid_oauth_state", "meta_authorization_expired", "meta_disconnect_existing_first"}
        else 422
    )
    return HTTPException(status, "Meta connection unavailable; return to Inlet and start again")


def accounts_view(grant: Any, wid: int) -> dict[str, Any]:
    return {
        "workspace_id": wid,
        "accounts": grant.accounts,
        "has_more": bool(grant.cursor),
        "conversion_actions": CONVERSION_ACTIONS,
        "live_verified": False,
    }


@router.get("/workspaces/{workspace_id}/meta/setup")
def setup(
    workspace_id: int, principal: Principal, db: Database, response: Response
) -> dict[str, Any]:
    _, role = customer_workspace(db, principal.user.id, workspace_id)
    response.headers["Cache-Control"] = "no-store"
    try:
        configured = configuration()
    except HTTPException:
        configured = None
    return {
        "enabled": configured is not None,
        "can_manage": role in {"owner", "admin"},
        "client_id": configured.meta_client_id if configured else "",
        "redirect_uri": configured.meta_redirect_uri if configured else "",
        "authorization_endpoint": f"https://www.facebook.com/{API_VERSION}/dialog/oauth",
        "conversion_actions": CONVERSION_ACTIONS,
        "account_limit": 1,
    }


@router.post("/workspaces/{workspace_id}/meta/authorize")
def authorize(
    workspace_id: int, principal: MutationPrincipal, db: Database, client: Client
) -> dict[str, Any]:
    guard_customer_mutation(db, principal, workspace_id)
    try:
        url = ConnectionService(db, configuration(), client).begin(
            workspace_id, principal.session.digest, datetime.now(UTC), customer=True
        )
    except MetaError as exc:
        raise unavailable(exc) from None
    return {"authorization_url": url, "live_verified": False}


@router.get("/meta/callback")
def browser_callback() -> Response:
    return FileResponse(
        Path(__file__).parents[1] / "portal" / "static" / "meta-callback.html",
        media_type="text/html",
        headers={
            "Cache-Control": "no-store",
            "Referrer-Policy": "no-referrer",
            "X-Frame-Options": "DENY",
            "Content-Security-Policy": (
                "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; "
                "base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
            ),
        },
    )


@router.post("/meta/callback")
def callback(
    body: Callback, principal: MutationPrincipal, db: Database, client: Client, provider: Provider
) -> dict[str, Any]:
    service = ConnectionService(db, configuration(), client)
    try:
        pending = service.pending(
            {"state": body.state}, principal.session.digest, datetime.now(UTC)
        )
        wid = pending.workspace_id

        def guard() -> None:
            guard_customer_mutation(db, principal, wid)
            provider.check_active(principal.user.subject, principal.session.authenticated_at)

        guard()
        _, role = customer_workspace(db, principal.user.id, wid)
        flow.finish(service, pending, body.code, role, lambda: datetime.now(UTC), guard)
        grant = flow.bound_grant(
            service, wid, principal.session.digest, body.state, datetime.now(UTC)
        )
        return accounts_view(grant, wid)
    except MetaError as exc:
        raise unavailable(exc) from None


@router.post("/workspaces/{workspace_id}/meta/accounts")
def more(
    workspace_id: int,
    body: State,
    principal: MutationPrincipal,
    db: Database,
    client: Client,
    provider: Provider,
) -> dict[str, Any]:
    service = ConnectionService(db, configuration(), client)

    def guard() -> None:
        guard_customer_mutation(db, principal, workspace_id)
        provider.check_active(principal.user.subject, principal.session.authenticated_at)

    guard()
    try:
        grant = flow.more_accounts(
            service,
            workspace_id,
            principal.session.digest,
            body.state,
            lambda: datetime.now(UTC),
            guard,
        )
        return accounts_view(grant, workspace_id)
    except MetaError as exc:
        raise unavailable(exc) from None


@router.post("/workspaces/{workspace_id}/meta/select")
def select_account(
    workspace_id: int,
    body: Selection,
    principal: MutationPrincipal,
    db: Database,
    client: Client,
    provider: Provider,
) -> dict[str, Any]:
    service = ConnectionService(db, configuration(), client)

    def guard() -> None:
        guard_customer_mutation(db, principal, workspace_id)
        provider.check_active(principal.user.subject, principal.session.authenticated_at)
        flow.bound_grant(
            service, workspace_id, principal.session.digest, body.state, datetime.now(UTC)
        )

    try:
        guard()
        _, role = customer_workspace(db, principal.user.id, workspace_id)
        row = service.select_account(
            workspace_id,
            principal.session.digest,
            body.external_account_id,
            body.conversion_action_type,
            role,
            datetime.now(UTC),
            before_persist=guard,
        )
        return {"workspace_id": workspace_id, "generation": row.generation, "live_verified": False}
    except MetaError as exc:
        raise unavailable(exc) from None


@router.get("/workspaces/{workspace_id}/meta")
def listing(
    workspace_id: int, principal: Principal, db: Database, response: Response
) -> dict[str, Any]:
    customer_workspace(db, principal.user.id, workspace_id)
    response.headers["Cache-Control"] = "no-store"
    return {**connection_report(db, workspace_id), "live_verified": False}


@router.delete("/workspaces/{workspace_id}/meta")
def disconnect(workspace_id: int, principal: MutationPrincipal, db: Database) -> Response:
    role = guard_customer_mutation(db, principal, workspace_id)
    ConnectionService(db, settings).disconnect(workspace_id, role)
    return Response(status_code=204)
