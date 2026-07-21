"""Read-only browser views backed by the existing repository layer."""

from datetime import UTC, date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ads.enums import ExecutionStatus, RecommendationStatus
from app.ads.models import ExecutionAudit, Recommendation, RecommendationAudit
from app.ads.operations import public_failure_summary, sync_health
from app.api.repository import ReadOnlyAdsRepository
from app.api.v1 import _windows, default_dates, ratios
from app.dashboard.auth import (
    COOKIE_NAME,
    cookie_secure,
    require_dashboard_session,
    revoke_session,
    validate_csrf,
)
from app.dashboard.formatting import money_from_micros, ratio_percent
from app.database.session import get_db
from app.executors.planner import plan_dry_run
from app.optimizer.recommendations import generate_findings
from app.settings import settings

router = APIRouter(prefix="/dashboard", dependencies=[Depends(require_dashboard_session)])
DASHBOARD_MAX_OFFSET = 10_000
templates = Jinja2Templates(directory="app/dashboard/templates")
templates.env.filters["money"] = money_from_micros
templates.env.filters["percent"] = ratio_percent
templates.env.filters["public_failure_summary"] = public_failure_summary



def redacted_mapping(value: object) -> object:
    if isinstance(value, dict):
        redacted: dict[str, object] = {}
        for key, item in value.items():
            key_text = str(key)
            if "id" in key_text.lower() or key_text.lower() in {"account", "customer"}:
                redacted[key_text] = "[redacted]"
            else:
                redacted[key_text] = redacted_mapping(item)
        return redacted
    if isinstance(value, list):
        return [redacted_mapping(item) for item in value]
    return value


def execution_safety_context() -> dict[str, object]:
    allowed_account_count = len(settings.allowed_execution_account_ids)
    allowed_mutations = sorted(settings.allowed_google_ads_mutations)
    return {
        "kill_switch_active": settings.google_ads_execution_kill_switch,
        "write_enabled": settings.google_ads_write_enabled,
        "allowed_account_count": allowed_account_count,
        "allowlist_configured": allowed_account_count > 0 and bool(allowed_mutations),
        "allowed_mutations": allowed_mutations,
    }

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
    db: Annotated[Session, Depends(get_db)],
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
    current_window, comparison_window = _windows(repository, account_id, start, end)
    findings = generate_findings(current_window, comparison_window, last_success_at=sync[1])
    recommendations = list(
        db.scalars(
            select(Recommendation)
            .where(
                Recommendation.account_id == account_id,
                Recommendation.status.in_(
                    [RecommendationStatus.PENDING_REVIEW, RecommendationStatus.APPROVED]
                ),
            )
            .order_by(Recommendation.generated_at.desc(), Recommendation.id.desc())
            .limit(25)
        ).all()
    )
    latest_execution_rows = db.execute(
        select(ExecutionAudit)
        .join(Recommendation, Recommendation.id == ExecutionAudit.recommendation_id)
        .where(Recommendation.account_id == account_id)
        .order_by(ExecutionAudit.created_at.desc(), ExecutionAudit.id.desc())
        .limit(25)
    ).scalars()
    latest_executions = {row.recommendation_id: row for row in latest_execution_rows}
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
            current_window=current_window,
            comparison_window=comparison_window,
            findings=findings,
            recommendations=recommendations,
            latest_executions=latest_executions,
            execution_status=ExecutionStatus,
            has_next=has_next(offset, limit, len(campaigns), total),
        ),
    )


@router.get("/accounts/{account_id}/execution-operations", response_class=HTMLResponse)
def execution_operations(
    request: Request,
    account_id: int,
    repository: Annotated[ReadOnlyAdsRepository, Depends(repo)],
    db: Annotated[Session, Depends(get_db)],
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0, le=DASHBOARD_MAX_OFFSET),
) -> HTMLResponse:
    account = repository.get_account(account_id)
    if account is None:
        raise HTTPException(status_code=404, detail="account not found")
    base_query = (
        select(ExecutionAudit, Recommendation)
        .join(Recommendation, Recommendation.id == ExecutionAudit.recommendation_id)
        .where(Recommendation.account_id == account_id)
    )
    total = db.scalar(
        select(func.count())
        .select_from(ExecutionAudit)
        .join(Recommendation, Recommendation.id == ExecutionAudit.recommendation_id)
        .where(Recommendation.account_id == account_id)
    ) or 0
    rows = list(
        db.execute(
            base_query.order_by(ExecutionAudit.created_at.desc(), ExecutionAudit.id.desc())
            .limit(limit)
            .offset(offset)
        ).all()
    )
    operations = [
        {
            "audit": audit,
            "recommendation": recommendation,
            "redacted_errors": redacted_mapping(audit.validation_errors),
            "redacted_payload": redacted_mapping(recommendation.planned_action),
        }
        for audit, recommendation in rows
    ]
    return templates.TemplateResponse(
        request,
        "execution_operations.html",
        page_context(
            request,
            title=f"Execution operations for {account.name}",
            account=account,
            operations=operations,
            total=total,
            limit=limit,
            offset=offset,
            has_next=has_next(offset, limit, len(operations), total),
            safety=execution_safety_context(),
            execution_status=ExecutionStatus,
        ),
    )


@router.post("/recommendations/{recommendation_id}/approve")
async def dashboard_approve_recommendation(
    request: Request,
    recommendation_id: int,
    db: Annotated[Session, Depends(get_db)],
) -> RedirectResponse:
    form = await request.form()
    request.scope["_form"] = dict(form)
    validate_csrf(request)
    reason = str(form.get("reason")) if form.get("reason") is not None else None
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
        action = "expired"
        reason = "expired before approval"
    else:
        rec.status = RecommendationStatus.APPROVED
        action = "approved"
    db.add(
        RecommendationAudit(
            recommendation_id=rec.id,
            actor="dashboard_operator",
            action=action,
            reason=reason,
        )
    )
    db.commit()
    return RedirectResponse(url=f"/dashboard/accounts/{rec.account_id}", status_code=303)


@router.post("/recommendations/{recommendation_id}/reject")
async def dashboard_reject_recommendation(
    request: Request,
    recommendation_id: int,
    db: Annotated[Session, Depends(get_db)],
) -> RedirectResponse:
    form = await request.form()
    request.scope["_form"] = dict(form)
    validate_csrf(request)
    reason = str(form.get("reason")) if form.get("reason") is not None else None
    rec = db.get(Recommendation, recommendation_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="recommendation not found")
    if rec.status != RecommendationStatus.PENDING_REVIEW:
        raise HTTPException(status_code=422, detail="recommendation is not pending review")
    rec.status = RecommendationStatus.REJECTED
    db.add(
        RecommendationAudit(
            recommendation_id=rec.id,
            actor="dashboard_operator",
            action="rejected",
            reason=reason,
        )
    )
    db.commit()
    return RedirectResponse(url=f"/dashboard/accounts/{rec.account_id}", status_code=303)


@router.post("/recommendations/{recommendation_id}/execute-dry-run")
async def dashboard_execute_dry_run(
    request: Request,
    recommendation_id: int,
    db: Annotated[Session, Depends(get_db)],
) -> RedirectResponse:
    form = await request.form()
    request.scope["_form"] = dict(form)
    validate_csrf(request)
    idempotency_key = str(form.get("idempotency_key") or "")
    if not idempotency_key:
        raise HTTPException(status_code=422, detail="idempotency key is required")
    rec = db.get(Recommendation, recommendation_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="recommendation not found")
    if rec.status != RecommendationStatus.APPROVED:
        raise HTTPException(status_code=422, detail="recommendation must be approved by a human")
    existing = (
        db.query(ExecutionAudit)
        .filter_by(recommendation_id=recommendation_id, idempotency_key=idempotency_key)
        .first()
    )
    if existing is None:
        plan = plan_dry_run(rec, settings)
        existing = ExecutionAudit(
            recommendation_id=rec.id,
            idempotency_key=idempotency_key,
            status=plan.status,
            dry_run=True,
            validation_errors=plan.validation_errors,
            rollback_instructions=plan.rollback_instructions,
        )
        if plan.status == ExecutionStatus.DRY_RUN_SUCCEEDED:
            rec.status = RecommendationStatus.EXECUTED_DRY_RUN
        db.add(existing)
        db.commit()
    return RedirectResponse(url=f"/dashboard/accounts/{rec.account_id}", status_code=303)


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
