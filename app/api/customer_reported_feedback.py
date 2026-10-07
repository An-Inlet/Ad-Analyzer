"""Owned operational comparisons; customer intent never supplies report or policy proof."""

from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import Field
from sqlalchemy import select

from app.ads.models import AdvertisingAccount, Campaign
from app.customers.access import Database, MutationPrincipal, Principal, Provider
from app.initial_planning import preview
from app.initial_planning.clock import effective_now
from app.initial_planning.contracts import Frozen
from app.initial_planning.models import PreviewRow
from app.publication.customer_authority import bind_authority
from app.publication.execution_models import ProviderExecutionAttempt
from app.reported_feedback.contracts import (
    ComparisonIntentV1,
    ComparisonProgressV1,
    FeedbackPreviewIntentV1,
    OperationalReportedComparisonV1,
    ReportedFeedbackPolicyV1,
    ReportedFeedbackPreviewV1,
    ReportedWindowPolicyV1,
)
from app.reported_feedback.runtime import ReportedFeedbackRuntime, get_reported_feedback_runtime

router = APIRouter(
    prefix="/api/customer/v1/workspaces/{workspace_id}/reported-feedback", tags=["customer"]
)
Runtime = Annotated[ReportedFeedbackRuntime | None, Depends(get_reported_feedback_runtime)]


class ActionOption(Frozen):
    id: str = Field(pattern=r"^[a-f0-9]{32}$")
    label: str = Field(max_length=320)
    goal_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    goal_revision: int = Field(strict=True, gt=0)
    currency: str
    observed_at: datetime


class BaselineOption(Frozen):
    id: str = Field(pattern=r"^[a-f0-9]{32}$")
    label: str = Field(max_length=320)
    goal_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    goal_revision: int = Field(strict=True, gt=0)
    currency: str
    amount_micros: int
    expires_at: datetime


class FeedbackOptions(Frozen):
    comparison_available: bool
    preview_update_available: bool
    environment: Literal["contract_test", "live"] | None
    window_policy: ReportedWindowPolicyV1 | None
    feedback_policy: ReportedFeedbackPolicyV1 | None
    actions: tuple[ActionOption, ...] = Field(max_length=50)
    baselines: tuple[BaselineOption, ...] = Field(max_length=50)
    coverage: Literal["recent_owned_choices"] = "recent_owned_choices"
    truncated: bool
    spending_authority: Literal["none"] = "none"
    review_available: Literal[False] = False


def available(runtime: ReportedFeedbackRuntime | None) -> ReportedFeedbackRuntime:
    if runtime is None or runtime.window_policy is None:
        raise HTTPException(503, "Reported comparison is not configured for this workspace.")
    return runtime


@router.get("/options", response_model=FeedbackOptions)
def options(
    workspace_id: int,
    principal: Principal,
    provider: Provider,
    db: Database,
    runtime: Runtime,
    response: Response,
) -> FeedbackOptions:
    authorize = bind_authority(principal, provider)
    authorize(db, workspace_id, principal.user.id)
    response.headers["Cache-Control"] = "no-store"
    if runtime is None or runtime.window_policy is None:
        return FeedbackOptions(
            comparison_available=False,
            preview_update_available=False,
            environment=None,
            window_policy=None,
            feedback_policy=None,
            actions=(),
            baselines=(),
            truncated=False,
        )
    from app.reported_feedback.anchor import resolve_anchor

    attempts = list(
        db.scalars(
            select(ProviderExecutionAttempt)
            .where(
                ProviderExecutionAttempt.workspace_id == workspace_id,
            )
            .order_by(ProviderExecutionAttempt.dispatched_at.desc(), ProviderExecutionAttempt.id)
            .limit(51)
        )
    )
    actions = []
    for attempt in attempts[:50]:
        try:
            anchor = resolve_anchor(
                db, workspace_id, attempt.id, principal.user.id, effective_now(db, runtime.initial)
            )
        except HTTPException as exc:
            if exc.status_code not in {404, 409}:
                raise
            continue
        if anchor.environment != runtime.window_policy.environment:
            continue
        account = db.get(AdvertisingAccount, anchor.cohort.account_id)
        campaign = db.get(Campaign, anchor.cohort.campaign_id)
        if not account or not campaign or account.workspace_id != workspace_id:
            continue
        actions.append(
            ActionOption(
                id=attempt.id,
                label=f"{account.name} · {campaign.name}"[:320],
                goal_id=anchor.goal_id,
                goal_revision=anchor.goal_revision,
                currency=anchor.cohort.currency,
                observed_at=anchor.configuration_observed_at,
            )
        )
    rows = list(
        db.scalars(
            select(PreviewRow)
            .where(
                PreviewRow.workspace_id == workspace_id,
                PreviewRow.original_actor_id == principal.user.id,
                PreviewRow.original_session_digest == principal.session.digest,
            )
            .order_by(PreviewRow.created_at.desc(), PreviewRow.id)
            .limit(51)
        )
    )
    baselines = []
    for row in rows[:50]:
        try:
            value = preview.read_preview(
                db, principal, provider, workspace_id, row.id, runtime.initial
            )
        except HTTPException as exc:
            if exc.status_code not in {404, 409}:
                raise
            continue
        if value.after_budget_micros is None or value.recommendation_status != "proposed":
            continue
        campaign = db.get(Campaign, value.objective.cohort.campaign_id)
        if campaign is None:
            continue
        baselines.append(
            BaselineOption(
                id=value.id,
                label=campaign.name[:320],
                goal_id=value.objective.goal_id,
                goal_revision=value.objective.goal_revision,
                currency=value.objective.cohort.currency,
                amount_micros=value.after_budget_micros,
                expires_at=value.expires_at,
            )
        )
    authorize(db, workspace_id, principal.user.id)
    now = effective_now(db, runtime.initial)
    baselines = [item for item in baselines if item.expires_at > now]
    return FeedbackOptions(
        comparison_available=True,
        preview_update_available=runtime.feedback_policy is not None,
        environment=runtime.window_policy.environment,
        window_policy=runtime.window_policy,
        feedback_policy=runtime.feedback_policy,
        actions=tuple(actions),
        baselines=tuple(baselines),
        truncated=len(attempts) > 50 or len(rows) > 50,
    )


@router.post("/comparisons", response_model=ComparisonProgressV1)
def request_comparison(
    workspace_id: int,
    body: ComparisonIntentV1,
    principal: MutationPrincipal,
    provider: Provider,
    db: Database,
    runtime: Runtime,
    response: Response,
) -> ComparisonProgressV1:
    bind_authority(principal, provider)(db, workspace_id, principal.user.id)
    current = available(runtime)
    from app.reported_feedback import service

    result = service.request_comparison(db, principal, provider, workspace_id, body, current)
    db.commit()
    response.headers["Cache-Control"] = "no-store"
    return result


@router.get("/comparisons/{request_id}/status", response_model=ComparisonProgressV1)
def progress(
    workspace_id: int,
    request_id: str,
    principal: Principal,
    provider: Provider,
    db: Database,
    runtime: Runtime,
    response: Response,
) -> ComparisonProgressV1:
    bind_authority(principal, provider)(db, workspace_id, principal.user.id)
    current = available(runtime)
    from app.reported_feedback import service

    response.headers["Cache-Control"] = "no-store"
    return service.read_comparison_progress(
        db, principal, provider, workspace_id, request_id, current
    )


@router.get("/comparisons/{request_id}", response_model=OperationalReportedComparisonV1)
def detail(
    workspace_id: int,
    request_id: str,
    principal: Principal,
    provider: Provider,
    db: Database,
    runtime: Runtime,
    response: Response,
) -> OperationalReportedComparisonV1:
    bind_authority(principal, provider)(db, workspace_id, principal.user.id)
    current = available(runtime)
    from app.reported_feedback import service

    response.headers["Cache-Control"] = "no-store"
    result = service.read_comparison(db, principal, provider, workspace_id, request_id, current)
    # The owned detail read materializes its immutable local assessment/dependencies.
    # No provider request, spending permission or advertising mutation is performed.
    db.commit()
    return result


@router.post("/previews", response_model=ReportedFeedbackPreviewV1)
def apply_preview(
    workspace_id: int,
    body: FeedbackPreviewIntentV1,
    principal: MutationPrincipal,
    provider: Provider,
    db: Database,
    runtime: Runtime,
    response: Response,
) -> ReportedFeedbackPreviewV1:
    bind_authority(principal, provider)(db, workspace_id, principal.user.id)
    current = available(runtime)
    from app.reported_feedback import service

    result = service.apply_feedback_preview(db, principal, provider, workspace_id, body, current)
    db.commit()
    response.headers["Cache-Control"] = "no-store"
    return result


@router.get("/previews/{preview_id}", response_model=ReportedFeedbackPreviewV1)
def read_preview(
    workspace_id: int,
    preview_id: str,
    principal: Principal,
    provider: Provider,
    db: Database,
    runtime: Runtime,
    response: Response,
) -> ReportedFeedbackPreviewV1:
    bind_authority(principal, provider)(db, workspace_id, principal.user.id)
    current = available(runtime)
    from app.reported_feedback import service

    response.headers["Cache-Control"] = "no-store"
    return service.read_feedback_preview(db, principal, provider, workspace_id, preview_id, current)


@router.get("/comparisons", response_model=list[ComparisonProgressV1])
def history(
    workspace_id: int,
    principal: Principal,
    provider: Provider,
    db: Database,
    runtime: Runtime,
    response: Response,
) -> list[ComparisonProgressV1]:
    bind_authority(principal, provider)(db, workspace_id, principal.user.id)
    current = available(runtime)
    from app.reported_feedback import service
    from app.reported_feedback.models import ReportedFeedbackJob

    identifiers = list(
        db.scalars(
            select(ReportedFeedbackJob.id)
            .where(
                ReportedFeedbackJob.workspace_id == workspace_id,
                ReportedFeedbackJob.original_actor_id == principal.user.id,
                ReportedFeedbackJob.original_session_digest == principal.session.digest,
            )
            .order_by(ReportedFeedbackJob.created_at.desc(), ReportedFeedbackJob.id)
            .limit(20)
        )
    )
    results = []
    for identifier in identifiers:
        try:
            results.append(
                service.read_comparison_progress(
                    db,
                    principal,
                    provider,
                    workspace_id,
                    identifier,
                    current,
                )
            )
        except HTTPException as exc:
            if exc.status_code not in {404, 409}:
                raise
    bind_authority(principal, provider)(db, workspace_id, principal.user.id)
    response.headers["Cache-Control"] = "no-store"
    return results


@router.post("/comparisons/{request_id}/reobserve", response_model=ComparisonProgressV1)
def reobserve(
    workspace_id: int,
    request_id: str,
    principal: MutationPrincipal,
    provider: Provider,
    db: Database,
    runtime: Runtime,
    response: Response,
) -> ComparisonProgressV1:
    bind_authority(principal, provider)(db, workspace_id, principal.user.id)
    current = available(runtime)
    from app.reported_feedback import service

    result = service.reobserve_comparison(
        db, principal, provider, workspace_id, request_id, current
    )
    db.commit()
    response.headers["Cache-Control"] = "no-store"
    return result
