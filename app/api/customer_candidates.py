"""Original-session candidate read intents; never automatic approval or execution."""

from collections.abc import Iterator
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select

from app.ads.models import AdvertisingAccount
from app.customers.access import Database, MutationPrincipal, Principal, Provider
from app.goals import service as goals
from app.goals.schemas import GoalDefinition
from app.optimization_candidates import review_bridge, selection, service
from app.optimization_candidates.customer_contracts import (
    CandidateCapabilities,
    CandidateMandateOption,
    CandidatePolicyOption,
    CandidateReadIntent,
    CandidateReadPrepared,
    CandidateReadStatus,
)
from app.optimization_candidates.models import CandidateResult
from app.optimization_candidates.review_contracts import (
    CandidateReviewIntent,
    CandidateReviewPrepared,
)
from app.optimization_candidates.selection_contracts import CandidatePolicyRef
from app.production_runtime.candidate_assembly import CandidateRuntimeBundle, configured_candidates
from app.publication import customer_intents, execution_mandates
from app.publication.execution_models import ProviderExecutionMandate
from app.publication.service import owner
from app.settings import settings

router = APIRouter(
    prefix="/api/customer/v1/workspaces/{workspace_id}/execution/candidates", tags=["customer"]
)


def get_configured_candidate_runtime(
    db: Database, principal: Principal, provider: Provider
) -> Iterator[CandidateRuntimeBundle | None]:
    with configured_candidates(db, principal, provider, settings) as runtime:
        yield runtime


Runtime = Annotated[CandidateRuntimeBundle | None, Depends(get_configured_candidate_runtime)]


def required(runtime: CandidateRuntimeBundle | None) -> CandidateRuntimeBundle:
    if runtime is None:
        raise HTTPException(409, "candidate_runtime_unavailable")
    return runtime


@router.get("/capabilities", response_model=CandidateCapabilities)
def capabilities(
    workspace_id: int, db: Database, principal: Principal, runtime: Runtime, response: Response
) -> CandidateCapabilities:
    response.headers["Cache-Control"] = "no-store"
    owner(db, workspace_id, principal.user.id)
    if runtime is None:
        return CandidateCapabilities(configured=False, policies=[], mandates=[], truncated=False)
    service.authorize(db, principal, workspace_id, runtime.candidate)
    policies = [p for p in runtime.policies.candidate_policies if p.workspace_id == workspace_id]
    rows = list(
        db.scalars(
            select(ProviderExecutionMandate)
            .where(
                ProviderExecutionMandate.workspace_id == workspace_id,
                ProviderExecutionMandate.state == "active",
            )
            .order_by(ProviderExecutionMandate.id)
            .limit(21)
        )
    )
    options = []
    for row in rows[:20]:
        try:
            binding = customer_intents.binding(db, workspace_id, row.id, row.revision)
            _, policy = execution_mandates.checked(
                db, workspace_id, binding, principal.user.id, runtime.candidate.clock
            )
            if (
                policy.environment != runtime.candidate.environment
                or "existing_campaign_optimize" not in policy.allowed_purposes
            ):
                continue
            goal = goals.owned(db, workspace_id, policy.goal_id)
            goals.expect(goal, policy.goal_revision)
            definition = GoalDefinition.model_validate(goals.current(db, goal).definition)
            names = list(
                db.scalars(
                    select(AdvertisingAccount.name).where(
                        AdvertisingAccount.workspace_id == workspace_id,
                        AdvertisingAccount.id.in_([a.account.account_id for a in policy.accounts]),
                    )
                )
            )
            budget_label = (
                f"Net sales {policy.currency} {Decimal(definition.target_micros) / 1000000:g}"
                f" · {', '.join(names)[:50]} · budget {policy.currency} "
                f"{Decimal(policy.total_cap_micros) / 1000000:g}"
            )
            options.append(
                CandidateMandateOption(
                    mandate_id=row.id,
                    revision=row.revision,
                    policy_digest=policy.digest(),
                    label=budget_label[:160],
                )
            )
        except HTTPException as exc:
            if exc.status_code in {401, 403}:
                raise
    service.authorize(db, principal, workspace_id, runtime.candidate)
    return CandidateCapabilities(
        configured=True,
        policies=[
            CandidatePolicyOption(
                policy=CandidatePolicyRef(policy_id=p.policy_id, revision=p.revision),
                label=(
                    f"Budget step {Decimal(p.budget_step_micros) / 1000000:g} in account currency"
                    if p.budget_step_micros is not None
                    else "Budget step unconfigured"
                )
                + (
                    f" · minimum {p.minimum_observations} observations"
                    if p.minimum_observations is not None
                    else " · observation minimum unconfigured"
                ),
            )
            for p in policies[:20]
        ],
        mandates=options,
        truncated=len(rows) > 20 or len(policies) > 20,
    )


@router.post("/reads", response_model=CandidateReadPrepared, status_code=201)
def enqueue(
    workspace_id: int,
    body: CandidateReadIntent,
    db: Database,
    principal: MutationPrincipal,
    runtime: Runtime,
    response: Response,
) -> CandidateReadPrepared:
    response.headers["Cache-Control"] = "no-store"
    bundle = required(runtime)
    service.authorize(db, principal, workspace_id, bundle.candidate)
    binding = customer_intents.binding(db, workspace_id, body.mandate_id, body.mandate_revision)
    batch, jobs = selection.enqueue_candidate_selection(
        db, principal, workspace_id, binding, body.policy, bundle.selection_for(binding)
    )
    return CandidateReadPrepared(selection=batch, job_ids=[job.id for job in jobs])


@router.get("/reads/{job_id}", response_model=CandidateReadStatus)
def status(
    workspace_id: int,
    job_id: str,
    db: Database,
    principal: Principal,
    runtime: Runtime,
    response: Response,
) -> CandidateReadStatus:
    response.headers["Cache-Control"] = "no-store"
    bundle = required(runtime)
    service.authorize(db, principal, workspace_id, bundle.candidate)
    row = service.load(db, workspace_id, job_id)
    if (row.actor_id, row.auth_session_digest) != (principal.user.id, principal.session.digest):
        raise HTTPException(409, "candidate_original_session_required")
    service.current(db, service.owned_work(row), principal, bundle.candidate)
    result = db.scalar(
        select(CandidateResult).where(
            CandidateResult.workspace_id == workspace_id, CandidateResult.job_id == job_id
        )
    )
    decision = (
        service.read_result(
            db, workspace_id, result.id, principal, bundle.candidate, erase_invalid=False
        )
        if result
        else None
    )
    service.authorize(db, principal, workspace_id, bundle.candidate)
    return CandidateReadStatus(
        job_id=row.id,
        state=row.state,
        result_id=result.id if result else None,
        decision=decision,
        decision_digest=decision.digest() if decision is not None else None,
    )


@router.post("/results/{result_id}/review", response_model=CandidateReviewPrepared)
def review(
    workspace_id: int,
    result_id: str,
    body: CandidateReviewIntent,
    db: Database,
    principal: MutationPrincipal,
    runtime: Runtime,
    response: Response,
) -> CandidateReviewPrepared:
    response.headers["Cache-Control"] = "no-store"
    if body.result_id != result_id:
        raise HTTPException(409, "candidate_result_mismatch")
    return review_bridge.prepare_candidate_review(
        db, principal, workspace_id, body, required(runtime).review
    )
