"""Read-only browser views backed by the existing repository layer."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.ads.operations import sync_health
from app.api.repository import ReadOnlyAdsRepository
from app.api.v1 import default_dates, ratios
from app.dashboard.auth import (
    COOKIE_NAME,
    cookie_secure,
    require_dashboard_session,
    revoke_session,
    validate_csrf,
)
from app.dashboard.formatting import money_from_micros, ratio_percent
from app.database.session import get_db
from app.settings import settings

router = APIRouter(prefix="/dashboard", dependencies=[Depends(require_dashboard_session)])
DASHBOARD_MAX_OFFSET = 10_000
templates = Jinja2Templates(directory="app/dashboard/templates")
templates.env.filters["money"] = money_from_micros
templates.env.filters["percent"] = ratio_percent


def repo(db: Annotated[Session, Depends(get_db)]) -> ReadOnlyAdsRepository:
    return ReadOnlyAdsRepository(db)


def page_context(request: Request, **values: object) -> dict[str, object]:
    return {"read_only": True, "csrf_token": getattr(request.state, "dashboard_csrf", ""), **values}


def has_next(offset: int, limit: int, returned: int, total: int) -> bool:
    return offset + returned < total and offset + limit <= DASHBOARD_MAX_OFFSET


def valid_dates(date_from: date | None, date_to: date | None) -> tuple[date, date]:
    try:
        return default_dates(date_from, date_to)
    except HTTPException as exc:
        raise HTTPException(status_code=422, detail="invalid date range") from exc


@router.get("", response_class=HTMLResponse)
def overview(
    request: Request,
    repository: Annotated[ReadOnlyAdsRepository, Depends(repo)],
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0, le=DASHBOARD_MAX_OFFSET),
) -> HTMLResponse:
    accounts, total = repository.dashboard_accounts(limit, offset)
    jobs, job_total = repository.list_job_runs(None, None, None, 10, 0)
    health = sync_health(repository.session, settings)
    return templates.TemplateResponse(
        request,
        "overview.html",
        page_context(
            request,
            accounts=accounts,
            total=total,
            jobs=jobs,
            job_total=job_total,
            health=health,
            title="Dashboard",
            limit=limit,
            offset=offset,
            has_next=has_next(offset, limit, len(accounts), total),
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
    offset: int = Query(0, ge=0, le=DASHBOARD_MAX_OFFSET),
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
            request,
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
            has_next=has_next(offset, limit, len(campaigns), total),
        ),
    )


@router.post("/logout")
async def logout(request: Request) -> RedirectResponse:
    """Revoke the current session; only a same-origin CSRF-protected POST may do so."""
    form = await request.form()
    request.scope["_form"] = dict(form)
    validate_csrf(request)
    revoke_session(request.cookies.get(COOKIE_NAME))
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie(
        COOKIE_NAME,
        path="/dashboard",
        httponly=True,
        samesite="strict",
        secure=cookie_secure(request),
    )
    return response


@router.get("/campaigns/{campaign_id}", response_class=HTMLResponse)
def campaign_detail(
    request: Request,
    campaign_id: int,
    repository: Annotated[ReadOnlyAdsRepository, Depends(repo)],
    date_from: date | None = None,
    date_to: date | None = None,
    ad_group_limit: int = Query(25, ge=1, le=100),
    ad_group_offset: int = Query(0, ge=0, le=DASHBOARD_MAX_OFFSET),
    metric_limit: int = Query(25, ge=1, le=100),
    metric_offset: int = Query(0, ge=0, le=DASHBOARD_MAX_OFFSET),
) -> HTMLResponse:
    campaign = repository.get_campaign(campaign_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail="campaign not found")
    start, end = valid_dates(date_from, date_to)
    groups, group_total = repository.list_campaign_ad_groups(
        campaign_id, ad_group_limit, ad_group_offset
    )
    metrics, metric_total = repository.list_campaign_metrics(
        campaign_id, start, end, metric_limit, metric_offset
    )
    return templates.TemplateResponse(
        request,
        "campaign.html",
        page_context(
            request,
            title=campaign.name,
            campaign=campaign,
            groups=groups,
            group_total=group_total,
            metrics=metrics,
            metric_total=metric_total,
            ad_group_limit=ad_group_limit,
            ad_group_offset=ad_group_offset,
            metric_limit=metric_limit,
            metric_offset=metric_offset,
            has_next_ad_groups=has_next(ad_group_offset, ad_group_limit, len(groups), group_total),
            has_next_metrics=has_next(metric_offset, metric_limit, len(metrics), metric_total),
            date_from=start,
            date_to=end,
        ),
    )


@router.get("/job-runs", response_class=HTMLResponse)
def job_runs(
    request: Request,
    repository: Annotated[ReadOnlyAdsRepository, Depends(repo)],
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0, le=DASHBOARD_MAX_OFFSET),
) -> HTMLResponse:
    jobs, total = repository.list_job_runs(None, None, None, limit, offset)
    return templates.TemplateResponse(
        request,
        "job_runs.html",
        page_context(
            request,
            title="Job runs",
            jobs=jobs,
            total=total,
            limit=limit,
            offset=offset,
            has_next=has_next(offset, limit, len(jobs), total),
        ),
    )
