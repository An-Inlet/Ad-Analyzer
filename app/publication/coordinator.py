"""Durable, separately consented real-adapter creation coordinator.

No HTTP under database locks. An original committed attempt is never replayed or
re-fenced because a clock elapsed or a provider read returned no row.
"""

from collections.abc import Callable
from datetime import datetime
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.automation.catalog import AutomationControlKey
from app.automation.models import PlatformAutomationControl
from app.campaign_review import service as sources
from app.campaign_review.contracts import MediaStore
from app.publication import execution_mandates as mandates
from app.publication.contracts import fingerprint
from app.publication.coordinator_contracts import (
    CreationExecutionReview,
    CreationPlan,
    CreationReceipt,
    CreationRequest,
    CreationResponse,
    CreationRuntime,
    DispatchClaim,
)
from app.publication.execution_contracts import (
    ExecutionAccount,
    NormalizedProviderReceipt,
    ProviderMandateBinding,
)
from app.publication.execution_models import (
    ProviderExecutionApproval,
    ProviderExecutionAttempt,
    ProviderExecutionReceipt,
    ProviderExecutionResponse,
    ProviderExecutionReview,
    ProviderExecutionRun,
    ProviderExecutionStep,
    ProviderExposureReservation,
)
from app.publication.google_compiler import compile_google, materialize_google
from app.publication.provider_contracts import (
    BoundProviderRequest,
    ProviderPublishPlan,
    ProviderReceipt,
    ProviderResponse,
)
from app.publication.service import owner
from app.publication.social_compiler import compile_social, materialize_social
from app.publication.social_contracts import (
    SocialBoundRequest,
    SocialProviderReceipt,
    SocialProviderResponse,
    SocialPublishPlan,
)
from app.publication.tiktok_creation_policy import new_creation_allowed
from app.publication.tiktok_linked_plan import (
    LINKED_OUTPUTS,
    LinkedPushBoundRequestV1,
    LinkedPushPlanV1,
    compile_linked_push,
    materialize_linked_push,
)
from app.shopify.security import utc
from app.workspaces.models import Workspace

Clock = Callable[[], datetime]


def canonical(plan: CreationPlan) -> None:
    if isinstance(plan, ProviderPublishPlan):
        rebuilt: CreationPlan = compile_google(plan.review)
    elif isinstance(plan, SocialPublishPlan):
        rebuilt = compile_social(plan.review)
    else:
        rebuilt = compile_linked_push(plan.review)
    if rebuilt != plan:
        raise HTTPException(409, "registered canonical provider plan required")


def gate(runtime: CreationRuntime, environment: str, plan: CreationPlan | None = None) -> None:
    if runtime.environment != environment or (environment == "live" and not runtime.live_enabled):
        raise HTTPException(409, "provider execution runtime unavailable")
    if isinstance(plan, SocialPublishPlan):
        if environment == "live" and plan.review.configuration_review is None:
            raise HTTPException(409, "customer configuration confirmation required")
        if (
            plan.review.configuration_review is not None
            and runtime.social_configuration_current is None
        ):
            raise HTTPException(409, "current social configuration validator unavailable")
    if isinstance(plan, LinkedPushPlanV1) and (
        environment != "contract_test"
        or runtime.linked_tiktok is None
        or runtime.linked_context is None
        or runtime.linked_configuration_current is None
    ):
        raise HTTPException(409, "linked configuration runtime unavailable")


def source_current(
    db: Session, wid: int, plan: CreationPlan, actor: str, store: MediaStore, clock: Clock
) -> None:
    canonical(plan)
    if plan.review.scope.workspace_id != wid:
        raise HTTPException(404, "provider review unavailable")
    owner(db, wid, actor)
    row, artifact = sources.preview(db, wid, plan.review.source.draft_id, store, clock())
    if (
        row.approved_by is None
        or artifact != plan.review.source
        or artifact.fingerprint() != plan.review.source_digest
    ):
        raise HTTPException(409, "current approved source revision required")
    owner(db, wid, row.approved_by)
    mandates.current_account(db, ExecutionAccount.from_publication(plan.review.scope))
    if isinstance(plan, SocialPublishPlan) and plan.review.configuration_review is not None:
        from app.publication.social_review_service import verify_plan

        verify_plan(db, wid, plan, actor)
    if isinstance(plan, LinkedPushPlanV1):
        from app.publication.tiktok_linked_review_service import verify_plan as verify_linked

        verify_linked(db, wid, plan, actor)


def social_configuration_current(
    db: Session,
    wid: int,
    plan: CreationPlan,
    actor: str,
    runtime: CreationRuntime,
    clock: Clock,
) -> None:
    gate(runtime, runtime.environment, plan)
    if isinstance(plan, SocialPublishPlan) and plan.review.configuration_review is not None:
        from app.publication.social_review_service import verify_plan

        document = verify_plan(db, wid, plan, actor)
        if document.environment != runtime.environment:
            raise HTTPException(409, "configuration environment changed")
        if runtime.social_configuration_current is None:
            raise HTTPException(409, "current social configuration validator unavailable")
        runtime.social_configuration_current(document, clock())
    if isinstance(plan, LinkedPushPlanV1):
        from app.publication.tiktok_linked_review_service import verify_plan as verify_linked

        linked_document = verify_linked(db, wid, plan, actor)
        if (
            linked_document.environment != runtime.environment
            or runtime.linked_configuration_current is None
        ):
            raise HTTPException(409, "linked configuration runtime unavailable")
        runtime.linked_configuration_current(linked_document, clock())


def prepare_creation(
    db: Session,
    wid: int,
    plan: CreationPlan,
    binding: ProviderMandateBinding,
    actor: str,
    store: MediaStore,
    runtime: CreationRuntime,
    clock: Clock,
) -> ProviderExecutionReview:
    new_creation_allowed(plan)
    gate(runtime, binding.environment, plan)
    runtime.authorize(db, wid, actor)
    _, policy = mandates.checked(db, wid, binding, actor, clock)
    source_current(db, wid, plan, actor, store, clock)
    social_configuration_current(db, wid, plan, actor, runtime, clock)
    if "create_paused" not in policy.allowed_purposes:
        raise HTTPException(409, "creation outside approved policy")
    db.commit()
    qualification = runtime.qualification_reader(plan, clock())
    exposure = runtime.exposure_reader(db, binding, plan, clock())
    db.commit()  # any read-side transaction is released before lock reacquisition
    runtime.authorize(db, wid, actor)
    ledger, policy = mandates.checked(db, wid, binding, actor, clock)
    source_current(db, wid, plan, actor, store, clock)
    social_configuration_current(db, wid, plan, actor, runtime, clock)
    document = CreationExecutionReview(
        mandate=binding, plan=plan, qualification=qualification, exposure=exposure
    )
    now = clock()
    if (
        not qualification.observed_at <= now < qualification.expires_at
        or not exposure.eligible(policy, now)
        or ledger.spent_high_water_micros > exposure.reported_spend_micros
    ):
        raise HTTPException(409, "fresh bounded provider qualification required")
    existing = db.scalar(
        select(ProviderExecutionReview).where(
            ProviderExecutionReview.workspace_id == wid,
            ProviderExecutionReview.digest == document.digest(),
        )
    )
    now = clock()
    if not qualification.observed_at <= now < qualification.expires_at or not exposure.eligible(
        policy, now
    ):
        raise HTTPException(409, "execution qualification expired before persistence")
    if existing is not None:
        return existing
    source = plan.review.source
    row = ProviderExecutionReview(
        id=uuid4().hex,
        workspace_id=wid,
        consent_id=binding.consent_id,
        account_id=plan.review.scope.account.account_id,
        integration_id=plan.review.scope.account.connection_id,
        source_draft_id=source.draft_id,
        source_revision=source.revision,
        document=document.model_dump(mode="json"),
        digest=document.digest(),
        plan_digest=plan.digest(),
        actor=actor,
        created_at=clock(),
    )
    db.add(row)
    db.commit()
    return row


def checked_review(
    db: Session,
    wid: int,
    review_id: str,
    actor: str,
    store: MediaStore,
    runtime: CreationRuntime,
    clock: Clock,
) -> tuple[ProviderExecutionReview, CreationExecutionReview]:
    runtime.authorize(db, wid, actor)
    row = db.scalar(
        select(ProviderExecutionReview).where(
            ProviderExecutionReview.id == review_id, ProviderExecutionReview.workspace_id == wid
        )
    )
    if row is None:
        raise HTTPException(404, "provider execution review unavailable")
    document = CreationExecutionReview.model_validate(row.document)
    gate(runtime, document.mandate.environment, document.plan)
    _, policy = mandates.checked(db, wid, document.mandate, actor, clock)
    source_current(db, wid, document.plan, actor, store, clock)
    social_configuration_current(db, wid, document.plan, actor, runtime, clock)
    master = db.get(
        PlatformAutomationControl, AutomationControlKey.ALL_DATA_SYNCS.value, populate_existing=True
    )
    if master is not None and not master.enabled:
        raise HTTPException(409, "master automation disabled")
    db.refresh(row, with_for_update=True)
    if (
        row.digest != document.digest()
        or row.document != document.model_dump(mode="json")
        or row.plan_digest != document.plan.digest()
        or row.consent_id != document.mandate.consent_id
    ):
        raise HTTPException(409, "execution review changed")
    now = clock()
    if (
        document.purpose not in policy.allowed_purposes
        or not document.qualification.observed_at <= now < document.qualification.expires_at
        or not document.exposure.eligible(policy, now)
    ):
        raise HTTPException(409, "execution review qualification expired")
    return row, document


def approve_creation(
    db: Session,
    wid: int,
    review_id: str,
    digest: str,
    plan_digest: str,
    actor: str,
    store: MediaStore,
    runtime: CreationRuntime,
    clock: Clock,
) -> ProviderExecutionApproval:
    row, document = checked_review(db, wid, review_id, actor, store, runtime, clock)
    new_creation_allowed(document.plan)
    if (digest, plan_digest) != (row.digest, row.plan_digest):
        raise HTTPException(409, "exact execution review and plan approval required")
    approval = db.get(ProviderExecutionApproval, row.id)
    now = clock()
    if not document.qualification.observed_at <= now < document.qualification.expires_at:
        raise HTTPException(409, "execution qualification expired")
    if approval is None:
        approval = ProviderExecutionApproval(
            review_id=row.id,
            workspace_id=wid,
            review_digest=digest,
            plan_digest=plan_digest,
            actor=actor,
            approved_at=now,
        )
        db.add(approval)
    db.commit()
    return approval


def create_run(
    db: Session,
    wid: int,
    review_id: str,
    actor: str,
    store: MediaStore,
    runtime: CreationRuntime,
    clock: Clock,
) -> ProviderExecutionRun:
    row, document = checked_review(db, wid, review_id, actor, store, runtime, clock)
    new_creation_allowed(document.plan)
    approval = db.get(ProviderExecutionApproval, row.id)
    if approval is None or (approval.review_digest, approval.plan_digest) != (
        row.digest,
        row.plan_digest,
    ):
        raise HTTPException(409, "exact creation approval required")
    owner(db, wid, approval.actor)
    existing = db.scalar(
        select(ProviderExecutionRun).where(ProviderExecutionRun.review_id == row.id)
    )
    if existing is not None:
        return existing
    run = ProviderExecutionRun(
        id=uuid4().hex, workspace_id=wid, review_id=row.id, state="ready", created_at=clock()
    )
    db.add(run)
    db.flush()
    step_ids = (
        [s.step_id for s in document.plan.steps]
        if isinstance(document.plan, ProviderPublishPlan)
        else [s.step_id for s in document.plan.steps]
    )
    for ordinal, step_id in enumerate(step_ids):
        db.add(
            ProviderExecutionStep(
                run_id=run.id,
                step_id=step_id,
                workspace_id=wid,
                ordinal=ordinal,
                state="pending",
            )
        )
    db.commit()
    return run


def locked_run(
    db: Session,
    wid: int,
    run_id: str,
    actor: str,
    store: MediaStore,
    runtime: CreationRuntime,
    clock: Clock,
) -> tuple[ProviderExecutionRun, CreationExecutionReview]:
    run = db.scalar(
        select(ProviderExecutionRun).where(
            ProviderExecutionRun.id == run_id, ProviderExecutionRun.workspace_id == wid
        )
    )
    if run is None:
        raise HTTPException(404, "provider execution run unavailable")
    row, document = checked_review(db, wid, run.review_id, actor, store, runtime, clock)
    approval = db.get(ProviderExecutionApproval, row.id)
    if approval is None or (approval.review_digest, approval.plan_digest) != (
        row.digest,
        row.plan_digest,
    ):
        raise HTTPException(409, "exact creation approval required")
    owner(db, wid, approval.actor)
    db.refresh(run, with_for_update=True)
    if run.canceled_at is not None or run.state == "canceled":
        raise HTTPException(409, "provider execution canceled")
    return run, document


def request_for(document: CreationExecutionReview, raw: dict[str, object]) -> CreationRequest:
    if isinstance(document.plan, ProviderPublishPlan):
        return BoundProviderRequest.model_validate(raw)
    if isinstance(document.plan, LinkedPushPlanV1):
        return LinkedPushBoundRequestV1.model_validate(raw)
    return SocialBoundRequest.model_validate(raw)


def receipt_for(document: CreationExecutionReview, raw: dict[str, object]) -> CreationReceipt:
    return (
        ProviderReceipt.model_validate(raw)
        if isinstance(document.plan, ProviderPublishPlan)
        else SocialProviderReceipt.model_validate(raw)
    )


def claim_creation_step(
    db: Session,
    wid: int,
    run_id: str,
    actor: str,
    store: MediaStore,
    runtime: CreationRuntime,
    clock: Clock,
) -> DispatchClaim | None:
    run, document = locked_run(db, wid, run_id, actor, store, runtime, clock)
    new_creation_allowed(document.plan)
    ledger, policy = mandates.checked(db, wid, document.mandate, actor, clock)
    if run.reservation_id is None:
        e = document.exposure
        held = (
            db.scalar(
                select(func.coalesce(func.sum(ProviderExposureReservation.amount_micros), 0)).where(
                    ProviderExposureReservation.workspace_id == wid,
                    ProviderExposureReservation.environment == document.mandate.environment,
                    ProviderExposureReservation.state == "held",
                )
            )
            or 0
        )
        if (
            held != e.existing_reservations_micros
            or e.reported_spend_micros < ledger.spent_high_water_micros
            or not e.eligible(policy, clock())
            or ledger.action_count >= policy.action_limit
            or (
                ledger.last_dispatch_at is not None
                and (clock() - utc(ledger.last_dispatch_at)).total_seconds()
                < policy.cooldown_seconds
            )
        ):
            raise HTTPException(409, "current portfolio exposure or action limit changed")
        competing = db.scalar(
            select(ProviderExposureReservation.id).where(
                ProviderExposureReservation.workspace_id == wid,
                ProviderExposureReservation.environment == document.mandate.environment,
                ProviderExposureReservation.budget_owner_key == e.budget_owner_key,
                ProviderExposureReservation.state == "held",
            )
        )
        if competing is not None:
            raise HTTPException(409, "budget owner already has unresolved exposure")
        assert e.proposed_owner_upper_micros is not None
        if e.proposed_owner_upper_micros < document.plan.review.configuration.reservation_micros:
            raise HTTPException(409, "reviewed exposure exceeds qualified reservation")
        reservation = ProviderExposureReservation(
            id=uuid4().hex,
            workspace_id=wid,
            ledger_id=ledger.id,
            environment=document.mandate.environment,
            budget_owner_key=e.budget_owner_key,
            amount_micros=e.proposed_owner_upper_micros,
            state="held",
            evidence=e.model_dump(mode="json"),
        )
        db.add(reservation)
        db.flush()
        run.reservation_id = reservation.id
        ledger.spent_high_water_micros = max(
            ledger.spent_high_water_micros, e.reported_spend_micros
        )
        ledger.action_count += 1
        ledger.last_dispatch_at = clock()
        run.state = "reserved"
        db.commit()
        # Reacquire all authority after the durable parent claim; cancel/revoke may win.
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
    step = next((s for s in steps if s.state != "verified_effect"), None)
    if step is None:
        run.state = "created_paused"
        db.commit()
        return None
    if step.state != "pending":
        return None  # dispatching/unknown/conflict/no-effect is not a retryable clock lease
    originals: dict[str, CreationRequest] = {}
    receipts: dict[str, CreationReceipt] = {}
    for attempt in db.scalars(
        select(ProviderExecutionAttempt).where(ProviderExecutionAttempt.run_id == run.id)
    ):
        originals[attempt.step_id] = request_for(document, attempt.request)
        latest = db.scalar(
            select(ProviderExecutionReceipt)
            .where(ProviderExecutionReceipt.attempt_id == attempt.id)
            .order_by(ProviderExecutionReceipt.sequence.desc())
            .limit(1)
        )
        if latest is not None:
            receipts[attempt.step_id] = receipt_for(document, latest.receipt)
    fence, now = uuid4().hex, clock()
    if (
        not document.qualification.observed_at <= now < document.qualification.expires_at
        or not document.exposure.eligible(policy, now)
    ):
        raise HTTPException(409, "execution qualification expired before dispatch")
    if isinstance(document.plan, ProviderPublishPlan):
        request: CreationRequest = materialize_google(
            document.plan,
            run.id,
            step.step_id,
            {k: v for k, v in receipts.items() if isinstance(v, ProviderReceipt)},
            {k: v for k, v in originals.items() if isinstance(v, BoundProviderRequest)},
            fence,
            now,
        )
    elif isinstance(document.plan, LinkedPushPlanV1):
        request = materialize_linked_push(
            document.plan,
            run.id,
            step.step_id,
            {k: v for k, v in receipts.items() if isinstance(v, SocialProviderReceipt)},
            {k: v for k, v in originals.items() if isinstance(v, LinkedPushBoundRequestV1)},
            fence,
            now,
        )
    else:
        request = materialize_social(
            document.plan,
            run.id,
            step.step_id,
            {k: v for k, v in receipts.items() if isinstance(v, SocialProviderReceipt)},
            {k: v for k, v in originals.items() if isinstance(v, SocialBoundRequest)},
            fence,
            now,
        )
    attempt = ProviderExecutionAttempt(
        id=uuid4().hex,
        workspace_id=wid,
        run_id=run.id,
        step_id=step.step_id,
        fence=fence,
        request=request.model_dump(mode="json"),
        request_digest=request.digest(),
        dispatched_at=now,
    )
    db.add(attempt)
    step.state, run.state = "dispatching", "dispatching"
    db.commit()
    return DispatchClaim(
        workspace_id=wid,
        run_id=run.id,
        attempt_id=attempt.id,
        environment=document.mandate.environment,
        request=request,
    )


def evidence_lock(
    db: Session, wid: int, attempt_id: str
) -> tuple[
    ProviderExecutionRun, CreationExecutionReview, ProviderExecutionAttempt, CreationRequest
]:
    # Evidence admission also works while closing; it never restores current authority.
    workspace = db.scalar(select(Workspace).where(Workspace.id == wid).with_for_update())
    if workspace is None:
        raise HTTPException(404, "workspace unavailable")
    attempt = db.scalar(
        select(ProviderExecutionAttempt).where(
            ProviderExecutionAttempt.id == attempt_id, ProviderExecutionAttempt.workspace_id == wid
        )
    )
    if attempt is None:
        raise HTTPException(404, "provider attempt unavailable")
    run = db.scalar(
        select(ProviderExecutionRun)
        .where(ProviderExecutionRun.id == attempt.run_id, ProviderExecutionRun.workspace_id == wid)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    assert run is not None
    row = db.get(ProviderExecutionReview, run.review_id)
    assert row is not None and row.workspace_id == wid
    document = CreationExecutionReview.model_validate(row.document)
    request = request_for(document, attempt.request)
    expected_steps = (
        [s for s in document.plan.steps]
        if isinstance(document.plan, ProviderPublishPlan)
        else [s for s in document.plan.steps]
    )
    expected_step = next((s for s in expected_steps if s.step_id == attempt.step_id), None)
    if (
        request.step != expected_step
        or request.digest() != attempt.request_digest
        or request.fence != attempt.fence
        or request.plan_id != run.id
        or request.plan_digest != document.plan.digest()
        or request.review_digest != document.plan.review_digest
        or request.scope != document.plan.review.scope
        or request.step.step_id != attempt.step_id
        or request.dispatched_at != utc(attempt.dispatched_at)
    ):
        raise HTTPException(409, "original provider attempt binding changed")
    return run, document, attempt, request


def record_response(
    db: Session, wid: int, attempt_id: str, response: CreationResponse, clock: Clock
) -> None:
    _, original_review, attempt, request = evidence_lock(db, wid, attempt_id)
    if response.request_digest != request.digest():
        raise HTTPException(409, "provider response belongs to another request")
    raw = response.model_dump(mode="json")
    digest = fingerprint("inlet.provider-response.v1", raw)
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
    from app.publication.google_execution_completion_contracts import GoogleCapturedCreationResponse

    if isinstance(response, GoogleCapturedCreationResponse):
        if not isinstance(request, BoundProviderRequest):
            raise HTTPException(409, "original Google request unavailable")
        capture_execution_response(
            db, request, response, attempt, original_review.mandate.environment, digest, clock()
        )
    db.commit()


def normalized(
    db: Session,
    run: ProviderExecutionRun,
    document: CreationExecutionReview,
    attempt: ProviderExecutionAttempt,
    receipt: CreationReceipt,
    receipt_id: str,
    digest: str,
    sequence: int,
    supersedes: str | None,
) -> NormalizedProviderReceipt:
    from app.publication.execution_contracts import ProviderMandatePolicy
    from app.publication.execution_models import ProviderExecutionRevision

    revision = db.get(
        ProviderExecutionRevision, (document.mandate.mandate_id, document.mandate.revision)
    )
    if revision is None or revision.workspace_id != run.workspace_id:
        raise HTTPException(409, "original provider policy unavailable")
    policy = ProviderMandatePolicy.model_validate(revision.policy)
    if policy.digest() != document.mandate.policy_digest:
        raise HTTPException(409, "original provider policy changed")
    resource_kind = receipt.resource_name.split("/")[2] if receipt.resource_name else None
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
        purpose=document.purpose,
        account=ExecutionAccount.from_publication(document.plan.review.scope),
        mandate=document.mandate,
        source_draft_id=document.plan.review.source.draft_id,
        source_revision=document.plan.review.source.revision,
        goal_id=policy.goal_id,
        goal_revision=policy.goal_revision,
        budget_owner_key=document.exposure.budget_owner_key,
        target_set_digest=document.exposure.target_set_digest,
        before_state_digest=None,
        after_state_digest=receipt.readback_digest,
        dispatched_at=utc(attempt.dispatched_at),
        observed_at=receipt.observed_at,
        outcome=receipt.outcome,
        evidence=receipt.evidence,
        resource_kind=resource_kind,
        resource_name=receipt.resource_name,
        readback_digest=receipt.readback_digest,
    )


def record_receipt(
    db: Session, wid: int, attempt_id: str, receipt: CreationReceipt, clock: Clock
) -> ProviderExecutionReceipt:
    run, document, attempt, request = evidence_lock(db, wid, attempt_id)
    receipt = receipt_for(document, receipt.model_dump(mode="json"))
    if (
        receipt.scope != request.scope
        or receipt.plan_id != request.plan_id
        or receipt.plan_digest != request.plan_digest
        or receipt.step_id != request.step.step_id
        or receipt.fence != request.fence
        or receipt.request_digest != request.digest()
        or not request.dispatched_at <= receipt.observed_at <= clock()
    ):
        raise HTTPException(409, "receipt does not match original provider attempt")
    if receipt.resource_name:
        if isinstance(request, BoundProviderRequest):
            from app.executors.google_publication import serialize

            expected_kind = serialize(request)[0]
        elif isinstance(request, LinkedPushBoundRequestV1):
            expected_kind = LINKED_OUTPUTS[request.step.operation.kind]
        else:
            from app.publication.social_contracts import OUTPUT_KINDS

            expected_kind = OUTPUT_KINDS[request.step.operation.kind]
        if receipt.resource_name.split("/")[2] != expected_kind:
            raise HTTPException(409, "provider receipt resource kind changed")
    if receipt.outcome == "verified_effect":
        prior_verified = list(
            db.scalars(
                select(ProviderExecutionReceipt).where(
                    ProviderExecutionReceipt.attempt_id == attempt.id
                )
            )
        )
        if any(
            r.receipt.get("outcome") == "verified_effect"
            and r.receipt.get("resource_name") != receipt.resource_name
            for r in prior_verified
        ):
            receipt = receipt.model_copy(
                update={
                    "outcome": "conflict",
                    "evidence": "mismatch",
                    "resource_name": None,
                    "readback_digest": None,
                }
            )
    raw = receipt.model_dump(mode="json")
    digest = fingerprint("inlet.provider-receipt.v1", raw)
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
        raise HTTPException(409, "stale receipt cannot supersede newer evidence")
    # Every newer observation appends, including unknown/conflict after prior success.
    # Consumers select the latest sequence; historical success is never resurrected.
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
        run.state = "ready" if receipt.outcome == "verified_effect" else receipt.outcome
    db.commit()
    return row


def read_owned_outcome_receipt(
    db: Session, workspace_id: int, attempt_id: str, actor: str
) -> NormalizedProviderReceipt | None:
    """Latest immutable same-attempt projection; closing preserves historical access.

    Caller must use an authenticated customer principal; the current owner check is
    repeated here. No caller-supplied run/account/success state participates in lineage.
    """
    # Dispatch only after scoped database joins; each reader repeats the workspace lock
    # and exact immutable original request/receipt validation.
    purpose = db.scalar(
        select(ProviderExecutionReview.document)
        .join(ProviderExecutionRun, ProviderExecutionRun.review_id == ProviderExecutionReview.id)
        .join(ProviderExecutionAttempt, ProviderExecutionAttempt.run_id == ProviderExecutionRun.id)
        .where(
            ProviderExecutionAttempt.id == attempt_id,
            ProviderExecutionAttempt.workspace_id == workspace_id,
            ProviderExecutionRun.workspace_id == workspace_id,
            ProviderExecutionReview.workspace_id == workspace_id,
        )
    )
    if purpose is not None and purpose.get("purpose") == "activate":
        from app.publication.activation import read_owned_outcome_receipt as activation_receipt

        return activation_receipt(db, workspace_id, attempt_id, actor)
    if purpose is not None and purpose.get("purpose") == "existing_campaign_optimize":
        from app.publication.optimization import read_owned_outcome_receipt as optimization_receipt

        return optimization_receipt(db, workspace_id, attempt_id, actor)
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
    receipt = receipt_for(document, latest.receipt)
    if (
        receipt.scope != request.scope
        or receipt.plan_id != request.plan_id
        or receipt.plan_digest != request.plan_digest
        or receipt.step_id != request.step.step_id
        or receipt.fence != request.fence
        or receipt.request_digest != request.digest()
        or receipt.observed_at < request.dispatched_at
    ):
        raise HTTPException(409, "stored receipt binding changed")
    if latest.sequence > 1:
        previous = db.get(ProviderExecutionReceipt, latest.supersedes_id)
        if (
            previous is None
            or previous.workspace_id != workspace_id
            or previous.attempt_id != attempt_id
            or previous.sequence + 1 != latest.sequence
        ):
            raise HTTPException(409, "stored receipt supersession changed")
    digest = fingerprint("inlet.provider-receipt.v1", receipt.model_dump(mode="json"))
    expected = normalized(
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
    if latest.digest != digest or latest.projection != expected.model_dump(mode="json"):
        raise HTTPException(409, "provider receipt projection changed")
    return expected


def unknown(request: CreationRequest, now: datetime) -> CreationReceipt:
    values = dict(
        scope=request.scope,
        plan_id=request.plan_id,
        plan_digest=request.plan_digest,
        step_id=request.step.step_id,
        fence=request.fence,
        request_digest=request.digest(),
        outcome="unknown",
        evidence="unresolved",
        observed_at=now,
    )
    if isinstance(request, LinkedPushBoundRequestV1):
        values["resource_kind"] = LINKED_OUTPUTS[request.step.operation.kind]
    elif isinstance(request, SocialBoundRequest):
        from app.publication.social_contracts import OUTPUT_KINDS

        values["resource_kind"] = OUTPUT_KINDS[request.step.operation.kind]
    return (
        ProviderReceipt.model_validate(values)
        if isinstance(request, BoundProviderRequest)
        else SocialProviderReceipt.model_validate(values)
    )


def checked_dispatch_step(
    db: Session,
    claim: DispatchClaim,
    actor: str,
    store: MediaStore,
    runtime: CreationRuntime,
    clock: Clock,
) -> ProviderExecutionStep:
    run, document = locked_run(db, claim.workspace_id, claim.run_id, actor, store, runtime, clock)
    new_creation_allowed(document.plan)
    attempt = db.get(ProviderExecutionAttempt, claim.attempt_id)
    step = db.get(ProviderExecutionStep, (run.id, claim.request.step.step_id))
    if (
        attempt is None
        or attempt.workspace_id != claim.workspace_id
        or attempt.run_id != run.id
        or attempt.request != claim.request.model_dump(mode="json")
        or step is None
        or step.state != "dispatching"
        or claim.environment != document.mandate.environment
    ):
        raise HTTPException(409, "original claim already emitted or changed")
    return step


def execute_claim(
    db: Session,
    claim: DispatchClaim,
    actor: str,
    store: MediaStore,
    runtime: CreationRuntime,
    clock: Clock,
) -> CreationReceipt:
    # Resolve credentials outside product locks, then reacquire current authority.
    checked_dispatch_step(db, claim, actor, store, runtime, clock)
    db.commit()
    request = claim.request
    google_context = (
        runtime.google_context(request) if isinstance(request, BoundProviderRequest) else None
    )
    social_context = (
        runtime.social_context(request) if isinstance(request, SocialBoundRequest) else None
    )
    linked_context = None
    if isinstance(request, LinkedPushBoundRequestV1):
        if runtime.linked_context is None or runtime.linked_tiktok is None:
            raise HTTPException(409, "linked runtime unavailable")
        linked_context = runtime.linked_context(request)
    step = checked_dispatch_step(db, claim, actor, store, runtime, clock)
    step.state = "emitting"
    db.commit()  # durable one-emission marker; cancellation now preserves this in-flight attempt
    request = claim.request
    response: CreationResponse
    receipt: CreationReceipt
    try:
        if isinstance(request, BoundProviderRequest):
            assert google_context is not None
            response = runtime.google.apply_once(request, google_context, clock())
        elif isinstance(request, LinkedPushBoundRequestV1):
            assert linked_context is not None and runtime.linked_tiktok is not None
            response = runtime.linked_tiktok.apply_once(request, linked_context, clock())
        else:
            adapter = (
                runtime.meta if request.scope.account.platform == "meta_ads" else runtime.tiktok
            )
            assert social_context is not None
            response = adapter.apply_once(request, social_context, clock())
    except Exception:
        response = (
            ProviderResponse(request_digest=request.digest(), outcome="unknown")
            if isinstance(request, BoundProviderRequest)
            else SocialProviderResponse(request_digest=request.digest(), outcome="unknown")
        )
    record_response(db, claim.workspace_id, claim.attempt_id, response, clock)
    try:
        if isinstance(request, BoundProviderRequest) and isinstance(response, ProviderResponse):
            receipt = runtime.google.read_back(
                request, response, runtime.google_context(request), clock()
            )
        elif isinstance(request, LinkedPushBoundRequestV1) and isinstance(
            response, SocialProviderResponse
        ):
            assert runtime.linked_context is not None and runtime.linked_tiktok is not None
            receipt = runtime.linked_tiktok.read_back(
                request, response, runtime.linked_context(request), clock()
            )
        elif isinstance(request, SocialBoundRequest) and isinstance(
            response, SocialProviderResponse
        ):
            adapter = (
                runtime.meta if request.scope.account.platform == "meta_ads" else runtime.tiktok
            )
            receipt = adapter.read_back(request, response, runtime.social_context(request), clock())
        else:
            raise ValueError("provider response type mismatch")
    except Exception:
        receipt = unknown(request, clock())
    record_receipt(db, claim.workspace_id, claim.attempt_id, receipt, clock)
    return receipt


def reconcile_attempt(
    db: Session, wid: int, attempt_id: str, runtime: CreationRuntime, clock: Clock
) -> CreationReceipt:
    _, document, _, request = evidence_lock(db, wid, attempt_id)
    if runtime.environment != document.mandate.environment:
        raise HTTPException(409, "reconciliation environment mismatch")
    history = list(
        db.scalars(
            select(ProviderExecutionResponse).where(
                ProviderExecutionResponse.attempt_id == attempt_id,
                ProviderExecutionResponse.workspace_id == wid,
            )
        )
    )
    raw_history = [r.response for r in history]
    receipt: CreationReceipt
    db.commit()  # read-only provider IO may fail after closure; never emits replacement
    try:
        if isinstance(request, BoundProviderRequest):
            receipt = runtime.google.reconcile(
                request,
                [ProviderResponse.model_validate(r) for r in raw_history],
                runtime.google_context(request),
                clock(),
            )
        elif isinstance(request, LinkedPushBoundRequestV1):
            if runtime.linked_context is None or runtime.linked_tiktok is None:
                raise HTTPException(409, "linked runtime unavailable")
            receipt = runtime.linked_tiktok.reconcile(
                request,
                [SocialProviderResponse.model_validate(r) for r in raw_history],
                runtime.linked_context(request),
                clock(),
            )
        else:
            adapter = (
                runtime.meta if request.scope.account.platform == "meta_ads" else runtime.tiktok
            )
            receipt = adapter.reconcile(
                request,
                [SocialProviderResponse.model_validate(r) for r in raw_history],
                runtime.social_context(request),
                clock(),
            )
    except Exception:
        receipt = unknown(request, clock())
    record_receipt(db, wid, attempt_id, receipt, clock)
    return receipt


def cancel_creation(db: Session, wid: int, run_id: str, actor: str, clock: Clock) -> None:
    workspace = db.scalar(select(Workspace).where(Workspace.id == wid).with_for_update())
    if workspace is None:
        raise HTTPException(404, "workspace unavailable")
    owner(db, wid, actor)
    run = db.scalar(
        select(ProviderExecutionRun)
        .where(ProviderExecutionRun.id == run_id, ProviderExecutionRun.workspace_id == wid)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if run is None:
        raise HTTPException(404, "provider execution run unavailable")
    run.state, run.canceled_at = "canceled", clock()
    db.commit()  # no claim that cancellation erased paused resources or an in-flight effect
