"""Atomic local closure fence. No fact/media purge, provider revocation or billing calls."""

import hashlib
import json
import time
from datetime import datetime
from typing import Any
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.customers.access import CustomerPrincipal
from app.customers.identity import IdentityProvider, denied
from app.customers.models import CustomerMembership, CustomerSession, CustomerUser
from app.database.session import Base
from app.lifecycle.contracts import LifecycleBlockerV1, LifecycleScopeV1
from app.lifecycle.inventory import inventory, predicate
from app.lifecycle.local_work import cancel_analysis_queue
from app.lifecycle.models import LifecycleRequest, LifecycleStep
from app.workspaces.locking import lock_workspace_row
from app.workspaces.models import Workspace


def owner(
    db: Session,
    principal: CustomerPrincipal,
    provider: IdentityProvider,
    wid: int,
) -> Workspace:
    """Dedicated receipt/closure authority; never grants normal access to closing workspaces."""
    workspace = lock_workspace_row(db, wid)
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
    member = db.scalar(
        select(CustomerMembership)
        .where(
            CustomerMembership.user_id == principal.user.id, CustomerMembership.workspace_id == wid
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if (
        user is None
        or session is None
        or user.status != "active"
        or user.issuer != provider.issuer
        or session.user_id != user.id
        or session.revoked_at is not None
    ):
        raise denied()
    if (
        workspace is None
        or workspace.status not in {"active", "closing"}
        or member is None
        or member.status != "active"
    ):
        raise HTTPException(404, "workspace unavailable")
    if member.role != "owner":
        raise HTTPException(403, "workspace owner required")
    provider.check_active(user.subject, session.authenticated_at)
    if session.expires_at <= int(time.time()):
        raise denied()
    return workspace


def preview_digest(db: Session, wid: int) -> str:
    evidence = inventory(db, LifecycleScopeV1(workspace_id=wid))
    return hashlib.sha256(
        json.dumps(evidence, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def quiesce(
    db: Session,
    principal: CustomerPrincipal,
    provider: IdentityProvider,
    wid: int,
    request_id: str,
    expected_revision: int,
    confirmed_inventory_digest: str,
    now: datetime,
) -> LifecycleRequest:
    workspace = owner(db, principal, provider, wid)
    request = db.scalar(
        select(LifecycleRequest)
        .where(LifecycleRequest.id == request_id, LifecycleRequest.workspace_id == wid)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if request is None or request.operation != "close" or request.requested_by != principal.user.id:
        raise HTTPException(404, "closure request unavailable")
    step = db.get(LifecycleStep, (request.id, "inventory"), populate_existing=True)
    if (
        step is None
        or step.state != "complete"
        or step.evidence_digest != confirmed_inventory_digest
        or step.request_revision != expected_revision
    ):
        raise HTTPException(409, "confirmed closure inventory required")
    if (
        workspace.status == "closing"
        and request.state == "blocked"
        and request.revision == expected_revision + 1
    ):
        return request
    if (
        request.state != "requested"
        or request.revision != expected_revision
        or workspace.status != "active"
    ):
        raise HTTPException(409, "closure request changed")
    if preview_digest(db, wid) != confirmed_inventory_digest:
        raise HTTPException(409, "closure inventory changed")
    scope = LifecycleScopeV1(workspace_id=wid)
    # The workspace lock fences admission; all modifications are in this one transaction.
    from app.lifecycle.privacy import bump_workspace_export_revision

    bump_workspace_export_revision(db, workspace.id)
    automations = Base.metadata.tables["session_automation_runs"]
    db.execute(
        update(automations)
        .where(automations.c.workspace_id == wid, automations.c.stopped_at.is_(None))
        .values(
            state="stopped",
            reason="customer_stopped",
            stopped_at=now,
            stopped_by=principal.user.id,
        )
    )
    workspace.status = "closing"
    db.flush()
    for name in (
        "google_customer_authorizations",
        "customer_source_authorizations",
        "meta_oauth_states",
        "meta_pending_grants",
        "shopify_oauth_states",
    ):
        table = Base.metadata.tables[name]
        db.execute(delete(table).where(predicate(name, scope)))
    values: dict[str, dict[str, Any]] = {
        "workspace_integrations": {"status": "revoked", "secret_manager_reference": None},
        "crm_connections": {"status": "closed", "secret_manager_reference": ""},
        "google_customer_connections": {
            "status": "disconnected",
            "encrypted_grant": None,
            "cursor": None,
            "staged": {},
            "next_attempt_at": None,
        },
        "customer_source_connections": {
            "status": "disconnected",
            "encrypted_grant": None,
            "cursor": None,
            "staged": {},
            "next_attempt_at": None,
        },
        "meta_connections": {
            "status": "reconnect_required",
            "encrypted_credentials": "",
            "cursor": None,
            "next_attempt_at": None,
        },
        "shopify_connections": {
            "status": "reconnect_required",
            "encrypted_credentials": "",
            "cursor": None,
            "next_attempt_at": None,
        },
        "customer_context_checkpoints": {
            "state": "closed",
            "encrypted_progress": "",
            "fence": None,
            "lease_until": None,
            "ack_digest": None,
        },
        "workspace_automation_controls": {"enabled": False},
        "spending_mandates": {"paused": True},
        "provider_execution_mandates": {"state": "revoked"},
        "mandate_actions": {"cancel_requested": True},
    }
    for name, changes in values.items():
        table = Base.metadata.tables[name]
        if name in {
            "google_customer_connections",
            "customer_source_connections",
            "meta_connections",
        }:
            changes["generation"] = table.c.generation + 1
        db.execute(update(table).where(predicate(name, scope)).values(**changes))
    # Cancel only future provider steps. Original attempts/receipts and exposure remain;
    # a late readback may append evidence but must never revive a creation run.
    executions = Base.metadata.tables["provider_execution_runs"]
    db.execute(
        update(executions)
        .where(predicate("provider_execution_runs", scope), executions.c.canceled_at.is_(None))
        .values(state="canceled", canceled_at=now)
    )
    # Preserve worker state, monetary reservations, all facts and media. They are not
    # evidence of cancellation merely because normal admission is now disabled.
    request.state, request.revision, request.fence = "blocked", request.revision + 1, uuid4().hex
    request.updated_at = now
    cancel_analysis_queue(db, request)
    pending_blockers = [
        LifecycleBlockerV1(code=code, subsystem=subsystem, resolution_kind=kind).model_dump()
        for code, subsystem, kind in [
            ("retention_policy_unset", "lifecycle", "owner_policy"),
            ("provider_revocation_unverified", "connections", "operator_evidence"),
            ("billing_unresolved", "billing", "operator_evidence"),
            ("worker_not_quiescent", "jobs", "implementation"),
        ]
    ]
    request.blockers = list(
        {
            (blocker["code"], blocker["subsystem"]): blocker
            for blocker in [*inventory(db, scope)["blockers"], *pending_blockers]
        }.values()
    )
    db.flush()
    return request
