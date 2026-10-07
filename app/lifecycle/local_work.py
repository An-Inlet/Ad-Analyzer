"""Closing-workspace observations and local queue receipts, never process termination."""

import hashlib
import json
from datetime import UTC, datetime
from typing import Any
from typing import cast as typing_cast
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import String, cast, func, or_, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Session

from app.customers.access import CustomerPrincipal
from app.customers.identity import IdentityProvider
from app.database.session import Base
from app.lifecycle.contracts import LifecycleBlockerV1, LifecycleScopeV1
from app.lifecycle.inventory import predicate, verify_registry
from app.lifecycle.models import LifecycleRequest, LifecycleStep


def evidence_digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def receipt(db: Session, request: LifecycleRequest, key: str, digest: str) -> None:
    step = db.get(LifecycleStep, (request.id, key))
    if step is None:
        step = LifecycleStep(
            request_id=request.id,
            step_key=key,
            workspace_id=request.workspace_id,
            request_revision=request.revision,
            fence=request.fence,
            attempts=0,
        )
        db.add(step)
    step.request_revision, step.fence = request.revision, request.fence
    step.attempts = (step.attempts or 0) + 1
    step.state, step.lease_until, step.evidence_digest = "complete", None, digest
    db.flush()


def cancel_analysis_queue(db: Session, request: LifecycleRequest) -> None:
    """Caller holds closing workspace and request locks; preserve source JobRun rows."""
    scope = LifecycleScopeV1(workspace_id=request.workspace_id)
    table = Base.metadata.tables["google_customer_import_completions"]
    result = db.execute(
        update(table)
        .where(predicate(table.name, scope), table.c.state == "pending")
        .values(state="canceled", next_attempt_at=None)
    )
    # A digest attests to the cancellation operation, not delivery or physical stopping.
    receipt(
        db,
        request,
        "analysis_queue_cancel",
        evidence_digest(
            {
                "schema_version": "inlet.lifecycle.queue_cancellation.v1",
                "workspace_id": request.workspace_id,
                "request_id": request.id,
                "revision": request.revision,
                "rows_canceled": typing_cast(CursorResult[Any], result).rowcount,
            }
        ),
    )


# Known persisted work families. Free-form legacy values not listed as terminal remain
# unknown/blocking. Terminal labels additionally require their actual completion timestamp.
LOCAL_RUNS = {
    "job_runs": ("status", ("succeeded", "failed"), "finished_at"),
    "analysis_runs": ("status", ("succeeded", "failed"), "finished_at"),
    "crm_sync_runs": ("status", ("succeeded", "failed"), "completed_at"),
}
# New persisted worker tables using these established suffixes require an explicit
# category before a local observation can be reported as complete.
WORK_FAMILIES = {
    "reported_feedback_jobs": "erasable_derived_read_queue",
    "campaign_performance_completions": "retained_source_completion",
    "initial_calibration_runs": "erasable_derived_read_queue",
    "session_automation_runs": "protected_publication",
    "optimization_candidate_jobs": "erasable_derived_read_queue",
    "job_runs": "local_run",
    "analysis_runs": "local_run",
    "crm_sync_runs": "local_run",
    "customer_context_checkpoints": "generation_fenced_context",
    "meta_detail_checkpoints": "generation_fenced_meta",
    "google_customer_import_completions": "local_queue",
    "mandate_actions": "protected_publication",
    "publication_steps": "protected_publication",
    "provider_execution_runs": "protected_publication",
    "provider_execution_steps": "protected_publication",
    "provider_execution_attempts": "protected_publication",
    "google_original_completions": "protected_publication",
    "customer_lifecycle_steps": "closing_compatible_maintenance",
}


def verify_work_registry() -> None:
    candidates = {
        name
        for name in Base.metadata.tables
        if name.endswith(
            ("_runs", "_checkpoints", "_actions", "_steps", "_attempts", "_completions", "_jobs")
        )
    }
    if candidates != set(WORK_FAMILIES):
        raise ValueError("local work classification incomplete")


ADMISSION_STATES = {
    "session_automation_runs": ("state", "stopped"),
    "workspace_integrations": ("status", "revoked"),
    "crm_connections": ("status", "closed"),
    "google_customer_connections": ("status", "disconnected"),
    "customer_source_connections": ("status", "disconnected"),
    "meta_connections": ("status", "reconnect_required"),
    "shopify_connections": ("status", "reconnect_required"),
    "provider_execution_mandates": ("state", "revoked"),
    "provider_execution_runs": ("state", "canceled"),
}


def observe(db: Session, request: LifecycleRequest, now: datetime) -> dict[str, Any]:
    """Current observation under the caller's workspace lock; no historical payload claim."""
    verify_registry()
    verify_work_registry()
    scope = LifecycleScopeV1(workspace_id=request.workspace_id)
    workspace = Base.metadata.tables["workspaces"]
    admission = (
        db.scalar(select(workspace.c.status).where(workspace.c.id == scope.workspace_id))
        == "closing"
    )
    violations: dict[str, int] = {}
    for name, (field, expected) in ADMISSION_STATES.items():
        table = Base.metadata.tables[name]
        count = int(
            db.scalar(
                select(func.count())
                .select_from(table)
                .where(
                    predicate(name, scope),
                    or_(table.c[field].is_(None), table.c[field] != expected),
                )
            )
            or 0
        )
        violations[name] = count
        admission = admission and count == 0
    # Status alone does not attest that local credential/continuation removal completed.
    for name, field, empty in [
        ("workspace_integrations", "secret_manager_reference", None),
        ("crm_connections", "secret_manager_reference", ""),
        ("google_customer_connections", "encrypted_grant", None),
        ("customer_source_connections", "encrypted_grant", None),
        ("meta_connections", "encrypted_credentials", ""),
        ("shopify_connections", "encrypted_credentials", ""),
    ]:
        table = Base.metadata.tables[name]
        invalid = (
            table.c[field].is_not(None)
            if empty is None
            else or_(table.c[field].is_(None), table.c[field] != empty)
        )
        count = int(
            db.scalar(
                select(func.count()).select_from(table).where(predicate(name, scope), invalid)
            )
            or 0
        )
        violations[name + "_credentials"] = count
        admission = admission and count == 0
    for name, field, expected_flag in [
        ("workspace_automation_controls", "enabled", False),
        ("spending_mandates", "paused", True),
        ("mandate_actions", "cancel_requested", True),
    ]:
        table = Base.metadata.tables[name]
        count = int(
            db.scalar(
                select(func.count())
                .select_from(table)
                .where(predicate(name, scope), table.c[field] != expected_flag)
            )
            or 0
        )
        violations[name] = count
        admission = admission and count == 0
    counts: dict[str, int] = {}
    for name, (field, terminals, completed) in LOCAL_RUNS.items():
        table = Base.metadata.tables[name]
        counts[name] = int(
            db.scalar(
                select(func.count())
                .select_from(table)
                .where(
                    predicate(name, scope),
                    or_(
                        func.lower(cast(table.c[field], String)).not_in(terminals),
                        table.c[field].is_(None),
                        table.c[completed].is_(None),
                    ),
                )
            )
            or 0
        )
    table = Base.metadata.tables["google_customer_import_completions"]
    counts[table.name] = int(
        db.scalar(
            select(func.count())
            .select_from(table)
            .where(predicate(table.name, scope), table.c.state.not_in(["delivered", "canceled"]))
        )
        or 0
    )
    table = Base.metadata.tables["customer_context_checkpoints"]
    counts[table.name] = int(
        db.scalar(
            select(func.count())
            .select_from(table)
            .where(
                predicate(table.name, scope),
                or_(
                    table.c.state != "closed",
                    table.c.fence.is_not(None),
                    table.c.lease_until.is_not(None),
                ),
            )
        )
        or 0
    )
    detail = Base.metadata.tables["meta_detail_checkpoints"]
    native = Base.metadata.tables["meta_connections"]
    counts[detail.name] = int(
        db.scalar(
            select(func.count())
            .select_from(
                detail.join(
                    native,
                    (native.c.id == detail.c.connection_id)
                    & (native.c.workspace_id == detail.c.workspace_id),
                )
            )
            .where(
                predicate(detail.name, scope),
                detail.c.phase != "complete",
                detail.c.generation == native.c.generation,
                native.c.status == "connected",
            )
        )
        or 0
    )
    candidate_jobs = Base.metadata.tables["optimization_candidate_jobs"]
    counts[candidate_jobs.name] = int(
        db.scalar(
            select(func.count())
            .select_from(candidate_jobs)
            .where(predicate(candidate_jobs.name, scope))
        )
        or 0
    )
    # Unknown publication accounting is deliberately separate from local job rows.
    # Never turn its absence into external cancellation or physical-worker evidence.
    return {
        "schema_version": "inlet.lifecycle.local_quiescence.v1",
        "workspace_id": request.workspace_id,
        "request_id": request.id,
        "request_revision": request.revision,
        "observed_at": now.isoformat(),
        "observation_kind": "current_only",
        "admission_fenced": admission,
        "local_records_drained": admission and not any(counts.values()),
        "physical_workers_stopped": None,
        "external_obligations_resolved": False,
        "unknown_or_nonterminal_records": counts,
        "admission_violations": violations,
        "worker_families": WORK_FAMILIES,
    }


def reconcile(
    db: Session,
    principal: CustomerPrincipal,
    provider: IdentityProvider,
    wid: int,
    request_id: str,
    expected_revision: int,
) -> tuple[LifecycleRequest, dict[str, Any]]:
    from app.lifecycle.quiescing import owner

    workspace = owner(db, principal, provider, wid)
    request = db.scalar(
        select(LifecycleRequest)
        .where(LifecycleRequest.id == request_id, LifecycleRequest.workspace_id == wid)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if request is None or request.operation != "close" or request.requested_by != principal.user.id:
        raise HTTPException(404, "closure request unavailable")
    if (
        workspace.status != "closing"
        or request.state != "blocked"
        or request.revision != expected_revision
    ):
        raise HTTPException(409, "closure request changed")
    # Fresh wall clock after all authority/request locks, never caller-supplied time.
    now = datetime.now(UTC)
    request.revision += 1
    request.fence, request.updated_at = uuid4().hex, now
    cancel_analysis_queue(db, request)
    observation = observe(db, request, now)
    remaining = [b for b in request.blockers if b["code"] != "worker_not_quiescent"]
    if not observation["local_records_drained"]:
        remaining.append(
            LifecycleBlockerV1(
                code="worker_not_quiescent", subsystem="jobs", resolution_kind="operator_evidence"
            ).model_dump()
        )
    request.blockers = remaining
    digest = evidence_digest(observation)
    receipt(db, request, "local_quiescence_v1", digest)
    observation["durable_receipt"] = {
        "evidence_digest": digest,
        "historical_payload_retained": False,
        "request_revision": request.revision,
    }
    return request, observation
