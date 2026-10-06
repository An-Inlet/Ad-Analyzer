"""Tenant-explicit TikTok fixture ingestion using common campaign/group/ad metrics."""

from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.ads.enums import AdvertisingPlatform, JobRunStatus, MetricEntityType
from app.ads.models import Ad, AdGroup, Campaign, DailyMetric
from app.ads.repository import AdvertisingMetricsRepository
from app.ads.schemas import AdCreate, AdGroupCreate, CampaignCreate, DailyMetricCreate
from app.google_connections.models import GoogleImportCompletion
from app.imports.scope import AdvertisingImportScope, validate_advertising_scope
from app.sources import service
from app.sources.contracts import AdvertisingPage, SourceTransport
from app.sources.models import SourceConnection


def _publish(
    db: Session, row: SourceConnection, scope: AdvertisingImportScope, pages: list[AdvertisingPage]
) -> int:
    repository = AdvertisingMetricsRepository(db)
    repository.scope = scope
    raw: dict[str, dict[str, Any]] = {"campaigns": {}, "groups": {}, "ads": {}, "metrics": {}}
    for page in pages:
        for kind in raw:
            for item in getattr(page, kind):
                key = item.id if kind != "metrics" else f"{item.level}:{item.id}:{item.day}"
                if key in raw[kind] and raw[kind][key] != item:
                    raise HTTPException(409, "conflicting source page")
                raw[kind][key] = item
    campaigns: dict[str, Campaign] = {}
    groups: dict[str, AdGroup] = {}
    ads: dict[str, Ad] = {}
    for key, c in raw["campaigns"].items():
        campaigns[key] = repository.upsert_campaign(
            CampaignCreate(
                account_id=scope.account_id,
                platform=scope.platform,
                external_campaign_id=key,
                name=c.name,
                status=c.status,
                channel_type=c.objective,
            )
        )
    for key, group in raw["groups"].items():
        parent = campaigns.get(group.campaign_id)
        if parent is None:
            raise HTTPException(409, "campaign inventory unavailable")
        groups[key] = repository.upsert_ad_group(
            AdGroupCreate(
                campaign_id=parent.id,
                platform=scope.platform,
                external_ad_group_id=key,
                name=group.name,
                status=group.status,
            )
        )
    for key, ad in raw["ads"].items():
        parent_group = groups.get(ad.group_id)
        if parent_group is None:
            raise HTTPException(409, "ad-group inventory unavailable")
        ads[key] = repository.upsert_ad(
            AdCreate(
                platform=scope.platform,
                ad_group_id=parent_group.id,
                external_ad_id=key,
                name=ad.name,
                status=ad.status,
            )
        )
    normalized = []
    for metric in raw["metrics"].values():
        if not row.window_start <= metric.day <= row.window_end:
            raise HTTPException(409, "metric window mismatch")
        group_id, ad_id = None, None
        if metric.level == "campaign":
            campaign = campaigns.get(metric.id)
            entity_id = campaign.id if campaign else 0
            campaign_id = entity_id
        elif metric.level == "ad_group":
            group = groups.get(metric.id)
            entity_id = group.id if group else 0
            group_id, campaign_id = entity_id, group.campaign_id if group else 0
        else:
            item = ads.get(metric.id)
            ad_id = item.id if item else 0
            group_id = item.ad_group_id if item else None
            group = next((g for g in groups.values() if g.id == group_id), None)
            entity_id, campaign_id = ad_id, group.campaign_id if group else 0
        if not entity_id or not campaign_id:
            raise HTTPException(409, "metric entity unavailable")
        normalized.append(
            DailyMetricCreate(
                platform=scope.platform,
                entity_type=MetricEntityType(metric.level),
                entity_id=entity_id,
                campaign_id=campaign_id,
                ad_group_id=group_id,
                ad_id=ad_id,
                metric_date=metric.day,
                impressions=metric.impressions,
                clicks=metric.clicks,
                cost_micros=metric.cost_micros,
                conversions=metric.conversions,
                conversion_value_micros=metric.conversion_value_micros,
            )
        )
    db.execute(
        delete(DailyMetric).where(
            DailyMetric.campaign_id.in_(
                select(Campaign.id).where(Campaign.account_id == scope.account_id)
            ),
            DailyMetric.platform == scope.platform,
            DailyMetric.entity_type.in_(["campaign", "ad_group", "ad"]),
            DailyMetric.metric_date >= row.window_start,
            DailyMetric.metric_date <= row.window_end,
        )
    )
    for metric in normalized:
        repository.upsert_daily_metric(metric)
    return len(normalized)


class SourceReadUnavailable(HTTPException):
    """Current provider transport call failed; staged pages remain retryable."""

    def __init__(self) -> None:
        super().__init__(502, "source read unavailable")


def tick(
    db: Session,
    workspace_id: int,
    connection_id: str,
    generation: int,
    transport: SourceTransport,
    now: datetime,
) -> int | None:
    from app.billing.entitlements import paid_work

    paid_work(db, workspace_id, now)
    service.ready(transport)
    row = service.owned(db, workspace_id, "tiktok_ads", connection_id)
    if row.generation != generation or row.account_id is None:
        raise HTTPException(409, "source generation unavailable")
    scope = AdvertisingImportScope(
        workspace_id, row.integration_id, row.account_id, AdvertisingPlatform.TIKTOK_ADS
    )
    account, _ = validate_advertising_scope(db, scope)
    try:
        token = service.token(row, now)
    except HTTPException:
        row.status, row.error_code = "reconnect_required", "token_expired_or_unavailable"
        db.commit()
        raise
    try:
        raw_page = transport.read(
            row.external_id, token, row.window_start, row.window_end, row.cursor
        )
    except Exception:
        row.error_code, row.next_attempt_at = "read_unavailable", now + timedelta(minutes=5)
        db.commit()
        raise SourceReadUnavailable() from None
    page = AdvertisingPage.model_validate(raw_page)
    if page.account_id != row.external_id or page.currency != account.currency_code:
        raise HTTPException(409, "source account/currency mismatch")
    staged = dict(row.staged)
    seen = list(staged.get("cursors", []))
    if page.next_cursor and (page.next_cursor == row.cursor or page.next_cursor in seen):
        raise HTTPException(409, "repeated source cursor")
    pages = list(staged.get("pages", [])) + [page.model_dump(mode="json")]
    if (
        len(pages) > 100
        or sum(sum(len(p[k]) for k in ("campaigns", "groups", "ads", "metrics")) for p in pages)
        > 50000
    ):
        raise HTTPException(409, "source import capacity exceeded")
    if page.next_cursor:
        row.error_code, row.next_attempt_at = None, None
        row.cursor, row.staged = (
            page.next_cursor,
            {"pages": pages, "cursors": seen + [page.next_cursor]},
        )
        db.commit()
        return None
    with db.begin_nested():
        count = _publish(db, row, scope, [AdvertisingPage.model_validate(p) for p in pages])
        repository = AdvertisingMetricsRepository(db)
        job = repository.create_job_run(
            platform=scope.platform,
            job_name="tiktok_fixture_sync",
            status=JobRunStatus.SUCCEEDED,
            account_id=scope.account_id,
            workspace_id=workspace_id,
            connection_id=scope.connection_id,
        )
        repository.finish_job_run(job, status=JobRunStatus.SUCCEEDED, records_processed=count)
        db.flush()
        # This job-key outbox is structurally provider-neutral; retain its original
        # table identity rather than migrating existing completion records away.
        db.add(GoogleImportCompletion(job_id=job.id, state="pending"))
        row.cursor, row.staged, row.error_code = None, {}, None
        row.covered_from, row.covered_through = row.window_start, row.window_end
        row.last_sync_at, row.next_attempt_at = now, now + timedelta(hours=1)
        end = now.astimezone(ZoneInfo(account.time_zone or "UTC")).date() - timedelta(days=1)
        row.window_start, row.window_end = end - timedelta(days=29), end
    db.commit()
    return job.id
