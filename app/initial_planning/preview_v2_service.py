"""Concrete owned v2 preview; native read evidence never becomes financial proof."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.customers.access import CustomerPrincipal
from app.customers.identity import IdentityProvider
from app.initial_planning import calibration, limits, native_budget, preview
from app.initial_planning.api_contracts import NativeBudgetChoice, PreviewIntent
from app.initial_planning.clock import effective_now
from app.initial_planning.contracts import EfficiencyObjectiveV1, PreviewIntentV1
from app.initial_planning.models import CalibrationRow, PreviewRow
from app.initial_planning.native_budget_contracts import NativeBudgetObservationV1
from app.initial_planning.planning_consents import checked_planning_limits
from app.initial_planning.preview_v2 import InitialPreviewV2, PreviewIntentV2
from app.initial_planning.runtime import InitialPlanningRuntime
from app.publication import customer_intents
from app.publication.contracts import fingerprint
from app.publication.customer_authority import bind_authority


def resolve_intent(
    db: Session,
    principal: CustomerPrincipal,
    provider: IdentityProvider,
    objective: EfficiencyObjectiveV1,
    body: PreviewIntent,
    runtime: InitialPlanningRuntime,
) -> PreviewIntentV2:
    if runtime.profile is None or (
        body.choice is not None and not isinstance(body.choice, NativeBudgetChoice)
    ):
        raise HTTPException(409, "native_budget_selection_required")
    _, _, goal_digest = preview.inputs(
        db,
        principal,
        provider,
        PreviewIntentV1(
            objective=objective,
            calibration_id=body.calibration_id,
            observation_id=body.observation_id,
        ),
        runtime,
    )
    return PreviewIntentV2(
        objective=objective,
        calibration_id=body.calibration_id,
        observation_id=body.observation_id,
        environment=runtime.profile.environment,
        profile_digest=runtime.profile.digest(),
        goal_digest=goal_digest,
        native_option_id=body.choice.option_id if body.choice else None,
        mandate_id=body.mandate_id,
        mandate_revision=body.mandate_revision,
    )


def amount(
    db: Session,
    principal: CustomerPrincipal,
    provider: IdentityProvider,
    intent: PreviewIntentV2,
    runtime: InitialPlanningRuntime,
    native: NativeBudgetObservationV1,
    direction: str,
) -> tuple[int, int, str, datetime]:
    assert runtime.configuration is not None
    assert intent.mandate_id is not None and intent.mandate_revision is not None
    wid = intent.objective.cohort.workspace_id
    authorize = bind_authority(principal, provider)
    authorize(db, wid, principal.user.id)
    policy = checked_planning_limits(
        db, principal, provider, wid, intent.mandate_id, intent.mandate_revision, runtime
    )
    cohort = intent.objective.cohort
    if (
        policy.environment != intent.environment
        or policy.goal_id != intent.objective.goal_id
        or policy.goal_revision != intent.objective.goal_revision
        or policy.currency != cohort.currency
        or policy.time_zone != cohort.time_zone
        or not any(a.model_dump() == native.request.scope.model_dump() for a in policy.accounts)
        or customer_intents.account(db, wid, cohort.account_id).model_dump()
        != native.request.scope.model_dump()
        or "existing_campaign_optimize" not in policy.allowed_purposes
        or policy.allowed_target_set_digest != native.budget_owner.target_set_digest()
        or native.unsupported_reasons
        or native.amount_micros is None
    ):
        raise HTTPException(409, "matching_consented_native_budget_required")
    before = native.amount_micros
    rule = next(
        r for r in runtime.configuration.rules if r.name == runtime.configuration.selected_rule
    )
    step = rule.budget_step_micros
    after = (
        before + step
        if direction == "increase"
        else before - step
        if direction == "decrease"
        else before
    )
    if (
        after <= 0
        or after > policy.per_plan_cap_micros
        or after > policy.total_cap_micros
        or before % 10 ** (6 - native.currency_exponent)
        or after % 10 ** (6 - native.currency_exponent)
        or (
            direction == "increase"
            and (
                step > policy.positive_change_cap_micros
                or step * 100 > before * policy.aggressiveness_percent
            )
        )
    ):
        raise HTTPException(409, "native_budget_proposal_outside_consented_limits")
    authorize(db, wid, principal.user.id)
    return before, after, policy.digest(), policy.ends_at


def prepare_preview(
    principal: CustomerPrincipal,
    provider: IdentityProvider,
    intent: PreviewIntentV2,
    runtime: InitialPlanningRuntime,
) -> InitialPreviewV2:
    if (
        runtime.profile is None
        or runtime.profile.digest() != intent.profile_digest
        or runtime.profile.environment != intent.environment
        or runtime.configuration != runtime.profile.initial
    ):
        raise HTTPException(409, "planning_profile_changed")
    wid = intent.objective.cohort.workspace_id
    with runtime.session_factory() as db:
        initial = preview.inputs(db, principal, provider, intent, runtime)
        option = None
        native_expiry = None
        if intent.native_option_id is not None:
            catalog = native_budget.catalog(db, principal, provider, intent.objective, runtime)
            option = next(
                (o for o in catalog.options if o.identifier() == intent.native_option_id), None
            )
            if option is None:
                raise HTTPException(409, "native_budget_selection_changed")
            native_expiry = catalog.expires_at
        report, observation, goal_digest = preview.inputs(db, principal, provider, intent, runtime)
        if initial != (report, observation, goal_digest) or goal_digest != intent.goal_digest:
            raise HTTPException(409, "preview_evidence_changed")
        configuration = runtime.configuration
        assert configuration is not None
        rule = next(r for r in configuration.rules if r.name == configuration.selected_rule)
        classification = calibration.classify(observation, intent.objective, rule)
        if report.status != "evaluated":
            classification = "insufficient"
        direction = classification if classification in {"increase", "decrease"} else "none"
        before = after = None
        native = None
        mandate_digest = None
        mandate_expiry = None
        reasons = [
            *report.reasons,
            "financial_exposure_and_remaining_capacity_unverified",
            "provider_acceptance_unverified",
        ]
        if option is not None and classification != "insufficient":
            native = option.observation
            before, after, mandate_digest, mandate_expiry = amount(
                db, principal, provider, intent, runtime, native, direction
            )
        elif option is None:
            reasons.append("native_selection_required")
        if preview.inputs(db, principal, provider, intent, runtime) != initial:
            raise HTTPException(409, "preview_evidence_changed")
        now = effective_now(db, runtime)
        expiry = min(
            report.expires_at,
            observation.expires_at,
            now + timedelta(seconds=configuration.preview_lifetime_seconds),
            datetime.fromtimestamp(principal.session.expires_at, UTC),
        )
        if native_expiry is not None:
            expiry = min(expiry, native_expiry)
        if mandate_expiry is not None:
            expiry = min(expiry, mandate_expiry)
        if now >= expiry:
            raise HTTPException(409, "preview_evidence_expired")
        document = InitialPreviewV2(
            id=uuid4().hex,
            calibration_id=report.id,
            observation_id=observation.id,
            objective=intent.objective,
            environment=intent.environment,
            profile_digest=intent.profile_digest,
            policy_digest=configuration.digest(),
            evidence_digest=fingerprint(
                "inlet.initial-preview-evidence.v2",
                {
                    "observation": observation.digest(),
                    "calibration": report.model_dump(mode="json"),
                    "native": native.digest() if native else None,
                    "mandate": mandate_digest,
                    "profile": intent.profile_digest,
                },
            ),
            recommendation_status="proposed" if direction != "none" else classification,
            direction=direction,
            before_budget_micros=before,
            after_budget_micros=after,
            native_observation=native,
            reasons=tuple(dict.fromkeys(reasons)),
            created_at=now,
            expires_at=expiry,
        )
        retained = list(
            db.scalars(
                select(PreviewRow.id)
                .join(CalibrationRow, CalibrationRow.id == PreviewRow.calibration_id)
                .where(
                    PreviewRow.workspace_id == wid,
                    PreviewRow.account_id == observation.cohort.account_id,
                    PreviewRow.campaign_id == observation.cohort.campaign_id,
                    CalibrationRow.workspace_id == wid,
                    CalibrationRow.environment == configuration.environment,
                )
                .limit(limits.MAX_RETAINED_PREVIEWS_PER_CAMPAIGN)
            )
        )
        if len(retained) >= limits.MAX_RETAINED_PREVIEWS_PER_CAMPAIGN:
            raise HTTPException(409, "initial_preview_capacity_reached")
        if effective_now(db, runtime) >= expiry:
            raise HTTPException(409, "preview_evidence_expired")
        db.add(
            PreviewRow(
                id=document.id,
                workspace_id=wid,
                account_id=observation.cohort.account_id,
                campaign_id=observation.cohort.campaign_id,
                calibration_id=report.id,
                observation_id=observation.id,
                intent=intent.model_dump(mode="json"),
                document=document.model_dump(mode="json"),
                document_digest=document.digest(),
                original_actor_id=principal.user.id,
                original_session_digest=principal.session.digest,
                goal_digest=goal_digest,
                source_generation=observation.generation,
                privacy_revision=observation.privacy_revision,
                completion_id=observation.completion_id,
                native_state_digest=None,
                mandate_digest=mandate_digest,
                created_at=now,
                expires_at=expiry,
            )
        )
        db.commit()
        return document
