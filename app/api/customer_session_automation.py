"""Owned CSRF-protected Start/Stop intents; no browser-supplied evidence or transport."""

from collections.abc import Iterator
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select

from app.ads.models import AdvertisingAccount
from app.customers.access import Database, MutationPrincipal, Principal, Provider
from app.initial_planning.start_contracts import (
    InitialRuleAutomaticOptionsV1,
    InitialRuleAutomaticPolicyV1,
    StartInitialReportedRuleAutomationV1,
)
from app.optimization_candidates.service import registered_policy
from app.publication import customer_intents, execution_mandates
from app.publication.execution_models import ProviderExecutionMandate
from app.publication.service import owner
from app.reported_feedback.automatic_contracts import (
    ReportedRuleAutomaticPolicyOptionV1,
    ReportedRuleAutomaticPolicyV1,
    SessionAutomationCapabilitiesWithReportedRules,
    StartReportedRuleAutomationV1,
)
from app.reported_feedback.candidate_contracts import ReportedRulePolicyV1
from app.reported_feedback.customer_contracts import rule_parameters
from app.session_automation import service
from app.session_automation.contracts import (
    AutomaticMandateOption,
    AutomaticPolicyOption,
    AutomaticPolicyRef,
    SessionAutomationHistory,
    SessionAutomationStatus,
    StartSessionAutomation,
)
from app.session_automation.models import SessionAutomationRun
from app.session_automation.runtime import SessionAutomationRuntime, get_session_automation_runtime

router = APIRouter(
    prefix="/api/customer/v1/workspaces/{workspace_id}/execution/automation", tags=["customer"]
)
LegacyRuntime = Annotated[SessionAutomationRuntime | None, Depends(get_session_automation_runtime)]


def get_customer_session_automation_runtime(
    db: Database,
    principal: Principal,
    provider: Provider,
    legacy: LegacyRuntime,
) -> Iterator[SessionAutomationRuntime | None]:
    if legacy is not None:
        yield legacy
        return
    from app.production_runtime.reported_automation import configured_session_automation
    from app.settings import settings

    with configured_session_automation(db, principal, provider, settings) as runtime:
        yield runtime


Runtime = Annotated[
    SessionAutomationRuntime | None, Depends(get_customer_session_automation_runtime)
]


def read_access(db: Database, principal: Principal, wid: int, response: Response) -> None:
    owner(db, wid, principal.user.id)
    response.headers["Cache-Control"] = "no-store"


@router.get("/capabilities", response_model=SessionAutomationCapabilitiesWithReportedRules)
def capabilities(
    workspace_id: int, principal: Principal, db: Database, runtime: Runtime, response: Response
) -> SessionAutomationCapabilitiesWithReportedRules:
    read_access(db, principal, workspace_id, response)
    policies: list[AutomaticPolicyOption | ReportedRuleAutomaticPolicyOptionV1] = []
    mandates: list[AutomaticMandateOption] = []
    if runtime is not None:
        for p in runtime.policies:
            if isinstance(p, InitialRuleAutomaticPolicyV1):
                continue  # Exact preview choices are exposed by the initial-planning API.
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
            if isinstance(p, ReportedRuleAutomaticPolicyV1):
                numeric = registered_policy(
                    db,
                    workspace_id,
                    p.candidate_policy.policy_id,
                    p.candidate_policy.revision,
                    runtime.selection.candidate,
                )
                if not isinstance(numeric, ReportedRulePolicyV1):
                    continue
                policies.append(
                    ReportedRuleAutomaticPolicyOptionV1(
                        policy=AutomaticPolicyRef(policy_id=p.policy_id, revision=p.revision),
                        policy_digest=p.digest(),
                        label=f"Reported-efficiency rule · {p.policy_id[:12]}",
                        environment=p.environment,
                        decision_basis=p.decision_basis,
                        rule_parameters=rule_parameters(numeric),
                        lifetime_seconds=p.lifetime_seconds,
                        cadence_seconds=p.cadence_seconds,
                    )
                )
                continue
            policies.append(
                AutomaticPolicyOption(
                    policy=AutomaticPolicyRef(policy_id=p.policy_id, revision=p.revision),
                    label=f"Budget adjustments · Policy {p.policy_id[:12]}",
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
                names = list(
                    db.scalars(
                        select(AdvertisingAccount.name)
                        .where(
                            AdvertisingAccount.workspace_id == workspace_id,
                            AdvertisingAccount.id.in_(
                                [a.account.account_id for a in mandate_policy.accounts]
                            ),
                        )
                        .order_by(AdvertisingAccount.id)
                    )
                )
                name = ", ".join(names) or "Approved spending mandate"
                suffix = f" · Mandate {row.id[:12]}"
                label = name[: 100 - len(suffix)] + suffix
                mandates.append(
                    AutomaticMandateOption(
                        mandate=binding,
                        label=label,
                        currency=mandate_policy.currency,
                        total_limit_micros=mandate_policy.total_cap_micros,
                        starts_at=mandate_policy.starts_at,
                        ends_at=mandate_policy.ends_at,
                    )
                )
            except HTTPException:
                continue
    available = bool(policies and mandates)
    return SessionAutomationCapabilitiesWithReportedRules(
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
    body: StartSessionAutomation
    | StartReportedRuleAutomationV1
    | StartInitialReportedRuleAutomationV1,
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


@router.get("/initial-options/{preview_id}")
def initial_options(
    workspace_id: int,
    preview_id: str,
    principal: Principal,
    db: Database,
    runtime: Runtime,
    response: Response,
) -> "InitialRuleAutomaticOptionsV1":
    from app.initial_planning.start_options import options

    read_access(db, principal, workspace_id, response)
    if runtime is None:
        raise HTTPException(409, "initial_automatic_runtime_unavailable")
    return options(db, principal, workspace_id, preview_id, runtime)
