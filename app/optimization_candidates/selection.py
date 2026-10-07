"""Current-session structural target selection; no execution or learning authority."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.customers.access import CustomerPrincipal
from app.goals import service as goals
from app.goals.schemas import StrictModel
from app.optimization_candidates import service
from app.optimization_candidates.contracts import CandidateScope, SourceFence
from app.optimization_candidates.models import CandidateJob
from app.optimization_candidates.selection_contracts import (
    CandidatePolicyRef,
    CandidateSelectionBatch,
    CandidateWorkV2,
    SelectionBlock,
    SelectionProvenance,
)
from app.publication import execution_mandates as mandates
from app.publication.contracts import fingerprint
from app.publication.customer_optimization_contracts import (
    TargetCatalog,
    TargetOption,
    TargetReader,
    TargetRequest,
)
from app.publication.execution_contracts import ProviderMandateBinding


class SelectionReadRequest(StrictModel):
    target_request: TargetRequest
    mandate: ProviderMandateBinding


class SourceFenceReader(Protocol):
    def __call__(
        self, db: Session, request: SelectionReadRequest, now: datetime, /
    ) -> SourceFence: ...


@dataclass(frozen=True)
class CandidateSelectionRuntime:
    candidate: service.CandidateRuntime
    catalog: TargetReader
    source_fence_reader: SourceFenceReader
    clock: Callable[[], datetime]


def get_candidate_selection_runtime() -> CandidateSelectionRuntime | None:
    return None


def catalog_digest(catalog: TargetCatalog) -> str:
    # Timing is separately checked; identities/observed settings must agree on reread.
    return fingerprint(
        "inlet.candidate-catalog.v1",
        {
            "request": catalog.request.model_dump(mode="json"),
            "options": sorted(o.identifier(catalog.request) for o in catalog.options),
            "complete": catalog.complete,
        },
    )


def read_catalog(runtime: CandidateSelectionRuntime, request: TargetRequest) -> TargetCatalog:
    result = TargetCatalog.model_validate(
        runtime.catalog(request, runtime.clock()).model_dump(mode="json")
    )
    now = runtime.clock()
    if result.request != request or not result.observed_at <= now < result.expires_at:
        raise HTTPException(409, "current complete owned target catalog required")
    return result


def owner_option(catalog: TargetCatalog, approved: str | None) -> tuple[TargetOption | None, str]:
    matching = [o for o in catalog.options if o.state.budget_owner.target_set_digest() == approved]
    owners = [o for o in matching if o.state.target == o.state.budget_owner.owner]
    if not owners:
        return None, "approved_owner_unavailable"
    keys = {(o.state.budget_owner.key(o.state.scope), o.state.digest()) for o in owners}
    # A single approved target-set cannot silently select multiple native owners.
    if len(keys) != 1:
        return None, "contradictory_owner_snapshots"
    selected = min(owners, key=lambda o: o.identifier(catalog.request))
    # Contradictory observations from a sibling cannot be hidden by selecting its owner.
    owner = selected.state.budget_owner
    if any(o.state.budget_owner != owner for o in matching):
        return None, "contradictory_owner_snapshots"
    return selected, ""


def plan_candidate_reads(
    db: Session,
    principal: CustomerPrincipal,
    wid: int,
    binding: ProviderMandateBinding,
    policy_ref: CandidatePolicyRef,
    runtime: CandidateSelectionRuntime,
) -> CandidateSelectionBatch:
    service.authorize(db, principal, wid, runtime.candidate)
    _, mandate = mandates.checked(db, wid, binding, principal.user.id, runtime.clock)
    if (
        mandate.environment != runtime.candidate.environment
        or "existing_campaign_optimize" not in mandate.allowed_purposes
    ):
        raise HTTPException(409, "current optimization mandate required")
    policy = runtime.candidate.policy_reader(db, wid, policy_ref.policy_id, policy_ref.revision)
    if policy is None or policy.workspace_id != wid or policy.environment != mandate.environment:
        raise HTTPException(409, "registered candidate policy required")
    goal = goals.owned(db, wid, mandate.goal_id)
    goal_digest = fingerprint(
        "inlet.optimization-goal.v1", {"definition": goals.current(db, goal).definition}
    )
    actor = principal.user.id
    requests = [
        TargetRequest(
            goal_id=mandate.goal_id,
            goal_revision=mandate.goal_revision,
            goal_digest=goal_digest,
            scope=a,
        )
        for a in sorted(mandate.accounts, key=lambda a: a.account.account_id)
    ]
    db.commit()
    observations = []
    for request in requests:
        catalog = read_catalog(runtime, request)
        source = SourceFence.model_validate(
            runtime.source_fence_reader(
                db, SelectionReadRequest(target_request=request, mandate=binding), runtime.clock()
            ).model_dump(mode="json")
        )
        db.commit()
        repeated = read_catalog(runtime, request)
        if catalog_digest(catalog) != catalog_digest(repeated):
            raise HTTPException(409, "candidate target catalog changed")
        observations.append((repeated, source))
    # All potentially blocking provider/storage work precedes the final admission locks.
    service.authorize(db, principal, wid, runtime.candidate)
    _, current_policy = mandates.checked(db, wid, binding, actor, runtime.clock)
    if current_policy != mandate:
        raise HTTPException(409, "candidate mandate changed")
    selected = []
    blocked = []
    manifest = fingerprint(
        "inlet.candidate-selection-manifest.v1",
        {
            "actor_id": actor,
            "mandate": binding.model_dump(mode="json"),
            "policy": policy.digest(),
            "observations": [
                {"catalog": catalog_digest(c), "source": f.model_dump(mode="json")}
                for c, f in observations
            ],
        },
    )
    for catalog, source in observations:
        option, reason = owner_option(catalog, mandate.allowed_target_set_digest)
        if option is None:
            blocked.append(
                SelectionBlock(account_id=catalog.request.scope.account.account_id, reason=reason)
            )
            continue
        state = option.state
        if (
            not 0
            <= (runtime.clock() - state.observed_at).total_seconds()
            <= mandate.freshness_seconds
        ):
            raise HTTPException(409, "candidate native observation expired")
        if (
            state.money.currency != mandate.currency
            or state.money.period_start != mandate.starts_at
            or state.money.period_end != mandate.ends_at
        ):
            raise HTTPException(409, "candidate native money scope changed")
        scope = CandidateScope(
            account=state.scope,
            mandate=binding,
            goal_id=mandate.goal_id,
            goal_revision=mandate.goal_revision,
            goal_digest=goal_digest,
            target=state.target,
            budget_owner_key=state.budget_owner.key(state.scope),
            target_set_digest=state.budget_owner.target_set_digest(),
            source=source,
        )
        work = CandidateWorkV2(
            scope=scope,
            policy=policy,
            selection=SelectionProvenance(
                actor_id=actor,
                scope_digest=scope.digest(),
                policy_digest=policy.digest(),
                catalog_digest=catalog_digest(catalog),
                option_id=option.identifier(catalog.request),
                state_digest=state.digest(),
                manifest_digest=manifest,
                observed_at=catalog.observed_at,
                expires_at=min(catalog.expires_at, mandate.ends_at),
            ),
        )
        service.current(db, work, principal, runtime.candidate)
        selected.append(work)
    # Even wholly blocked structural selection must recheck session, goal and policy.
    service.authorize(db, principal, wid, runtime.candidate)
    _, latest = mandates.checked(db, wid, binding, actor, runtime.clock)
    if (
        latest != mandate
        or runtime.candidate.policy_reader(db, wid, policy_ref.policy_id, policy_ref.revision)
        != policy
    ):
        raise HTTPException(409, "candidate selection policy changed")
    service.authorize(db, principal, wid, runtime.candidate)
    now = runtime.clock()
    if any(not c.observed_at <= now < c.expires_at for c, _ in observations):
        raise HTTPException(409, "candidate selection expired during admission")
    return CandidateSelectionBatch(
        workspace_id=wid, manifest_digest=manifest, selected=selected, blocked=blocked
    )


def enqueue_candidate_selection(
    db: Session,
    principal: CustomerPrincipal,
    wid: int,
    binding: ProviderMandateBinding,
    policy_ref: CandidatePolicyRef,
    runtime: CandidateSelectionRuntime,
) -> tuple[CandidateSelectionBatch, list[CandidateJob]]:
    # Caller supplies intent references only; a previously rendered batch is not proof.
    try:
        batch = plan_candidate_reads(db, principal, wid, binding, policy_ref, runtime)
        for work in batch.selected:
            service.current(db, work, principal, runtime.candidate)
        service.authorize(db, principal, batch.workspace_id, runtime.candidate)
        now = runtime.clock()
        if any(not w.selection.observed_at <= now < w.selection.expires_at for w in batch.selected):
            raise HTTPException(409, "candidate batch expired")
        jobs = [
            service._insert_checked(db, principal, work, runtime.candidate)
            for work in batch.selected
        ]
        service.authorize(db, principal, batch.workspace_id, runtime.candidate)
        final_now = runtime.clock()
        if any(final_now >= w.selection.expires_at for w in batch.selected):
            raise HTTPException(409, "candidate batch expired during insert")
        db.commit()
        return batch, jobs
    except Exception:
        db.rollback()
        raise
