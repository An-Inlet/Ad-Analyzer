"""Durable one-emission activation of the separately approved exact paused graph."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import advertising_capabilities
from app.campaign_review.contracts import MediaStore
from app.goals.schemas import StrictModel
from app.publication import activation_review as reviews
from app.publication import coordinator as creation
from app.publication import execution_mandates as mandates
from app.publication.activation_contracts import (
    ActivationContext,
    ActivationReceipt,
    ActivationRequest,
    ActivationResponse,
    ActivationTransport,
)
from app.publication.contracts import fingerprint
from app.publication.coordinator_contracts import CreationReceipt
from app.publication.execution_contracts import (
    Environment,
    NormalizedProviderReceipt,
    ProviderMandatePolicy,
)
from app.publication.execution_models import (
    ProviderExecutionApproval,
    ProviderExecutionAttempt,
    ProviderExecutionReceipt,
    ProviderExecutionResponse,
    ProviderExecutionReview,
    ProviderExecutionRevision,
    ProviderExecutionRun,
    ProviderExecutionStep,
    ProviderExposureReservation,
)
from app.publication.provider_contracts import BoundProviderRequest, Id, ProviderResponse
from app.publication.service import owner
from app.publication.social_contracts import SocialProviderResponse
from app.publication.tiktok_linked_plan import LinkedPushBoundRequestV1
from app.shopify.security import utc
from app.workspaces.models import Workspace


@dataclass(frozen=True)
class ActivationRuntime:
    review: reviews.ActivationReviewRuntime
    google: ActivationTransport
    meta: ActivationTransport
    tiktok: ActivationTransport
    context: Callable[[ActivationRequest], ActivationContext]

    linked_tiktok: ActivationTransport | None = None

    def transport(self, request: ActivationRequest) -> ActivationTransport:
        if isinstance(request.target.original_request, LinkedPushBoundRequestV1):
            if self.linked_tiktok is None:
                raise HTTPException(409, "linked_activation_unavailable")
            return self.linked_tiktok
        return {"google_ads": self.google, "meta_ads": self.meta, "tiktok_ads": self.tiktok}[
            request.account.account.platform
        ]


def get_activation_runtime() -> ActivationRuntime | None:
    return None


class ActivationClaim(StrictModel):
    workspace_id: int
    run_id: Id
    attempt_id: Id
    environment: Environment
    request: ActivationRequest


def locked_run(
    db: Session,
    wid: int,
    run_id: str,
    actor: str,
    store: MediaStore,
    runtime: ActivationRuntime,
    clock: creation.Clock,
) -> tuple[ProviderExecutionRun, reviews.ActivationExecutionReview]:
    run = db.scalar(
        select(ProviderExecutionRun).where(
            ProviderExecutionRun.id == run_id, ProviderExecutionRun.workspace_id == wid
        )
    )
    if run is None:
        raise HTTPException(404, "activation run unavailable")
    row, document = reviews.checked_review(
        db, wid, run.review_id, actor, store, runtime.review, clock
    )
    approval = db.get(ProviderExecutionApproval, row.id)
    if approval is None or (approval.review_digest, approval.plan_digest) != (
        row.digest,
        row.plan_digest,
    ):
        raise HTTPException(409, "separate exact activation approval required")
    owner(db, wid, approval.actor)
    db.refresh(run, with_for_update=True)
    if (
        run.canceled_at is not None
        or run.state == "canceled"
        or run.parent_run_id != document.plan.parent_run_id
        or run.reservation_id != document.reservation_id
    ):
        raise HTTPException(409, "activation canceled or original reservation changed")
    return run, document


def claim_step(
    db: Session,
    wid: int,
    run_id: str,
    actor: str,
    store: MediaStore,
    runtime: ActivationRuntime,
    clock: creation.Clock,
) -> ActivationClaim | None:
    advertising_capabilities.require_advertising_write()
    run, document = locked_run(db, wid, run_id, actor, store, runtime, clock)
    ledger, policy = mandates.checked(db, wid, document.mandate, actor, clock)
    # The original reservation remains held; never reserve this budget owner a second time.
    others = (
        db.scalar(
            select(func.coalesce(func.sum(ProviderExposureReservation.amount_micros), 0)).where(
                ProviderExposureReservation.workspace_id == wid,
                ProviderExposureReservation.environment == document.mandate.environment,
                ProviderExposureReservation.state == "held",
                ProviderExposureReservation.id != document.reservation_id,
            )
        )
        or 0
    )
    if others != document.exposure.existing_reservations_micros:
        raise HTTPException(409, "current activation portfolio exposure changed")
    first = db.scalar(
        select(ProviderExecutionAttempt.id)
        .where(
            ProviderExecutionAttempt.run_id == run.id, ProviderExecutionAttempt.workspace_id == wid
        )
        .limit(1)
    )
    if first is None and run.state == "ready":
        if ledger.action_count >= policy.action_limit or (
            ledger.last_dispatch_at is not None
            and (clock() - utc(ledger.last_dispatch_at)).total_seconds() < policy.cooldown_seconds
        ):
            raise HTTPException(409, "activation action limit or cooldown")
        ledger.action_count += 1
        ledger.last_dispatch_at = clock()
        ledger.spent_high_water_micros = max(
            ledger.spent_high_water_micros, document.exposure.reported_spend_micros
        )
        run.state = "reserved"
        db.commit()
        # A cancellation or revocation may win in this commit gap.
        run, document = locked_run(db, wid, run_id, actor, store, runtime, clock)
    steps = list(
        db.scalars(
            select(ProviderExecutionStep)
            .where(
                ProviderExecutionStep.run_id == run.id, ProviderExecutionStep.workspace_id == wid
            )
            .order_by(ProviderExecutionStep.ordinal)
            .with_for_update()
        )
    )
    step = next((s for s in steps if s.state != "verified_target_state"), None)
    if step is None:
        run.state = "activation_observed"
        db.commit()
        return None
    if step.state != "pending":
        return None  # no replacement fence for unknown, emitting or conflicting attempts
    target = next(t for t in document.plan.targets if t.step_id == step.step_id)
    reviews.validate_fresh(db, wid, document, actor, clock)
    request = ActivationRequest(
        run_id=run.id,
        plan_digest=document.plan.digest(),
        review_digest=document.digest(),
        mandate=document.mandate,
        target=target,
        fence=uuid4().hex,
        dispatched_at=clock(),
    )
    attempt = ProviderExecutionAttempt(
        id=uuid4().hex,
        workspace_id=wid,
        run_id=run.id,
        step_id=step.step_id,
        fence=request.fence,
        request=request.model_dump(mode="json"),
        request_digest=request.digest(),
        dispatched_at=request.dispatched_at,
    )
    db.add(attempt)
    step.state, run.state = "dispatching", "dispatching"
    db.commit()
    return ActivationClaim(
        workspace_id=wid,
        run_id=run.id,
        attempt_id=attempt.id,
        environment=document.mandate.environment,
        request=request,
    )


def evidence_lock(
    db: Session,
    wid: int,
    attempt_id: str,
) -> tuple[
    ProviderExecutionRun,
    reviews.ActivationExecutionReview,
    ProviderExecutionAttempt,
    ActivationRequest,
]:
    workspace = db.scalar(select(Workspace).where(Workspace.id == wid).with_for_update())
    if workspace is None:
        raise HTTPException(404, "workspace unavailable")
    attempt = db.scalar(
        select(ProviderExecutionAttempt).where(
            ProviderExecutionAttempt.id == attempt_id, ProviderExecutionAttempt.workspace_id == wid
        )
    )
    if attempt is None:
        raise HTTPException(404, "activation attempt unavailable")
    run = db.scalar(
        select(ProviderExecutionRun)
        .where(ProviderExecutionRun.id == attempt.run_id, ProviderExecutionRun.workspace_id == wid)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    assert run is not None
    row = db.get(ProviderExecutionReview, run.review_id)
    if row is None or row.workspace_id != wid or row.document.get("purpose") != "activate":
        raise HTTPException(409, "original activation review unavailable")
    document = reviews.ActivationExecutionReview.model_validate(row.document)
    request = ActivationRequest.model_validate(attempt.request)
    expected = next((t for t in document.plan.targets if t.step_id == attempt.step_id), None)
    if (
        row.digest != document.digest()
        or row.plan_digest != document.plan.digest()
        or request.target != expected
        or request.run_id != run.id
        or request.plan_digest != document.plan.digest()
        or request.review_digest != document.digest()
        or request.mandate != document.mandate
        or request.digest() != attempt.request_digest
        or request.fence != attempt.fence
        or request.dispatched_at != utc(attempt.dispatched_at)
        or run.parent_run_id != document.plan.parent_run_id
        or run.reservation_id != document.reservation_id
    ):
        raise HTTPException(409, "original activation attempt changed")
    return run, document, attempt, request


def validate_receipt(request: ActivationRequest, receipt: ActivationReceipt) -> None:
    if (
        receipt.run_id != request.run_id
        or receipt.step_id != request.target.step_id
        or receipt.account != request.account
        or receipt.fence != request.fence
        or receipt.request_digest != request.digest()
        or receipt.observed_at < request.dispatched_at
        or (
            receipt.resource_name is not None
            and receipt.resource_name != request.target.resource_name
        )
    ):
        raise HTTPException(409, "activation receipt does not bind original request")


def normalized(
    db: Session,
    run: ProviderExecutionRun,
    document: reviews.ActivationExecutionReview,
    attempt: ProviderExecutionAttempt,
    receipt: ActivationReceipt,
    receipt_id: str,
    digest: str,
    sequence: int,
    supersedes: str | None,
) -> NormalizedProviderReceipt:
    revision = db.get(
        ProviderExecutionRevision, (document.mandate.mandate_id, document.mandate.revision)
    )
    if revision is None or revision.workspace_id != run.workspace_id:
        raise HTTPException(409, "original activation policy unavailable")
    policy = ProviderMandatePolicy.model_validate(revision.policy)
    if policy.digest() != document.mandate.policy_digest:
        raise HTTPException(409, "original activation policy changed")
    request = ActivationRequest.model_validate(attempt.request)
    return NormalizedProviderReceipt(
        receipt_id=receipt_id,
        receipt_digest=digest,
        sequence=sequence,
        supersedes_receipt_id=supersedes,
        run_id=run.id,
        action_id=run.id,
        plan_id=run.id,
        step_id=attempt.step_id,
        attempt_id=attempt.id,
        review_digest=document.digest(),
        plan_digest=document.plan.digest(),
        request_digest=attempt.request_digest,
        fence=attempt.fence,
        environment=document.mandate.environment,
        purpose="activate",
        account=document.plan.account,
        mandate=document.mandate,
        source_draft_id=document.creation_plan.review.source.draft_id,
        source_revision=document.creation_plan.review.source.revision,
        goal_id=policy.goal_id,
        goal_revision=policy.goal_revision,
        budget_owner_key=document.exposure.budget_owner_key,
        target_set_digest=document.exposure.target_set_digest,
        before_state_digest=request.target.before_readback_digest,
        after_state_digest=receipt.readback_digest,
        dispatched_at=utc(attempt.dispatched_at),
        observed_at=receipt.observed_at,
        outcome=receipt.outcome,
        evidence=receipt.evidence,
        resource_kind=receipt.resource_name.split("/")[2] if receipt.resource_name else None,
        resource_name=receipt.resource_name,
        readback_digest=receipt.readback_digest,
    )


def record_receipt(
    db: Session,
    wid: int,
    attempt_id: str,
    receipt: ActivationReceipt,
    clock: creation.Clock,
) -> ProviderExecutionReceipt:
    run, document, attempt, request = evidence_lock(db, wid, attempt_id)
    receipt = ActivationReceipt.model_validate(receipt.model_dump(mode="json"))
    validate_receipt(request, receipt)
    if receipt.observed_at > clock():
        raise HTTPException(409, "future activation receipt")
    raw = receipt.model_dump(mode="json")
    digest = fingerprint("inlet.activation-receipt.v1", raw)
    existing = db.scalar(
        select(ProviderExecutionReceipt).where(
            ProviderExecutionReceipt.attempt_id == attempt.id,
            ProviderExecutionReceipt.digest == digest,
        )
    )
    if existing is not None:
        return existing
    previous = db.scalar(
        select(ProviderExecutionReceipt)
        .where(ProviderExecutionReceipt.attempt_id == attempt.id)
        .order_by(ProviderExecutionReceipt.sequence.desc())
        .limit(1)
    )
    if previous is not None and receipt.observed_at < utc(previous.observed_at):
        raise HTTPException(409, "stale activation receipt")
    from app.optimization_candidates.invalidation import erase_attempt_candidates

    erase_attempt_candidates(db, wid, attempt.id)
    rid, sequence = uuid4().hex, previous.sequence + 1 if previous else 1
    projection = normalized(
        db,
        run,
        document,
        attempt,
        receipt,
        rid,
        digest,
        sequence,
        previous.id if previous else None,
    )
    row = ProviderExecutionReceipt(
        id=rid,
        workspace_id=wid,
        attempt_id=attempt.id,
        sequence=sequence,
        supersedes_id=previous.id if previous else None,
        digest=digest,
        receipt=raw,
        projection=projection.model_dump(mode="json"),
        observed_at=receipt.observed_at,
    )
    db.add(row)
    step = db.get(ProviderExecutionStep, (run.id, attempt.step_id))
    assert step is not None
    step.state = receipt.outcome
    if run.canceled_at is None:
        run.state = "ready" if receipt.outcome == "verified_target_state" else receipt.outcome
    db.commit()
    return row


def read_owned_outcome_receipt(
    db: Session,
    workspace_id: int,
    attempt_id: str,
    actor: str,
) -> NormalizedProviderReceipt | None:
    run, document, attempt, request = evidence_lock(db, workspace_id, attempt_id)
    owner(db, workspace_id, actor)
    latest = db.scalar(
        select(ProviderExecutionReceipt)
        .where(
            ProviderExecutionReceipt.attempt_id == attempt.id,
            ProviderExecutionReceipt.workspace_id == workspace_id,
        )
        .order_by(ProviderExecutionReceipt.sequence.desc())
        .limit(1)
    )
    if latest is None:
        return None
    receipt = ActivationReceipt.model_validate(latest.receipt)
    validate_receipt(request, receipt)
    if latest.sequence > 1:
        previous = db.get(ProviderExecutionReceipt, latest.supersedes_id)
        if (
            previous is None
            or previous.workspace_id != workspace_id
            or previous.attempt_id != attempt.id
            or previous.sequence + 1 != latest.sequence
        ):
            raise HTTPException(409, "activation supersession changed")
    digest = fingerprint("inlet.activation-receipt.v1", receipt.model_dump(mode="json"))
    projection = normalized(
        db,
        run,
        document,
        attempt,
        receipt,
        latest.id,
        digest,
        latest.sequence,
        latest.supersedes_id,
    )
    if latest.digest != digest or latest.projection != projection.model_dump(mode="json"):
        raise HTTPException(409, "activation projection changed")
    return projection


def unknown(request: ActivationRequest, clock: creation.Clock) -> ActivationReceipt:
    return ActivationReceipt(
        run_id=request.run_id,
        step_id=request.target.step_id,
        account=request.account,
        fence=request.fence,
        request_digest=request.digest(),
        outcome="unknown",
        evidence="unresolved",
        observed_at=clock(),
    )


def record_response(
    db: Session,
    wid: int,
    attempt_id: str,
    response: ActivationResponse,
    clock: creation.Clock,
) -> None:
    _, original_review, attempt, request = evidence_lock(db, wid, attempt_id)
    if response.request_digest != request.digest():
        raise HTTPException(409, "activation response request mismatch")
    raw = response.model_dump(mode="json")
    digest = fingerprint("inlet.activation-response.v1", raw)
    if db.get(ProviderExecutionResponse, (attempt.id, digest)) is None:
        db.add(
            ProviderExecutionResponse(
                attempt_id=attempt.id,
                workspace_id=wid,
                digest=digest,
                response=raw,
                observed_at=clock(),
            )
        )
    from app.publication.google_execution_completion import capture_execution_response
    from app.publication.google_execution_completion_contracts import (
        GoogleCapturedActivationResponse,
    )

    if isinstance(response, GoogleCapturedActivationResponse):
        capture_execution_response(
            db, request, response, attempt, original_review.mandate.environment, digest, clock()
        )
    db.commit()


def preflight_graph(
    db: Session,
    claim: ActivationClaim,
    document: reviews.ActivationExecutionReview,
    runtime: ActivationRuntime,
    clock: creation.Clock,
) -> None:
    """Read every original field outside locks, including non-activatable resources.

    This is a fresh preflight, not provider CAS. External edits after these reads remain
    an explicit qualification limitation. No read can mint authority or a new fence.
    """
    states = {
        row.step_id: row.state
        for row in db.scalars(
            select(ProviderExecutionStep).where(
                ProviderExecutionStep.run_id == claim.run_id,
                ProviderExecutionStep.workspace_id == claim.workspace_id,
            )
        )
    }
    non_targets = []
    target_ids = {t.step_id for t in document.plan.targets}
    for ref in document.graph:
        if ref.step_id in target_ids:
            continue
        _, _, _, original = creation.evidence_lock(db, claim.workspace_id, ref.attempt_id)
        raw_history = [
            r.response
            for r in db.scalars(
                select(ProviderExecutionResponse).where(
                    ProviderExecutionResponse.attempt_id == ref.attempt_id,
                    ProviderExecutionResponse.workspace_id == claim.workspace_id,
                )
            )
        ]
        non_targets.append((ref, original, raw_history))
    db.commit()
    for target in document.plan.targets:
        probe = claim.request.model_copy(update={"target": target})
        expected: Literal["paused", "active"] = (
            "active" if states[target.step_id] == "verified_target_state" else "paused"
        )
        observation = runtime.transport(probe).read_exact(
            probe, runtime.context(probe), expected, clock()
        )
        if (
            observation.request_digest != probe.digest()
            or observation.resource_name != target.resource_name
            or observation.state != expected
            or (
                expected == "paused"
                and observation.readback_digest != target.before_readback_digest
            )
        ):
            raise HTTPException(409, "complete activation graph preflight changed")
    base = runtime.review.creation
    receipt: CreationReceipt
    for ref, original, raw_history in non_targets:
        if isinstance(original, BoundProviderRequest):
            receipt = base.google.reconcile(
                original,
                [ProviderResponse.model_validate(r) for r in raw_history],
                base.google_context(original),
                clock(),
            )
        elif isinstance(original, LinkedPushBoundRequestV1):
            if base.linked_tiktok is None or base.linked_context is None:
                raise HTTPException(409, "linked historical reader unavailable")
            receipt = base.linked_tiktok.reconcile(
                original,
                [SocialProviderResponse.model_validate(r) for r in raw_history],
                base.linked_context(original),
                clock(),
            )
        else:
            adapter = base.meta if original.scope.account.platform == "meta_ads" else base.tiktok
            receipt = adapter.reconcile(
                original,
                [SocialProviderResponse.model_validate(r) for r in raw_history],
                base.social_context(original),
                clock(),
            )
        if (
            receipt.outcome != "verified_effect"
            or receipt.request_digest != original.digest()
            or receipt.readback_digest != ref.readback_digest
            or receipt.scope != original.scope
            or receipt.fence != original.fence
        ):
            raise HTTPException(409, "non-activatable original graph changed")


def execute_claim(
    db: Session,
    claim: ActivationClaim,
    actor: str,
    store: MediaStore,
    runtime: ActivationRuntime,
    clock: creation.Clock,
) -> ActivationReceipt:
    advertising_capabilities.require_advertising_write()
    run, document = locked_run(db, claim.workspace_id, claim.run_id, actor, store, runtime, clock)
    original = db.get(ProviderExecutionAttempt, claim.attempt_id)
    initial_step = db.get(ProviderExecutionStep, (run.id, claim.request.target.step_id))
    if (
        original is None
        or original.workspace_id != claim.workspace_id
        or original.run_id != run.id
        or original.request != claim.request.model_dump(mode="json")
        or initial_step is None
        or initial_step.state != "dispatching"
        or claim.environment != document.mandate.environment
    ):
        raise HTTPException(409, "original activation claim unavailable")
    preflight_graph(db, claim, document, runtime, clock)
    emission_context = runtime.context(claim.request)
    # Reacquire exact authority after all blocking HTTP/storage/credential reads.
    run, document = locked_run(db, claim.workspace_id, claim.run_id, actor, store, runtime, clock)
    attempt = db.get(ProviderExecutionAttempt, claim.attempt_id)
    step = db.get(ProviderExecutionStep, (run.id, claim.request.target.step_id))
    if (
        attempt is None
        or attempt.workspace_id != claim.workspace_id
        or attempt.run_id != run.id
        or attempt.request != claim.request.model_dump(mode="json")
        or claim.environment != document.mandate.environment
        or step is None
        or step.state != "dispatching"
    ):
        raise HTTPException(409, "original activation claim unavailable")
    step.state = "emitting"
    db.commit()
    request = claim.request
    adapter = runtime.transport(request)
    try:
        response = adapter.apply_once(request, emission_context, clock())
    except advertising_capabilities.AdvertisingWritesDisabled:
        raise
    except Exception:
        response = ActivationResponse(request_digest=request.digest(), outcome="unknown")
    record_response(db, claim.workspace_id, claim.attempt_id, response, clock)
    try:
        receipt = adapter.read_back(request, response, runtime.context(request), clock())
    except advertising_capabilities.AdvertisingWritesDisabled:
        raise
    except Exception:
        receipt = unknown(request, clock)
    record_receipt(db, claim.workspace_id, claim.attempt_id, receipt, clock)
    return receipt


def reconcile_attempt(
    db: Session,
    wid: int,
    attempt_id: str,
    runtime: ActivationRuntime,
    clock: creation.Clock,
) -> ActivationReceipt:
    _, document, _, request = evidence_lock(db, wid, attempt_id)
    if runtime.review.creation.environment != document.mandate.environment:
        raise HTTPException(409, "activation reconciliation environment mismatch")
    history = [
        ActivationResponse.model_validate(row.response)
        for row in db.scalars(
            select(ProviderExecutionResponse).where(
                ProviderExecutionResponse.attempt_id == attempt_id,
                ProviderExecutionResponse.workspace_id == wid,
            )
        )
    ]
    db.commit()
    try:
        receipt = runtime.transport(request).reconcile(
            request, history, runtime.context(request), clock()
        )
    except advertising_capabilities.AdvertisingWritesDisabled:
        raise
    except Exception:
        receipt = unknown(request, clock)
    record_receipt(db, wid, attempt_id, receipt, clock)
    return receipt
