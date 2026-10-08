"""Customer-reviewed simulated mandates. There are no live dispatch routes."""

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Response
from sqlalchemy import select

from app import advertising_capabilities
from app.customers.access import (
    Database,
    MutationPrincipal,
    Principal,
    Provider,
    customer_workspace,
    lock_customer_mutation,
)
from app.mandates import service as s
from app.mandates.models import Mandate, MandateAction
from app.mandates.schemas import (
    ActionDraft,
    ClaimInput,
    DispatchInput,
    MandateDefinition,
    MandateEdit,
    ReconcileInput,
    ReviewInput,
    RevisionInput,
)
from app.publication.service import owner

router = APIRouter(prefix="/api/customer/v1/workspaces/{workspace_id}/mandates", tags=["customer"])


def access(
    db: Database, user_id: str, wid: int, response: Response, permission: str = "read"
) -> None:
    _, role = customer_workspace(db, user_id, wid)
    response.headers["Cache-Control"] = "no-store"
    allowed = {
        "read": {"owner", "admin", "analyst", "viewer"},
        "draft": {"owner", "admin", "analyst"},
        "start": {"owner"},
        "stop": {"owner", "admin"},
    }
    if role not in allowed[permission]:
        raise HTTPException(403, "insufficient role")


def mutation_access(
    db: Database,
    principal: MutationPrincipal,
    provider: Provider,
    workspace_id: int,
    response: Response,
    permission: str,
) -> None:
    roles = {
        "draft": frozenset({"owner", "admin", "analyst"}),
        "start": frozenset({"owner"}),
        "stop": frozenset({"owner", "admin"}),
    }
    lock_customer_mutation(db, principal, workspace_id, provider, allowed_roles=roles[permission])
    access(db, principal.user.id, workspace_id, response, permission)


@router.post("", status_code=201)
def create(
    workspace_id: int,
    body: MandateDefinition,
    principal: MutationPrincipal,
    provider: Provider,
    db: Database,
    response: Response,
) -> dict[str, Any]:
    mutation_access(db, principal, provider, workspace_id, response, "draft")
    m = s.create(db, workspace_id, body, principal.user.id, datetime.now(UTC))
    db.commit()
    return s.view(db, m)


@router.get("")
def listing(
    workspace_id: int, principal: Principal, db: Database, response: Response
) -> list[dict[str, Any]]:
    access(db, principal.user.id, workspace_id, response)
    return [
        s.view(db, m)
        for m in db.scalars(select(Mandate).where(Mandate.workspace_id == workspace_id))
    ]


@router.get("/{mandate_id}")
def read(
    workspace_id: int, mandate_id: str, principal: Principal, db: Database, response: Response
) -> dict[str, Any]:
    access(db, principal.user.id, workspace_id, response)
    m = s.owned(db, workspace_id, mandate_id)
    return {
        **s.view(db, m),
        "actions": [
            s.action_view(a)
            for a in db.scalars(select(MandateAction).where(MandateAction.mandate_id == m.id))
        ],
    }


@router.put("/{mandate_id}")
def edit(
    workspace_id: int,
    mandate_id: str,
    body: MandateEdit,
    principal: MutationPrincipal,
    provider: Provider,
    db: Database,
    response: Response,
) -> dict[str, Any]:
    mutation_access(db, principal, provider, workspace_id, response, "draft")
    m = s.owned(db, workspace_id, mandate_id)
    s.edit(db, m, body.expected_revision, body.definition, principal.user.id, datetime.now(UTC))
    db.commit()
    return s.view(db, m)


@router.post("/{mandate_id}/approve")
@router.post("/{mandate_id}/resume")
def approve(
    workspace_id: int,
    mandate_id: str,
    body: RevisionInput,
    principal: MutationPrincipal,
    provider: Provider,
    db: Database,
    response: Response,
) -> dict[str, Any]:
    mutation_access(db, principal, provider, workspace_id, response, "start")
    m = s.owned(db, workspace_id, mandate_id)
    s.approve(db, m, body.expected_revision, principal.user.id, datetime.now(UTC))
    db.commit()
    return s.view(db, m)


@router.post("/{mandate_id}/stop/{operation}")
def stop(
    workspace_id: int,
    mandate_id: str,
    operation: str,
    principal: MutationPrincipal,
    provider: Provider,
    db: Database,
    response: Response,
) -> dict[str, Any]:
    if operation not in {"pause", "revoke"}:
        raise HTTPException(404, "unknown stop operation")
    mutation_access(db, principal, provider, workspace_id, response, "stop")
    m = s.owned(db, workspace_id, mandate_id)
    s.stop(db, m, principal.user.id, datetime.now(UTC), revoke=operation == "revoke")
    db.commit()
    return s.view(db, m)


@router.post("/{mandate_id}/actions", status_code=201)
def draft(
    workspace_id: int,
    mandate_id: str,
    body: ActionDraft,
    principal: MutationPrincipal,
    provider: Provider,
    db: Database,
    response: Response,
) -> dict[str, Any]:
    mutation_access(db, principal, provider, workspace_id, response, "draft")
    m = s.owned(db, workspace_id, mandate_id)
    a = s.draft(db, m, body, principal.user.id, datetime.now(UTC))
    db.commit()
    return s.action_view(a)


@router.post("/{mandate_id}/actions/{action_id}/review")
def review(
    workspace_id: int,
    mandate_id: str,
    action_id: str,
    body: ReviewInput,
    principal: MutationPrincipal,
    provider: Provider,
    db: Database,
    response: Response,
) -> dict[str, Any]:
    owner(db, workspace_id, principal.user.id)
    advertising_capabilities.require_advertising_write()
    mutation_access(db, principal, provider, workspace_id, response, "start")
    m = s.owned(db, workspace_id, mandate_id)
    a = s.action(db, m, action_id)
    s.review(db, m, a, body.draft_digest, principal.user.id, datetime.now(UTC))
    db.commit()
    return s.action_view(a)


@router.post("/{mandate_id}/actions/{action_id}/simulate/claim")
def claim(
    workspace_id: int,
    mandate_id: str,
    action_id: str,
    body: ClaimInput,
    principal: MutationPrincipal,
    provider: Provider,
    db: Database,
    response: Response,
) -> dict[str, Any]:
    owner(db, workspace_id, principal.user.id)
    advertising_capabilities.require_advertising_write()
    mutation_access(db, principal, provider, workspace_id, response, "start")
    m = s.owned(db, workspace_id, mandate_id)
    a = s.action(db, m, action_id)
    s.claim(db, m, a, body, principal.user.id, datetime.now(UTC))
    return s.action_view(a)


@router.post("/{mandate_id}/actions/{action_id}/simulate/dispatch")
def dispatch(
    workspace_id: int,
    mandate_id: str,
    action_id: str,
    body: DispatchInput,
    principal: MutationPrincipal,
    provider: Provider,
    db: Database,
    response: Response,
) -> dict[str, Any]:
    owner(db, workspace_id, principal.user.id)
    advertising_capabilities.require_advertising_write()
    mutation_access(db, principal, provider, workspace_id, response, "start")
    m = s.owned(db, workspace_id, mandate_id)
    a = s.action(db, m, action_id)
    s.dispatch(db, m, a, body.fence, body.evidence, principal.user.id, datetime.now(UTC))
    return s.action_view(a)


@router.post("/{mandate_id}/actions/{action_id}/simulate/reconcile")
def reconcile(
    workspace_id: int,
    mandate_id: str,
    action_id: str,
    body: ReconcileInput,
    principal: MutationPrincipal,
    provider: Provider,
    db: Database,
    response: Response,
) -> dict[str, Any]:
    mutation_access(db, principal, provider, workspace_id, response, "start")
    m = s.owned(db, workspace_id, mandate_id)
    a = s.action(db, m, action_id)
    s.reconcile(db, m, a, body, principal.user.id, datetime.now(UTC))
    db.commit()
    return s.action_view(a)


@router.post("/{mandate_id}/actions/{action_id}/cancel")
def cancel(
    workspace_id: int,
    mandate_id: str,
    action_id: str,
    principal: MutationPrincipal,
    provider: Provider,
    db: Database,
    response: Response,
) -> dict[str, Any]:
    mutation_access(db, principal, provider, workspace_id, response, "stop")
    m = s.owned(db, workspace_id, mandate_id)
    a = s.action(db, m, action_id)
    s.cancel(db, m, a, principal.user.id, datetime.now(UTC))
    db.commit()
    return s.action_view(a)
