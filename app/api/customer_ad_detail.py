"""Customer-scoped Meta detail reporting. Does not invoke providers."""

from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query, Response
from sqlalchemy import select

from app.ads.enums import AdvertisingPlatform
from app.ads.models import Ad, AdSet, Campaign
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
    return {
        **report,
        "ads": [
            {
                "id": ad.id,
                "name": ad.name,
                "status": ad.status,
                "current_creative_id": ad.creative_external_id,
                "current_creative_name": ad.creative_name,
            }
            for ad in ads[:100]
        ],
        "has_more": len(ads) > 100,
    }
