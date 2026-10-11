"""Owned explicit aggregate acquisition; all publication effects share one SQL commit."""

from copy import deepcopy
from dataclasses import dataclass
from datetime import date
from typing import Any, Literal

from fastapi import HTTPException
from pydantic import Field, field_validator
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.ads.enums import AdvertisingPlatform, JobRunStatus, MetricEntityType
from app.ads.models import AdvertisingAccount, Campaign, DailyMetric
from app.ads.repository import AdvertisingMetricsRepository
from app.ads.schemas import CampaignCreate, DailyMetricCreate
from app.campaign_performance.aggregate import publish
from app.campaign_performance.models import CurrentPerformance, PerformanceCompletion
from app.campaign_performance.presence_contracts import Frozen, Id, Positive, _date
from app.campaign_performance.range_receipt_contracts import RangeReceiptV1
from app.campaign_performance.range_receipt_models import RangeReceiptRow
from app.campaign_performance.range_receipts import read_range_receipt, store_range_receipt
from app.campaign_performance.selected_contracts import ReportingScopeV1
from app.campaign_performance.selected_storage import current_scope
from app.google_connections.models import GoogleCustomerConnection
from app.google_connections.range_http import (
    GoogleAggregateRangeHTTP,
    GoogleAggregateRangeRequestV1,
)
from app.google_connections.selected_customer import SelectedCustomerService
from app.google_connections.selected_owned_context import OwnedGoogleReportingContext
from app.google_connections.selected_source_pin import SourcePin, source_pin
from app.imports.scope import AdvertisingImportScope, validate_advertising_scope
from app.lifecycle.privacy import workspace_export_revision


class RangeIntent(Frozen):
    account_id: Positive
    request_id: Id
    requested_starts_on: date
    requested_ends_on: date
    _dates = field_validator("requested_starts_on", "requested_ends_on", mode="before")(_date)


class RangeView(Frozen):
    request_id: Id
    account_id: Positive
    completion_id: Id
    requested_starts_on: date
    requested_ends_on: date
    row_count: int = Field(ge=0, le=50_000)
    state: Literal["completed"] = "completed"
    spending_authorized: Literal[False] = False


def unavailable() -> HTTPException:
    return HTTPException(409, "reporting_range_unavailable")


@dataclass(frozen=True, repr=False)
class Preparation:
    scope: ReportingScopeV1
    grant: SourcePin
    source_values: tuple[Any, ...]
    prior_completion: tuple[Any, ...] | None


def prepare(db: Session, service: SelectedCustomerService, aid: int) -> Preparation:
    service.guard(db, aid, read=True)
    pin = source_pin(db, service.wid, aid)
    source = db.get(GoogleCustomerConnection, pin.source_id, populate_existing=True)
    account = db.get(AdvertisingAccount, aid, populate_existing=True)
    if source is None or account is None or source.cursor or source.staged:
        raise unavailable()
    scope = ReportingScopeV1(
        workspace_id=service.wid,
        connection_id=account.connection_id,
        account_id=aid,
        platform="google_ads",
        source_connection_ref=source.id,
        generation=source.generation,
        privacy_revision=workspace_export_revision(db, service.wid),
        native_account_id=account.external_account_id,
        currency=account.currency_code,
        time_zone=account.time_zone,
    )
    current_scope(db, scope)
    current = db.get(CurrentPerformance, aid, populate_existing=True)
    previous = None
    if current is not None:
        completion = db.get(PerformanceCompletion, current.completion_id, populate_existing=True)
        if completion is None or (
            completion.workspace_id,
            completion.account_id,
            current.workspace_id,
        ) != (service.wid, aid, service.wid):
            raise unavailable()
        previous = tuple(
            deepcopy(getattr(completion, c.name)) for c in completion.__table__.columns
        )
    result = Preparation(
        scope,
        pin,
        tuple(deepcopy(getattr(source, c.name)) for c in source.__table__.columns),
        previous,
    )
    service.guard(db, aid, read=True)
    return result


def replay(
    db: Session, service: SelectedCustomerService, intent: RangeIntent
) -> RangeReceiptV1 | None:
    if db.get(RangeReceiptRow, intent.request_id, populate_existing=True) is None:
        return None
    receipt = read_range_receipt(db, service.wid, intent.account_id, intent.request_id)
    if (receipt.requested_starts_on, receipt.requested_ends_on) != (
        intent.requested_starts_on,
        intent.requested_ends_on,
    ):
        raise unavailable()
    service.guard(db, intent.account_id, read=True)
    return receipt


def view(receipt: RangeReceiptV1) -> RangeView:
    return RangeView(
        request_id=receipt.request_id,
        account_id=receipt.final_scope.account_id,
        completion_id=receipt.completion_id,
        requested_starts_on=receipt.requested_starts_on,
        requested_ends_on=receipt.requested_ends_on,
        row_count=receipt.row_count,
    )


def _receipt_id_collision(error: IntegrityError) -> bool:
    original = error.orig
    diagnostic = getattr(original, "diag", None)
    if getattr(original, "sqlstate", None) == "23505":
        return (
            getattr(diagnostic, "table_name", None) == "google_reporting_range_receipts"
            and getattr(diagnostic, "constraint_name", None)
            == "google_reporting_range_receipts_pkey"
        )
    return getattr(original, "sqlite_errorcode", None) in {1555, 2067} and str(original) == (
        "UNIQUE constraint failed: google_reporting_range_receipts.request_id"
    )


def acquire_range(service: SelectedCustomerService, intent: RangeIntent) -> RangeView:
    intent = RangeIntent.model_validate(intent)
    with service.open(intent.account_id) as db:
        prior = replay(db, service, intent)
        if prior is not None:
            return view(prior)
        if service.runtime is None:
            raise HTTPException(503, "reporting_range_runtime_unavailable")
        initial = prepare(db, service, intent.account_id)
    runtime = service.runtime
    assert service.sessions is not None
    resolver = OwnedGoogleReportingContext(
        service.sessions,
        service.original,
        service.provider,
        service.wid,
        intent.account_id,
        runtime.oauth,
        runtime.vault,
        runtime.clock,
        expected_grant=initial.grant.grant(),
    )
    base = resolver.catalog_request()
    if base.scope != initial.scope:
        raise unavailable()
    request = GoogleAggregateRangeRequestV1(
        base=base,
        requested_starts_on=intent.requested_starts_on,
        requested_ends_on=intent.requested_ends_on,
    )
    reader = GoogleAggregateRangeHTTP(
        resolver.catalog_context,
        resolver.revalidate_catalog,
        transport=runtime.transport(),
        clock=runtime.clock,
    )
    result = reader(request)
    if result.request != request:
        raise unavailable()
    with service.open(intent.account_id) as db:
        prior = replay(db, service, intent)
        if prior is not None:
            return view(prior)
        if prepare(db, service, intent.account_id) != initial or service.now() >= result.expires_at:
            raise unavailable()
        source = db.get(GoogleCustomerConnection, initial.grant.source_id, populate_existing=True)
        assert source is not None
        import_scope = AdvertisingImportScope(
            service.wid,
            initial.scope.connection_id,
            intent.account_id,
            AdvertisingPlatform.GOOGLE_ADS,
        )
        validate_advertising_scope(db, import_scope)
        repo = AdvertisingMetricsRepository(db)
        repo.scope = import_scope
        mapped = {
            row.native_campaign_id: repo.upsert_campaign(
                CampaignCreate(
                    account_id=intent.account_id,
                    platform=AdvertisingPlatform.GOOGLE_ADS,
                    external_campaign_id=row.native_campaign_id,
                    name=row.name,
                    status=row.status,
                    channel_type=row.channel,
                )
            )
            for row in result.campaigns
        }
        db.execute(
            delete(DailyMetric).where(
                DailyMetric.campaign_id.in_(
                    select(Campaign.id).where(Campaign.account_id == intent.account_id)
                ),
                DailyMetric.entity_type == MetricEntityType.CAMPAIGN,
                DailyMetric.metric_date >= intent.requested_starts_on,
                DailyMetric.metric_date <= intent.requested_ends_on,
            )
        )
        for row in result.metrics:
            campaign = mapped[row.native_campaign_id]
            repo.upsert_daily_metric(
                DailyMetricCreate(
                    platform=AdvertisingPlatform.GOOGLE_ADS,
                    metric_date=row.metric_date,
                    entity_type=MetricEntityType.CAMPAIGN,
                    entity_id=campaign.id,
                    campaign_id=campaign.id,
                    impressions=row.impressions,
                    clicks=row.clicks,
                    cost_micros=row.cost_micros,
                    conversions=row.conversions,
                    conversion_value_micros=row.conversion_value_micros,
                )
            )
        completed = service.now()
        job = repo.create_job_run(
            platform=AdvertisingPlatform.GOOGLE_ADS,
            job_name="google_customer_range_read",
            status=JobRunStatus.SUCCEEDED,
            account_id=intent.account_id,
            workspace_id=service.wid,
            connection_id=initial.scope.connection_id,
        )
        repo.finish_job_run(
            job, status=JobRunStatus.SUCCEEDED, records_processed=len(result.metrics)
        )
        publish(
            db,
            source,
            intent.requested_starts_on,
            intent.requested_ends_on,
            completed,
            reader,
            reader.performance_contract.commitment,
        )
        source.last_sync_at = completed
        db.flush()
        pointer = db.get(CurrentPerformance, intent.account_id, populate_existing=True)
        assert pointer is not None
        completion = db.get(PerformanceCompletion, pointer.completion_id, populate_existing=True)
        assert completion is not None
        final_scope = ReportingScopeV1.model_validate(
            initial.scope.model_copy(
                update={"privacy_revision": workspace_export_revision(db, service.wid)}
            )
        )
        receipt = RangeReceiptV1(
            request_id=intent.request_id,
            initiating_customer_id=service.original.user.id,
            requested_starts_on=intent.requested_starts_on,
            requested_ends_on=intent.requested_ends_on,
            original_scope=initial.scope,
            final_scope=final_scope,
            completion_id=completion.id,
            manifest_digest=completion.manifest_digest,
            query_version="google.v24.campaign-day.metrics-conversions.v1",
            completed_at=completed,
            row_count=completion.row_count,
            acquisition_digest=result.digest(),
            job_id=job.id,
        )
        try:
            store_range_receipt(db, receipt)
        except IntegrityError as error:
            # A globally colliding ID may belong to another workspace. Roll back
            # every publication effect, not only storage's nested savepoint.
            db.rollback()
            if _receipt_id_collision(error):
                raise unavailable() from None
            raise
        retained = read_range_receipt(db, service.wid, intent.account_id, intent.request_id)
        if retained != receipt or source_pin(db, service.wid, intent.account_id) != initial.grant:
            raise unavailable()
        db.flush()
        service.guard(db, intent.account_id, read=True)
        if not request.base.started_at <= service.now() < result.expires_at:
            raise unavailable()
        response = view(receipt)
        db.commit()
        return response
