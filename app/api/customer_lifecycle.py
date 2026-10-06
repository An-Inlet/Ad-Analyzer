"""Explicit customer closure preview/confirmation; local-only, never a deletion claim."""

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import Field

from app.customers.access import Database, MutationPrincipal, Principal, Provider
from app.goals.schemas import StrictModel
from app.lifecycle.contracts import LifecycleInputV1, LifecycleScopeV1
from app.lifecycle.inventory import inventory
from app.lifecycle.models import LifecycleRequest, LifecycleStep
from app.lifecycle.quiescing import owner, preview_digest, quiesce
from app.lifecycle.service import begin, claim_inventory, finish_inventory

router = APIRouter(prefix="/api/customer/v1", tags=["customer"])


class PreviewInput(StrictModel):
    pass


class ConfirmInput(StrictModel):
    expected_revision: int = Field(strict=True, ge=1)
    inventory_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    confirm_workspace_id: int = Field(strict=True, gt=0)


def view(row: LifecycleRequest) -> dict[str, Any]:
    return {
        "schema_version": row.schema_version,
        "request_id": row.id,
        "scope": LifecycleScopeV1(workspace_id=row.workspace_id).model_dump(),
        "state": row.state,
        "revision": row.revision,
        "blockers": row.blockers,
        "disposition_policy": None,
        "closed": False,
        "data_erased": False,
        "provider_actions_verified": False,
    }


@router.post("/workspaces/{workspace_id}/closure-preview")
def preview(
    workspace_id: int,
    body: PreviewInput,
    request: Request,
    response: Response,
    principal: MutationPrincipal,
    provider: Provider,
    db: Database,
) -> dict[str, Any]:
    keys = request.headers.getlist("idempotency-key")
    if len(keys) != 1:
        raise HTTPException(422, "invalid idempotency key")
    now = datetime.now(UTC)
    row = begin(
        db,
        principal,
        provider,
        LifecycleInputV1(scope=LifecycleScopeV1(workspace_id=workspace_id), operation="close"),
        keys[0],
        now,
    )
    step = db.get(LifecycleStep, (row.id, "inventory"))
    if step is None:
        _, fence = claim_inventory(db, workspace_id, row.id, row.revision, now)
        evidence = preview_digest(db, workspace_id)
        finish_inventory(db, workspace_id, row.id, row.revision, fence, evidence, now)
    else:
        evidence = preview_digest(db, workspace_id)
        if step.state != "complete" or step.evidence_digest != evidence:
            raise HTTPException(409, "closure inventory changed; request a new preview")
    result = {
        **view(row),
        "inventory_digest": evidence,
        "inventory": inventory(db, LifecycleScopeV1(workspace_id=workspace_id)),
    }
    db.commit()
    response.headers["Cache-Control"] = "no-store"
    return result


@router.post("/workspaces/{workspace_id}/closures/{request_id}/confirm")
def confirm(
    workspace_id: int,
    request_id: str,
    body: ConfirmInput,
    response: Response,
    principal: MutationPrincipal,
    provider: Provider,
    db: Database,
) -> dict[str, Any]:
    if body.confirm_workspace_id != workspace_id:
        raise HTTPException(422, "explicit workspace confirmation required")
    row = quiesce(
        db,
        principal,
        provider,
        workspace_id,
        request_id,
        body.expected_revision,
        body.inventory_digest,
        datetime.now(UTC),
    )
    db.commit()
    response.headers["Cache-Control"] = "no-store"
    return view(row)


@router.get("/workspaces/{workspace_id}/closures/{request_id}")
def status(
    workspace_id: int,
    request_id: str,
    response: Response,
    principal: Principal,
    provider: Provider,
    db: Database,
) -> dict[str, Any]:
    owner(db, principal, provider, workspace_id)
    row = db.get(LifecycleRequest, request_id)
    if row is None or row.workspace_id != workspace_id or row.operation != "close":
        raise HTTPException(404, "closure request unavailable")
    response.headers["Cache-Control"] = "no-store"
    return view(row)
