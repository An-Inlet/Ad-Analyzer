from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.ads.enums import AdvertisingPlatform, JobRunStatus
from app.ads.models import JobRun
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
    JobRunResponse,
    PaginatedResponse,
    SyncStatusResponse,
)
from app.database.session import get_db

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


def job_run_response(job_run: JobRun) -> JobRunResponse:
    """Expose only the bounded public error message, never stored job diagnostics."""
    return JobRunResponse(
        id=job_run.id,
        platform=job_run.platform,
        account_id=job_run.account_id,
        job_name=job_run.job_name,
        status=job_run.status,
        started_at=job_run.started_at,
        finished_at=job_run.finished_at,
        records_processed=job_run.records_processed,
        error_message="Advertising sync failed." if job_run.error_message is not None else None,
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
    limit: Limit = 25,
    offset: Offset = 0,
) -> PaginatedResponse[AccountResponse]:
    items, total = repository.list_accounts(platform, limit, offset)
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
    status: JobRunStatus | None = None,
    limit: Limit = 25,
    offset: Offset = 0,
) -> PaginatedResponse[JobRunResponse]:
    items, total = repository.list_job_runs(platform, account_id, status, limit, offset)
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
    limit: Limit = 25,
    offset: Offset = 0,
) -> PaginatedResponse[SyncStatusResponse]:
    rows, total = repository.sync_status(limit, offset)
    items = [
        SyncStatusResponse(
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
