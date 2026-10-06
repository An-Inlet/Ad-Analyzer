"""Atomic bounded Meta child-detail imports; campaign totals remain authoritative."""

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from fastapi import HTTPException
from pydantic import Field
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.ads.enums import AdvertisingPlatform, MetricEntityType
from app.ads.models import Ad, AdSet, Campaign, DailyMetric
from app.ads.repository import AdvertisingMetricsRepository
from app.ads.schemas import AdCreate, DailyMetricCreate
from app.goals.schemas import StrictModel
from app.imports.scope import AdvertisingImportScope, validate_advertising_scope
from app.meta.client import MetaClient, unpack_page
from app.meta.normalize import metric_values
from app.meta.security import MetaError, identifier
from app.settings import Settings


class InventoryAd(StrictModel):
    external_id: str = Field(pattern=r"^[0-9]{1,32}$")
    campaign_id: str = Field(pattern=r"^[0-9]{1,32}$")
    ad_set_id: str = Field(pattern=r"^[0-9]{1,32}$")
    name: str = Field(min_length=1, max_length=255)
    status: str = Field(min_length=1, max_length=64)
    creative_id: str = Field(pattern=r"^[0-9]{1,32}$")
    creative_name: str | None = Field(default=None, max_length=255)


class DetailMetric(StrictModel):
    level: Literal["ad_set", "ad"]
    campaign_id: str = Field(pattern=r"^[0-9]{1,32}$")
    ad_set_id: str = Field(pattern=r"^[0-9]{1,32}$")
    ad_id: str | None = Field(default=None, pattern=r"^[0-9]{1,32}$")
    metric_date: date
    impressions: int = Field(ge=0)
    clicks: int = Field(ge=0)
    cost_micros: int = Field(ge=0)
    conversions: Decimal = Field(ge=0)
    conversion_value_micros: int = Field(ge=0)


class DetailBatch(StrictModel):
    complete: Literal[True]
    account_external_id: str = Field(pattern=r"^[0-9]{1,32}$")
    start: date
    end: date
    inventory: list[InventoryAd] = Field(max_length=10000)
    metrics: list[DetailMetric] = Field(max_length=50000)


def collect(
    client: MetaClient,
    account_id: str,
    token: str,
    start: date,
    end: date,
    currency: str,
    action_type: str | None,
) -> DetailBatch:
    if not 0 <= (end - start).days <= 55:
        raise MetaError("meta_detail_window_invalid")
    inventory: list[InventoryAd] = []
    metrics: list[DetailMetric] = []
    for phase in ("ads", "adset_insights", "ad_insights"):
        cursor = None
        seen: set[str] = set()
        for _ in range(100):
            items, next_cursor = unpack_page(
                client.detail_page(account_id, token, phase, cursor, start, end), cursor
            )
            for item in items:
                if identifier(item["account_id"]) != account_id:
                    raise MetaError("meta_account_mismatch")
                if phase == "ads":
                    creative = item.get("creative")
                    if not isinstance(creative, dict):
                        raise MetaError("meta_creative_unavailable")
                    inventory.append(
                        InventoryAd(
                            external_id=identifier(item["id"]),
                            campaign_id=identifier(item["campaign_id"]),
                            ad_set_id=identifier(item["adset_id"]),
                            name=item["name"],
                            status=item["status"],
                            creative_id=identifier(creative["id"]),
                            creative_name=creative.get("name"),
                        )
                    )
                else:
                    values = metric_values(item, account_id, currency, start, end, action_type)
                    metrics.append(
                        DetailMetric(
                            level="ad_set" if phase == "adset_insights" else "ad",
                            campaign_id=identifier(item["campaign_id"]),
                            ad_set_id=identifier(item["adset_id"]),
                            ad_id=identifier(item["ad_id"]) if phase == "ad_insights" else None,
                            **values,
                        )
                    )
            if len(inventory) > 10000 or len(metrics) > 50000:
                raise MetaError("meta_detail_capacity_exceeded")
            if next_cursor is None:
                break
            if next_cursor in seen:
                raise MetaError("meta_invalid_cursor")
            seen.add(next_cursor)
            cursor = next_cursor
        else:
            raise MetaError("meta_detail_capacity_exceeded")
    return DetailBatch(
        complete=True,
        account_external_id=account_id,
        start=start,
        end=end,
        inventory=inventory,
        metrics=metrics,
    )


def publish(db: Session, scope: AdvertisingImportScope, batch: DetailBatch) -> int:
    with db.begin_nested():
        return _publish(db, scope, batch)


def _publish(db: Session, scope: AdvertisingImportScope, batch: DetailBatch) -> int:
    account, _ = validate_advertising_scope(db, scope)
    if (
        scope.platform != AdvertisingPlatform.META_ADS
        or account.external_account_id != batch.account_external_id
    ):
        raise HTTPException(409, "Meta detail ownership mismatch")
    if not 0 <= (batch.end - batch.start).days <= 55:
        raise HTTPException(422, "invalid detail window")
    campaigns = {
        c.external_campaign_id: c
        for c in db.scalars(
            select(Campaign).where(
                Campaign.account_id == scope.account_id, Campaign.platform == scope.platform
            )
        )
    }
    sets = {
        (c.external_campaign_id, a.external_ad_set_id): a
        for a, c in db.execute(
            select(AdSet, Campaign)
            .join(Campaign, Campaign.id == AdSet.campaign_id)
            .where(Campaign.account_id == scope.account_id, AdSet.platform == scope.platform)
        )
    }
    repository = AdvertisingMetricsRepository(db)
    repository.scope = scope
    ads: dict[str, Ad] = {}
    originals: dict[str, InventoryAd] = {}
    for item in batch.inventory:
        if item.external_id in originals and originals[item.external_id] != item:
            raise HTTPException(409, "conflicting ad inventory")
        originals[item.external_id] = item
        parent = sets.get((item.campaign_id, item.ad_set_id))
        if parent is None:
            raise HTTPException(409, "owned ad-set inventory unavailable")
        ads[item.external_id] = repository.upsert_ad(
            AdCreate(
                platform=scope.platform,
                external_ad_id=item.external_id,
                name=item.name,
                status=item.status,
                ad_set_id=parent.id,
                creative_external_id=item.creative_id,
                creative_name=item.creative_name,
            )
        )
    unique: dict[tuple[str, str, date], DetailMetric] = {}
    normalized: list[DailyMetricCreate] = []
    for metric in batch.metrics:
        key = (metric.level, metric.ad_id or metric.ad_set_id, metric.metric_date)
        if key in unique:
            if unique[key] != metric:
                raise HTTPException(409, "conflicting detail metrics")
            continue
        unique[key] = metric
        parent = sets.get((metric.campaign_id, metric.ad_set_id))
        campaign = campaigns.get(metric.campaign_id)
        if campaign is None or parent is None or not batch.start <= metric.metric_date <= batch.end:
            raise HTTPException(409, "metric parent/window unavailable")
        ad = ads.get(metric.ad_id or "")
        if metric.level == "ad" and (ad is None or ad.ad_set_id != parent.id):
            raise HTTPException(409, "owned ad inventory unavailable")
        if metric.level == "ad_set" and metric.ad_id is not None:
            raise HTTPException(422, "mixed metric grain")
        normalized.append(
            DailyMetricCreate(
                platform=scope.platform,
                entity_type=MetricEntityType(metric.level),
                entity_id=ad.id if ad is not None else parent.id,
                campaign_id=campaign.id,
                ad_set_id=parent.id,
                ad_id=ad.id if ad is not None else None,
                **metric.model_dump(exclude={"level", "campaign_id", "ad_set_id", "ad_id"}),
            )
        )
    db.execute(
        delete(DailyMetric).where(
            DailyMetric.campaign_id.in_([c.id for c in campaigns.values()]),
            DailyMetric.platform == scope.platform,
            DailyMetric.entity_type.in_(["ad_set", "ad"]),
            DailyMetric.metric_date >= batch.start,
            DailyMetric.metric_date <= batch.end,
        )
    )
    for normalized_metric in normalized:
        repository.upsert_daily_metric(normalized_metric)
    db.flush()
    return len(normalized)


def detail_report(
    db: Session, scope: AdvertisingImportScope, start: date, end: date
) -> dict[str, Any]:
    validate_advertising_scope(db, scope)
    rows = list(
        db.scalars(
            select(DailyMetric)
            .join(Campaign, Campaign.id == DailyMetric.campaign_id)
            .where(
                Campaign.account_id == scope.account_id,
                DailyMetric.platform == scope.platform,
                DailyMetric.entity_type.in_(["campaign", "ad_set", "ad"]),
                DailyMetric.metric_date >= start,
                DailyMetric.metric_date <= end,
            )
        )
    )
    totals = {
        level: sum(r.cost_micros for r in rows if r.entity_type == level)
        for level in ("campaign", "ad_set", "ad")
    }
    present = {r.entity_type for r in rows}
    return {
        "spend_micros": totals["campaign"] if "campaign" in present else None,
        "comparison": {level: totals[level] if level in present else None for level in totals},
        "children_reconcile": all(
            level in present and totals[level] == totals["campaign"] for level in totals
        ),
        "summed_across_grains": False,
        "historical_creative_attribution_available": False,
    }


def sync_window(
    db: Session,
    workspace_id: int,
    connection_id: int,
    configuration: Settings,
    client: MetaClient,
    start: date,
    end: date,
    now: datetime,
) -> int:
    """Explicit, disabled-by-default extension; no scheduler silently changes behavior."""
    from app.ads.enums import JobRunStatus
    from app.imports.native import bind_meta
    from app.meta.models import MetaConnection
    from app.meta.service import ConnectionService
    from app.meta.sync import syncing_allowed

    if not configuration.meta_detail_enabled or not syncing_allowed(db, workspace_id):
        raise HTTPException(409, "Meta detail sync disabled")
    row = db.scalar(
        select(MetaConnection)
        .where(MetaConnection.id == connection_id, MetaConnection.workspace_id == workspace_id)
        .with_for_update()
    )
    if row is None or row.status != "connected":
        raise HTTPException(404, "Meta connection unavailable")
    bind_meta(db, row)
    scope = AdvertisingImportScope(
        workspace_id,
        row.workspace_integration_id or 0,
        row.account_id,
        AdvertisingPlatform.META_ADS,
    )
    account, _ = validate_advertising_scope(db, scope)
    token = ConnectionService(db, configuration, client).access_token(row, now)
    batch = collect(
        client,
        row.external_account_id,
        token,
        start,
        end,
        account.currency_code,
        row.conversion_action_type,
    )
    count = publish(db, scope, batch)
    repository = AdvertisingMetricsRepository(db)
    job = repository.create_job_run(
        platform=scope.platform,
        job_name="meta_detail_sync",
        status=JobRunStatus.SUCCEEDED,
        account_id=scope.account_id,
        workspace_id=workspace_id,
        connection_id=scope.connection_id,
    )
    repository.finish_job_run(job, status=JobRunStatus.SUCCEEDED, records_processed=count)
    db.commit()
    return count
