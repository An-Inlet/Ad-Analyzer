"""Separate consent to exact v2 action, with fresh owned checks and durable provenance."""

from dataclasses import replace
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.ads.models import AdvertisingAccount, Campaign
from app.customers.access import CustomerPrincipal
from app.customers.identity import IdentityProvider
from app.customers.models import CustomerSession
from app.initial_planning.clock import effective_now
from app.initial_planning.review_models import InitialPreviewReviewLink
from app.initial_planning.review_v2_api_contracts import (
    InitialPreviewExecutionOptionsV1,
    InitialPreviewExecutionOptionV1,
    InitialPreviewExecutionRuntime,
)
from app.initial_planning.review_v2_contracts import (
    InitialPreviewExecutionIntentV1,
    InitialPreviewExecutionPreparedV1,
    InitialPreviewExecutionProofV1,
    qualification_commitment,
)
from app.initial_planning.review_v2_guard import guard_for
from app.initial_planning.review_v2_models import InitialPreviewExecutionProofRow
from app.initial_planning.review_v2_owned import (
    configured,
    current_preview,
    policy_pair,
    unavailable,
)
from app.initial_planning.review_v2_projection import native_review_match
from app.publication import customer_intents, customer_optimization, optimization
from app.publication.contracts import fingerprint
from app.publication.customer_authority import bind_authority
from app.publication.customer_optimization_contracts import TargetQuery
from app.publication.execution_models import ProviderExecutionMandate, ProviderExecutionReview
from app.publication.optimization_contracts import MetaBudgetSetV1, MetaCurrentState
from app.publication.replacement_contracts import OptimizationReview


def execution_review_options(
    runtime: InitialPreviewExecutionRuntime,
    principal: CustomerPrincipal,
    identity_provider: IdentityProvider,
    workspace_id: int,
    preview_id: str,
) -> InitialPreviewExecutionOptionsV1:
    with runtime.planning.session_factory() as db:
        value, row, intent = current_preview(
            db, principal, identity_provider, workspace_id, preview_id, runtime
        )
        choices: list[InitialPreviewExecutionOptionV1] = []
        reason = "execution_runtime_unavailable"
        truncated = False
        if configured(runtime):
            candidates = list(
                db.scalars(
                    select(ProviderExecutionMandate)
                    .where(
                        ProviderExecutionMandate.workspace_id == workspace_id,
                        ProviderExecutionMandate.state == "active",
                        ProviderExecutionMandate.id != intent.mandate_id,
                    )
                    .order_by(ProviderExecutionMandate.id)
                    .limit(51)
                )
            )
            truncated = len(candidates) > 50
            reason = (
                "matching_execution_mandate_unavailable"
                if candidates
                else "separate_execution_consent_required"
            )
            for candidate in candidates[:50]:
                try:
                    binding = customer_intents.binding(
                        db, workspace_id, candidate.id, candidate.revision
                    )
                    _, policy = policy_pair(
                        db,
                        workspace_id,
                        value,
                        row,
                        intent,
                        binding,
                        principal.user.id,
                        runtime,
                        runtime.planning.clock,
                    )
                except HTTPException as exc:
                    if exc.status_code in {401, 403}:
                        raise
                    continue
                account = db.get(AdvertisingAccount, row.account_id)
                campaign = db.get(Campaign, row.campaign_id)
                if account is None or campaign is None:
                    raise unavailable()
                choices.append(
                    InitialPreviewExecutionOptionV1(
                        mandate_id=binding.mandate_id,
                        mandate_revision=binding.revision,
                        policy_digest=binding.policy_digest,
                        account_label=account.name[:160],
                        target_label=campaign.name[:160],
                        currency="USD",
                        time_zone=policy.time_zone,
                        starts_at=policy.starts_at,
                        ends_at=policy.ends_at,
                        total_cap_micros=policy.total_cap_micros,
                        per_plan_cap_micros=policy.per_plan_cap_micros,
                        positive_change_cap_micros=policy.positive_change_cap_micros,
                    )
                )
        # Recheck original session and preview after potentially contended policy locks.
        current_preview(db, principal, identity_provider, workspace_id, preview_id, runtime)
        return InitialPreviewExecutionOptionsV1.model_validate(
            dict(
                preview_id=value.id,
                preview_digest=value.digest(),
                options=choices,
                truncated=truncated,
                status="available" if choices else "unavailable",
                unavailable_reason=None if choices else reason,
            )
        )


def prepare_preview_execution(
    runtime: InitialPreviewExecutionRuntime,
    principal: CustomerPrincipal,
    identity_provider: IdentityProvider,
    workspace_id: int,
    preview_id: str,
    intent: InitialPreviewExecutionIntentV1,
) -> InitialPreviewExecutionPreparedV1:
    if not configured(runtime):
        raise HTTPException(409, "execution_runtime_unavailable")
    assert runtime.optimization is not None
    actor = principal.user.id
    with runtime.planning.session_factory() as db:

        def clock() -> datetime:
            return effective_now(db, runtime.planning)

        native = customer_optimization.bind(
            replace(runtime.optimization, clock=clock), principal, identity_provider
        )
        fresh_runtime = replace(runtime, optimization=native)
        guard = guard_for(fresh_runtime, principal, identity_provider)
        authorize = bind_authority(principal, identity_provider)
        authorize(db, workspace_id, actor)

        def result(row: ProviderExecutionReview) -> InitialPreviewExecutionPreparedV1:
            guard(db, workspace_id, row.id, actor, clock)
            stored = db.get(
                InitialPreviewExecutionProofRow, (row.id, workspace_id), populate_existing=True
            )
            if stored is None:
                raise unavailable()
            proof = InitialPreviewExecutionProofV1.model_validate(stored.document)
            if proof.intent_digest != intent.digest():
                raise unavailable()
            return InitialPreviewExecutionPreparedV1(
                preview_id=preview_id,
                preview_digest=proof.preview_digest,
                review_id=row.id,
                review_digest=row.digest,
                plan_digest=row.plan_digest,
                execution_mandate=proof.execution_mandate,
            )

        def prior() -> InitialPreviewExecutionPreparedV1 | None:
            row = db.scalar(
                select(ProviderExecutionReview)
                .where(
                    ProviderExecutionReview.workspace_id == workspace_id,
                    ProviderExecutionReview.initial_preview_origin_id == preview_id,
                )
                .execution_options(populate_existing=True)
            )
            return result(row) if row is not None else None

        existing = prior()
        if existing is not None:
            return existing
        value, saved, selected = current_preview(
            db, principal, identity_provider, workspace_id, preview_id, runtime
        )
        if value.digest() != intent.expected_preview_digest:
            raise unavailable()
        binding = customer_intents.binding(
            db, workspace_id, intent.mandate_id, intent.mandate_revision
        )
        policy_pair(db, workspace_id, value, saved, selected, binding, actor, fresh_runtime, clock)
        catalog = customer_optimization.discover(
            db,
            workspace_id,
            TargetQuery(
                goal_id=value.objective.goal_id,
                goal_revision=value.objective.goal_revision,
                account_id=saved.account_id,
            ),
            actor,
            native,
            binding,
        )
        assert value.native_observation is not None and value.after_budget_micros is not None
        target = value.native_observation.request.target
        matches = [
            option
            for option in catalog.options
            if option.state.target.model_dump() == target.model_dump()
        ]
        if len(matches) != 1 or not isinstance(matches[0].state, MetaCurrentState):
            raise unavailable()
        state = matches[0].state
        try:
            native_review_match(value.native_observation, state)
        except ValueError:
            raise unavailable() from None
        reference = fingerprint(
            "inlet.initial-preview-execution-origin.v1",
            {"preview_id": preview_id, "intent_digest": intent.digest()},
        )

        def writer(
            session: Session, row: ProviderExecutionReview, document: OptimizationReview
        ) -> None:
            fresh, preview_row, saved_intent = current_preview(
                session, principal, identity_provider, workspace_id, preview_id, runtime
            )
            if fresh != value or row.actor != actor or row.workspace_id != workspace_id:
                raise unavailable()
            planning, _ = policy_pair(
                session,
                workspace_id,
                fresh,
                preview_row,
                saved_intent,
                binding,
                actor,
                fresh_runtime,
                clock,
            )
            if row.initial_preview_origin_id is not None:
                result(row)
                return
            if (
                session.get(InitialPreviewReviewLink, row.id) is not None
                or row.candidate_provenance_required
                or row.automatic_authority_required
            ):
                raise unavailable()
            plan = document.plan
            if (
                not isinstance(plan.before, MetaCurrentState)
                or fresh.native_observation is None
                or not isinstance(plan.intent.action, MetaBudgetSetV1)
                or plan.intent.action.budget_field != "daily_budget"
                or plan.intent.action.amount_micros != fresh.after_budget_micros
                or plan.intent.mandate != binding
                or plan.intent.rationale_reference != reference
            ):
                raise unavailable()
            try:
                match = native_review_match(fresh.native_observation, plan.before)
            except ValueError:
                raise unavailable() from None
            now = clock()
            original_session = session.get(
                CustomerSession, principal.session.digest, populate_existing=True
            )
            if original_session is None:
                raise unavailable()
            expires = min(
                fresh.expires_at,
                plan.qualification.expires_at,
                plan.exposure.expires_at,
                datetime.fromtimestamp(original_session.expires_at, UTC),
            )
            if now >= expires:
                raise unavailable()
            proof = InitialPreviewExecutionProofV1(
                workspace_id=workspace_id,
                preview_id=preview_id,
                review_id=row.id,
                preview_digest=fresh.digest(),
                profile_digest=fresh.profile_digest,
                intent_digest=intent.digest(),
                native_observation_digest=fresh.native_observation.digest(),
                semantic_match_digest=match.digest(),
                planning_mandate=planning.model_dump(),
                execution_mandate=binding.model_dump(),
                qualified_state_digest=plan.before.digest(),
                qualification_digest=qualification_commitment(plan.qualification),
                plan_digest=plan.digest(),
                created_at=now,
                expires_at=expires,
            )
            row.initial_preview_provenance_required = True
            row.initial_preview_origin_id = preview_id
            session.add(
                InitialPreviewReviewLink(
                    review_id=row.id,
                    workspace_id=workspace_id,
                    preview_id=preview_id,
                    preview_workspace_id=workspace_id,
                    preview_account_id=preview_row.account_id,
                    preview_campaign_id=preview_row.campaign_id,
                    actor_id=actor,
                    original_session_digest=principal.session.digest,
                    environment=binding.environment,
                    preview_digest=fresh.digest(),
                    intent_digest=intent.digest(),
                    policy_digest=fresh.policy_digest,
                    evidence_digest=fresh.evidence_digest,
                    native_state_digest=plan.before.digest(),
                    mandate_digest=binding.policy_digest,
                    review_digest=row.digest,
                    plan_digest=plan.digest(),
                    expires_at=expires,
                    created_at=now,
                )
            )
            session.flush()
            session.add(
                InitialPreviewExecutionProofRow(
                    review_id=row.id,
                    workspace_id=workspace_id,
                    digest=proof.digest(),
                    document=proof.model_dump(mode="json"),
                )
            )
            session.flush()
            guard(session, workspace_id, row.id, actor, clock)

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
                MetaBudgetSetV1(
                    budget_field="daily_budget", amount_micros=value.after_budget_micros
                ),
                reference,
                actor,
                execution,
                clock,
            )
        except IntegrityError:
            db.rollback()
            authorize(db, workspace_id, actor)
            existing = prior()
            if existing is None:
                raise unavailable() from None
            return existing
        return result(row)
