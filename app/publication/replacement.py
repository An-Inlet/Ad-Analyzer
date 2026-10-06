"""Sequential same-owner optimization with fully funded inherited obligations.

No native closure/transition source ships here. A server-only source must qualify
both the entire predecessor chain and current/proposed/delayed transition exposure.
"""

from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.publication import coordinator as creation
from app.publication import execution_mandates as mandates
from app.publication import optimization as o
from app.publication.contracts import fingerprint
from app.publication.execution_contracts import (
    ExecutionAccount,
    ExposureEvidence,
    ProviderMandateBinding,
    ProviderMandatePolicy,
)
from app.publication.execution_models import (
    ProviderExecutionAttempt,
    ProviderExecutionReview,
    ProviderExecutionRun,
    ProviderExposureReservation,
    ProviderPeriodLedger,
    ProviderReservationReplacement,
)
from app.publication.optimization_contracts import (
    OptimizationAction,
    OptimizationIntent,
    OptimizationTarget,
)
from app.publication.optimization_execution_contracts import (
    OptimizationPlan,
    OptimizationRuntime,
    positive_delta,
)
from app.publication.replacement_contracts import (
    RepeatOptimizationReview,
    ReplacementAuditDocument,
    ReplacementSnapshot,
    ReservationAncestor,
    parse_review,
)
from app.publication.replacement_lineage import ancestors, require_successor_capacity
from app.shopify.security import utc


def snapshot(
    db: Session,
    wid: int,
    predecessor_id: str,
    actor: str,
    ledger: ProviderPeriodLedger,
    policy: ProviderMandatePolicy,
    scope: ExecutionAccount,
) -> ReplacementSnapshot:
    predecessor = db.scalar(
        select(ProviderExposureReservation)
        .where(
            ProviderExposureReservation.id == predecessor_id,
            ProviderExposureReservation.workspace_id == wid,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if predecessor is None or predecessor.state != "held" or predecessor.ledger_id != ledger.id:
        raise HTTPException(409, "current same-period retained predecessor required")
    exposure = ExposureEvidence.model_validate(predecessor.evidence)
    if exposure.account != scope or exposure.environment != policy.environment:
        raise HTTPException(409, "same generation and environment predecessor required")
    chain = ancestors(db, predecessor)
    ids = [row.id for row, _ in chain]
    runs = list(
        db.scalars(
            select(ProviderExecutionRun)
            .where(
                ProviderExecutionRun.workspace_id == wid,
                ProviderExecutionRun.reservation_id.in_(ids),
            )
            .order_by(ProviderExecutionRun.id)
        )
    )
    receipts = []
    for run in runs:
        review = db.get(ProviderExecutionReview, run.review_id)
        if review is None or review.document.get("purpose") != "existing_campaign_optimize":
            raise HTTPException(409, "only exact optimization owner chains may be replaced")
        document = parse_review(review.document)
        if (
            document.plan.intent.scope != scope
            or document.plan.intent.budget_owner.key(scope) != predecessor.budget_owner_key
            or document.plan.intent.approved_target_set_digest != exposure.target_set_digest
        ):
            raise HTTPException(409, "complete original target lineage required")
        attempts = list(
            db.scalars(
                select(ProviderExecutionAttempt)
                .where(
                    ProviderExecutionAttempt.workspace_id == wid,
                    ProviderExecutionAttempt.run_id == run.id,
                )
                .order_by(ProviderExecutionAttempt.id)
            )
        )
        if not attempts and run.canceled_at is None:
            raise HTTPException(409, "cancel unattempted ancestor before replacement")
        for attempt in attempts:
            receipt = o.read_owned_outcome_receipt(db, wid, attempt.id, actor)
            if receipt is None or receipt.outcome not in {
                "verified_target_state",
                "verified_no_effect",
            }:
                raise HTTPException(409, "unknown original attempt cannot be replaced")
            receipts.append(receipt)
    return ReplacementSnapshot(
        workspace_id=wid,
        predecessor_id=predecessor.id,
        ledger_id=ledger.id,
        environment=policy.environment,
        account=scope,
        currency=ledger.currency,
        period_start=utc(ledger.starts_at),
        period_end=utc(ledger.ends_at),
        accounting_account_set_digest=fingerprint(
            "inlet.accounting-account-set.v1",
            {"accounts": sorted(mandates.accounting_account_set(policy))},
        ),
        budget_owner_key=predecessor.budget_owner_key,
        target_set_digest=exposure.target_set_digest,
        ancestry=[
            ReservationAncestor(
                reservation_id=row.id,
                state=row.state,
                amount_micros=row.amount_micros,
                evidence_digest=ExposureEvidence.model_validate(row.evidence).digest(),
                replacement_audit_id=link.id if link else None,
                replacement_audit_digest=link.digest if link else None,
            )
            for row, link in chain
        ],
        run_ids=[run.id for run in runs],
        receipts=receipts,
        spent_high_water_micros=ledger.spent_high_water_micros,
        action_count=ledger.action_count,
        positive_changes_micros=o.positive_changes_used(db, wid, ledger.id),
    )


def prepare_repeat_optimization(
    db: Session,
    wid: int,
    binding: ProviderMandateBinding,
    scope: ExecutionAccount,
    predecessor_id: str,
    target: OptimizationTarget,
    action: OptimizationAction,
    rationale_reference: str,
    actor: str,
    runtime: OptimizationRuntime,
    clock: creation.Clock,
) -> ProviderExecutionReview:
    if runtime.replacement_reader is None:
        raise HTTPException(409, "authoritative original closure and transition source unavailable")
    ledger, policy = o.current(db, wid, binding, scope, actor, runtime, clock)
    original = snapshot(db, wid, predecessor_id, actor, ledger, policy, scope)
    require_successor_capacity(original)
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
    proof = runtime.replacement_reader(
        db, binding, intent, before, qualification, original, clock()
    )
    db.commit()
    ledger, policy = o.current(db, wid, binding, scope, actor, runtime, clock)
    if snapshot(db, wid, predecessor_id, actor, ledger, policy, scope) != original:
        raise HTTPException(409, "replacement predecessor changed during qualification")
    proof.bind(original, intent)
    plan = OptimizationPlan(
        intent=intent,
        before=before,
        qualification=qualification,
        exposure=proof.portfolio,
        positive_change_micros=positive_delta(intent, before),
    )
    document = RepeatOptimizationReview(plan=plan, predecessor=original, replacement=proof)
    o.validate_plan(plan, policy, clock())
    if not proof.observed_at <= clock() < proof.expires_at:
        raise HTTPException(409, "replacement proof expired")
    row = db.scalar(
        select(ProviderExecutionReview).where(
            ProviderExecutionReview.workspace_id == wid,
            ProviderExecutionReview.digest == document.digest(),
        )
    )
    if row is None:
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
    o.persist_candidate_writer(db, row, document, runtime)
    db.commit()
    return row


def transfer(
    db: Session,
    wid: int,
    run: ProviderExecutionRun,
    document: RepeatOptimizationReview,
    actor: str,
    runtime: OptimizationRuntime,
    clock: creation.Clock,
) -> None:
    if runtime.replacement_reader is None:
        raise HTTPException(409, "authoritative replacement source unavailable")
    plan = document.plan
    binding, scope = plan.intent.mandate, plan.intent.scope
    ledger, policy = o.current(db, wid, binding, scope, actor, runtime, clock)
    original = snapshot(db, wid, document.predecessor.predecessor_id, actor, ledger, policy, scope)
    require_successor_capacity(original)
    if original != document.predecessor:
        raise HTTPException(409, "reviewed replacement predecessor changed")
    run_id = run.id
    db.commit()
    proof = runtime.replacement_reader(
        db, binding, plan.intent, plan.before, plan.qualification, original, clock()
    )
    db.commit()
    # Reacquire fresh session, workspace and ledger authority after all source IO.
    run, current_document = o.locked_run(db, wid, run_id, actor, runtime, clock)
    ledger, policy = o.current(db, wid, binding, scope, actor, runtime, clock)
    if run.reservation_id is not None:
        return
    if (
        current_document != document
        or proof != document.replacement
        or snapshot(db, wid, original.predecessor_id, actor, ledger, policy, scope) != original
    ):
        raise HTTPException(409, "exact reviewed closure and transition proof changed")
    proof.bind(original, plan.intent)
    held = (
        db.scalar(
            select(func.coalesce(func.sum(ProviderExposureReservation.amount_micros), 0)).where(
                ProviderExposureReservation.workspace_id == wid,
                ProviderExposureReservation.environment == binding.environment,
                ProviderExposureReservation.state == "held",
                ProviderExposureReservation.id != original.predecessor_id,
            )
        )
        or 0
    )
    if (
        held != plan.exposure.existing_reservations_micros
        or ledger.action_count >= policy.action_limit
        or original.positive_changes_micros + plan.positive_change_micros
        > policy.positive_change_cap_micros
        or (
            ledger.last_dispatch_at is not None
            and (clock() - utc(ledger.last_dispatch_at)).total_seconds() < policy.cooldown_seconds
        )
        or not proof.observed_at <= clock() < proof.expires_at
    ):
        raise HTTPException(409, "replacement accounting or qualification changed")
    from app.publication.forward_provenance import check_id

    check_id(db, wid, run.review_id, actor, runtime, clock)
    o.validate_document(document, policy, clock())
    predecessor = db.get(ProviderExposureReservation, original.predecessor_id)
    assert predecessor is not None
    try:
        predecessor.state = "superseded"
        db.flush()  # release the unique held-owner slot only within this atomic transaction
        assert plan.exposure.proposed_owner_upper_micros is not None
        successor = ProviderExposureReservation(
            id=uuid4().hex,
            workspace_id=wid,
            ledger_id=ledger.id,
            environment=binding.environment,
            budget_owner_key=original.budget_owner_key,
            amount_micros=plan.exposure.proposed_owner_upper_micros,
            state="held",
            evidence=plan.exposure.model_dump(mode="json"),
        )
        db.add(successor)
        db.flush()
        run.reservation_id = successor.id
        run.state = "reserved"
        now = clock()
        audit = ReplacementAuditDocument(
            predecessor_id=predecessor.id,
            successor_id=successor.id,
            successor_run_id=run.id,
            review_id=run.review_id,
            review_digest=document.digest(),
            snapshot=original,
            evidence=proof,
            actor=actor,
            replaced_at=now,
        )
        db.add(
            ProviderReservationReplacement(
                id=uuid4().hex,
                workspace_id=wid,
                ledger_id=ledger.id,
                environment=binding.environment,
                budget_owner_key=original.budget_owner_key,
                predecessor_id=predecessor.id,
                successor_id=successor.id,
                successor_run_id=run.id,
                review_id=run.review_id,
                old_amount_micros=predecessor.amount_micros,
                new_amount_micros=successor.amount_micros,
                document=audit.model_dump(mode="json"),
                digest=audit.digest(),
                actor=actor,
                replaced_at=now,
            )
        )
        for old_id in original.run_ids:
            old_run = db.get(ProviderExecutionRun, old_id)
            assert old_run is not None
            old_run.state = "canceled"
            old_run.canceled_at = old_run.canceled_at or now
        ledger.action_count += 1
        ledger.last_dispatch_at = now
        ledger.spent_high_water_micros = max(
            ledger.spent_high_water_micros, plan.exposure.reported_spend_micros
        )
        db.flush()
        o.current(db, wid, binding, scope, actor, runtime, clock)
        o.validate_plan(plan, policy, clock())
        if not proof.observed_at <= clock() < proof.expires_at:
            raise HTTPException(409, "replacement expired before durable transfer")
        db.commit()
    except Exception:
        db.rollback()
        raise
