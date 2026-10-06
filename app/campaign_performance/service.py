"""Current-only owned evidence. Completion metadata cannot replay old metric bodies."""

import hashlib
import json
from collections.abc import Callable
from datetime import date, datetime
from decimal import Decimal
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ads.models import AdvertisingAccount, Campaign, DailyMetric
from app.campaign_performance.contracts import CampaignPerformanceV1
from app.campaign_performance.models import CurrentPerformance, PerformanceCompletion
from app.lifecycle.privacy import workspace_export_revision
from app.meta.models import MetaConnection
from app.meta.security import API_VERSION, PURCHASE_ACTIONS, utc

MAX_ROWS = 100_000
Authorize = Callable[[Session, int, str], None]


def unavailable() -> HTTPException:
    return HTTPException(409, "current campaign reporting evidence unavailable")


def manifest(
    db: Session, account: AdvertisingAccount, start: date, end: date
) -> tuple[str, list[DailyMetric]]:
    rows = list(
        db.scalars(
            select(DailyMetric)
            .join(
                Campaign,
                (Campaign.id == DailyMetric.campaign_id)
                & (Campaign.platform == DailyMetric.platform),
            )
            .where(
                Campaign.account_id == account.id,
                Campaign.platform == account.platform,
                DailyMetric.entity_type == "campaign",
                DailyMetric.metric_date >= start,
                DailyMetric.metric_date <= end,
            )
            .order_by(DailyMetric.campaign_id, DailyMetric.metric_date)
            .limit(MAX_ROWS + 1)
            .execution_options(populate_existing=True)
        )
    )
    if len(rows) > MAX_ROWS:
        raise ValueError("campaign reporting capacity exceeded")
    body = [
        [
            r.campaign_id,
            r.metric_date.isoformat(),
            r.impressions,
            r.clicks,
            r.cost_micros,
            format(r.conversions, ".6f"),
            r.conversion_value_micros,
        ]
        for r in rows
    ]
    digest = hashlib.sha256(
        json.dumps(
            ["inlet.campaign-performance-manifest.v1", body],
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    return digest, rows


def publish_meta(
    db: Session, source: MetaConnection, start: date, end: date, now: datetime
) -> None:
    """Called only by terminal Meta import under its existing workspace/source locks."""
    account = db.get(AdvertisingAccount, source.account_id)
    if account is None or account.workspace_id != source.workspace_id or not account.time_zone:
        raise ValueError("campaign reporting account unavailable")
    db.flush()
    digest, rows = manifest(db, account, start, end)
    item = PerformanceCompletion(
        id=uuid4().hex,
        workspace_id=source.workspace_id,
        account_id=account.id,
        platform="meta_ads",
        source_connection_ref=str(source.id),
        generation=source.generation,
        privacy_revision=workspace_export_revision(db, source.workspace_id),
        starts_on=start,
        ends_on=end,
        currency=account.currency_code,
        time_zone=account.time_zone,
        query_version=f"meta.{API_VERSION}.campaign-day.v1",
        semantics="explicit_platform_event"
        if source.conversion_action_type
        else "traffic_spend_only",
        selected_event=source.conversion_action_type,
        reporting_basis="provider_defaults_unspecified",
        completed_at=now,
        row_count=len(rows),
        manifest_digest=digest,
    )
    db.add(item)
    db.flush()
    current = db.get(CurrentPerformance, account.id)
    if current is None:
        db.add(
            CurrentPerformance(
                account_id=account.id, workspace_id=source.workspace_id, completion_id=item.id
            )
        )
    else:
        current.completion_id = item.id
    db.flush()


def read_current(
    db: Session,
    workspace_id: int,
    actor: str,
    account_id: int,
    campaign_id: int,
    expected_completion_id: str | None,
    authorize: Authorize,
) -> CampaignPerformanceV1:
    """Original-session callback is mandatory; no IO, commit or historical replay."""
    authorize(db, workspace_id, actor)
    source = db.scalar(
        select(MetaConnection)
        .where(
            MetaConnection.workspace_id == workspace_id,
            MetaConnection.account_id == account_id,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    current = db.get(CurrentPerformance, account_id, populate_existing=True)
    account = db.get(AdvertisingAccount, account_id, populate_existing=True)
    campaign = db.get(Campaign, campaign_id, populate_existing=True)
    if (
        source is None
        or source.status != "connected"
        or source.error_code
        or current is None
        or current.workspace_id != workspace_id
        or account is None
        or account.workspace_id != workspace_id
        or account.external_account_id != source.external_account_id
        or account.connection_id != source.workspace_integration_id
        or campaign is None
        or campaign.account_id != account_id
        or (expected_completion_id is not None and current.completion_id != expected_completion_id)
    ):
        raise unavailable()
    item = db.get(PerformanceCompletion, current.completion_id, populate_existing=True)
    if (
        item is None
        or item.platform != "meta_ads"
        or item.query_version != f"meta.{API_VERSION}.campaign-day.v1"
        or item.reporting_basis != "provider_defaults_unspecified"
        or item.semantics
        != ("explicit_platform_event" if source.conversion_action_type else "traffic_spend_only")
        or item.source_connection_ref != str(source.id)
        or item.generation != source.generation
        or item.selected_event != source.conversion_action_type
        or item.privacy_revision != workspace_export_revision(db, workspace_id)
        or item.currency != account.currency_code
        or item.time_zone != account.time_zone
        or (item.starts_on, item.ends_on) != (source.covered_from, source.covered_through)
        or source.last_sync_at is None
        or utc(item.completed_at) != utc(source.last_sync_at)
    ):
        raise unavailable()
    digest, rows = manifest(db, account, item.starts_on, item.ends_on)
    if digest != item.manifest_digest or len(rows) != item.row_count:
        raise unavailable()
    selected = [r for r in rows if r.campaign_id == campaign_id]
    # Empty sparse campaign reports are not upgraded to observed zero.
    spend = sum(r.cost_micros for r in selected)
    conversions = (
        sum((r.conversions for r in selected), Decimal(0))
        if item.selected_event and selected
        else None
    )
    value = (
        sum(r.conversion_value_micros for r in selected)
        if item.selected_event in PURCHASE_ACTIONS and selected
        else None
    )
    authorize(db, workspace_id, actor)
    return CampaignPerformanceV1.model_validate(
        {
            "schema_version": "inlet.owned-campaign-performance.v1",
            "completion_id": item.id,
            "manifest_digest": item.manifest_digest,
            "account_id": account_id,
            "campaign_id": campaign_id,
            "generation": item.generation,
            "privacy_revision": item.privacy_revision,
            "starts_on": item.starts_on.isoformat(),
            "ends_on": item.ends_on.isoformat(),
            "currency": item.currency,
            "time_zone": item.time_zone,
            "completed_at": utc(item.completed_at).isoformat(),
            "semantics": item.semantics,
            "selected_event": item.selected_event,
            "reporting_basis": item.reporting_basis,
            "reported_day_count": len(selected),
            "campaign_rows_available": bool(selected),
            "impressions": sum(r.impressions for r in selected) if selected else None,
            "clicks": sum(r.clicks for r in selected) if selected else None,
            "spend_micros": spend if selected else None,
            "conversions": str(conversions) if conversions is not None else None,
            "conversion_value_micros": value,
            "cpa_micros": str(Decimal(spend) / conversions)
            if conversions is not None and conversions > 0
            else None,
            "reported_roas": str(Decimal(value) / spend)
            if value is not None and spend > 0
            else None,
            "maturity": "unqualified",
            "causal_attribution": "unavailable",
            "spending_authorized": False,
        }
    )
