"""Atomic customer workspace provisioning with owner-bound replay receipts."""

import json
import re

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.customers.access import CustomerPrincipal, customer_workspace, digest
from app.customers.identity import denied
from app.customers.models import CustomerMembership, CustomerUser, WorkspaceSignup
from app.workspaces.models import Workspace, WorkspaceConfiguration


class WorkspaceSignupRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=255)
    slug: str = Field(min_length=3, max_length=64, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def provision_workspace(
    db: Session,
    principal: CustomerPrincipal,
    key: str,
    body: WorkspaceSignupRequest,
) -> tuple[Workspace, bool]:
    if not re.fullmatch(r"[A-Za-z0-9_-]{16,128}", key):
        raise HTTPException(422, "invalid idempotency key")
    fingerprint = digest(json.dumps(body.model_dump(), sort_keys=True, separators=(",", ":")))
    # Serialize signups for one internal user across replicas. No email-based ownership.
    user = db.scalar(
        select(CustomerUser)
        .where(CustomerUser.id == principal.user.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if user is None or user.status != "active":
        raise denied()
    receipt = db.get(WorkspaceSignup, (user.id, digest(key)))
    if receipt is not None:
        if receipt.request_digest != fingerprint:
            raise HTTPException(409, "idempotency key already used")
        workspace, role = customer_workspace(db, user.id, receipt.workspace_id)
        if role != "owner":
            raise HTTPException(409, "workspace ownership changed")
        return workspace, False
    workspace = Workspace(
        slug=body.slug, name=body.name, client_name=body.name, status="active", is_default=False
    )
    try:
        db.add(workspace)
        db.flush()
        db.add(
            WorkspaceConfiguration(
                workspace_id=workspace.id,
                analysis={},
                automation={"live_writes_enabled": False},
                notifications={},
                branding={"workspace_name": body.name},
            )
        )
        db.add(
            CustomerMembership(
                user_id=user.id, workspace_id=workspace.id, role="owner", status="active"
            )
        )
        db.add(
            WorkspaceSignup(
                user_id=user.id,
                key_digest=digest(key),
                workspace_id=workspace.id,
                request_digest=fingerprint,
            )
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "workspace signup conflict") from None
    return workspace, True
