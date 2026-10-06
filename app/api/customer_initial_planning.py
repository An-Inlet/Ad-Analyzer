"""Owned initial report comparison; intent only, never execution authority."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ads.enums import AdvertisingPlatform
from app.ads.models import AdvertisingAccount, Campaign
from app.customers.access import Database, MutationPrincipal, Principal, Provider
from app.initial_planning import calibration, capture, native, preview
from app.initial_planning.api_contracts import (
    CalibrationIntent,
    CampaignOption,
    CaptureIntent,
    MandateOption,
    NativeOption,
    NativeOptions,
    PlanningOptions,
    PreviewIntent,
)
from app.initial_planning.clock import effective_now
from app.initial_planning.contracts import (
    CalibrationReportV1,
    EfficiencyObjectiveV1,
    InitialPreviewV1,
    ObservationV1,
    PreviewIntentV1,
)
from app.initial_planning.runtime import InitialPlanningRuntime, get_initial_planning_configuration
from app.publication import customer_intents, customer_optimization, execution_mandates
from app.publication.customer_authority import bind_authority
from app.publication.customer_optimization_contracts import (
    TargetChoice,
    get_customer_optimization_runtime,
)
from app.publication.execution_models import ProviderExecutionMandate

router = APIRouter(
    prefix="/api/customer/v1/workspaces/{workspace_id}/initial-planning", tags=["customer"]
)


def get_initial_planning_runtime(db: Database) -> InitialPlanningRuntime:
    engine = db.get_bind()
    return InitialPlanningRuntime(
        session_factory=lambda: Session(engine),
        configuration=get_initial_planning_configuration(),
        native=get_customer_optimization_runtime(),
    )


Runtime = Annotated[InitialPlanningRuntime, Depends(get_initial_planning_runtime)]


def validated_preview_intent(
    objective: EfficiencyObjectiveV1, body: PreviewIntent
) -> PreviewIntentV1:
    """Validate the client selection against owned facts without leaking either."""
    try:
        return PreviewIntentV1(objective=objective, **body.model_dump())
    except ValidationError:
        raise HTTPException(
            409, "The selected campaign or goal changed. Refresh and choose again."
        ) from None


@router.get("/options", response_model=PlanningOptions)
def options(
    workspace_id: int,
    principal: Principal,
    provider: Provider,
    db: Database,
    runtime: Runtime,
    response: Response,
) -> PlanningOptions:
    authorize = bind_authority(principal, provider)
    authorize(db, workspace_id, principal.user.id)
    rows = list(
        db.execute(
            select(AdvertisingAccount, Campaign)
            .join(Campaign, Campaign.account_id == AdvertisingAccount.id)
            .where(
                AdvertisingAccount.workspace_id == workspace_id,
                AdvertisingAccount.platform == AdvertisingPlatform.META_ADS,
            )
            .order_by(Campaign.id)
            .limit(201)
        )
    )
    if len(rows) > 200:
        raise HTTPException(409, "The campaign catalog exceeds this preview's supported size.")
    choices = []
    for account, campaign in rows:
        try:
            customer_intents.account(db, workspace_id, account.id)
        except HTTPException as exc:
            if exc.status_code not in {404, 409}:
                raise
            continue
        choices.append(
            CampaignOption(
                account_id=account.id,
                campaign_id=campaign.id,
                account_name=account.name,
                campaign_name=campaign.name,
                currency=account.currency_code,
            )
        )
    authorize(db, workspace_id, principal.user.id)
    response.headers["Cache-Control"] = "no-store"
    return PlanningOptions(
        configured=runtime.configuration is not None,
        configuration=runtime.configuration,
        environment=runtime.configuration.environment if runtime.configuration else None,
        campaigns=tuple(choices),
        native_catalog_available=bool(
            runtime.configuration
            and runtime.native
            and runtime.native.catalog
            and runtime.native.execution.environment == runtime.configuration.environment
        ),
        reason=None if runtime.configuration else "planning_policy_unavailable",
    )


@router.post("/captures", response_model=ObservationV1)
def capture_report(
    workspace_id: int,
    body: CaptureIntent,
    principal: MutationPrincipal,
    provider: Provider,
    db: Database,
    runtime: Runtime,
    response: Response,
) -> ObservationV1:
    response.headers["Cache-Control"] = "no-store"
    result = capture.capture_current(
        db, principal, provider, workspace_id, body.account_id, body.campaign_id, runtime
    )
    db.commit()
    return result


@router.post("/calibrations", response_model=CalibrationReportV1)
def calibrate(
    workspace_id: int,
    body: CalibrationIntent,
    principal: MutationPrincipal,
    provider: Provider,
    db: Database,
    runtime: Runtime,
    response: Response,
) -> CalibrationReportV1:
    observation = capture.read_observation(
        db, principal, provider, workspace_id, body.observation_id, runtime
    )
    objective = EfficiencyObjectiveV1(
        cohort=observation.cohort,
        goal_id=body.goal_id,
        goal_revision=body.goal_revision,
        maximum_reported_cpa_micros=body.maximum_reported_cpa_micros,
    )
    response.headers["Cache-Control"] = "no-store"
    result = calibration.run_calibration(db, principal, provider, objective, runtime)
    db.commit()
    return result


@router.get("/calibrations/{calibration_id}", response_model=CalibrationReportV1)
def read_calibration(
    workspace_id: int,
    calibration_id: str,
    principal: Principal,
    provider: Provider,
    db: Database,
    runtime: Runtime,
    response: Response,
) -> CalibrationReportV1:
    response.headers["Cache-Control"] = "no-store"
    return calibration.read_calibration(
        db, principal, provider, workspace_id, calibration_id, runtime
    )


@router.post("/native-options", response_model=NativeOptions)
def native_options(
    workspace_id: int,
    body: PreviewIntent,
    principal: MutationPrincipal,
    provider: Provider,
    db: Database,
    runtime: Runtime,
    response: Response,
) -> NativeOptions:
    objective = calibration.read_objective(
        db, principal, provider, workspace_id, body.calibration_id, runtime
    )
    intent = validated_preview_intent(objective, body)
    before = preview.inputs(db, principal, provider, intent, runtime)
    db.rollback()
    catalog = native.catalog(db, principal, provider, objective, runtime)
    if preview.inputs(db, principal, provider, intent, runtime) != before:
        raise HTTPException(409, "The reporting context changed.")
    mandates = list(
        db.scalars(
            select(ProviderExecutionMandate)
            .where(
                ProviderExecutionMandate.workspace_id == workspace_id,
                ProviderExecutionMandate.state == "active",
            )
            .order_by(ProviderExecutionMandate.id)
            .limit(51)
        )
    )
    if len(mandates) > 50:
        raise HTTPException(409, "Too many spending plans to show a complete selection.")
    choices = []
    for row in mandates:
        try:
            binding = customer_intents.binding(db, workspace_id, row.id, row.revision)
            _, policy = execution_mandates.checked(
                db, workspace_id, binding, principal.user.id, lambda: effective_now(db, runtime)
            )
        except HTTPException as exc:
            if exc.status_code != 409:
                raise
            continue
        if (
            runtime.configuration
            and policy.environment == runtime.configuration.environment
            and policy.goal_id == objective.goal_id
            and policy.goal_revision == objective.goal_revision
            and policy.currency == objective.cohort.currency
            and any(
                o.state.scope in policy.accounts
                and policy.allowed_target_set_digest == o.state.budget_owner.target_set_digest()
                for o in catalog.options
            )
        ):
            choices.append(
                {
                    "id": row.id,
                    "revision": row.revision,
                    "label": (
                        f"Spending Plan {row.id[:8]} · Revision {row.revision} · {policy.currency}"
                    ),
                }
            )
    preview.inputs(db, principal, provider, intent, runtime)
    if effective_now(db, runtime) >= catalog.expires_at:
        raise HTTPException(409, "The native budget options expired.")
    response.headers["Cache-Control"] = "no-store"
    projected = []
    for option in catalog.options:
        view = customer_optimization.option_view(option)
        projected.append(
            NativeOption(
                id=option.identifier(catalog.request),
                choice=TargetChoice(
                    goal_id=objective.goal_id,
                    goal_revision=objective.goal_revision,
                    account_id=objective.cohort.account_id,
                    option_id=option.identifier(catalog.request),
                ),
                label=option.label,
                currency=view["currency"],
                budget_kind=view["budget_kind"],
                amount_micros=view["amount_micros"],
            )
        )
    return NativeOptions(
        options=tuple(projected), mandates=tuple(MandateOption.model_validate(v) for v in choices)
    )


@router.post("/previews", response_model=InitialPreviewV1)
def prepare(
    workspace_id: int,
    body: PreviewIntent,
    principal: MutationPrincipal,
    provider: Provider,
    db: Database,
    runtime: Runtime,
    response: Response,
) -> InitialPreviewV1:
    objective = calibration.read_objective(
        db, principal, provider, workspace_id, body.calibration_id, runtime
    )
    intent = validated_preview_intent(objective, body)
    # Preserve already verified original identity references without allowing an
    # expired ORM attribute to silently reopen the API transaction during native IO.
    # Every service boundary still reloads and locks this exact session in SQL.
    db.expunge(principal.user)
    db.expunge(principal.session)
    db.rollback()
    response.headers["Cache-Control"] = "no-store"
    return preview.prepare_preview(principal, provider, intent, runtime)


@router.get("/previews/{preview_id}", response_model=InitialPreviewV1)
def read_preview(
    workspace_id: int,
    preview_id: str,
    principal: Principal,
    provider: Provider,
    db: Database,
    runtime: Runtime,
    response: Response,
) -> InitialPreviewV1:
    response.headers["Cache-Control"] = "no-store"
    return preview.read_preview(db, principal, provider, workspace_id, preview_id, runtime)
