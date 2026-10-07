"""Original-session-bound read work; no optimization mutation/admission is reachable."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import Engine, delete, func, or_, select
from sqlalchemy.orm import Session

from app.automation import AutomationControlKey
from app.automation.models import PlatformAutomationControl
from app.commerce.evidence import digest as source_digest
from app.commerce.models import CommerceEvidenceState, CommerceMeasurementPublication, CommerceStore
from app.commerce.publication_contracts import version_filter
from app.customers.access import CustomerPrincipal, lock_customer_mutation
from app.customers.identity import IdentityProvider
from app.customers.models import CustomerSession, CustomerUser
from app.goals import service as goals
from app.optimization_candidates.compiler import compile_candidate
from app.optimization_candidates.contracts import (
    CandidateDecision,
    CandidateObservation,
    CandidatePolicy,
    CandidateReadPort,
    CandidateScope,
    CandidateWork,
)
from app.optimization_candidates.models import CandidateJob, CandidateResult
from app.optimization_candidates.selection_contracts import CandidateWorkV2, parse_work
from app.publication import execution_mandates as mandates
from app.publication.contracts import fingerprint
from app.publication.coordinator import read_owned_outcome_receipt
from app.publication.execution_contracts import Environment, ProviderMandatePolicy
from app.publication.optimization import positive_changes_used
from app.publication.service import owner
from app.shopify.security import utc
from app.workspaces.models import Workspace

Clock = Callable[[], datetime]
PolicyReader = Callable[[Session, int, str, int], CandidatePolicy | None]
ACTUAL_UNQUALIFIED_SCHEMAS = frozenset(
    {
        "inlet.owned-outcome-assessment.v2",
        "inlet.owned-outcome-assessment.v3",
        "inlet.owned-reconciliation-observations.v1",
    }
)


class FinalEvidenceCurrent(Protocol):
    """Pure local final lineage check; no commits, network calls or authority grants."""

    def __call__(
        self,
        db: Session,
        work: CandidateWork | CandidateWorkV2,
        observation: CandidateObservation,
        /,
    ) -> None: ...


class AuthorizedEvidenceTransform(Protocol):
    """Local evidence-only derivation under the actual original-session fence.

    No provider IO, commits, state changes or authority grants. The worker supplies
    its persisted original principal; adapters must never infer an owner/session.
    """

    def __call__(
        self,
        db: Session,
        principal: CustomerPrincipal,
        work: CandidateWork | CandidateWorkV2,
        observation: CandidateObservation,
        now: datetime,
        /,
    ) -> CandidateObservation: ...


class AuthorizedFinalEvidenceCurrent(Protocol):
    """Original-principal variant of the local, noncommitting final checker."""

    def __call__(
        self,
        db: Session,
        principal: CustomerPrincipal,
        work: CandidateWork | CandidateWorkV2,
        observation: CandidateObservation,
        /,
    ) -> None: ...


@dataclass(frozen=True)
class CandidateRuntime:
    environment: Environment
    identity: IdentityProvider
    reader: CandidateReadPort
    policy_reader: PolicyReader
    clock: Clock = lambda: datetime.now(UTC)
    # Registry is server-owned; no genuine measured-learning profile ships enabled.
    learning_profiles: frozenset[tuple[str, str, int, str]] = frozenset()
    feedback_dependent_schemas: frozenset[str] = frozenset()
    final_evidence_current: FinalEvidenceCurrent | None = None
    authorized_evidence_transform: AuthorizedEvidenceTransform | None = None
    authorized_final_evidence_current: AuthorizedFinalEvidenceCurrent | None = None


def get_candidate_runtime() -> CandidateRuntime | None:
    return None


def authorize(
    db: Session, principal: CustomerPrincipal, wid: int, runtime: CandidateRuntime
) -> None:
    lock_customer_mutation(db, principal, wid, runtime.identity)
    owner(db, wid, principal.user.id)


def source_current(db: Session, scope: CandidateScope, actor: str) -> None:
    wid, fence = scope.account.workspace_id, scope.source
    workspace = db.get(Workspace, wid, populate_existing=True)
    publication = db.scalar(
        select(CommerceMeasurementPublication)
        .where(
            CommerceMeasurementPublication.id == fence.publication_id,
            CommerceMeasurementPublication.workspace_id == wid,
        )
        .execution_options(populate_existing=True)
    )
    store = db.scalar(
        select(CommerceStore)
        .where(CommerceStore.id == fence.store_id, CommerceStore.workspace_id == wid)
        .execution_options(populate_existing=True)
    )
    state = db.get(CommerceEvidenceState, fence.store_id, populate_existing=True)
    latest_v1 = db.scalar(
        select(CommerceMeasurementPublication.id)
        .where(
            CommerceMeasurementPublication.workspace_id == wid,
            CommerceMeasurementPublication.store_id == fence.store_id,
            version_filter(),
        )
        .order_by(CommerceMeasurementPublication.publication_revision.desc())
        .limit(1)
    )
    if (
        workspace is None
        or workspace.status != "active"
        or workspace.export_privacy_revision != fence.workspace_privacy_revision
        or publication is None
        or store is None
        or state is None
        or publication.store_id != fence.store_id
        or state.workspace_id != wid
        or publication.generation != fence.generation
        or state.generation != fence.generation
        or publication.privacy_epoch != fence.privacy_epoch
        or state.privacy_epoch != fence.privacy_epoch
        or publication.publication_revision != fence.publication_revision
        or latest_v1 != fence.publication_id
        or publication.source_revision != fence.source_revision
        or store.revision != fence.source_revision
        or publication.manifest_digest != fence.manifest_digest
    ):
        raise HTTPException(409, "candidate source changed")
    if fence.attempt_id is not None:
        receipt = read_owned_outcome_receipt(db, wid, fence.attempt_id, actor)
        if (
            receipt is None
            or receipt.account != scope.account
            or receipt.environment != scope.mandate.environment
            or receipt.goal_id != scope.goal_id
            or receipt.goal_revision != scope.goal_revision
            or receipt.receipt_id != fence.receipt_id
            or receipt.sequence != fence.receipt_sequence
            or receipt.receipt_digest != fence.receipt_digest
            or source_digest(["inlet.owned-receipt.v1", receipt.model_dump(mode="json")])
            != fence.projection_digest
        ):
            raise HTTPException(409, "candidate evidence retracted")


def current(
    db: Session,
    work: CandidateWork | CandidateWorkV2,
    principal: CustomerPrincipal,
    runtime: CandidateRuntime,
) -> tuple[ProviderMandatePolicy, int, int]:
    wid, scope = work.scope.account.workspace_id, work.scope
    authorize(db, principal, wid, runtime)
    if work.policy.environment != runtime.environment:
        raise HTTPException(409, "candidate environment unavailable")
    ledger, policy = mandates.checked(db, wid, scope.mandate, principal.user.id, runtime.clock)
    if (
        "existing_campaign_optimize" not in policy.allowed_purposes
        or scope.account not in policy.accounts
        or policy.allowed_target_set_digest != scope.target_set_digest
    ):
        raise HTTPException(409, "candidate account scope changed")
    master = db.get(
        PlatformAutomationControl, AutomationControlKey.ALL_DATA_SYNCS.value, populate_existing=True
    )
    if master is not None and not master.enabled:
        raise HTTPException(409, "candidate reads disabled")
    goal = goals.owned(db, wid, scope.goal_id)
    goals.expect(goal, scope.goal_revision)
    if (
        goal.id != policy.goal_id
        or goal.revision != policy.goal_revision
        or fingerprint(
            "inlet.optimization-goal.v1", {"definition": goals.current(db, goal).definition}
        )
        != scope.goal_digest
    ):
        raise HTTPException(409, "candidate goal changed")
    registered = runtime.policy_reader(db, wid, work.policy.policy_id, work.policy.revision)
    if registered != work.policy:
        raise HTTPException(409, "candidate policy unavailable")
    source_current(db, scope, principal.user.id)
    # Final session check follows all potentially blocking source/policy reads.
    authorize(db, principal, wid, runtime)
    if isinstance(work, CandidateWorkV2) and (
        work.selection.actor_id != principal.user.id
        or not work.selection.observed_at <= runtime.clock() < work.selection.expires_at
    ):
        raise HTTPException(409, "candidate selection expired or actor changed")
    return policy, positive_changes_used(db, wid, ledger.id), ledger.action_count


def enqueue(
    db: Session,
    principal: CustomerPrincipal,
    work: CandidateWork | CandidateWorkV2,
    runtime: CandidateRuntime,
) -> CandidateJob:
    work = parse_work(work.model_dump(mode="json"))
    current(db, work, principal, runtime)
    row = _insert_checked(db, principal, work, runtime)
    db.commit()
    return row


def _insert_checked(
    db: Session,
    principal: CustomerPrincipal,
    work: CandidateWork | CandidateWorkV2,
    runtime: CandidateRuntime,
) -> CandidateJob:
    """Internal: caller holds current workspace/session/mandate/source fences."""
    wid = work.scope.account.workspace_id
    existing = db.scalar(
        select(CandidateJob).where(
            CandidateJob.workspace_id == wid, CandidateJob.input_digest == work.digest()
        )
    )
    if existing is not None:
        return existing
    row = CandidateJob(
        id=uuid4().hex,
        workspace_id=wid,
        environment=runtime.environment,
        publication_id=work.scope.source.publication_id,
        attempt_id=work.scope.source.attempt_id,
        actor_id=principal.user.id,
        auth_session_digest=principal.session.digest,
        input_digest=work.digest(),
        work=work.model_dump(mode="json"),
        state="pending",
        attempts=0,
        due_at=runtime.clock(),
        created_at=runtime.clock(),
    )
    db.add(row)
    db.flush()
    return row


def principal_for(db: Session, row: CandidateJob) -> CustomerPrincipal:
    user = db.get(CustomerUser, row.actor_id, populate_existing=True)
    session = db.get(CustomerSession, row.auth_session_digest, populate_existing=True)
    if user is None or session is None or session.user_id != row.actor_id:
        raise HTTPException(401, "candidate session unavailable")
    return CustomerPrincipal(user=user, session=session)


def load(db: Session, wid: int, job_id: str) -> CandidateJob:
    row = db.scalar(
        select(CandidateJob)
        .where(CandidateJob.id == job_id, CandidateJob.workspace_id == wid)
        .execution_options(populate_existing=True)
    )
    if row is None:
        raise HTTPException(404, "candidate job retired")
    return row


def owned_work(row: CandidateJob) -> CandidateWork | CandidateWorkV2:
    work = parse_work(row.work)
    if (
        work.scope.account.workspace_id != row.workspace_id
        or work.policy.environment != row.environment
        or work.scope.source.publication_id != row.publication_id
        or work.scope.source.attempt_id != row.attempt_id
        or (isinstance(work, CandidateWorkV2) and work.selection.actor_id != row.actor_id)
        or work.digest() != row.input_digest
    ):
        raise HTTPException(409, "candidate job ownership changed")
    return work


def claim(db: Session, wid: int, job_id: str, runtime: CandidateRuntime) -> str | None:
    row = load(db, wid, job_id)
    work = owned_work(row)
    current(db, work, principal_for(db, row), runtime)
    db.refresh(row, with_for_update=True)
    now = runtime.clock()
    if row.input_digest != work.digest() or row.work != work.model_dump(mode="json"):
        raise HTTPException(409, "candidate job integrity changed")
    if row.state not in {"pending", "claimed"} or utc(row.due_at) > now:
        return None
    if row.state == "claimed" and row.lease_until is not None and utc(row.lease_until) > now:
        return None
    row.state, row.fence = "claimed", uuid4().hex
    row.attempts += 1
    row.lease_until = now + timedelta(minutes=2)
    db.commit()
    return row.fence


def retire_or_retry(
    db: Session, wid: int, job_id: str, token: str | None, now: datetime, *, retry: bool
) -> None:
    # No financial lock follows this path: only own read-job metadata is changed.
    db.scalar(select(Workspace).where(Workspace.id == wid).with_for_update())
    row = db.scalar(
        select(CandidateJob)
        .where(CandidateJob.id == job_id, CandidateJob.workspace_id == wid)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if (
        row is None
        or (token is not None and row.fence != token)
        or (token is None and row.state != "pending")
    ):
        return
    row.error_code = "candidate_source_unavailable" if retry else "candidate_authority_changed"
    row.state = "pending" if retry and row.attempts < 5 else "blocked"
    row.due_at = now + timedelta(seconds=min(3600, 30 * 2 ** min(row.attempts, 7)))
    row.lease_until, row.fence = None, None
    db.commit()


def check_evidence_profile(observation: CandidateObservation, runtime: CandidateRuntime) -> None:
    evidence = observation.evidence
    profile = (
        evidence.source_schema,
        evidence.qualification_profile or "",
        evidence.qualification_revision or 0,
        evidence.qualification_digest or "",
    )
    if evidence.qualification == "qualified_learning" and (
        evidence.source_schema in ACTUAL_UNQUALIFIED_SCHEMAS
        or profile not in runtime.learning_profiles
    ):
        raise HTTPException(409, "measured learning producer unavailable")
    if evidence.qualification == "contract_scenario" and runtime.environment != "contract_test":
        raise HTTPException(409, "contract evidence cannot qualify live")


def process(engine: Engine, wid: int, job_id: str, runtime: CandidateRuntime) -> str:
    token: str | None = None
    with Session(engine) as db:
        try:
            token = claim(db, wid, job_id, runtime)
            if token is None:
                return "not_due"
            row = load(db, wid, job_id)
            work = owned_work(row)
            db.commit()
            observation = runtime.reader(db, work.scope, runtime.clock())
            from app.optimization_candidates.contracts import CandidateObservation

            observation = CandidateObservation.model_validate(observation.model_dump(mode="json"))
            db.commit()
            if observation.scope != work.scope or (
                isinstance(work, CandidateWorkV2)
                and observation.state.digest() != work.selection.state_digest
            ):
                raise HTTPException(409, "candidate observation changed")
            evidence = observation.evidence
            check_evidence_profile(observation, runtime)
            row = load(db, wid, job_id)
            policy, positive, actions = current(db, work, principal_for(db, row), runtime)
            db.refresh(row, with_for_update=True)
            if (
                row.state != "claimed"
                or row.fence != token
                or row.work != work.model_dump(mode="json")
                or row.lease_until is None
                or utc(row.lease_until) <= runtime.clock()
            ):
                return "superseded"
            if isinstance(work, CandidateWorkV2) and runtime.clock() >= work.selection.expires_at:
                raise HTTPException(409, "candidate selection expired during result lock")
            if runtime.authorized_evidence_transform is not None:
                original_state = observation.state.model_dump(mode="json")
                original_scope = observation.scope.model_dump(mode="json")
                transformed = runtime.authorized_evidence_transform(
                    db,
                    principal_for(db, row),
                    work,
                    observation.model_copy(deep=True),
                    runtime.clock(),
                )
                observation = CandidateObservation.model_validate(
                    transformed.model_dump(mode="json")
                )
                if (
                    observation.scope.model_dump(mode="json") != original_scope
                    or observation.state.model_dump(mode="json") != original_state
                ):
                    raise HTTPException(409, "local evidence cannot change owned scope or state")
                check_evidence_profile(observation, runtime)
                evidence = observation.evidence
                policy, positive, actions = current(db, work, principal_for(db, row), runtime)
                if (
                    isinstance(work, CandidateWorkV2)
                    and runtime.clock() >= work.selection.expires_at
                ):
                    raise HTTPException(409, "candidate selection expired during local derivation")
            if evidence.source_schema in runtime.feedback_dependent_schemas:
                if runtime.authorized_final_evidence_current is not None:
                    runtime.authorized_final_evidence_current(
                        db, principal_for(db, row), work, observation
                    )
                elif runtime.final_evidence_current is not None:
                    runtime.final_evidence_current(db, work, observation)
                else:
                    raise HTTPException(409, "current feedback lineage reader unavailable")
                # This callback is local/noncommitting; resample authority and time
                # after any dependency locks it needed before storing derived data.
                policy, positive, actions = current(db, work, principal_for(db, row), runtime)
                if (
                    isinstance(work, CandidateWorkV2)
                    and runtime.clock() >= work.selection.expires_at
                ):
                    raise HTTPException(409, "candidate selection expired during evidence check")
            # Local dependency locks can outlast the read claim even when the
            # original customer session remains valid. Never publish from an
            # expired lease after either local callback.
            if row.lease_until is None or utc(row.lease_until) <= runtime.clock():
                return "superseded"
            decision = compile_candidate(
                observation, work.policy, policy, positive, actions, runtime.clock()
            )
            db.add(
                CandidateResult(
                    id=uuid4().hex,
                    workspace_id=wid,
                    job_id=row.id,
                    input_digest=row.input_digest,
                    policy_digest=decision.policy_digest,
                    evidence_digest=decision.evidence_digest,
                    decision_digest=decision.digest(),
                    decision=decision.model_dump(mode="json"),
                    created_at=runtime.clock(),
                )
            )
            row.state, row.completed_at = "completed", runtime.clock()
            row.error_code, row.lease_until, row.fence = None, None, None
            db.commit()
            return "completed"
        except HTTPException:
            db.rollback()
            retire_or_retry(db, wid, job_id, token, runtime.clock(), retry=False)
            return "blocked"
        except Exception:
            db.rollback()
            retire_or_retry(db, wid, job_id, token, runtime.clock(), retry=True)
            return "retry"


def run_candidate_reads(
    engine: Engine,
    factory: Callable[[], CandidateRuntime | None] = get_candidate_runtime,
    *,
    limit: int = 10,
) -> dict[str, int]:
    runtime = factory()
    if runtime is None:
        return {}
    if not 1 <= limit <= 100:
        raise ValueError("bounded candidate batch required")
    now = runtime.clock()
    with Session(engine) as db:
        due = (
            CandidateJob.environment == runtime.environment,
            CandidateJob.due_at <= now,
            or_(
                CandidateJob.state == "pending",
                (CandidateJob.state == "claimed") & (CandidateJob.lease_until <= now),
            ),
        )
        tenants = list(
            db.scalars(
                select(CandidateJob.workspace_id)
                .where(*due)
                .group_by(CandidateJob.workspace_id)
                .order_by(func.min(CandidateJob.due_at), CandidateJob.workspace_id)
                .limit(limit)
            )
        )
        jobs = [
            (
                wid,
                db.scalar(
                    select(CandidateJob.id)
                    .where(*due, CandidateJob.workspace_id == wid)
                    .order_by(CandidateJob.due_at, CandidateJob.id)
                    .limit(1)
                ),
            )
            for wid in tenants
        ]
    counts: dict[str, int] = {}
    for wid, identifier in jobs:
        if identifier is not None:
            try:
                result = process(engine, wid, identifier, runtime)
            except Exception:
                # Failed read-job bookkeeping cannot starve other selected workspaces.
                result = "unavailable"
            counts[result] = counts.get(result, 0) + 1
    return counts


def read_result(
    db: Session,
    wid: int,
    identifier: str,
    principal: CustomerPrincipal,
    runtime: CandidateRuntime,
    *,
    erase_invalid: bool = True,
) -> CandidateDecision:
    authorize(db, principal, wid, runtime)
    result = db.scalar(
        select(CandidateResult).where(
            CandidateResult.id == identifier, CandidateResult.workspace_id == wid
        )
    )
    if result is None:
        raise HTTPException(404, "candidate result unavailable")
    job = load(db, wid, result.job_id)
    work = owned_work(job)
    try:
        current(db, work, principal, runtime)
    except HTTPException:
        if not erase_invalid:
            raise HTTPException(409, "candidate source invalidated") from None
        db.execute(
            delete(CandidateJob).where(CandidateJob.id == job.id, CandidateJob.workspace_id == wid)
        )
        db.commit()
        raise HTTPException(404, "candidate source invalidated") from None
    decision = CandidateDecision.model_validate(result.decision)
    if (
        decision.digest() != result.decision_digest
        or decision.scope != work.scope
        or decision.policy_digest != work.policy.digest()
        or result.input_digest != work.digest()
        or decision.evidence_digest != result.evidence_digest
    ):
        raise HTTPException(409, "candidate integrity unavailable")
    if decision.expires_at <= runtime.clock():
        raise HTTPException(409, "candidate observation expired")
    return decision
