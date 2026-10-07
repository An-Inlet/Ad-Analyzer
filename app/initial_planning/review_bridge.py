"""Exact initial-preview handoff using genuine existing qualification/exposure readers."""

from collections.abc import Callable
from dataclasses import replace
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.customers.access import CustomerPrincipal
from app.customers.identity import IdentityProvider
from app.initial_planning.clock import effective_now
from app.initial_planning.contracts import InitialPreviewV1, PreviewIntentV1
from app.initial_planning.models import PreviewRow
from app.initial_planning.preview import read_preview
from app.initial_planning.review_contracts import (
    InitialPreviewReviewGuard,
    InitialPreviewReviewPrepared,
    InitialPreviewReviewRuntime,
)
from app.initial_planning.review_models import InitialPreviewReviewLink
from app.initial_planning.runtime import InitialPlanningRuntime
from app.meta.security import utc
from app.publication import (
    customer_intents,
    customer_optimization,
    execution_mandates,
    optimization,
)
from app.publication.contracts import fingerprint
from app.publication.customer_authority import bind_authority
from app.publication.execution_models import ProviderExecutionReview
from app.publication.optimization_contracts import MetaBudgetSetV1, MetaCurrentState
from app.publication.replacement_contracts import OptimizationReview, parse_review


def unavailable() -> HTTPException:
    return HTTPException(409, "initial_preview_review_retracted_or_changed")


def rationale(value: InitialPreviewV1) -> str:
    return fingerprint(
        "inlet.initial-preview-review-origin.v1", {"id": value.id, "digest": value.digest()}
    )


def current_preview(
    db: Session,
    principal: CustomerPrincipal,
    provider: IdentityProvider,
    wid: int,
    preview_id: str,
    runtime: InitialPlanningRuntime,
) -> tuple[InitialPreviewV1, PreviewRow, PreviewIntentV1]:
    value = read_preview(db, principal, provider, wid, preview_id, runtime)
    if not isinstance(value, InitialPreviewV1):
        raise HTTPException(409, "initial_preview_native_read_unqualified")
    row = db.get(PreviewRow, preview_id, populate_existing=True)
    if row is None:
        raise unavailable()
    intent = PreviewIntentV1.model_validate(row.intent)
    if (
        value.recommendation_status != "proposed"
        or value.direction not in {"increase", "decrease"}
        or value.before_budget_micros is None
        or value.after_budget_micros is None
        or value.native_state_digest is None
        or intent.choice is None
        or intent.mandate_id is None
        or intent.mandate_revision is None
        or row.mandate_digest is None
    ):
        raise HTTPException(409, "initial_preview_exact_native_action_required")
    return value, row, intent


def validate_plan(
    value: InitialPreviewV1, row: PreviewRow, intent: PreviewIntentV1, document: OptimizationReview
) -> None:
    plan = document.plan
    action, before = plan.intent.action, plan.before
    if (
        not isinstance(before, MetaCurrentState)
        or not isinstance(action, MetaBudgetSetV1)
        or intent.choice is None
        or before.target.kind != "campaign"
        or before.target != before.budget_owner.owner
        or plan.intent.scope.workspace_id != row.workspace_id
        or plan.intent.scope.account.account_id != row.account_id
        or plan.intent.scope != before.scope
        or plan.intent.target != before.target
        or plan.intent.expected_state_digest != value.native_state_digest
        or before.digest() != value.native_state_digest
        or action.amount_micros != value.after_budget_micros
        or (
            before.daily_budget_micros
            if action.budget_field == "daily_budget"
            else before.lifetime_budget_micros
        )
        != value.before_budget_micros
        or plan.intent.mandate.mandate_id != intent.mandate_id
        or plan.intent.mandate.revision != intent.mandate_revision
        or plan.intent.mandate.policy_digest != row.mandate_digest
        or plan.intent.rationale_reference != rationale(value)
        or plan.intent.approved_target_set_digest != before.budget_owner.target_set_digest()
    ):
        raise unavailable()


def guard_for(
    planning: InitialPlanningRuntime, principal: CustomerPrincipal, provider: IdentityProvider
) -> InitialPreviewReviewGuard:
    def guard(
        db: Session, wid: int, review_id: str, actor: str, clock: Callable[[], datetime]
    ) -> None:
        fresh = replace(planning, clock=clock)
        bind_authority(principal, provider)(db, wid, actor)
        row = db.get(ProviderExecutionReview, review_id, populate_existing=True)
        link = db.get(InitialPreviewReviewLink, review_id, populate_existing=True)
        if (
            row is None
            or row.workspace_id != wid
            or not row.initial_preview_provenance_required
            or row.initial_preview_origin_id is None
            or row.candidate_provenance_required
            or row.automatic_authority_required
            or link is None
            or link.workspace_id != wid
            or link.actor_id != actor
            or actor != principal.user.id
            or link.original_session_digest != principal.session.digest
            or link.preview_id != row.initial_preview_origin_id
            or link.preview_workspace_id != wid
        ):
            raise unavailable()
        origin = row.initial_preview_origin_id
        value, preview_row, intent = current_preview(db, principal, provider, wid, origin, fresh)
        link = db.get(
            InitialPreviewReviewLink, review_id, populate_existing=True, with_for_update=True
        )
        row = db.get(ProviderExecutionReview, review_id, populate_existing=True)
        if (
            link is None
            or row is None
            or link.preview_id != origin
            or link.preview_workspace_id != wid
            or link.preview_account_id != preview_row.account_id
            or link.preview_campaign_id != preview_row.campaign_id
            or row.initial_preview_origin_id != origin
            or not row.initial_preview_provenance_required
            or row.account_id != preview_row.account_id
            or row.actor != actor
        ):
            raise unavailable()
        document = parse_review(row.document)
        validate_plan(value, preview_row, intent, document)
        if (
            link.preview_digest != value.digest()
            or link.intent_digest
            != fingerprint("inlet.initial-preview-intent.v1", intent.model_dump(mode="json"))
            or link.policy_digest != value.policy_digest
            or link.evidence_digest != value.evidence_digest
            or link.native_state_digest != value.native_state_digest
            or link.mandate_digest != preview_row.mandate_digest
            or link.review_digest != row.digest
            or row.digest != document.digest()
            or link.plan_digest != row.plan_digest
            or row.plan_digest != document.plan.digest()
            or planning.configuration is None
            or link.environment != planning.configuration.environment
            or document.plan.intent.mandate.environment != link.environment
            or utc(link.expires_at) != value.expires_at
        ):
            raise unavailable()
        bind_authority(principal, provider)(db, wid, actor)
        if effective_now(db, fresh) >= value.expires_at:
            raise unavailable()

    return guard


def prepared(
    row: ProviderExecutionReview, link: InitialPreviewReviewLink
) -> InitialPreviewReviewPrepared:
    assert row.initial_preview_origin_id is not None
    return InitialPreviewReviewPrepared(
        preview_id=row.initial_preview_origin_id,
        preview_digest=link.preview_digest,
        review_id=row.id,
        review_digest=row.digest,
        plan_digest=row.plan_digest,
    )


def prepare_preview_review(
    runtime: InitialPreviewReviewRuntime,
    principal: CustomerPrincipal,
    identity_provider: IdentityProvider,
    workspace_id: int,
    preview_id: str,
    expected_preview_digest: str,
) -> InitialPreviewReviewPrepared:
    configured = runtime.optimization.initial_planning
    if (
        configured is None
        or configured.configuration is None
        or runtime.planning.configuration is None
        or configured.configuration.digest() != runtime.planning.configuration.digest()
        or runtime.optimization.execution.environment != runtime.planning.configuration.environment
    ):
        raise HTTPException(503, "initial_preview_forward_runtime_unavailable")
    with runtime.planning.session_factory() as db:

        def clock() -> datetime:
            return effective_now(db, runtime.planning)

        native = customer_optimization.bind(
            replace(runtime.optimization, clock=clock),
            principal,
            identity_provider,
        )
        actor = principal.user.id
        authorize = bind_authority(principal, identity_provider)
        authorize(db, workspace_id, actor)
        guard = guard_for(runtime.planning, principal, identity_provider)

        def existing() -> InitialPreviewReviewPrepared | None:
            found = db.scalar(
                select(ProviderExecutionReview)
                .where(
                    ProviderExecutionReview.workspace_id == workspace_id,
                    ProviderExecutionReview.initial_preview_origin_id == preview_id,
                )
                .execution_options(populate_existing=True)
            )
            if found is None:
                return None
            guard(db, workspace_id, found.id, actor, runtime.planning.clock)
            link = db.get(InitialPreviewReviewLink, found.id, populate_existing=True)
            if link is None or link.preview_digest != expected_preview_digest:
                raise unavailable()
            optimization.checked_review(db, workspace_id, found.id, actor, native.execution, clock)
            return prepared(found, link)

        prior = existing()
        if prior is not None:
            return prior
        value, preview_row, intent = current_preview(
            db, principal, identity_provider, workspace_id, preview_id, runtime.planning
        )
        if value.digest() != expected_preview_digest:
            raise unavailable()
        assert intent.choice is not None and intent.mandate_id and intent.mandate_revision
        option = customer_optimization.choose(db, workspace_id, intent.choice, actor, native)
        current, _, _ = current_preview(
            db, principal, identity_provider, workspace_id, preview_id, runtime.planning
        )
        if (
            current != value
            or not isinstance(option.state, MetaCurrentState)
            or option.state.digest() != value.native_state_digest
        ):
            raise unavailable()
        state = option.state
        binding = customer_intents.binding(
            db, workspace_id, intent.mandate_id, intent.mandate_revision
        )
        _, policy = execution_mandates.checked(db, workspace_id, binding, actor, clock)
        if (
            policy.goal_id != intent.objective.goal_id
            or policy.goal_revision != intent.objective.goal_revision
            or policy.allowed_target_set_digest != state.budget_owner.target_set_digest()
            or policy.currency != state.money.currency
            or policy.time_zone != state.money.account_timezone
            or binding.policy_digest != preview_row.mandate_digest
        ):
            raise unavailable()
        assert value.after_budget_micros is not None
        action = MetaBudgetSetV1(
            amount_micros=value.after_budget_micros,
            budget_field="daily_budget" if state.daily_budget_micros else "lifetime_budget",
        )

        def writer(
            session: Session, row: ProviderExecutionReview, document: OptimizationReview
        ) -> None:
            fresh, saved, saved_intent = current_preview(
                session, principal, identity_provider, workspace_id, preview_id, runtime.planning
            )
            if fresh != value or row.actor != actor or row.workspace_id != workspace_id:
                raise unavailable()
            validate_plan(fresh, saved, saved_intent, document)
            if row.initial_preview_origin_id is not None:
                guard(session, workspace_id, row.id, actor, runtime.planning.clock)
                return
            # Never adopt an already committed ordinary/manual review.
            if (
                session.get(InitialPreviewReviewLink, row.id) is not None
                or row.candidate_provenance_required
                or row.automatic_authority_required
            ):
                raise unavailable()
            row.initial_preview_provenance_required = True
            row.initial_preview_origin_id = preview_id
            assert fresh.native_state_digest is not None and saved.mandate_digest is not None
            session.add(
                InitialPreviewReviewLink(
                    review_id=row.id,
                    workspace_id=workspace_id,
                    preview_id=preview_id,
                    preview_workspace_id=workspace_id,
                    preview_account_id=saved.account_id,
                    preview_campaign_id=saved.campaign_id,
                    actor_id=actor,
                    original_session_digest=principal.session.digest,
                    environment=binding.environment,
                    preview_digest=fresh.digest(),
                    intent_digest=fingerprint(
                        "inlet.initial-preview-intent.v1", saved_intent.model_dump(mode="json")
                    ),
                    policy_digest=fresh.policy_digest,
                    evidence_digest=fresh.evidence_digest,
                    native_state_digest=fresh.native_state_digest,
                    mandate_digest=saved.mandate_digest,
                    review_digest=row.digest,
                    plan_digest=row.plan_digest,
                    expires_at=fresh.expires_at,
                    created_at=clock(),
                )
            )
            session.flush()
            guard(session, workspace_id, row.id, actor, runtime.planning.clock)

        execution = replace(
            native.execution,
            initial_preview_review_writer=writer,
            initial_preview_review_guard=guard,
            candidate_review_writer=None,
            candidate_review_guard=None,
            automatic_authority_guard=None,
        )
        try:
            row = optimization.prepare_optimization(
                db,
                workspace_id,
                binding,
                state.scope,
                state.target,
                action,
                rationale(value),
                actor,
                execution,
                clock,
            )
        except IntegrityError:
            db.rollback()
            # The unique protected origin remains authoritative even if its child was erased.
            result = existing()
            if result is None:
                raise
            return result
        link = db.get(InitialPreviewReviewLink, row.id, populate_existing=True)
        if link is None:
            raise unavailable()
        guard(db, workspace_id, row.id, actor, runtime.planning.clock)
        return prepared(row, link)
