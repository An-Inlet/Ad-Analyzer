"""Owned CSRF-protected Start/Stop intents; no browser-supplied evidence or transport."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select

from app.customers.access import Database, MutationPrincipal, Principal, Provider
from app.publication import customer_intents, execution_mandates
from app.publication.execution_models import ProviderExecutionMandate
from app.publication.service import owner
from app.session_automation import service
from app.session_automation.contracts import (
    AutomaticMandateOption,
    AutomaticPolicyOption,
    AutomaticPolicyRef,
    SessionAutomationCapabilities,
    SessionAutomationHistory,
    SessionAutomationStatus,
    StartSessionAutomation,
)
from app.session_automation.models import SessionAutomationRun
from app.session_automation.runtime import SessionAutomationRuntime, get_session_automation_runtime

router = APIRouter(
    prefix="/api/customer/v1/workspaces/{workspace_id}/execution/automation", tags=["customer"]
)
Runtime = Annotated[SessionAutomationRuntime | None, Depends(get_session_automation_runtime)]


def read_access(db: Database, principal: Principal, wid: int, response: Response) -> None:
    owner(db, wid, principal.user.id)
    response.headers["Cache-Control"] = "no-store"


@router.get("/capabilities", response_model=SessionAutomationCapabilities)
def capabilities(
    workspace_id: int, principal: Principal, db: Database, runtime: Runtime, response: Response
) -> SessionAutomationCapabilities:
    read_access(db, principal, workspace_id, response)
    policies: list[AutomaticPolicyOption] = []
    mandates: list[AutomaticMandateOption] = []
    if runtime is not None:
        for p in runtime.policies:
            if p.workspace_id != workspace_id:
                continue
            try:
                service.policy_for(
                    db,
                    runtime,
                    workspace_id,
                    AutomaticPolicyRef(policy_id=p.policy_id, revision=p.revision),
                )
            except HTTPException:
                continue
            policies.append(
                AutomaticPolicyOption(
                    policy=AutomaticPolicyRef(policy_id=p.policy_id, revision=p.revision),
                    label="Existing campaign budget adjustments",
                    environment=p.environment,
                )
            )
        rows = db.scalars(
            select(ProviderExecutionMandate)
            .where(
                ProviderExecutionMandate.workspace_id == workspace_id,
                ProviderExecutionMandate.state == "active",
            )
            .order_by(ProviderExecutionMandate.id)
            .limit(20)
        )
        for row in rows:
            try:
                binding = customer_intents.binding(db, workspace_id, row.id, row.revision)
                _, mandate_policy = execution_mandates.checked(
                    db, workspace_id, binding, principal.user.id, runtime.clock
                )
                if (
                    mandate_policy.environment != runtime.review.execution.environment
                    or ("existing_campaign_optimize" not in mandate_policy.allowed_purposes)
                    or mandate_policy.total_cap_micros <= 0
                ):
                    continue
                mandates.append(
                    AutomaticMandateOption(
                        mandate=binding,
                        label="Approved existing campaign spending mandate",
                        currency=mandate_policy.currency,
                        total_limit_micros=mandate_policy.total_cap_micros,
                        starts_at=mandate_policy.starts_at,
                        ends_at=mandate_policy.ends_at,
                    )
                )
            except HTTPException:
                continue
    available = bool(policies and mandates)
    return SessionAutomationCapabilities(
        available=available,
        reason="ready" if available else "automation_not_available",
        policies=policies[:20],
        mandates=mandates,
        message=service.SESSION_MESSAGE
        if available
        else "Automatic budget adjustments are not available for this workspace yet.",
    )


@router.post("/start", response_model=SessionAutomationStatus)
def start(
    workspace_id: int,
    body: StartSessionAutomation,
    principal: MutationPrincipal,
    db: Database,
    runtime: Runtime,
    response: Response,
) -> SessionAutomationStatus:
    read_access(db, principal, workspace_id, response)
    if runtime is None:
        raise HTTPException(409, "automation_not_available")
    row = service.start(db, principal, workspace_id, body, runtime)
    return service.status(db, workspace_id, row.id, runtime)


@router.get("/runs", response_model=SessionAutomationHistory)
def history(
    workspace_id: int, principal: Principal, db: Database, runtime: Runtime, response: Response
) -> SessionAutomationHistory:
    read_access(db, principal, workspace_id, response)
    identifiers = list(
        db.scalars(
            select(SessionAutomationRun.id)
            .where(
                SessionAutomationRun.workspace_id == workspace_id,
            )
            .order_by(SessionAutomationRun.created_at.desc(), SessionAutomationRun.id)
            .limit(20)
        )
    )
    return SessionAutomationHistory(
        runs=[service.status(db, workspace_id, identifier, runtime) for identifier in identifiers]
    )


@router.get("/{run_id}", response_model=SessionAutomationStatus)
def status(
    workspace_id: int,
    run_id: str,
    principal: Principal,
    db: Database,
    runtime: Runtime,
    response: Response,
) -> SessionAutomationStatus:
    read_access(db, principal, workspace_id, response)
    return service.status(db, workspace_id, run_id, runtime)


@router.post("/{run_id}/stop", response_model=SessionAutomationStatus)
def stop(
    workspace_id: int,
    run_id: str,
    principal: MutationPrincipal,
    db: Database,
    identity: Provider,
    runtime: Runtime,
    response: Response,
) -> SessionAutomationStatus:
    read_access(db, principal, workspace_id, response)
    service.stop(db, principal, workspace_id, run_id, identity, runtime)
    return service.status(db, workspace_id, run_id, runtime)
