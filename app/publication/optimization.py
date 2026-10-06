"""Durable separately consented exact existing-campaign optimization.

No simulation mandate grants authority. Unknown original requests retain their fence
and native budget-owner reservation. No provider IO occurs under database locks.
"""

from datetime import datetime
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.automation.catalog import AutomationControlKey
from app.automation.models import PlatformAutomationControl
from app.publication import coordinator as creation
from app.publication import execution_mandates as mandates
from app.publication.contracts import fingerprint
from app.publication.execution_contracts import (
    ExecutionAccount,
    NormalizedProviderReceipt,
    ProviderMandateBinding,
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
    ProviderPeriodLedger,
)
from app.publication.optimization_contracts import (
    GoogleBudgetSetV1,
    GoogleStatusSetV1,
    MetaBudgetSetV1,
    MetaStatusSetV1,
    OptimizationAction,
    OptimizationIntent,
    OptimizationReceipt,
    OptimizationRequest,
    OptimizationResponse,
    OptimizationTarget,
    TikTokBudgetSetV1,
    TikTokStatusSetV1,
)
from app.publication.optimization_execution_contracts import (
    OptimizationClaim,
    OptimizationExecutionReview,
    OptimizationPlan,
    OptimizationRuntime,
    positive_delta,
)
from app.publication.replacement_contracts import (
    OptimizationReview,
    RepeatOptimizationReview,
    parse_review,
)
from app.publication.service import owner
from app.shopify.security import utc
from app.workspaces.models import Workspace

STEP = "optimize"


def current(
    db: Session,
    wid: int,
    binding: ProviderMandateBinding,
    scope: ExecutionAccount,
    actor: str,
    runtime: OptimizationRuntime,
    clock: creation.Clock,
) -> tuple[ProviderPeriodLedger, ProviderMandatePolicy]:
    if runtime.environment != binding.environment or (
        binding.environment == "live" and not runtime.live_enabled
    ):
        raise HTTPException(409, "optimization runtime unavailable")
    runtime.authorize(db, wid, actor)
    ledger, policy = mandates.checked(db, wid, binding, actor, clock)
    if scope.workspace_id != wid or scope not in policy.accounts:
        raise HTTPException(409, "current owned optimization scope required")
    master = db.get(
        PlatformAutomationControl, AutomationControlKey.ALL_DATA_SYNCS.value, populate_existing=True
    )
    if "existing_campaign_optimize" not in policy.allowed_purposes or (
        master is not None and not master.enabled
    ):
        raise HTTPException(409, "optimization outside current approved policy")
    runtime.transport(scope)
    return ledger, policy


def validate_plan(plan: OptimizationPlan, policy: ProviderMandatePolicy, now: datetime) -> None:
    i, q, s, e = plan.intent, plan.qualification, plan.before, plan.exposure
    if (
        i.approved_target_set_digest != policy.allowed_target_set_digest
        or not q.observed_at <= now < q.expires_at
        or not 0 <= (now - s.observed_at).total_seconds() <= policy.freshness_seconds
        or not s.complete
        or s.unsupported_features
        or not e.eligible(policy, now)
        or plan.positive_change_micros > policy.positive_change_cap_micros
    ):
        raise HTTPException(409, "fresh qualified exact optimization within mandate required")
    action = i.action
    if isinstance(action, (GoogleBudgetSetV1, MetaBudgetSetV1, TikTokBudgetSetV1)):
        previous = action.amount_micros - plan.positive_change_micros
        if plan.positive_change_micros * 100 > previous * policy.aggressiveness_percent:
            raise HTTPException(409, "positive budget change exceeds approved aggressiveness")
    elif (
        isinstance(action, (GoogleStatusSetV1, MetaStatusSetV1)) and s.configured_status == "PAUSED"
    ):
        raise HTTPException(409, "target already paused")
    elif isinstance(action, TikTokStatusSetV1) and s.configured_status == "DISABLE":
        raise HTTPException(409, "target already disabled")


def validate_document(
    document: OptimizationReview, policy: ProviderMandatePolicy, now: datetime
) -> None:
    validate_plan(document.plan, policy, now)
    if isinstance(document, RepeatOptimizationReview) and not (
        document.replacement.observed_at <= now < document.replacement.expires_at
    ):
        raise HTTPException(409, "replacement proof expired")


def prepare_optimization(
    db: Session,
    wid: int,
    binding: ProviderMandateBinding,
    scope: ExecutionAccount,
    target: OptimizationTarget,
    action: OptimizationAction,
    rationale_reference: str,
    actor: str,
    runtime: OptimizationRuntime,
    clock: creation.Clock,
) -> ProviderExecutionReview:
    current(db, wid, binding, scope, actor, runtime, clock)
    db.commit()
    qualification = runtime.qualification_reader(db, binding, scope, target, clock())
    db.commit()
    before = runtime.transport(scope).read_current(
        scope,
        target,
        qualification.money,
        qualification.qualification_id,
        qualification.qualification_revision,
        runtime.context(scope),
        clock(),
    )
    intent = OptimizationIntent(
        scope=scope,
        mandate=binding,
        target=target,
        budget_owner=before.budget_owner,
        action=action,
        expected_state_digest=before.digest(),
        approved_target_set_digest=before.budget_owner.target_set_digest(),
        qualification_id=qualification.qualification_id,
        qualification_revision=qualification.qualification_revision,
        rationale_reference=rationale_reference,
    )
    exposure = runtime.exposure_reader(db, intent, before, qualification, clock())
    db.commit()
    ledger, policy = current(db, wid, binding, scope, actor, runtime, clock)
    plan = OptimizationPlan(
        intent=intent,
        before=before,
        qualification=qualification,
        exposure=exposure,
        positive_change_micros=positive_delta(intent, before),
    )
    document = OptimizationExecutionReview(plan=plan)
    existing = db.scalar(
        select(ProviderExecutionReview).where(
            ProviderExecutionReview.workspace_id == wid,
            ProviderExecutionReview.digest == document.digest(),
        )
    )
    validate_document(document, policy, clock())
    if ledger.spent_high_water_micros > exposure.reported_spend_micros:
        raise HTTPException(409, "optimization reporting below recorded spend")
    if existing is not None:
        return existing
    row = ProviderExecutionReview(
        id=uuid4().hex,
        workspace_id=wid,
        consent_id=binding.consent_id,
        account_id=scope.account.account_id,
        integration_id=scope.account.connection_id,
        source_draft_id=None,
        source_revision=None,
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
    runtime: OptimizationRuntime,
    clock: creation.Clock,
) -> tuple[ProviderExecutionReview, OptimizationReview]:
    row = db.scalar(
        select(ProviderExecutionReview).where(
            ProviderExecutionReview.id == review_id, ProviderExecutionReview.workspace_id == wid
        )
    )
    if row is None or row.document.get("purpose") != "existing_campaign_optimize":
        raise HTTPException(404, "optimization review unavailable")
    document = parse_review(row.document)
    plan = document.plan
    ledger, policy = current(db, wid, plan.intent.mandate, plan.intent.scope, actor, runtime, clock)
    db.refresh(row, with_for_update=True)
    if (
        row.document != document.model_dump(mode="json")
        or row.digest != document.digest()
        or row.plan_digest != plan.digest()
        or row.consent_id != plan.intent.mandate.consent_id
        or row.account_id != plan.intent.scope.account.account_id
        or row.integration_id != plan.intent.scope.account.connection_id
        or row.source_draft_id is not None
        or row.source_revision is not None
    ):
        raise HTTPException(409, "optimization review binding changed")
    validate_document(document, policy, clock())
    if isinstance(document, RepeatOptimizationReview) and not (
        document.replacement.observed_at <= clock() < document.replacement.expires_at
    ):
        raise HTTPException(409, "replacement proof expired")
    if ledger.spent_high_water_micros > plan.exposure.reported_spend_micros:
        raise HTTPException(409, "optimization reporting below recorded spend")
    if isinstance(document, RepeatOptimizationReview):
        admitted = db.scalar(
            select(ProviderExecutionRun.reservation_id).where(
                ProviderExecutionRun.review_id == row.id,
                ProviderExecutionRun.workspace_id == wid,
            )
        )
        if admitted is None:
            from app.publication.replacement import snapshot
            from app.publication.replacement_lineage import require_successor_capacity

            require_successor_capacity(document.predecessor)

            if (
                snapshot(
                    db,
                    wid,
                    document.predecessor.predecessor_id,
                    actor,
                    ledger,
                    policy,
                    plan.intent.scope,
                )
                != document.predecessor
            ):
                raise HTTPException(409, "reviewed replacement ancestry changed")
        if not document.replacement.observed_at <= clock() < document.replacement.expires_at:
            raise HTTPException(409, "replacement proof expired after ancestry locks")
        validate_document(document, policy, clock())
    return row, document


def approve_optimization(
    db: Session,
    wid: int,
    review_id: str,
    digest: str,
    plan_digest: str,
    actor: str,
    runtime: OptimizationRuntime,
    clock: creation.Clock,
) -> ProviderExecutionApproval:
    row, document = checked_review(db, wid, review_id, actor, runtime, clock)
    if (digest, plan_digest) != (row.digest, row.plan_digest):
        raise HTTPException(409, "exact optimization approval required")
    existing = db.get(ProviderExecutionApproval, row.id)
    _, policy = current(
        db, wid, document.plan.intent.mandate, document.plan.intent.scope, actor, runtime, clock
    )
    validate_document(document, policy, clock())
    if existing is None:
        existing = ProviderExecutionApproval(
            review_id=row.id,
            workspace_id=wid,
            review_digest=row.digest,
            plan_digest=row.plan_digest,
            actor=actor,
            approved_at=clock(),
        )
        db.add(existing)
    db.commit()
    return existing


def create_run(
    db: Session,
    wid: int,
    review_id: str,
    actor: str,
    runtime: OptimizationRuntime,
    clock: creation.Clock,
) -> ProviderExecutionRun:
    row, document = checked_review(db, wid, review_id, actor, runtime, clock)
    approval = db.get(ProviderExecutionApproval, row.id)
    if approval is None or (approval.review_digest, approval.plan_digest) != (
        row.digest,
        row.plan_digest,
    ):
        raise HTTPException(409, "exact optimization approval required")
    owner(db, wid, approval.actor)
    existing = db.scalar(
        select(ProviderExecutionRun).where(ProviderExecutionRun.review_id == row.id)
    )
    if existing is not None:
        return existing
    _, policy = current(
        db, wid, document.plan.intent.mandate, document.plan.intent.scope, actor, runtime, clock
    )
    validate_document(document, policy, clock())
    run = ProviderExecutionRun(
        id=uuid4().hex, workspace_id=wid, review_id=row.id, state="ready", created_at=clock()
    )
    db.add(run)
    db.flush()
    db.add(
        ProviderExecutionStep(
            run_id=run.id, step_id=STEP, workspace_id=wid, ordinal=0, state="pending"
        )
    )
    db.commit()
    return run


def locked_run(
    db: Session,
    wid: int,
    run_id: str,
    actor: str,
    runtime: OptimizationRuntime,
    clock: creation.Clock,
) -> tuple[ProviderExecutionRun, OptimizationReview]:
    run = db.scalar(
        select(ProviderExecutionRun).where(
            ProviderExecutionRun.id == run_id, ProviderExecutionRun.workspace_id == wid
        )
    )
    if run is None:
        raise HTTPException(404, "optimization run unavailable")
    row, document = checked_review(db, wid, run.review_id, actor, runtime, clock)
    approval = db.get(ProviderExecutionApproval, row.id)
    if approval is None or (approval.review_digest, approval.plan_digest) != (
        row.digest,
        row.plan_digest,
    ):
        raise HTTPException(409, "exact optimization approval required")
    owner(db, wid, approval.actor)
    db.refresh(run, with_for_update=True)
    if run.canceled_at is not None or run.state == "canceled":
        raise HTTPException(409, "optimization canceled")
    return run, document


def positive_changes_used(db: Session, wid: int, ledger_id: str) -> int:
    rows = db.execute(
        select(ProviderExecutionRun.id, ProviderExecutionReview.document)
        .join(ProviderExecutionReview, ProviderExecutionReview.id == ProviderExecutionRun.review_id)
        .join(
            ProviderExposureReservation,
            ProviderExposureReservation.id == ProviderExecutionRun.reservation_id,
        )
        .where(
            ProviderExecutionRun.workspace_id == wid,
            ProviderExecutionReview.workspace_id == wid,
            ProviderExposureReservation.workspace_id == wid,
            ProviderExposureReservation.ledger_id == ledger_id,
        )
    )
    return sum(
        parse_review(raw).plan.positive_change_micros
        for _, raw in rows
        if raw.get("purpose") == "existing_campaign_optimize"
    )


def claim_step(
    db: Session,
    wid: int,
    run_id: str,
    actor: str,
    runtime: OptimizationRuntime,
    clock: creation.Clock,
) -> OptimizationClaim | None:
    run, document = locked_run(db, wid, run_id, actor, runtime, clock)
    plan = document.plan
    ledger, policy = current(db, wid, plan.intent.mandate, plan.intent.scope, actor, runtime, clock)
    if run.reservation_id is None and isinstance(document, RepeatOptimizationReview):
        from app.publication.replacement import transfer

        transfer(db, wid, run, document, actor, runtime, clock)
        run, document = locked_run(db, wid, run_id, actor, runtime, clock)
        plan = document.plan
    if run.reservation_id is None:
        e = plan.exposure
        held = (
            db.scalar(
                select(func.coalesce(func.sum(ProviderExposureReservation.amount_micros), 0)).where(
                    ProviderExposureReservation.workspace_id == wid,
                    ProviderExposureReservation.environment == e.environment,
                    ProviderExposureReservation.state == "held",
                )
            )
            or 0
        )
        competing = db.scalar(
            select(ProviderExposureReservation.id).where(
                ProviderExposureReservation.workspace_id == wid,
                ProviderExposureReservation.environment == e.environment,
                ProviderExposureReservation.budget_owner_key == e.budget_owner_key,
                ProviderExposureReservation.state == "held",
            )
        )
        if competing is not None:
            raise HTTPException(409, "native budget owner already has retained exposure")
        if (
            held != e.existing_reservations_micros
            or ledger.action_count >= policy.action_limit
            or positive_changes_used(db, wid, ledger.id) + plan.positive_change_micros
            > policy.positive_change_cap_micros
            or (
                ledger.last_dispatch_at is not None
                and (clock() - utc(ledger.last_dispatch_at)).total_seconds()
                < policy.cooldown_seconds
            )
        ):
            raise HTTPException(409, "current portfolio or cumulative action limits changed")
        validate_document(document, policy, clock())
        assert e.proposed_owner_upper_micros is not None
        reservation = ProviderExposureReservation(
            id=uuid4().hex,
            workspace_id=wid,
            ledger_id=ledger.id,
            environment=e.environment,
            budget_owner_key=e.budget_owner_key,
            amount_micros=e.proposed_owner_upper_micros,
            state="held",
            evidence=e.model_dump(mode="json"),
        )
        db.add(reservation)
        db.flush()
        run.reservation_id = reservation.id
        ledger.action_count += 1
        ledger.last_dispatch_at = clock()
        ledger.spent_high_water_micros = max(
            ledger.spent_high_water_micros, e.reported_spend_micros
        )
        run.state = "reserved"
        db.commit()
        run, document = locked_run(db, wid, run_id, actor, runtime, clock)
        plan = document.plan
    validate_reservation(db, run, plan, actor)
    step = db.get(ProviderExecutionStep, (run.id, STEP), with_for_update=True)
    assert step is not None
    if step.state != "pending":
        return None
    _, policy = current(db, wid, plan.intent.mandate, plan.intent.scope, actor, runtime, clock)
    validate_document(document, policy, clock())
    attempt_id, fence = uuid4().hex, uuid4().hex
    request = plan.request(run.id, attempt_id, fence, clock())
    db.add(
        ProviderExecutionAttempt(
            id=attempt_id,
            workspace_id=wid,
            run_id=run.id,
            step_id=STEP,
            fence=fence,
            request=request.model_dump(mode="json"),
            request_digest=request.digest(),
            dispatched_at=request.dispatched_at,
        )
    )
    step.state, run.state = "dispatching", "dispatching"
    db.commit()
    return OptimizationClaim(
        workspace_id=wid,
        run_id=run.id,
        attempt_id=attempt_id,
        environment=plan.intent.mandate.environment,
        request=request,
    )


def validate_reservation(
    db: Session, run: ProviderExecutionRun, plan: OptimizationPlan, actor: str
) -> None:
    row = db.scalar(
        select(ProviderExposureReservation)
        .where(
            ProviderExposureReservation.id == run.reservation_id,
            ProviderExposureReservation.workspace_id == run.workspace_id,
        )
        .with_for_update()
    )
    e = plan.exposure
    others = (
        db.scalar(
            select(func.coalesce(func.sum(ProviderExposureReservation.amount_micros), 0)).where(
                ProviderExposureReservation.workspace_id == run.workspace_id,
                ProviderExposureReservation.environment == e.environment,
                ProviderExposureReservation.state == "held",
                ProviderExposureReservation.id != run.reservation_id,
            )
        )
        or 0
    )
    if (
        row is None
        or row.state != "held"
        or row.ledger_id != e.mandate.ledger_id
        or row.environment != e.environment
        or row.budget_owner_key != e.budget_owner_key
        or row.amount_micros != e.proposed_owner_upper_micros
        or others != e.existing_reservations_micros
    ):
        raise HTTPException(409, "retained optimization exposure or portfolio changed")

    from app.publication.replacement_lineage import ancestors

    chain = ancestors(db, row)
    incoming = chain[-1][1]
    if incoming is not None:
        from app.publication.replacement_contracts import ReplacementAuditDocument

        audit = ReplacementAuditDocument.model_validate(incoming.document)
        for original in audit.snapshot.receipts:
            latest = read_owned_outcome_receipt(db, run.workspace_id, original.attempt_id, actor)
            if latest != original:
                raise HTTPException(409, "replacement ancestor evidence changed before emission")


def evidence_lock(
    db: Session,
    wid: int,
    attempt_id: str,
) -> tuple[ProviderExecutionRun, OptimizationReview, ProviderExecutionAttempt, OptimizationRequest]:
    if db.scalar(select(Workspace).where(Workspace.id == wid).with_for_update()) is None:
        raise HTTPException(404, "workspace unavailable")
    attempt = db.scalar(
        select(ProviderExecutionAttempt).where(
            ProviderExecutionAttempt.id == attempt_id, ProviderExecutionAttempt.workspace_id == wid
        )
    )
    if attempt is None:
        raise HTTPException(404, "optimization attempt unavailable")
    run = db.scalar(
        select(ProviderExecutionRun)
        .where(ProviderExecutionRun.id == attempt.run_id, ProviderExecutionRun.workspace_id == wid)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    assert run is not None
    row = db.get(ProviderExecutionReview, run.review_id)
    if (
        row is None
        or row.workspace_id != wid
        or row.document.get("purpose") != "existing_campaign_optimize"
    ):
        raise HTTPException(409, "original optimization review unavailable")
    document = parse_review(row.document)
    request = OptimizationRequest.model_validate(attempt.request)
    if (
        row.digest != document.digest()
        or row.plan_digest != document.plan.digest()
        or request
        != document.plan.request(run.id, attempt.id, attempt.fence, utc(attempt.dispatched_at))
        or attempt.step_id != STEP
        or request.digest() != attempt.request_digest
    ):
        raise HTTPException(409, "original optimization attempt binding changed")
    return run, document, attempt, request


def validate_receipt(request: OptimizationRequest, receipt: OptimizationReceipt) -> None:
    i = request.intent
    if (
        receipt.action_id != request.action_id
        or receipt.attempt_id != request.attempt_id
        or receipt.fence != request.fence
        or receipt.scope != i.scope
        or receipt.mandate != i.mandate
        or receipt.intent_digest != i.digest()
        or receipt.request_digest != request.digest()
        or receipt.budget_owner_key != i.budget_owner.key(i.scope)
        or receipt.before_state_digest != request.before.digest()
        or receipt.observed_at < request.dispatched_at
    ):
        raise HTTPException(409, "receipt does not match original optimization request")
    evidence = {
        "verified_target_state": "exact_readback",
        "unknown": "unresolved",
        "conflict": "mismatch",
        "verified_no_effect": "authoritative_no_effect",
    }
    if receipt.evidence != evidence[receipt.outcome]:
        raise HTTPException(409, "optimization receipt evidence mismatch")
    if receipt.after is not None:
        after, action = receipt.after, i.action
        updates: dict[str, object] = {}
        if isinstance(action, GoogleBudgetSetV1):
            updates["budget_amount_micros"] = action.amount_micros
        elif isinstance(action, MetaBudgetSetV1):
            updates[action.budget_field + "_micros"] = action.amount_micros
        elif isinstance(action, TikTokBudgetSetV1):
            updates["budget_micros"] = action.amount_micros
        else:
            status = "DISABLE" if isinstance(action, TikTokStatusSetV1) else "PAUSED"
            updates["configured_status"] = status
            updates["effective_status"] = after.effective_status
            if i.target.kind == "campaign":
                updates["parent_configured_status"] = status
        expected = request.before.model_copy(update=updates)
        if after.digest() != expected.digest():
            raise HTTPException(409, "optimization readback exceeds reviewed change")


def normalized(
    db: Session,
    run: ProviderExecutionRun,
    document: OptimizationReview,
    attempt: ProviderExecutionAttempt,
    receipt: OptimizationReceipt,
    receipt_id: str,
    digest: str,
    sequence: int,
    supersedes: str | None,
) -> NormalizedProviderReceipt:
    plan = document.plan
    binding = plan.intent.mandate
    revision = db.get(ProviderExecutionRevision, (binding.mandate_id, binding.revision))
    if revision is None or revision.workspace_id != run.workspace_id:
        raise HTTPException(409, "original optimization policy unavailable")
    policy = ProviderMandatePolicy.model_validate(revision.policy)
    if policy.digest() != binding.policy_digest:
        raise HTTPException(409, "original optimization policy changed")
    resource = None
    if receipt.after is not None:
        scope, target = plan.intent.scope, plan.intent.target
        if scope.account.platform == "google_ads":
            resource = (
                plan.intent.budget_owner.key(scope)
                if isinstance(plan.intent.action, GoogleBudgetSetV1)
                else f"customers/{scope.external_advertiser_id}/campaigns/{target.external_id}"
            )
        else:
            family = scope.account.platform.removesuffix("_ads")
            plural = {"campaign": "campaigns", "adset": "adsets", "adgroup": "adgroups"}[
                target.kind
            ]
            resource = f"{family}/{scope.external_advertiser_id}/{plural}/{target.external_id}"
    return NormalizedProviderReceipt(
        receipt_id=receipt_id,
        receipt_digest=digest,
        sequence=sequence,
        supersedes_receipt_id=supersedes,
        run_id=run.id,
        action_id=run.id,
        plan_id=run.id,
        step_id=STEP,
        attempt_id=attempt.id,
        review_digest=document.digest(),
        plan_digest=plan.digest(),
        request_digest=attempt.request_digest,
        fence=attempt.fence,
        environment=binding.environment,
        purpose=document.purpose,
        account=plan.intent.scope,
        mandate=binding,
        source_draft_id=None,
        source_revision=None,
        goal_id=policy.goal_id,
        goal_revision=policy.goal_revision,
        budget_owner_key=plan.exposure.budget_owner_key,
        target_set_digest=plan.intent.approved_target_set_digest,
        before_state_digest=plan.before.digest(),
        after_state_digest=receipt.after.digest() if receipt.after else None,
        dispatched_at=utc(attempt.dispatched_at),
        observed_at=receipt.observed_at,
        outcome=receipt.outcome,
        evidence=receipt.evidence,
        resource_kind=resource.split("/")[2] if resource else None,
        resource_name=resource,
        readback_digest=receipt.after.digest() if receipt.after else None,
    )


def record_receipt(
    db: Session,
    wid: int,
    attempt_id: str,
    receipt: OptimizationReceipt,
    clock: creation.Clock,
) -> ProviderExecutionReceipt:
    run, document, attempt, request = evidence_lock(db, wid, attempt_id)
    receipt = OptimizationReceipt.model_validate(receipt.model_dump(mode="json"))
    validate_receipt(request, receipt)
    if receipt.observed_at > clock():
        raise HTTPException(409, "future optimization receipt")
    raw = receipt.model_dump(mode="json")
    digest = fingerprint("inlet.optimization-receipt.v1", raw)
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
        raise HTTPException(409, "stale optimization receipt")
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
    step = db.get(ProviderExecutionStep, (run.id, STEP))
    assert step is not None
    step.state = receipt.outcome
    if run.canceled_at is None:
        run.state = receipt.outcome
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
    receipt = OptimizationReceipt.model_validate(latest.receipt)
    validate_receipt(request, receipt)
    if latest.sequence > 1:
        previous = db.get(ProviderExecutionReceipt, latest.supersedes_id)
        if (
            previous is None
            or previous.workspace_id != workspace_id
            or previous.attempt_id != attempt.id
            or previous.sequence + 1 != latest.sequence
        ):
            raise HTTPException(409, "optimization receipt supersession changed")
    digest = fingerprint("inlet.optimization-receipt.v1", receipt.model_dump(mode="json"))
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
    if digest != latest.digest or projection.model_dump(mode="json") != latest.projection:
        raise HTTPException(409, "optimization receipt projection changed")
    return projection


def record_response(
    db: Session,
    wid: int,
    attempt_id: str,
    response: OptimizationResponse,
    clock: creation.Clock,
) -> None:
    _, _, attempt, request = evidence_lock(db, wid, attempt_id)
    if response.request_digest != request.digest():
        raise HTTPException(409, "optimization response belongs to another request")
    raw = response.model_dump(mode="json")
    digest = fingerprint("inlet.optimization-response.v1", raw)
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
    db.commit()


def unknown(request: OptimizationRequest, clock: creation.Clock) -> OptimizationReceipt:
    return OptimizationReceipt(
        action_id=request.action_id,
        attempt_id=request.attempt_id,
        fence=request.fence,
        scope=request.intent.scope,
        mandate=request.intent.mandate,
        intent_digest=request.intent.digest(),
        request_digest=request.digest(),
        budget_owner_key=request.intent.budget_owner.key(request.intent.scope),
        before_state_digest=request.before.digest(),
        after=None,
        outcome="unknown",
        evidence="unresolved",
        observed_at=clock(),
    )


def checked_claim(
    db: Session,
    claim: OptimizationClaim,
    run: ProviderExecutionRun,
    document: OptimizationReview,
    actor: str,
) -> ProviderExecutionStep:
    attempt = db.get(ProviderExecutionAttempt, claim.attempt_id)
    step = db.get(ProviderExecutionStep, (run.id, STEP))
    if (
        attempt is None
        or attempt.workspace_id != claim.workspace_id
        or attempt.run_id != run.id
        or attempt.request != claim.request.model_dump(mode="json")
        or attempt.request_digest != claim.request.digest()
        or claim.environment != document.plan.intent.mandate.environment
        or step is None
        or step.state != "dispatching"
    ):
        raise HTTPException(409, "original optimization claim unavailable")
    validate_reservation(db, run, document.plan, actor)
    return step


def execute_claim(
    db: Session,
    claim: OptimizationClaim,
    actor: str,
    runtime: OptimizationRuntime,
    clock: creation.Clock,
) -> OptimizationReceipt:
    run, document = locked_run(db, claim.workspace_id, claim.run_id, actor, runtime, clock)
    checked_claim(db, claim, run, document, actor)
    request = claim.request
    db.commit()
    adapter = runtime.transport(request.intent.scope)
    state = adapter.read_current(
        request.intent.scope,
        request.intent.target,
        request.before.money,
        request.intent.qualification_id,
        request.intent.qualification_revision,
        runtime.context(request.intent.scope),
        clock(),
    )
    if state.digest() != request.before.digest():
        raise HTTPException(409, "optimization state changed before emission")
    validation = adapter.validate_only(request, runtime.context(request.intent.scope), clock())
    if not validation.valid or validation.blockers or validation.request_digest != request.digest():
        raise HTTPException(409, "optimization provider validation unavailable")
    emission_context = runtime.context(request.intent.scope)
    # Reacquire all authority after blocking provider/context IO and resample the clock.
    run, document = locked_run(db, claim.workspace_id, claim.run_id, actor, runtime, clock)
    step = checked_claim(db, claim, run, document, actor)
    # Ancestor receipt locks/reads may wait too; final authority and proof time
    # are sampled after those waits, immediately before the durable emitting state.
    _, policy = current(
        db, claim.workspace_id, request.intent.mandate, request.intent.scope, actor, runtime, clock
    )
    validate_document(document, policy, clock())
    step.state = "emitting"
    db.commit()
    try:
        response = adapter.apply_once(request, emission_context, clock())
    except Exception:
        response = OptimizationResponse(request_digest=request.digest(), outcome="unknown")
    record_response(db, claim.workspace_id, claim.attempt_id, response, clock)
    try:
        receipt = adapter.read_back(
            request, response, runtime.context(request.intent.scope), clock()
        )
    except Exception:
        receipt = unknown(request, clock)
    record_receipt(db, claim.workspace_id, claim.attempt_id, receipt, clock)
    return receipt


def reconcile_attempt(
    db: Session,
    wid: int,
    attempt_id: str,
    runtime: OptimizationRuntime,
    clock: creation.Clock,
) -> OptimizationReceipt:
    _, document, _, request = evidence_lock(db, wid, attempt_id)
    if runtime.environment != document.plan.intent.mandate.environment:
        raise HTTPException(409, "optimization reconciliation environment mismatch")
    history = [
        OptimizationResponse.model_validate(row.response)
        for row in db.scalars(
            select(ProviderExecutionResponse).where(
                ProviderExecutionResponse.attempt_id == attempt_id,
                ProviderExecutionResponse.workspace_id == wid,
            )
        )
    ]
    db.commit()
    try:
        receipt = runtime.transport(request.intent.scope).reconcile(
            request, history, runtime.context(request.intent.scope), clock()
        )
    except Exception:
        receipt = unknown(request, clock)
    record_receipt(db, wid, attempt_id, receipt, clock)
    return receipt
