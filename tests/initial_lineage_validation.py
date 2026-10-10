"""Current DB-only validation of two exact immutable Meta history graphs."""

from typing import TYPE_CHECKING

from app.ads.models import AdvertisingAccount
from app.meta.models import MetaConnection
from app.publication import coordinator
from app.publication.activation_contracts import ActivationRequest, ActivationResponse
from app.publication.activation_review import ActivationExecutionReview
from app.publication.contracts import fingerprint
from app.publication.coordinator_contracts import CreationExecutionReview
from app.publication.execution_contracts import ProviderMandatePolicy
from app.publication.execution_models import (
    ProviderExecutionApproval,
    ProviderExecutionAttempt,
    ProviderExecutionConsent,
    ProviderExecutionMandate,
    ProviderExecutionReceipt,
    ProviderExecutionResponse,
    ProviderExecutionReview,
    ProviderExecutionRevision,
    ProviderExecutionRun,
    ProviderExecutionStep,
    ProviderExposureReservation,
    ProviderPeriodLedger,
    ProviderReservationReplacement,
)
from app.publication.service import owner
from app.publication.social_contracts import (
    SocialBoundRequest,
    SocialProviderResponse,
    SocialPublishPlan,
)
from app.shopify.security import utc
from sqlalchemy import func, select
from sqlalchemy.orm import Session

if TYPE_CHECKING:
    from tests.initial_lineage_retained_fixture import InitialLineageSource


def load_initial_lineage(db: Session, source: "InitialLineageSource") -> ProviderExecutionRun:
    assert db.get_bind() is source.engine
    ids = source.ids
    owner(db, ids.workspace_id, ids.actor_id)
    run = db.get(ProviderExecutionRun, ids.run_id)
    assert run and run.workspace_id == ids.workspace_id and run.review_id == ids.review_id
    assert run.parent_run_id == ids.parent_run_id and run.reservation_id == ids.reservation_id
    assert run.state == ("created_paused" if ids.mode == "creation" else "activation_observed")
    parent = db.get(ProviderExecutionRun, ids.parent_run_id) if ids.parent_run_id else None
    if parent:
        assert parent.review_id == ids.parent_review_id and parent.workspace_id == ids.workspace_id
        assert parent.reservation_id == ids.reservation_id and parent.parent_run_id is None
        assert parent.state == "created_paused"
    runs = [parent, run] if parent else [run]
    account = db.get(AdvertisingAccount, ids.account_id)
    native = db.get(MetaConnection, int(ids.native_id))
    assert account and account.workspace_id == ids.workspace_id and account.platform == "meta_ads"
    assert (
        native and native.workspace_id == ids.workspace_id and native.account_id == ids.account_id
    )
    total = 8 if parent else 5
    for model, count in (
        (ProviderExecutionRun, len(runs)),
        (ProviderExecutionReview, len(runs)),
        (ProviderExecutionApproval, len(runs)),
        (ProviderExecutionStep, total),
        (ProviderExecutionAttempt, total),
        (ProviderExecutionResponse, total),
        (ProviderExecutionReceipt, total),
        (ProviderExposureReservation, 1),
        (ProviderReservationReplacement, 0),
    ):
        assert db.scalar(select(func.count()).select_from(model)) == count
    held = db.get(ProviderExposureReservation, ids.reservation_id)
    assert held and held.workspace_id == ids.workspace_id and held.state == "held"
    for current in runs:
        assert current is not None and current.canceled_at is None
        assert current.authority_kind == "customer_exact_approval"
        assert current.automatic_decision_id is None
        row = db.get(ProviderExecutionReview, current.review_id)
        assert row and row.workspace_id == ids.workspace_id
        creation = current.parent_run_id is None
        document = (
            CreationExecutionReview.model_validate(row.document)
            if creation
            else ActivationExecutionReview.model_validate(row.document)
        )
        assert document.digest() == row.digest and document.plan.digest() == row.plan_digest
        if current.id == ids.run_id:
            assert row.digest == ids.review_digest and row.plan_digest == ids.plan_digest
        approval = db.get(ProviderExecutionApproval, row.id)
        assert approval and approval.workspace_id == ids.workspace_id
        assert approval.actor == ids.actor_id and approval.review_digest == row.digest
        assert approval.plan_digest == row.plan_digest
        plan = (
            document.plan
            if isinstance(document, CreationExecutionReview)
            else document.creation_plan
        )
        assert isinstance(plan, SocialPublishPlan)
        assert plan.review.scope.workspace_id == ids.workspace_id
        assert plan.review.scope.account.account_id == ids.account_id
        assert plan.review.scope.account.platform == "meta_ads"
        assert plan.review.scope.external_advertiser_id == native.external_account_id
        binding = document.mandate
        mandate = db.get(ProviderExecutionMandate, binding.mandate_id)
        revision = db.get(ProviderExecutionRevision, (binding.mandate_id, binding.revision))
        consent = db.get(ProviderExecutionConsent, binding.consent_id)
        ledger = db.get(ProviderPeriodLedger, binding.ledger_id)
        assert mandate and revision and consent and ledger
        assert {
            mandate.workspace_id,
            revision.workspace_id,
            consent.workspace_id,
            ledger.workspace_id,
        } == {ids.workspace_id}
        policy = ProviderMandatePolicy.model_validate(revision.policy)
        assert policy.digest() == revision.digest == binding.policy_digest == consent.policy_digest
        assert consent.mandate_id == mandate.id and consent.revision == binding.revision
        assert consent.actor == ids.actor_id and revision.actor == ids.actor_id
        assert ledger.environment == binding.environment == held.environment
        assert ledger.id == held.ledger_id
        if isinstance(document, ActivationExecutionReview):
            assert document.plan.parent_run_id == ids.parent_run_id
            assert document.reservation_id == ids.reservation_id
            step_ids = [target.step_id for target in document.plan.targets]
        else:
            step_ids = [step.step_id for step in document.plan.steps]
        steps = list(
            db.scalars(
                select(ProviderExecutionStep)
                .where(ProviderExecutionStep.run_id == current.id)
                .order_by(ProviderExecutionStep.ordinal)
            )
        )
        assert [step.step_id for step in steps] == step_ids
        for step in steps:
            assert step.workspace_id == ids.workspace_id
            expected = "verified_effect" if creation else "verified_target_state"
            assert step.state == expected
            attempt = db.scalars(
                select(ProviderExecutionAttempt).where(
                    ProviderExecutionAttempt.run_id == current.id,
                    ProviderExecutionAttempt.step_id == step.step_id,
                )
            ).one()
            request = (
                SocialBoundRequest.model_validate(attempt.request)
                if creation
                else ActivationRequest.model_validate(attempt.request)
            )
            assert attempt.workspace_id == ids.workspace_id
            assert request.digest() == attempt.request_digest and request.fence == attempt.fence
            assert utc(request.dispatched_at) == utc(attempt.dispatched_at)
            assert request.plan_digest == row.plan_digest
            assert request.review_digest == (plan.review_digest if creation else row.digest)
            if isinstance(request, SocialBoundRequest):
                assert request.plan_id == current.id and request.step.step_id == step.step_id
            else:
                assert request.run_id == current.id and request.target.step_id == step.step_id
            response = db.scalars(
                select(ProviderExecutionResponse).where(
                    ProviderExecutionResponse.attempt_id == attempt.id
                )
            ).one()
            parsed = (
                SocialProviderResponse.model_validate(response.response)
                if creation
                else ActivationResponse.model_validate(response.response)
            )
            assert response.workspace_id == ids.workspace_id
            assert (
                parsed.request_digest == attempt.request_digest and parsed.outcome == "acknowledged"
            )
            family = "provider" if creation else "activation"
            assert response.digest == fingerprint(f"inlet.{family}-response.v1", response.response)
            receipt = db.scalars(
                select(ProviderExecutionReceipt).where(
                    ProviderExecutionReceipt.attempt_id == attempt.id
                )
            ).one()
            assert receipt.workspace_id == ids.workspace_id
            assert receipt.sequence == 1 and receipt.supersedes_id is None
            # Actual current reader reconstructs/validates typed request, receipt,
            # digest, mandate references and normalized projection; no provider IO.
            projected = coordinator.read_owned_outcome_receipt(
                db, ids.workspace_id, attempt.id, ids.actor_id
            )
            assert projected and projected.outcome == expected
            assert projected.fence == attempt.fence and projected.receipt_id == receipt.id
    return run
