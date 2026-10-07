"""Preview-bound named automatic choices; no source reads or default policy registration."""

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.customers.access import CustomerPrincipal
from app.initial_planning.automatic_contracts import InitialReportedRulePolicyV1
from app.initial_planning.review_v2_owned import current_preview, policy_pair
from app.initial_planning.start_contracts import (
    InitialRuleAutomaticOptionsV1,
    InitialRuleAutomaticOptionV1,
    InitialRuleAutomaticPolicyV1,
)
from app.optimization_candidates import service as candidates
from app.publication import customer_intents
from app.publication.execution_models import ProviderExecutionMandate
from app.session_automation import service
from app.session_automation.contracts import AutomaticPolicyRef
from app.session_automation.runtime import SessionAutomationRuntime


def options(
    db: Session,
    principal: CustomerPrincipal,
    wid: int,
    preview_id: str,
    runtime: SessionAutomationRuntime,
) -> InitialRuleAutomaticOptionsV1:
    candidates.authorize(db, principal, wid, runtime.review.candidate)
    planning = runtime.review.candidate.initial_planning
    if planning is None:
        raise HTTPException(409, "initial_automatic_runtime_unavailable")
    value, row, intent = current_preview(
        db, principal, runtime.review.candidate.identity, wid, preview_id, planning
    )
    rows = list(
        db.scalars(
            select(ProviderExecutionMandate)
            .where(
                ProviderExecutionMandate.workspace_id == wid,
                ProviderExecutionMandate.state == "active",
            )
            .order_by(ProviderExecutionMandate.id)
            .limit(21)
        )
    )
    result: list[InitialRuleAutomaticOptionV1] = []
    truncated = len(rows) > 20
    for p in runtime.policies:
        if not isinstance(p, InitialRuleAutomaticPolicyV1) or p.workspace_id != wid:
            continue
        try:
            service.policy_for(
                db, runtime, wid, AutomaticPolicyRef(policy_id=p.policy_id, revision=p.revision)
            )
            numeric = candidates.registered_policy(
                db,
                wid,
                p.candidate_policy.policy_id,
                p.candidate_policy.revision,
                runtime.review.candidate,
            )
            if (
                not isinstance(numeric, InitialReportedRulePolicyV1)
                or numeric.initial.digest() != value.policy_digest
                or numeric.planning_profile_digest != value.profile_digest
            ):
                continue
            rule = next(
                rule for rule in numeric.initial.rules if rule.name == numeric.initial.selected_rule
            )
        except HTTPException as exc:
            if exc.status_code in {401, 403}:
                raise
            continue
        for mandate in rows[:20]:
            try:
                binding = customer_intents.binding(db, wid, mandate.id, mandate.revision)
                _, policy = policy_pair(
                    db, wid, value, row, intent, binding, principal.user.id, planning, runtime.clock
                )
                if policy.total_cap_micros <= 0 or policy.currency != "USD":
                    continue
            except HTTPException as exc:
                if exc.status_code in {401, 403}:
                    raise
                continue
            if len(result) == 20:
                truncated = True
                break
            result.append(
                InitialRuleAutomaticOptionV1(
                    policy=AutomaticPolicyRef(policy_id=p.policy_id, revision=p.revision),
                    policy_digest=p.digest(),
                    label=f"Initial rule · {rule.name}",
                    mandate=binding,
                    currency="USD",
                    total_limit_micros=policy.total_cap_micros,
                    selected_rule=rule.name,
                    maximum_adjustment_micros=rule.budget_step_micros,
                    lifetime_seconds=p.lifetime_seconds,
                    cadence_seconds=p.cadence_seconds,
                )
            )
    candidates.authorize(db, principal, wid, runtime.review.candidate)
    current_preview(db, principal, runtime.review.candidate.identity, wid, preview_id, planning)
    return InitialRuleAutomaticOptionsV1(
        preview_id=value.id,
        preview_digest=value.digest(),
        options=tuple(result),
        truncated=truncated,
    )
