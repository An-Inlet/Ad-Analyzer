"""Owned initial preview. No approval, reservation, or executor is reachable here."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.customers.access import CustomerPrincipal
from app.customers.identity import IdentityProvider
from app.goals import service as goals
from app.initial_planning import calibration, limits, native, native_budget
from app.initial_planning.clock import effective_now
from app.initial_planning.contracts import (
    CalibrationReportV1,
    InitialPreviewV1,
    ObservationV1,
    PreviewIntentV1,
)
from app.initial_planning.models import CalibrationRow, PreviewRow
from app.initial_planning.preview_binding import bind_preview_row, preview_mandate_reference
from app.initial_planning.preview_v2 import InitialPreviewV2, PreviewIntentV2
from app.initial_planning.runtime import InitialPlanningRuntime
from app.meta.security import utc
from app.publication import customer_intents, execution_mandates
from app.publication.contracts import fingerprint
from app.publication.customer_authority import bind_authority
from app.publication.customer_optimization_contracts import TargetOption
from app.publication.optimization_contracts import MetaCurrentState


def inputs(
    db: Session,
    principal: CustomerPrincipal,
    provider: IdentityProvider,
    intent: PreviewIntentV1 | PreviewIntentV2,
    runtime: InitialPlanningRuntime,
) -> tuple[CalibrationReportV1, ObservationV1, str]:
    objective = intent.objective
    wid = objective.cohort.workspace_id
    authorize = bind_authority(principal, provider)
    authorize(db, wid, principal.user.id)
    checked = calibration._read_calibration_inputs(
        db, principal, provider, wid, intent.calibration_id, runtime
    )
    report, saved = checked.report, checked.objective
    observation = next(
        (item for item in checked.observations if item.id == intent.observation_id), None
    )
    if observation is None:
        raise HTTPException(409, "The current objective and reporting history must match.")
    configuration = runtime.configuration
    if (
        configuration is None
        or saved != objective
        or report.objective_digest != objective.digest()
        or report.policy_digest != configuration.digest()
        or report.environment != configuration.environment
        or observation.environment != configuration.environment
        or observation.cohort != objective.cohort
        or observation.id not in report.observation_ids
    ):
        raise HTTPException(409, "The current objective and reporting history must match.")
    if checked.current_objective.report.completion_id != observation.completion_id:
        raise HTTPException(409, "The current objective and reporting history must match.")
    goal = checked.current_objective.goal
    goals.expect(goal, objective.goal_revision)
    if goals.assessment(db, goal, effective_now(db, runtime)) != "confirmed":
        raise HTTPException(409, "Confirm the current goal before preparing a preview.")
    goal_digest = checked.current_objective.goal_definition_digest
    authorize(db, wid, principal.user.id)
    if effective_now(db, runtime) >= min(report.expires_at, observation.expires_at):
        raise HTTPException(409, "The reporting evidence expired.")
    return report, observation, goal_digest


def amount(
    db: Session,
    principal: CustomerPrincipal,
    provider: IdentityProvider,
    intent: PreviewIntentV1,
    runtime: InitialPlanningRuntime,
    option: TargetOption,
    direction: str,
) -> tuple[int, int, str, datetime]:
    assert intent.mandate_id is not None and intent.mandate_revision is not None
    assert runtime.configuration is not None
    wid = intent.objective.cohort.workspace_id
    authorize = bind_authority(principal, provider)
    authorize(db, wid, principal.user.id)
    binding = customer_intents.binding(db, wid, intent.mandate_id, intent.mandate_revision)
    _, policy = execution_mandates.checked(
        db, wid, binding, principal.user.id, lambda: effective_now(db, runtime)
    )
    state = option.state
    cohort = intent.objective.cohort
    if (
        not isinstance(state, MetaCurrentState)
        or policy.environment != runtime.configuration.environment
        or policy.goal_id != intent.objective.goal_id
        or policy.goal_revision != intent.objective.goal_revision
        or policy.currency != cohort.currency
        or policy.time_zone != cohort.time_zone
        or (state.money.period_start, state.money.period_end) != (policy.starts_at, policy.ends_at)
        or state.scope not in policy.accounts
        or state.scope != customer_intents.account(db, wid, cohort.account_id)
        or "existing_campaign_optimize" not in policy.allowed_purposes
        or policy.allowed_target_set_digest != state.budget_owner.target_set_digest()
        or bool(state.daily_budget_micros) == bool(state.lifetime_budget_micros)
    ):
        raise HTTPException(
            409, "A matching current campaign budget and consented plan are required."
        )
    before = state.daily_budget_micros or state.lifetime_budget_micros
    assert before is not None
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
    # Do not silently clamp a policy-selected amount into a different proposal.
    if (
        after <= 0
        or after > policy.per_plan_cap_micros
        or after > policy.total_cap_micros
        or before % 10 ** (6 - state.money.currency_exponent)
        or after % 10 ** (6 - state.money.currency_exponent)
    ):
        raise HTTPException(409, "The proposed amount is outside the separately consented limits.")
    if direction == "increase" and (
        step > policy.positive_change_cap_micros
        or step * 100 > before * policy.aggressiveness_percent
    ):
        raise HTTPException(
            409, "The proposed increase is outside the separately consented limits."
        )
    authorize(db, wid, principal.user.id)
    return before, after, policy.digest(), policy.ends_at


def prepare_preview(
    principal: CustomerPrincipal,
    provider: IdentityProvider,
    intent: PreviewIntentV1,
    runtime: InitialPlanningRuntime,
) -> InitialPreviewV1:
    wid = intent.objective.cohort.workspace_id
    option = None
    native_expiry = None
    with runtime.session_factory() as db:
        initial = inputs(db, principal, provider, intent, runtime)
        db.rollback()
        if intent.choice is not None:
            catalog = native.catalog(db, principal, provider, intent.objective, runtime)
            option = next(
                (
                    o
                    for o in catalog.options
                    if o.identifier(catalog.request) == intent.choice.option_id
                ),
                None,
            )
            if option is None:
                raise HTTPException(409, "The selected native campaign budget changed.")
            native_expiry = catalog.expires_at
            db.rollback()
        report, observation, goal_digest = inputs(db, principal, provider, intent, runtime)
        if initial != (report, observation, goal_digest):
            raise HTTPException(409, "Reporting or goal context changed during the native read.")
        configuration = runtime.configuration
        assert configuration is not None
        rule = next(r for r in configuration.rules if r.name == configuration.selected_rule)
        classification = calibration.classify(observation, intent.objective, rule)
        if report.status != "evaluated":
            classification = "insufficient"
        direction = classification if classification in {"increase", "decrease"} else "none"
        before = after = None
        state_digest = mandate_digest = None
        mandate_expiry = None
        reasons = [
            *report.reasons,
            "financial_exposure_and_remaining_capacity_unverified",
            "provider_acceptance_unverified",
        ]
        if option is not None and classification != "insufficient":
            before, after, mandate_digest, mandate_expiry = amount(
                db, principal, provider, intent, runtime, option, direction
            )
            state_digest = option.state.digest()
        elif option is None:
            reasons.append("native_selection_required")
        # Mandate and native operations may wait. Re-read every database fact and
        # original session after them, sampling time only after those waits.
        if inputs(db, principal, provider, intent, runtime) != (report, observation, goal_digest):
            raise HTTPException(409, "The preview evidence changed.")
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
            raise HTTPException(409, "The preview evidence expired.")
        document = InitialPreviewV1(
            id=uuid4().hex,
            calibration_id=report.id,
            observation_id=observation.id,
            objective=intent.objective,
            policy_digest=configuration.digest(),
            evidence_digest=fingerprint(
                "inlet.initial-preview-evidence.v1",
                {
                    "observation": observation.digest(),
                    "calibration": report.model_dump(mode="json"),
                    "native": state_digest,
                    "mandate": mandate_digest,
                },
            ),
            recommendation_status="proposed" if direction != "none" else classification,
            direction=direction,
            before_budget_micros=before,
            after_budget_micros=after,
            native_state_digest=state_digest,
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
            raise HTTPException(409, "The preview evidence expired.")
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
                document_digest=fingerprint(
                    document.schema_version, document.model_dump(mode="json")
                ),
                original_actor_id=principal.user.id,
                original_session_digest=principal.session.digest,
                goal_digest=goal_digest,
                source_generation=observation.generation,
                privacy_revision=observation.privacy_revision,
                completion_id=observation.completion_id,
                native_state_digest=state_digest,
                mandate_digest=mandate_digest,
                created_at=now,
                expires_at=expiry,
            )
        )
        db.commit()
        return document


def read_preview(
    db: Session,
    principal: CustomerPrincipal,
    provider: IdentityProvider,
    workspace_id: int,
    preview_id: str,
    runtime: InitialPlanningRuntime,
) -> InitialPreviewV1 | InitialPreviewV2:
    bind_authority(principal, provider)(db, workspace_id, principal.user.id)
    row = db.get(PreviewRow, preview_id, populate_existing=True)
    if row is None or row.workspace_id != workspace_id:
        raise HTTPException(404, "Preview unavailable.")
    if (
        row.original_actor_id != principal.user.id
        or row.original_session_digest != principal.session.digest
    ):
        raise HTTPException(409, "Read this preview from its original customer session.")
    values = {column.name: getattr(row, column.name) for column in row.__table__.columns}
    try:
        document = bind_preview_row(values)
        intent: PreviewIntentV1 | PreviewIntentV2 = (
            PreviewIntentV1.model_validate(row.intent)
            if isinstance(document, InitialPreviewV1)
            else PreviewIntentV2.model_validate(row.intent)
        )
    except ValueError:
        raise HTTPException(409, "The preview is no longer current.") from None
    if isinstance(document, InitialPreviewV2) and (
        runtime.profile is None
        or runtime.profile.digest() != document.profile_digest
        or runtime.profile.environment != document.environment
    ):
        raise HTTPException(409, "The planning profile changed.")
    if isinstance(document, InitialPreviewV2) and document.native_observation is not None:
        current_request = native_budget.owned_request(
            db, principal, provider, document.objective, runtime
        )
        if current_request != document.native_observation.request:
            raise HTTPException(409, "The native observation scope changed.")
    _, observation, goal_digest = inputs(db, principal, provider, intent, runtime)
    if (
        fingerprint(document.schema_version, document.model_dump(mode="json"))
        != row.document_digest
        or document.id != row.id
        or document.calibration_id != row.calibration_id
        or document.observation_id != row.observation_id
        or intent.calibration_id != row.calibration_id
        or intent.observation_id != row.observation_id
        or (
            document.objective.cohort.workspace_id,
            document.objective.cohort.account_id,
            document.objective.cohort.campaign_id,
        )
        != (row.workspace_id, row.account_id, row.campaign_id)
        or utc(row.created_at) != document.created_at
        or utc(row.expires_at) != document.expires_at
        or document.objective != intent.objective
        or goal_digest != row.goal_digest
        or observation.generation != row.source_generation
        or observation.privacy_revision != row.privacy_revision
        or observation.completion_id != row.completion_id
        or effective_now(db, runtime) >= document.expires_at
    ):
        raise HTTPException(409, "The preview is no longer current.")
    if row.mandate_digest is not None:
        reference = preview_mandate_reference(values, document)
        if reference is None:
            raise HTTPException(409, "The separately consented plan changed.")
        binding = customer_intents.binding(db, workspace_id, *reference)
        _, policy = execution_mandates.checked(
            db, workspace_id, binding, principal.user.id, runtime.clock
        )
        if policy.digest() != row.mandate_digest:
            raise HTTPException(409, "The separately consented plan changed.")
        inputs(db, principal, provider, intent, runtime)
        if effective_now(db, runtime) >= document.expires_at:
            raise HTTPException(409, "The preview expired.")
    return document
