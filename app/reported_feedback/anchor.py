"""Current owned configuration readback, never an inferred delivery interval."""

from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ads.models import Campaign
from app.commerce.evidence import lock_workspace
from app.goals import service as goals
from app.initial_planning.capture import source_current
from app.initial_planning.contracts import CohortV1
from app.lifecycle.privacy import workspace_export_revision
from app.meta.security import API_VERSION, PURCHASE_ACTIONS
from app.publication.coordinator import read_owned_outcome_receipt
from app.publication.execution_mandates import current_account
from app.publication.execution_models import (
    ProviderExecutionAttempt,
    ProviderExecutionReceipt,
    ProviderExecutionResponse,
    ProviderExecutionReview,
    ProviderExecutionRun,
    ProviderExecutionStep,
    ProviderExposureReservation,
    ProviderPeriodLedger,
)
from app.publication.optimization_contracts import (
    MetaBudgetSetV1,
    MetaCurrentState,
    OptimizationReceipt,
    OptimizationRequest,
)
from app.publication.replacement_contracts import parse_review
from app.publication.replacement_lineage import ancestors
from app.reported_feedback.contracts import ConfigurationObservationAnchorV1
from app.reported_feedback.forward_context import ReportedForwardContext, owned_successor


def unavailable(reason: str) -> HTTPException:
    return HTTPException(409, reason)


def resolve_anchor(
    db: Session,
    wid: int,
    attempt_id: str,
    actor: str,
    now: datetime,
    *,
    forward_context: ReportedForwardContext | None = None,
) -> ConfigurationObservationAnchorV1:
    lock_workspace(db, wid, active=True)
    receipt = read_owned_outcome_receipt(db, wid, attempt_id, actor)
    if (
        receipt is None
        or receipt.purpose != "existing_campaign_optimize"
        or receipt.outcome
        not in {
            "verified_effect",
            "verified_target_state",
        }
        or receipt.account.account.platform != "meta_ads"
    ):
        raise unavailable("reported_feedback_verified_meta_configuration_required")
    current_account(db, receipt.account)
    run = db.get(ProviderExecutionRun, receipt.run_id, populate_existing=True)
    row = db.get(ProviderExecutionReview, run.review_id, populate_existing=True) if run else None
    raw_receipt = db.get(ProviderExecutionReceipt, receipt.receipt_id, populate_existing=True)
    if (
        run is None
        or row is None
        or raw_receipt is None
        or run.workspace_id != wid
        or row.workspace_id != wid
    ):
        raise unavailable("reported_feedback_original_plan_unavailable")
    review = parse_review(row.document)
    plan = review.plan
    actual = OptimizationReceipt.model_validate(raw_receipt.receipt)
    before, after, action = plan.before, actual.after, plan.intent.action
    if (
        review.digest() != row.digest
        or row.digest != receipt.review_digest
        or plan.digest() != row.plan_digest
        or row.plan_digest != receipt.plan_digest
        or not isinstance(before, MetaCurrentState)
        or not isinstance(after, MetaCurrentState)
        or not isinstance(action, MetaBudgetSetV1)
        or plan.intent.target.kind != "campaign"
        or plan.intent.budget_owner.owner != plan.intent.target
        or before.scope != receipt.account
        or after.scope != receipt.account
        or before.budget_owner != after.budget_owner
        or before.target != after.target
        or before.target != plan.intent.target
        or before.objective != "OUTCOME_SALES"
        or before.buying_type != "AUCTION"
        or before.sharing_enabled is not False
        or before.schedule_adjustments_enabled is not False
        or before.rebalance_enabled is not False
        or after.sharing_enabled is not False
        or after.schedule_adjustments_enabled is not False
        or after.rebalance_enabled is not False
        or not before.complete
        or not after.complete
        or before.unsupported_features
        or after.unsupported_features
        or before.money != after.money
        or before.unaffected_settings_digest != after.unaffected_settings_digest
        or receipt.observed_at > now
    ):
        raise unavailable("reported_feedback_campaign_budget_profile_required")
    held = list(
        db.scalars(
            select(ProviderExposureReservation)
            .where(
                ProviderExposureReservation.workspace_id == wid,
                ProviderExposureReservation.environment == receipt.environment,
                ProviderExposureReservation.budget_owner_key == receipt.budget_owner_key,
                ProviderExposureReservation.state == "held",
            )
            .with_for_update()
            .limit(2)
        )
    )
    own_successor_id = None
    if len(held) != 1:
        raise unavailable("reported_feedback_current_original_head_required")
    if run.reservation_id != held[0].id:
        if forward_context is None or forward_context.actor_id != actor:
            raise unavailable("reported_feedback_current_original_head_required")
        own_successor_id = owned_successor(db, wid, attempt_id, run, held[0], forward_context)
    ledger = db.get(
        ProviderPeriodLedger, held[0].ledger_id, with_for_update=True, populate_existing=True
    )
    if ledger is None or ledger.workspace_id != wid:
        raise unavailable("reported_feedback_original_ledger_unavailable")
    ancestors(db, held[0])
    attempts = list(
        db.scalars(
            select(ProviderExecutionAttempt)
            .where(
                ProviderExecutionAttempt.workspace_id == wid,
                ProviderExecutionAttempt.run_id == run.id,
            )
            .limit(2)
        )
    )
    if len(attempts) != 1 or attempts[0].id != attempt_id:
        raise unavailable("reported_feedback_unique_original_attempt_required")
    later = list(
        db.scalars(
            select(ProviderExecutionAttempt)
            .join(ProviderExecutionRun, ProviderExecutionRun.id == ProviderExecutionAttempt.run_id)
            .join(
                ProviderExecutionReview,
                ProviderExecutionReview.id == ProviderExecutionRun.review_id,
            )
            .where(
                ProviderExecutionAttempt.workspace_id == wid,
                ProviderExecutionRun.workspace_id == wid,
                ProviderExecutionReview.workspace_id == wid,
                ProviderExecutionReview.account_id == receipt.account.account.account_id,
                ProviderExecutionAttempt.id != attempt_id,
                ProviderExecutionAttempt.dispatched_at >= receipt.dispatched_at,
            )
            .limit(65)
        )
    )
    if len(later) > 64:
        raise unavailable("reported_feedback_later_action_capacity")
    for candidate in later:
        # Known later dispatch is an intervention even if its acknowledgement was
        # lost. Never reinterpret unknown/old-value readback as harmless no-effect.
        if "intent" not in candidate.request:
            raise unavailable("reported_feedback_later_action_shape_unavailable")
        intervening = OptimizationRequest.model_validate(candidate.request)
        if intervening.digest() != candidate.request_digest:
            raise unavailable("reported_feedback_later_action_changed")
        if intervening.intent.scope != receipt.account:
            raise unavailable("reported_feedback_later_action_scope_changed")
        if intervening.intent.target.campaign_id == plan.intent.target.campaign_id:
            if candidate.run_id != own_successor_id:
                raise unavailable("reported_feedback_later_campaign_intervention")
            step = db.get(
                ProviderExecutionStep, (candidate.run_id, candidate.step_id), populate_existing=True
            )
            successor = db.get(ProviderExecutionRun, candidate.run_id, populate_existing=True)
            successor_review = (
                db.get(ProviderExecutionReview, successor.review_id, populate_existing=True)
                if successor
                else None
            )
            if successor_review is None or step is None:
                raise unavailable("reported_rule_successor_claim_unavailable")
            next_plan = parse_review(successor_review.document).plan
            if (
                step.workspace_id != wid
                or step.state != "dispatching"
                or intervening.action_id != candidate.run_id
                or intervening.attempt_id != candidate.id
                or intervening.fence != candidate.fence
                or next_plan.request(
                    candidate.run_id, candidate.id, candidate.fence, intervening.dispatched_at
                )
                != intervening
                or db.scalar(
                    select(ProviderExecutionResponse.attempt_id)
                    .where(ProviderExecutionResponse.attempt_id == candidate.id)
                    .limit(1)
                )
                is not None
                or db.scalar(
                    select(ProviderExecutionReceipt.id)
                    .where(ProviderExecutionReceipt.attempt_id == candidate.id)
                    .limit(1)
                )
                is not None
            ):
                raise unavailable("reported_rule_successor_already_emitted")
    source = source_current(db, wid, receipt.account.account.account_id)
    if source.conversion_action_type not in PURCHASE_ACTIONS:
        raise unavailable("reported_feedback_selected_purchase_event_required")
    campaign = db.scalar(
        select(Campaign).where(
            Campaign.account_id == source.account_id,
            Campaign.external_campaign_id == plan.intent.target.external_id,
        )
    )
    if campaign is None:
        raise unavailable("reported_feedback_owned_campaign_unavailable")
    goal = goals.owned(db, wid, receipt.goal_id)
    goals.expect(goal, receipt.goal_revision)
    definition = goals.current(db, goal)
    before_amount = (
        before.daily_budget_micros
        if action.budget_field == "daily_budget"
        else before.lifetime_budget_micros
    )
    after_amount = (
        after.daily_budget_micros
        if action.budget_field == "daily_budget"
        else after.lifetime_budget_micros
    )
    if (
        before_amount is None
        or after_amount != action.amount_micros
        or before_amount == after_amount
    ):
        raise unavailable("reported_feedback_exact_budget_change_required")
    from app.publication.contracts import fingerprint

    assert run.reservation_id is not None
    return ConfigurationObservationAnchorV1(
        environment=receipt.environment,
        cohort=CohortV1(
            workspace_id=wid,
            account_id=source.account_id,
            campaign_id=campaign.id,
            selected_event=source.conversion_action_type,
            currency=before.money.currency,
            time_zone=before.money.account_timezone,
            query_version=f"meta.{API_VERSION}.campaign-day.v1",
        ),
        integration_id=receipt.account.account.connection_id,
        source_connection_id=source.id,
        source_generation=source.generation,
        external_account_id=source.external_account_id,
        external_campaign_id=campaign.external_campaign_id,
        original_attempt_id=attempt_id,
        original_request_digest=receipt.request_digest,
        original_plan_digest=receipt.plan_digest,
        reservation_id=run.reservation_id,
        ledger_id=ledger.id,
        latest_receipt_id=receipt.receipt_id,
        latest_receipt_digest=receipt.receipt_digest,
        latest_receipt_sequence=receipt.sequence,
        dispatched_at=receipt.dispatched_at,
        configuration_observed_at=receipt.observed_at,
        before_configuration_digest=before.digest(),
        after_configuration_digest=after.digest(),
        budget_field=action.budget_field,
        before_budget_micros=before_amount,
        after_budget_micros=after_amount,
        goal_id=goal.id,
        goal_revision=goal.revision,
        goal_digest=fingerprint(
            "inlet.reported-feedback-goal.v1", {"definition": definition.definition}
        ),
        privacy_revision=workspace_export_revision(db, wid),
    )
