"""Concrete Google/TikTok reported metrics; no event-specific or learning proof."""

import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import uuid4

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.ads.models import AdvertisingAccount, Campaign
from app.campaign_performance.contracts import CampaignPerformanceV2
from app.campaign_performance.models import CurrentPerformance, PerformanceCompletion
from app.campaign_performance.service import (
    Authorize,
    manifest,
    require_active_integration,
    unavailable,
)
from app.google_connections.models import GoogleCustomerConnection
from app.lifecycle.privacy import workspace_export_revision
from app.meta.security import utc
from app.sources.models import SourceConnection


@dataclass(frozen=True)
class ReportingDescriptor:
    platform: str
    query_version: str

    def __post_init__(self) -> None:
        google = self.platform == "google_ads" and re.fullmatch(
            r"google\.v[1-9][0-9]{1,2}\.campaign-day\.metrics-conversions\.v1", self.query_version
        )
        tiktok = (
            self.platform == "tiktok_ads"
            and self.query_version == "tiktok.v1.3.basic-campaign-day.generic-conversion.v1"
        )
        if not (google or tiktok):
            raise ValueError("unsupported campaign reporting descriptor")

    @property
    def commitment(self) -> str:
        return self.platform + ":" + self.query_version


def descriptor(transport: object) -> ReportingDescriptor | None:
    # Only concrete server adapters carry these verified query mappings. Duck-typed
    # properties/browser data do not qualify an arbitrary importer implementation.
    from app.google_connections.http import GoogleHTTPRead
    from app.tiktok.http import TikTokHTTPRead

    if type(transport) is GoogleHTTPRead:
        return transport.performance_contract
    if type(transport) is TikTokHTTPRead:
        return transport.performance_contract
    return None


def stage_contract(staged: dict[str, Any], transport: object) -> str | None:
    current = descriptor(transport)
    value = current.commitment if current else None
    if staged.get("pages"):
        prior = staged.get("performance_contract")
        if prior is None:
            # Legacy/unqualified pages may finish ordinary import, but the entire
            # completion remains unqualified. Never adopt a descriptor midstream.
            return None
        if prior != value:
            raise unavailable()
    return value


def publish(
    db: Session,
    source: GoogleCustomerConnection | SourceConnection,
    start: date,
    end: date,
    now: datetime,
    transport: object,
    staged_contract: str | None,
) -> None:
    declared = descriptor(transport)
    account = db.get(AdvertisingAccount, source.account_id)
    if account is None or account.workspace_id != source.workspace_id:
        raise unavailable()
    if declared is None or staged_contract is None:
        db.execute(
            delete(CurrentPerformance).where(
                CurrentPerformance.account_id == account.id,
                CurrentPerformance.workspace_id == source.workspace_id,
            )
        )
        return
    if (
        declared.commitment != staged_contract
        or declared.platform != account.platform.value
        or not account.time_zone
    ):
        raise unavailable()
    db.flush()
    digest, rows = manifest(db, account, start, end)
    item = PerformanceCompletion(
        id=uuid4().hex,
        workspace_id=source.workspace_id,
        account_id=account.id,
        platform=declared.platform,
        source_connection_ref=source.id,
        generation=source.generation,
        privacy_revision=workspace_export_revision(db, source.workspace_id),
        starts_on=start,
        ends_on=end,
        currency=account.currency_code,
        time_zone=account.time_zone,
        query_version=declared.query_version,
        semantics="provider_aggregate_unspecified",
        selected_event=None,
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


def read(
    db: Session,
    workspace_id: int,
    actor: str,
    account: AdvertisingAccount,
    campaign_id: int,
    expected: str | None,
    authorize: Authorize,
) -> CampaignPerformanceV2:
    platform = account.platform.value
    source: GoogleCustomerConnection | SourceConnection | None
    if platform == "google_ads":
        source = db.scalar(
            select(GoogleCustomerConnection)
            .where(
                GoogleCustomerConnection.account_id == account.id,
                GoogleCustomerConnection.workspace_id == workspace_id,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    elif platform == "tiktok_ads":
        source = db.scalar(
            select(SourceConnection)
            .where(
                SourceConnection.account_id == account.id,
                SourceConnection.workspace_id == workspace_id,
                SourceConnection.provider == "tiktok_ads",
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    else:
        raise unavailable()
    current = db.get(CurrentPerformance, account.id, populate_existing=True)
    campaign = db.get(Campaign, campaign_id, populate_existing=True)
    if (
        source is None
        or source.status != "connected"
        or source.error_code
        or source.integration_id != account.connection_id
        or account.workspace_id != workspace_id
        or current is None
        or current.workspace_id != workspace_id
        or campaign is None
        or campaign.account_id != account.id
        or (expected is not None and current.completion_id != expected)
    ):
        raise unavailable()
    require_active_integration(db, account)
    native = (
        source.external_account_id
        if isinstance(source, GoogleCustomerConnection)
        else source.external_id
    )
    item = db.get(PerformanceCompletion, current.completion_id, populate_existing=True)

    if (
        item is None
        or item.platform != platform
        or native != account.external_account_id
        or item.source_connection_ref != source.id
        or item.generation != source.generation
        or item.privacy_revision != workspace_export_revision(db, workspace_id)
        or item.currency != account.currency_code
        or item.time_zone != account.time_zone
        or item.selected_event is not None
        or item.semantics != "provider_aggregate_unspecified"
        or item.reporting_basis != "provider_defaults_unspecified"
        or source.last_sync_at is None
        or utc(source.last_sync_at) != utc(item.completed_at)
        or not 0 <= (item.ends_on - item.starts_on).days < 400
    ):
        raise unavailable()
    if isinstance(source, GoogleCustomerConnection):
        if (
            re.fullmatch(
                r"google\.v[1-9][0-9]{1,2}\.campaign-day\.metrics-conversions\.v1",
                item.query_version,
            )
            is None
        ):
            raise unavailable()
    elif item.query_version != "tiktok.v1.3.basic-campaign-day.generic-conversion.v1" or (
        item.starts_on,
        item.ends_on,
    ) != (source.covered_from, source.covered_through):
        raise unavailable()
    digest, rows = manifest(db, account, item.starts_on, item.ends_on)
    if digest != item.manifest_digest or len(rows) != item.row_count:
        raise unavailable()
    selected = [r for r in rows if r.campaign_id == campaign_id]
    spend = sum(r.cost_micros for r in selected)
    count = sum((r.conversions for r in selected), Decimal(0)) if selected else None
    google = platform == "google_ads"
    value = sum(r.conversion_value_micros for r in selected) if google and selected else None
    authorize(db, workspace_id, actor)
    return CampaignPerformanceV2(
        completion_id=item.id,
        manifest_digest=digest,
        account_id=account.id,
        campaign_id=campaign_id,
        generation=item.generation,
        privacy_revision=item.privacy_revision,
        starts_on=item.starts_on,
        ends_on=item.ends_on,
        currency=item.currency,
        time_zone=item.time_zone,
        completed_at=utc(item.completed_at),
        platform=platform,
        conversion_basis="google_metrics_conversions" if google else "tiktok_generic_conversion",
        reported_day_count=len(selected),
        campaign_rows_available=bool(selected),
        impressions=sum(r.impressions for r in selected) if selected else None,
        clicks=sum(r.clicks for r in selected) if selected else None,
        spend_micros=spend if selected else None,
        conversions=str(count) if google and count is not None else None,
        reported_generic_conversions=str(count) if not google and count is not None else None,
        conversion_value_micros=value,
        cpa_micros=str(Decimal(spend) / count)
        if google and count is not None and count > 0
        else None,
        reported_roas=str(Decimal(value) / spend) if value is not None and spend > 0 else None,
    )
