from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Annotated, Any

from app.ads.enums import AdvertisingPlatform, ExecutionStatus, JobRunStatus, RecommendationStatus
from app.ads.models import ExecutionAudit, JobRun, Recommendation, RecommendationAudit
from app.ads.operations import public_failure_summary, sync_health
from app.api.auth import require_api_token
from app.api.repository import ReadOnlyAdsRepository
from app.api.schemas import (
    AccountMetricSummaryResponse,
    AccountResponse,
    AdGroupResponse,
    ApiErrorResponse,
    CampaignDetailResponse,
    CampaignResponse,
    DailyMetricResponse,
    ExecutionAuditResponse,
    FindingResponse,
    JobRunResponse,
    MetricWindowResponse,
    PaginatedResponse,
    RecommendationDecisionRequest,
    RecommendationResponse,
    SyncHealthResponse,
    SyncStatusResponse,
    WorkspaceConfigurationResponse,
    WorkspaceIntegrationResponse,
    WorkspaceMembershipResponse,
    WorkspaceResponse,
)
from app.database.session import get_db
from app.executors.planner import plan_dry_run
from app.optimizer.analytics import MetricWindow, inclusive_window_days
from app.optimizer.recommendations import generate_findings, recommendations_from_findings
from app.settings import settings
from app.workspaces.models import Workspace
from app.workspaces.repository import WorkspaceRepository
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

router = APIRouter(
    prefix="/api/v1",
    tags=["read-only advertising data"],
    dependencies=[Depends(require_api_token)],
)
Limit = Annotated[
    int, Query(ge=1, le=100, description="Page size. Defaults to 25 and is capped at 100.")
]
Offset = Annotated[int, Query(ge=0)]
VALIDATION_AND_DATABASE_ERRORS: dict[int | str, dict[str, Any]] = {
    401: {"model": ApiErrorResponse},
    422: {"model": ApiErrorResponse},
    503: {"model": ApiErrorResponse},
}
RESOURCE_ERRORS: dict[int | str, dict[str, Any]] = {
    404: {"model": ApiErrorResponse},
    **VALIDATION_AND_DATABASE_ERRORS,
}


def repo(db: Annotated[Session, Depends(get_db)]) -> ReadOnlyAdsRepository:
    return ReadOnlyAdsRepository(db)


def workspace_repo(db: Annotated[Session, Depends(get_db)]) -> WorkspaceRepository:
    return WorkspaceRepository(db)


@router.get(
    "/workspaces",
    response_model=PaginatedResponse[WorkspaceResponse],
    operation_id="list_ad_analyzer_workspaces",
    responses=VALIDATION_AND_DATABASE_ERRORS,
)
def list_workspaces(
    repository: Annotated[WorkspaceRepository, Depends(workspace_repo)],
    limit: Limit = 25,
    offset: Offset = 0,
) -> PaginatedResponse[WorkspaceResponse]:
    items, total = repository.list_workspaces(None, limit, offset)
    return PaginatedResponse(items=items, limit=limit, offset=offset, total=total)


def _workspace_or_404(repository: WorkspaceRepository, workspace_slug: str) -> Workspace:
    workspace = repository.get_by_slug(workspace_slug)
    if workspace is None:
        raise HTTPException(status_code=404, detail="workspace not found")
    return workspace


@router.get(
    "/workspaces/{workspace_slug}",
    response_model=WorkspaceResponse,
    operation_id="get_ad_analyzer_workspace",
    responses=RESOURCE_ERRORS,
)
def get_workspace(
    workspace_slug: str,
    repository: Annotated[WorkspaceRepository, Depends(workspace_repo)],
) -> object:
    return _workspace_or_404(repository, workspace_slug)


@router.get(
    "/workspaces/{workspace_slug}/advertising-accounts",
    response_model=PaginatedResponse[AccountResponse],
    operation_id="list_workspace_advertising_accounts",
    responses=RESOURCE_ERRORS,
)
def list_workspace_advertising_accounts(
    workspace_slug: str,
    repository: Annotated[WorkspaceRepository, Depends(workspace_repo)],
    limit: Limit = 25,
    offset: Offset = 0,
) -> PaginatedResponse[AccountResponse]:
    workspace = _workspace_or_404(repository, workspace_slug)
    items, total = repository.list_advertising_accounts(workspace.id, limit, offset)
    return PaginatedResponse(items=items, limit=limit, offset=offset, total=total)


@router.get(
    "/workspaces/{workspace_slug}/configuration",
    response_model=WorkspaceConfigurationResponse,
    operation_id="get_workspace_configuration",
    responses=RESOURCE_ERRORS,
)
def get_workspace_configuration(
    workspace_slug: str,
    repository: Annotated[WorkspaceRepository, Depends(workspace_repo)],
) -> object:
    workspace = _workspace_or_404(repository, workspace_slug)
    configuration = repository.configuration(workspace.id)
    if configuration is None:
        raise HTTPException(status_code=404, detail="workspace configuration not found")
    return configuration


@router.get(
    "/workspaces/{workspace_slug}/integrations",
    response_model=list[WorkspaceIntegrationResponse],
    operation_id="list_workspace_integrations",
    responses=RESOURCE_ERRORS,
)
def list_workspace_integrations(
    workspace_slug: str,
    repository: Annotated[WorkspaceRepository, Depends(workspace_repo)],
) -> list[WorkspaceIntegrationResponse]:
    workspace = _workspace_or_404(repository, workspace_slug)
    return [
        WorkspaceIntegrationResponse(
            id=item.id,
            workspace_id=item.workspace_id,
            integration_key=item.integration_key,
            provider=item.provider,
            display_name=item.display_name,
            status=item.status,
            configuration=item.configuration,
            credential_reference_configured=item.secret_manager_reference is not None,
        )
        for item in repository.integrations(workspace.id)
    ]


@router.get(
    "/workspaces/{workspace_slug}/memberships",
    response_model=list[WorkspaceMembershipResponse],
    operation_id="list_workspace_memberships",
    responses=RESOURCE_ERRORS,
)
def list_workspace_memberships(
    workspace_slug: str,
    repository: Annotated[WorkspaceRepository, Depends(workspace_repo)],
) -> object:
    workspace = _workspace_or_404(repository, workspace_slug)
    return repository.memberships(workspace.id)


@router.get(
    "/operations/sync-health",
    response_model=SyncHealthResponse,
    operation_id="read_only_google_ads_sync_health",
    responses=VALIDATION_AND_DATABASE_ERRORS,
)
def get_sync_health(db: Annotated[Session, Depends(get_db)]) -> SyncHealthResponse:
    return SyncHealthResponse.model_validate(sync_health(db, settings).__dict__)


def job_run_response(job_run: JobRun) -> JobRunResponse:
    """Expose only the bounded public error message, never stored job diagnostics."""
    return JobRunResponse(
        id=job_run.id,
        workspace_id=job_run.workspace_id or 1,
        platform=job_run.platform,
        account_id=job_run.account_id,
        job_name=job_run.job_name,
        status=job_run.status,
        started_at=job_run.started_at,
        finished_at=job_run.finished_at,
        records_processed=job_run.records_processed,
        error_message=public_failure_summary(job_run.error_message),
    )


def default_dates(date_from: date | None, date_to: date | None) -> tuple[date, date]:
    end = date_to or datetime.now(UTC).date()
    start = date_from or (end - timedelta(days=29))
    if end < start:
        raise HTTPException(status_code=422, detail="date_to must be on or after date_from")
    if (end - start).days > 365:
        raise HTTPException(status_code=422, detail="date range must not exceed 366 days")
    return start, end


def ratios(
    clicks: int, impressions: int, cost: int, conversions: Decimal
) -> tuple[Decimal, Decimal, Decimal, Decimal]:
    ctr = Decimal(clicks) / Decimal(impressions) if impressions else Decimal("0")
    avg_cpc = Decimal(cost) / Decimal(clicks) if clicks else Decimal("0")
    conv_rate = conversions / Decimal(clicks) if clicks else Decimal("0")
    cpa = Decimal(cost) / conversions if conversions else Decimal("0")
    return ctr, avg_cpc, conv_rate, cpa


@router.get(
    "/accounts",
    response_model=PaginatedResponse[AccountResponse],
    operation_id="read_only_list_accounts",
    responses=VALIDATION_AND_DATABASE_ERRORS,
)
def list_accounts(
    repository: Annotated[ReadOnlyAdsRepository, Depends(repo)],
    platform: AdvertisingPlatform | None = None,
    workspace_id: int | None = None,
    limit: Limit = 25,
    offset: Offset = 0,
) -> PaginatedResponse[AccountResponse]:
    items, total = repository.list_accounts(platform, limit, offset, workspace_id)
    return PaginatedResponse(items=items, limit=limit, offset=offset, total=total)


@router.get(
    "/accounts/{account_id}",
    response_model=AccountResponse,
    operation_id="read_only_get_account",
    responses=RESOURCE_ERRORS,
)
def get_account(
    account_id: int, repository: Annotated[ReadOnlyAdsRepository, Depends(repo)]
) -> object:
    account = repository.get_account(account_id)
    if account is None:
        raise HTTPException(status_code=404, detail="account not found")
    return account


@router.get(
    "/accounts/{account_id}/campaigns",
    response_model=PaginatedResponse[CampaignResponse],
    operation_id="read_only_list_account_campaigns",
    responses=RESOURCE_ERRORS,
)
def list_account_campaigns(
    account_id: int,
    repository: Annotated[ReadOnlyAdsRepository, Depends(repo)],
    status: str | None = Query(default=None, max_length=64),
    limit: Limit = 25,
    offset: Offset = 0,
) -> PaginatedResponse[CampaignResponse]:
    if repository.get_account(account_id) is None:
        raise HTTPException(status_code=404, detail="account not found")
    items, total = repository.list_account_campaigns(account_id, status, limit, offset)
    return PaginatedResponse(items=items, limit=limit, offset=offset, total=total)


@router.get(
    "/campaigns/{campaign_id}",
    response_model=CampaignDetailResponse,
    operation_id="read_only_get_campaign",
    responses=RESOURCE_ERRORS,
)
def get_campaign(
    campaign_id: int, repository: Annotated[ReadOnlyAdsRepository, Depends(repo)]
) -> object:
    campaign = repository.get_campaign(campaign_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail="campaign not found")
    return campaign


@router.get(
    "/campaigns/{campaign_id}/ad-groups",
    response_model=PaginatedResponse[AdGroupResponse],
    operation_id="read_only_list_campaign_ad_groups",
    responses=RESOURCE_ERRORS,
)
def list_campaign_ad_groups(
    campaign_id: int,
    repository: Annotated[ReadOnlyAdsRepository, Depends(repo)],
    limit: Limit = 25,
    offset: Offset = 0,
) -> PaginatedResponse[AdGroupResponse]:
    if repository.get_campaign(campaign_id) is None:
        raise HTTPException(status_code=404, detail="campaign not found")
    items, total = repository.list_campaign_ad_groups(campaign_id, limit, offset)
    return PaginatedResponse(items=items, limit=limit, offset=offset, total=total)


@router.get(
    "/campaigns/{campaign_id}/metrics",
    response_model=PaginatedResponse[DailyMetricResponse],
    operation_id="read_only_list_campaign_metrics",
    responses=RESOURCE_ERRORS,
)
def list_campaign_metrics(
    campaign_id: int,
    repository: Annotated[ReadOnlyAdsRepository, Depends(repo)],
    date_from: date | None = None,
    date_to: date | None = None,
    limit: Limit = 25,
    offset: Offset = 0,
) -> PaginatedResponse[DailyMetricResponse]:
    if repository.get_campaign(campaign_id) is None:
        raise HTTPException(status_code=404, detail="campaign not found")
    start, end = default_dates(date_from, date_to)
    items, total = repository.list_campaign_metrics(campaign_id, start, end, limit, offset)
    return PaginatedResponse(items=items, limit=limit, offset=offset, total=total)


@router.get(
    "/accounts/{account_id}/metrics/summary",
    response_model=AccountMetricSummaryResponse,
    operation_id="read_only_get_account_metric_summary",
    responses=RESOURCE_ERRORS,
)
def account_metric_summary(
    account_id: int,
    repository: Annotated[ReadOnlyAdsRepository, Depends(repo)],
    date_from: date | None = None,
    date_to: date | None = None,
) -> AccountMetricSummaryResponse:
    if repository.get_account(account_id) is None:
        raise HTTPException(status_code=404, detail="account not found")
    start, end = default_dates(date_from, date_to)
    totals = repository.account_metric_totals(account_id, start, end)
    impressions = int(totals["impressions"] or 0)
    clicks = int(totals["clicks"] or 0)
    cost = int(totals["cost_micros"] or 0)
    conversions = Decimal(totals["conversions"] or 0)
    value = int(totals["conversion_value_micros"] or 0)
    ctr, avg_cpc, conv_rate, cpa = ratios(clicks, impressions, cost, conversions)
    return AccountMetricSummaryResponse(
        account_id=account_id,
        date_from=start,
        date_to=end,
        impressions=impressions,
        clicks=clicks,
        cost_micros=cost,
        conversions=conversions,
        conversion_value_micros=value,
        ctr=ctr,
        average_cpc_micros=avg_cpc,
        conversion_rate=conv_rate,
        cost_per_conversion_micros=cpa,
    )


@router.get(
    "/job-runs",
    response_model=PaginatedResponse[JobRunResponse],
    operation_id="read_only_list_job_runs",
    responses=VALIDATION_AND_DATABASE_ERRORS,
)
def list_job_runs(
    repository: Annotated[ReadOnlyAdsRepository, Depends(repo)],
    platform: AdvertisingPlatform | None = None,
    account_id: int | None = None,
    workspace_id: int | None = None,
    status: JobRunStatus | None = None,
    limit: Limit = 25,
    offset: Offset = 0,
) -> PaginatedResponse[JobRunResponse]:
    items, total = repository.list_job_runs(
        platform, account_id, status, limit, offset, workspace_id
    )
    return PaginatedResponse(
        items=[job_run_response(item) for item in items], limit=limit, offset=offset, total=total
    )


@router.get(
    "/job-runs/latest",
    response_model=JobRunResponse,
    operation_id="read_only_get_latest_job_run",
    responses=RESOURCE_ERRORS,
)
def latest_job_run(
    repository: Annotated[ReadOnlyAdsRepository, Depends(repo)],
    platform: AdvertisingPlatform | None = None,
    account_id: int | None = None,
) -> JobRunResponse:
    job = repository.latest_job_run(platform, account_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job run not found")
    return job_run_response(job)


@router.get(
    "/sync-status",
    response_model=PaginatedResponse[SyncStatusResponse],
    operation_id="read_only_sync_status",
    responses=VALIDATION_AND_DATABASE_ERRORS,
)
def sync_status(
    repository: Annotated[ReadOnlyAdsRepository, Depends(repo)],
    workspace_id: int | None = None,
    limit: Limit = 25,
    offset: Offset = 0,
) -> PaginatedResponse[SyncStatusResponse]:
    rows, total = repository.sync_status(limit, offset, workspace_id)
    items = [
        SyncStatusResponse(
            workspace_id=a.workspace_id,
            account_id=a.id,
            platform=a.platform,
            external_account_id=a.external_account_id,
            account_name=a.name,
            latest_job_run_id=j.id if j else None,
            latest_status=j.status if j else None,
            latest_started_at=j.started_at if j else None,
            latest_finished_at=j.finished_at if j else None,
            records_processed=j.records_processed if j else None,
            last_success_at=s,
        )
        for a, j, s in rows
    ]
    return PaginatedResponse(items=items, limit=limit, offset=offset, total=total)


def _window(
    repository: ReadOnlyAdsRepository, account_id: int, start: date, end: date
) -> MetricWindow:
    totals = repository.account_metric_totals(account_id, start, end)
    return MetricWindow(
        date_from=start,
        date_to=end,
        window_days=inclusive_window_days(start, end),
        days_with_metric_rows=int(totals.get("days_with_metrics") or 0),
        impressions=int(totals["impressions"] or 0),
        clicks=int(totals["clicks"] or 0),
        cost_micros=int(totals["cost_micros"] or 0),
        conversions=Decimal(totals["conversions"] or 0),
        conversion_value_micros=int(totals["conversion_value_micros"] or 0),
    )


def _windows(
    repository: ReadOnlyAdsRepository, account_id: int, start: date, end: date
) -> tuple[MetricWindow, MetricWindow]:
    span = inclusive_window_days(start, end)
    comparison_end = start - timedelta(days=1)
    comparison_start = comparison_end - timedelta(days=span - 1)
    return (
        _window(repository, account_id, start, end),
        _window(repository, account_id, comparison_start, comparison_end),
    )


@router.get(
    "/accounts/{account_id}/analytics/window",
    response_model=MetricWindowResponse,
    operation_id="read_only_account_analytics_window",
    responses=RESOURCE_ERRORS,
)
def account_analytics_window(
    account_id: int,
    repository: Annotated[ReadOnlyAdsRepository, Depends(repo)],
    date_from: date | None = None,
    date_to: date | None = None,
) -> MetricWindowResponse:
    if repository.get_account(account_id) is None:
        raise HTTPException(status_code=404, detail="account not found")
    start, end = default_dates(date_from, date_to)
    current, comparison = _windows(repository, account_id, start, end)
    return MetricWindowResponse(
        account_id=account_id,
        date_from=start,
        date_to=end,
        comparison_date_from=comparison.date_from,
        comparison_date_to=comparison.date_to,
        window_days=current.window_days,
        days_with_metric_rows=current.days_with_metric_rows,
        data_coverage_ratio=current.data_coverage_ratio,
        comparison_window_days=comparison.window_days,
        comparison_days_with_metric_rows=comparison.days_with_metric_rows,
        comparison_data_coverage_ratio=comparison.data_coverage_ratio,
        impressions=current.impressions,
        clicks=current.clicks,
        cost_micros=current.cost_micros,
        conversions=current.conversions,
        ctr=current.ctr,
        average_cpc_micros=current.average_cpc_micros,
        conversion_rate=current.conversion_rate,
        cost_per_conversion_micros=current.cost_per_conversion_micros,
        data_coverage=current.coverage_status,
        comparison_data_coverage=comparison.coverage_status,
    )


@router.get(
    "/accounts/{account_id}/findings",
    response_model=list[FindingResponse],
    operation_id="read_only_account_findings",
    responses=RESOURCE_ERRORS,
)
def account_findings(
    account_id: int,
    repository: Annotated[ReadOnlyAdsRepository, Depends(repo)],
    date_from: date | None = None,
    date_to: date | None = None,
) -> list[FindingResponse]:
    account = repository.get_account(account_id)
    if account is None:
        raise HTTPException(status_code=404, detail="account not found")
    start, end = default_dates(date_from, date_to)
    latest, success_at = repository.account_sync_status(account_id)
    del latest
    current, comparison = _windows(repository, account_id, start, end)
    findings = generate_findings(current, comparison, last_success_at=success_at)
    return [
        FindingResponse(
            workspace_id=account.workspace_id,
            advertising_account_id=account.id,
            **finding.__dict__,
        )
        for finding in findings
    ]


@router.post(
    "/accounts/{account_id}/recommendations/generate",
    response_model=list[RecommendationResponse],
    operation_id="generate_account_recommendations",
    responses=RESOURCE_ERRORS,
    include_in_schema=False,
)
def generate_account_recommendations(
    account_id: int,
    db: Annotated[Session, Depends(get_db)],
    repository: Annotated[ReadOnlyAdsRepository, Depends(repo)],
    date_from: date | None = None,
    date_to: date | None = None,
) -> list[Recommendation]:
    account = repository.get_account(account_id)
    if account is None:
        raise HTTPException(status_code=404, detail="account not found")
    start, end = default_dates(date_from, date_to)
    _, success_at = repository.account_sync_status(account_id)
    current, comparison = _windows(repository, account_id, start, end)
    findings = generate_findings(current, comparison, last_success_at=success_at)
    drafts = recommendations_from_findings(
        findings, expires_at=datetime.now(UTC) + timedelta(days=14)
    )
    rows = [
        Recommendation(
            workspace_id=account.workspace_id,
            platform=account.platform,
            account_id=account.id,
            recommendation_type=d.recommendation_type,
            severity=d.severity,
            confidence=d.confidence,
            rationale=d.rationale,
            supporting_metrics=d.supporting_metrics,
            planned_action=d.planned_action,
            status=RecommendationStatus.PENDING_REVIEW,
            generated_at=datetime.now(UTC),
            expires_at=d.expires_at,
        )
        for d in drafts
    ]
    db.add_all(rows)
    db.commit()
    for row in rows:
        db.refresh(row)
    return rows


@router.get(
    "/recommendations",
    response_model=PaginatedResponse[RecommendationResponse],
    operation_id="list_recommendations",
    responses=VALIDATION_AND_DATABASE_ERRORS,
)
def list_recommendations(
    db: Annotated[Session, Depends(get_db)],
    status: RecommendationStatus | None = None,
    workspace_id: int | None = None,
    limit: Limit = 25,
    offset: Offset = 0,
) -> PaginatedResponse[RecommendationResponse]:
    from sqlalchemy import func, select

    stmt = select(Recommendation)
    if workspace_id is not None:
        stmt = stmt.where(Recommendation.workspace_id == workspace_id)
    if status:
        stmt = stmt.where(Recommendation.status == status)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    items = list(
        db.scalars(stmt.order_by(Recommendation.id.asc()).limit(limit).offset(offset)).all()
    )
    return PaginatedResponse(items=items, limit=limit, offset=offset, total=total)


@router.post(
    "/recommendations/{recommendation_id}/approve",
    response_model=RecommendationResponse,
    operation_id="approve_recommendation",
    responses=RESOURCE_ERRORS,
    include_in_schema=False,
)
def approve_recommendation(
    recommendation_id: int,
    payload: RecommendationDecisionRequest,
    db: Annotated[Session, Depends(get_db)],
) -> Recommendation:
    rec = db.get(Recommendation, recommendation_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="recommendation not found")
    if rec.status != RecommendationStatus.PENDING_REVIEW:
        raise HTTPException(status_code=422, detail="recommendation is not pending review")
    expires_at = (
        rec.expires_at.replace(tzinfo=UTC) if rec.expires_at.tzinfo is None else rec.expires_at
    )
    if expires_at < datetime.now(UTC):
        rec.status = RecommendationStatus.EXPIRED
        db.add(
            RecommendationAudit(
                recommendation_id=rec.id,
                actor=payload.actor,
                action="expired",
                reason="expired before approval",
            )
        )
        db.commit()
        raise HTTPException(status_code=422, detail="recommendation expired")
    rec.status = RecommendationStatus.APPROVED
    db.add(
        RecommendationAudit(
            recommendation_id=rec.id, actor=payload.actor, action="approved", reason=payload.reason
        )
    )
    db.commit()
    db.refresh(rec)
    return rec


@router.post(
    "/recommendations/{recommendation_id}/reject",
    response_model=RecommendationResponse,
    operation_id="reject_recommendation",
    responses=RESOURCE_ERRORS,
    include_in_schema=False,
)
def reject_recommendation(
    recommendation_id: int,
    payload: RecommendationDecisionRequest,
    db: Annotated[Session, Depends(get_db)],
) -> Recommendation:
    rec = db.get(Recommendation, recommendation_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="recommendation not found")
    if rec.status != RecommendationStatus.PENDING_REVIEW:
        raise HTTPException(status_code=422, detail="recommendation is not pending review")
    rec.status = RecommendationStatus.REJECTED
    db.add(
        RecommendationAudit(
            recommendation_id=rec.id, actor=payload.actor, action="rejected", reason=payload.reason
        )
    )
    db.commit()
    db.refresh(rec)
    return rec


@router.post(
    "/recommendations/{recommendation_id}/execute-dry-run",
    response_model=ExecutionAuditResponse,
    operation_id="execute_recommendation_dry_run",
    responses=RESOURCE_ERRORS,
    include_in_schema=False,
)
def execute_recommendation_dry_run(
    recommendation_id: int, idempotency_key: str, db: Annotated[Session, Depends(get_db)]
) -> ExecutionAudit:
    rec = db.get(Recommendation, recommendation_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="recommendation not found")
    existing = (
        db.query(ExecutionAudit)
        .filter_by(recommendation_id=recommendation_id, idempotency_key=idempotency_key)
        .first()
    )
    if existing:
        return existing
    if rec.status != RecommendationStatus.APPROVED:
        raise HTTPException(status_code=422, detail="recommendation must be approved by a human")
    plan = plan_dry_run(rec, settings)
    audit = ExecutionAudit(
        recommendation_id=rec.id,
        idempotency_key=idempotency_key,
        status=plan.status,
        dry_run=True,
        validation_errors=plan.validation_errors,
        rollback_instructions=plan.rollback_instructions,
    )
    if plan.status == ExecutionStatus.DRY_RUN_SUCCEEDED:
        rec.status = RecommendationStatus.EXECUTED_DRY_RUN
    db.add(audit)
    db.commit()
    db.refresh(audit)
    return audit
