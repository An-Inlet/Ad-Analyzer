"""Read-only browser views backed by the existing repository layer."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.api.repository import ReadOnlyAdsRepository
from app.api.v1 import default_dates, ratios
from app.dashboard.auth import require_dashboard_session
from app.dashboard.formatting import money_from_micros, ratio_percent
from app.database.session import get_db

router = APIRouter(prefix="/dashboard", dependencies=[Depends(require_dashboard_session)])
templates = Jinja2Templates(directory="app/dashboard/templates")
templates.env.filters["money"] = money_from_micros
templates.env.filters["percent"] = ratio_percent


def repo(db: Annotated[Session, Depends(get_db)]) -> ReadOnlyAdsRepository:
    return ReadOnlyAdsRepository(db)


def page_context(**values: object) -> dict[str, object]:
    return {"read_only": True, **values}


def valid_dates(date_from: date | None, date_to: date | None) -> tuple[date, date]:
    try:
        return default_dates(date_from, date_to)
    except HTTPException as exc:
        raise HTTPException(status_code=422, detail="invalid date range") from exc


@router.get("", response_class=HTMLResponse)
def overview(
    request: Request, repository: Annotated[ReadOnlyAdsRepository, Depends(repo)]
) -> HTMLResponse:
    accounts, total = repository.dashboard_accounts()
    jobs, job_total = repository.list_job_runs(None, None, None, 10, 0)
    return templates.TemplateResponse(
        request,
        "overview.html",
        page_context(
            accounts=accounts,
            total=total,
            jobs=jobs,
            job_total=job_total,
            title="Dashboard",
        ),
    )


@router.get("/accounts/{account_id}", response_class=HTMLResponse)
def account_detail(
    request: Request,
    account_id: int,
    repository: Annotated[ReadOnlyAdsRepository, Depends(repo)],
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> HTMLResponse:
    account = repository.get_account(account_id)
    if account is None:
        raise HTTPException(status_code=404, detail="account not found")
    start, end = valid_dates(date_from, date_to)
    campaigns, total = repository.list_account_campaigns(account_id, None, limit, offset)
    totals = repository.account_metric_totals(account_id, start, end)
    impressions, clicks, cost = (
        int(totals["impressions"]),
        int(totals["clicks"]),
        int(totals["cost_micros"]),
    )
    conversions = totals["conversions"]
    ctr, _cpc, _rate, cpa = ratios(clicks, impressions, cost, conversions)
    sync = repository.account_sync_status(account_id)
    return templates.TemplateResponse(
        request,
        "account.html",
        page_context(
            title=account.name,
            account=account,
            campaigns=campaigns,
            total=total,
            limit=limit,
            offset=offset,
            date_from=start,
            date_to=end,
            totals=totals,
            ctr=ctr,
            cpa=cpa,
            sync=sync,
        ),
    )


@router.get("/campaigns/{campaign_id}", response_class=HTMLResponse)
def campaign_detail(
    request: Request,
    campaign_id: int,
    repository: Annotated[ReadOnlyAdsRepository, Depends(repo)],
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> HTMLResponse:
    campaign = repository.get_campaign(campaign_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail="campaign not found")
    start, end = valid_dates(date_from, date_to)
    groups, group_total = repository.list_campaign_ad_groups(campaign_id, limit, offset)
    metrics, metric_total = repository.list_campaign_metrics(campaign_id, start, end, limit, offset)
    return templates.TemplateResponse(
        request,
        "campaign.html",
        page_context(
            title=campaign.name,
            campaign=campaign,
            groups=groups,
            group_total=group_total,
            metrics=metrics,
            metric_total=metric_total,
            limit=limit,
            offset=offset,
            date_from=start,
            date_to=end,
        ),
    )


@router.get("/job-runs", response_class=HTMLResponse)
def job_runs(
    request: Request,
    repository: Annotated[ReadOnlyAdsRepository, Depends(repo)],
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> HTMLResponse:
    jobs, total = repository.list_job_runs(None, None, None, limit, offset)
    return templates.TemplateResponse(
        request,
        "job_runs.html",
        page_context(title="Job runs", jobs=jobs, total=total, limit=limit, offset=offset),
    )
