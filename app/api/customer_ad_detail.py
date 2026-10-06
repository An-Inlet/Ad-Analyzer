"""Customer-scoped Meta detail reporting. Does not invoke providers."""

from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query, Response
from sqlalchemy import func, select

from app.ads.enums import AdvertisingPlatform
from app.ads.models import Ad, AdSet, Campaign, DailyMetric
from app.customers.access import Database, Principal, customer_workspace
from app.imports.scope import AdvertisingImportScope, ImportScopeError
from app.meta.detail import detail_report
from app.meta.models import MetaConnection

router = APIRouter(prefix="/api/customer/v1/workspaces/{workspace_id}/meta", tags=["customer"])


@router.get("/connections/{connection_id}/detail")
def detail(
    workspace_id: int,
    connection_id: int,
    start: date,
    end: date,
    principal: Principal,
    db: Database,
    response: Response,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict[str, Any]:
    customer_workspace(db, principal.user.id, workspace_id)
    response.headers["Cache-Control"] = "no-store"
    if not 0 <= (end - start).days <= 55:
        raise HTTPException(422, "detail window must be at most 56 days")
    row = db.scalar(
        select(MetaConnection).where(
            MetaConnection.id == connection_id, MetaConnection.workspace_id == workspace_id
        )
    )
    if row is None or row.workspace_integration_id is None:
        raise HTTPException(404, "connection unavailable")
    scope = AdvertisingImportScope(
        workspace_id, row.workspace_integration_id, row.account_id, AdvertisingPlatform.META_ADS
    )
    try:
        report = detail_report(db, scope, start, end)
    except ImportScopeError:
        raise HTTPException(404, "connection unavailable") from None
    ads = list(
        db.scalars(
            select(Ad)
            .join(AdSet, AdSet.id == Ad.ad_set_id)
            .join(Campaign, Campaign.id == AdSet.campaign_id)
            .where(Campaign.account_id == row.account_id, Ad.platform == scope.platform)
            .order_by(Ad.id)
            .offset(offset)
            .limit(101)
        )
    )
    sets = list(
        db.scalars(
            select(AdSet)
            .join(Campaign, Campaign.id == AdSet.campaign_id)
            .where(Campaign.account_id == row.account_id, AdSet.platform == scope.platform)
            .order_by(AdSet.id)
            .offset(offset)
            .limit(101)
        )
    )

    def performance(level: str, ids: list[int]) -> dict[int, dict[str, Any]]:
        metrics = db.execute(
            select(
                DailyMetric.entity_id,
                func.sum(DailyMetric.impressions),
                func.sum(DailyMetric.clicks),
                func.sum(DailyMetric.cost_micros),
                func.sum(DailyMetric.conversions),
                func.sum(DailyMetric.conversion_value_micros),
            )
            .join(Campaign, Campaign.id == DailyMetric.campaign_id)
            .where(
                Campaign.account_id == row.account_id,
                DailyMetric.platform == scope.platform,
                DailyMetric.entity_type == level,
                DailyMetric.entity_id.in_(ids),
                DailyMetric.metric_date >= start,
                DailyMetric.metric_date <= end,
            )
            .group_by(DailyMetric.entity_id)
        )
        return {
            item[0]: {
                "impressions": int(item[1]),
                "clicks": int(item[2]),
                "spend_micros": int(item[3]),
                "conversions": str(item[4]),
                "conversion_value_micros": int(item[5]),
            }
            for item in metrics
        }

    ad_metrics = performance("ad", [ad.id for ad in ads[:100]])
    set_metrics = performance("ad_set", [item.id for item in sets[:100]])
    return {
        **report,
        "ads": [
            {
                "id": ad.id,
                "name": ad.name,
                "status": ad.status,
                "ad_set_id": ad.ad_set_id,
                "performance": ad_metrics.get(ad.id),
                "current_creative_id": ad.creative_external_id,
                "current_creative_name": ad.creative_name,
            }
            for ad in ads[:100]
        ],
        "has_more": len(ads) > 100,
        "ad_sets": [
            {
                "id": item.id,
                "campaign_id": item.campaign_id,
                "name": item.name,
                "status": item.status,
                "performance": set_metrics.get(item.id),
            }
            for item in sets[:100]
        ],
        "ad_sets_has_more": len(sets) > 100,
        "conversion_action_type": row.conversion_action_type,
        "import_status": row.error_code
        or ("syncing" if row.window_end else ("complete" if row.last_sync_at else "not_synced")),
    }
