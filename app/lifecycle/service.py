"""Package-one receipts and fenced inventory work. No closure effects or provider IO."""

import hashlib
import json
import re
from datetime import datetime, timedelta
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.customers.access import CustomerPrincipal, customer_workspace, lock_customer_mutation
from app.customers.identity import IdentityProvider
from app.lifecycle.contracts import LifecycleBlockerV1, LifecycleInputV1
from app.lifecycle.models import LifecycleRequest, LifecycleStep
from app.shopify.security import utc


def begin(
    db: Session,
    principal: CustomerPrincipal,
    provider: IdentityProvider,
    body: LifecycleInputV1,
    key: str,
    now: datetime,
) -> LifecycleRequest:
    if not re.fullmatch(r"[A-Za-z0-9_-]{16,128}", key):
        raise HTTPException(422, "invalid idempotency key")
    wid = body.scope.workspace_id
    if body.operation == "export":
        from app.lifecycle.quiescing import owner

        owner(db, principal, provider, wid)
    else:
        lock_customer_mutation(db, principal, wid, provider)
        if customer_workspace(db, principal.user.id, wid)[1] != "owner":
            raise HTTPException(403, "workspace owner required")
    key_digest = hashlib.sha256(key.encode()).hexdigest()
    request_digest = hashlib.sha256(
        json.dumps(body.model_dump(), sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    row = db.scalar(
        select(LifecycleRequest).where(
            LifecycleRequest.workspace_id == wid,
            LifecycleRequest.requested_by == principal.user.id,
            LifecycleRequest.operation == body.operation,
            LifecycleRequest.key_digest == key_digest,
        )
    )
    if row is not None:
        if row.request_digest != request_digest:
            raise HTTPException(409, "idempotency key already used")
        return row
    row = LifecycleRequest(
        id=uuid4().hex,
        workspace_id=wid,
        requested_by=principal.user.id,
        operation=body.operation,
        key_digest=key_digest,
        request_digest=request_digest,
        state="requested",
        revision=1,
        fence=uuid4().hex,
        disposition_policy=None,
        blockers=[
            LifecycleBlockerV1(
                code="retention_policy_unset", subsystem="lifecycle", resolution_kind="owner_policy"
            ).model_dump()
        ]
        if body.operation == "close"
        else [],
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    db.flush()
    # Caller owns commit, including any future atomic quiescing package.
    return row


def claim_inventory(
    db: Session,
    workspace_id: int,
    request_id: str,
    expected_revision: int,
    now: datetime,
) -> tuple[LifecycleStep, str]:
    from app.workspaces.models import Workspace

    db.scalar(select(Workspace).where(Workspace.id == workspace_id).with_for_update())
    request = db.scalar(
        select(LifecycleRequest)
        .where(
            LifecycleRequest.workspace_id == workspace_id,
            LifecycleRequest.id == request_id,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if request is None:
        raise HTTPException(404, "lifecycle request unavailable")
    if request.revision != expected_revision or request.state != "requested":
        raise HTTPException(409, "lifecycle request changed")
    step = db.get(LifecycleStep, (request.id, "inventory"), populate_existing=True)
    if step is not None and (
        step.state == "complete" or (step.lease_until is not None and utc(step.lease_until) > now)
    ):
        raise HTTPException(409, "inventory already claimed")
    fence = uuid4().hex
    request.fence, request.updated_at = fence, now
    if step is None:
        step = LifecycleStep(
            request_id=request.id,
            step_key="inventory",
            workspace_id=workspace_id,
            request_revision=request.revision,
            fence=fence,
            attempts=0,
        )
        db.add(step)
    step.state, step.fence = "running", fence
    step.request_revision = request.revision
    step.attempts += 1
    step.lease_until = now + timedelta(seconds=60)
    db.flush()
    return step, fence


def finish_inventory(
    db: Session,
    workspace_id: int,
    request_id: str,
    expected_revision: int,
    fence: str,
    evidence_digest: str,
    now: datetime,
) -> None:
    from app.workspaces.models import Workspace

    if not re.fullmatch(r"[a-f0-9]{64}", evidence_digest):
        raise HTTPException(422, "invalid evidence digest")
    db.scalar(select(Workspace).where(Workspace.id == workspace_id).with_for_update())
    request = db.scalar(
        select(LifecycleRequest)
        .where(
            LifecycleRequest.workspace_id == workspace_id,
            LifecycleRequest.id == request_id,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    step = db.get(LifecycleStep, (request_id, "inventory"), populate_existing=True)
    if (
        request is None
        or step is None
        or step.workspace_id != workspace_id
        or request.state != "requested"
        or request.revision != expected_revision
        or step.request_revision != expected_revision
        or request.fence != fence
        or step.fence != fence
    ):
        raise HTTPException(409, "stale lifecycle fence")
    if step.state == "complete":
        if step.evidence_digest != evidence_digest:
            raise HTTPException(409, "inventory evidence changed")
        return
    if step.state != "running" or step.lease_until is None or utc(step.lease_until) <= now:
        raise HTTPException(409, "lifecycle lease expired")
    step.state, step.evidence_digest, step.lease_until = "complete", evidence_digest, None
    request.updated_at = now
    # Completing inventory NEVER completes export delivery or account closure.
    db.flush()
