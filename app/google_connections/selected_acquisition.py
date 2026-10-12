"""Original-session selected acquisition and retained capture receipt, never ad writes."""

from datetime import date, timedelta
from typing import Literal

from fastapi import HTTPException
from pydantic import AwareDatetime, Field, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.ads.models import Campaign
from app.campaign_performance.capture_settings import google_capture_settings
from app.campaign_performance.models import CurrentPerformance, PerformanceCompletion
from app.campaign_performance.presence_contracts import (
    AttributionBasisV1,
    Frozen,
    Id,
    Positive,
    _date,
)
from app.campaign_performance.selected_contracts import (
    AggregateDependencyV1,
    SelectedCaptureRequestV1,
    SelectedCaptureV1,
    selection_digest,
)
from app.campaign_performance.selected_models import SelectedCaptureRow
from app.campaign_performance.selected_storage import (
    _aggregate,
    read_selected_capture,
    read_selection,
    store_selected_capture,
)
from app.google_connections.selected_collection import collect_google_selected_capture
from app.google_connections.selected_customer import InvalidationIntent, SelectedCustomerService
from app.google_connections.selected_http import GoogleSelectedHTTPRead
from app.google_connections.selected_owned_context import OwnedGoogleReportingContext
from app.google_connections.selected_presence import PRODUCER
from app.google_connections.selected_source_pin import source_pin


class CaptureIntent(InvalidationIntent):
    request_id: Id
    starts_on: date
    ends_on: date

    _dates = field_validator("starts_on", "ends_on", mode="before")(_date)


class CaptureView(Frozen):
    capture_id: Id
    account_id: Positive
    selection_id: Id
    selection_digest: str = Field(strict=True, pattern=r"^[a-f0-9]{64}$")
    starts_on: date
    ends_on: date
    completed_at: AwareDatetime
    returned_rows: int = Field(strict=True, ge=0, le=50_000)
    spending_authorized: Literal[False] = False


def unavailable() -> HTTPException:
    return HTTPException(409, "reporting_capture_unavailable")


def _receipt(capture: SelectedCaptureV1) -> CaptureView:
    request = capture.request
    return CaptureView(
        capture_id=request.capture_id,
        account_id=request.aggregate.scope.account_id,
        selection_id=request.selection.selection_id,
        selection_digest=request.selection_digest,
        starts_on=request.requested_starts_on,
        ends_on=request.requested_ends_on,
        completed_at=capture.completed_at,
        returned_rows=len(capture.facts),
    )


def _mapping(db: Session, aid: int) -> dict[str, int]:
    campaigns = list(
        db.scalars(
            select(Campaign)
            .where(Campaign.account_id == aid, Campaign.platform == "google_ads")
            .order_by(Campaign.id)
            .limit(50_001)
            .execution_options(populate_existing=True)
        )
    )
    if len(campaigns) > 50_000:
        raise unavailable()
    mapping = {row.external_campaign_id: row.id for row in campaigns}
    if len(mapping) != len(campaigns):
        raise unavailable()
    return mapping


def _existing(
    db: Session, service: SelectedCustomerService, intent: CaptureIntent
) -> SelectedCaptureV1 | None:
    row = db.get(SelectedCaptureRow, intent.request_id, populate_existing=True)
    if row is None:
        return None
    if (row.workspace_id, row.account_id) != (service.wid, intent.account_id):
        raise unavailable()
    capture = read_selected_capture(db, service.wid, intent.account_id, intent.request_id)
    request = capture.request
    if (
        request.selection.selection_id,
        request.selection_digest,
        request.requested_starts_on,
        request.requested_ends_on,
    ) != (
        intent.expected_selection_id,
        intent.expected_selection_digest,
        intent.starts_on,
        intent.ends_on,
    ):
        raise unavailable()
    return capture


def _capture_id_collision(error: IntegrityError) -> bool:
    """Only the capture header's two ID uniqueness constraints are recoverable."""
    original = error.orig
    diagnostic = getattr(original, "diag", None)
    if getattr(original, "sqlstate", None) == "23505":
        return getattr(diagnostic, "table_name", None) == "selected_reporting_captures" and getattr(
            diagnostic, "constraint_name", None
        ) in {"selected_reporting_captures_pkey", "uq_selected_capture_scope"}
    return getattr(original, "sqlite_errorcode", None) in {1555, 2067} and str(original) in {
        "UNIQUE constraint failed: selected_reporting_captures.id",
        "UNIQUE constraint failed: selected_reporting_captures.id, "
        "selected_reporting_captures.account_id, selected_reporting_captures.workspace_id",
    }


def acquire_selected(service: SelectedCustomerService, supplied: CaptureIntent) -> CaptureView:
    intent = CaptureIntent.model_validate(supplied)
    runtime = service.runtime
    if runtime is None:
        raise HTTPException(503, "reporting_selection_runtime_unavailable")
    with service.open(intent.account_id, read=True) as db:
        service.guard(db, intent.account_id, read=True)
        service.cas(db, intent)
        existing = _existing(db, service, intent)
        if existing is not None:
            result = _receipt(existing)
            service.guard(db, intent.account_id, read=True)
            return result
        choice = read_selection(db, service.wid, intent.account_id)
        pointer = db.get(CurrentPerformance, intent.account_id, populate_existing=True)
        completion = (
            db.get(PerformanceCompletion, pointer.completion_id, populate_existing=True)
            if pointer
            else None
        )
        if completion is None:
            raise unavailable()
        dependency = AggregateDependencyV1(
            completion_id=completion.id,
            manifest_digest=completion.manifest_digest,
            scope=choice.scope,
            starts_on=completion.starts_on,
            ends_on=completion.ends_on,
        )
        _aggregate(db, dependency)
        mapping = _mapping(db, intent.account_id)
        pin = source_pin(db, service.wid, intent.account_id)
        if pin.source_id != choice.scope.source_connection_ref:
            raise unavailable()
        attribution = AttributionBasisV1(
            click_window_days=None,
            view_window_days=None,
            report_time_basis="unknown",
            provenance="provider_default_unknown",
            producer_contract=PRODUCER,
        )
        request = SelectedCaptureRequestV1(
            schema_version="inlet.selected-capture-request.v2",
            settings=google_capture_settings(choice.metric_family, attribution),
            capture_id=intent.request_id,
            aggregate=dependency,
            selection=choice,
            selection_digest=selection_digest(choice),
            requested_starts_on=intent.starts_on,
            requested_ends_on=intent.ends_on,
            started_at=service.now(),
            producer_contract=PRODUCER,
            query_profile_digest=choice.query_profile_digest,
            attribution=attribution,
        )
        service.guard(db, intent.account_id, read=True)
    context = OwnedGoogleReportingContext(
        runtime.sessions,
        service.original,
        service.provider,
        service.wid,
        intent.account_id,
        runtime.oauth,
        runtime.vault,
        runtime.clock,
        expected_grant=pin.grant(),
        runtime_available=runtime.available,
    )
    read = GoogleSelectedHTTPRead(
        context.selected_context,
        context.revalidate_selected,
        transport=runtime.transport(),
        clock=runtime.clock,
    )
    capture = collect_google_selected_capture(
        request, mapping, read, context.revalidate_selected, runtime.clock
    )
    with service.open(intent.account_id, read=True) as db:
        service.guard(db, intent.account_id, read=True)
        service.cas(db, intent)
        if read_selection(db, service.wid, intent.account_id) != choice:
            raise unavailable()
        _aggregate(db, dependency)
        if source_pin(db, service.wid, intent.account_id) != pin:
            raise unavailable()
        if _mapping(db, intent.account_id) != mapping:
            raise unavailable()
        if not request.started_at <= service.now() < request.started_at + timedelta(seconds=60):
            raise unavailable()
        # Concurrent identical operation may have committed while SQL was closed.
        winner = _existing(db, service, intent)
        if winner is None:
            try:
                store_selected_capture(db, capture)
            except IntegrityError as error:
                # Storage has rolled back its savepoint; unrelated constraints must
                # still fail, and a foreign ID collision reveals no foreign receipt.
                if not _capture_id_collision(error):
                    raise
                service.guard(db, intent.account_id, read=True)
                winner = _existing(db, service, intent)
                if winner is None:
                    raise unavailable() from None
            else:
                winner = read_selected_capture(
                    db, service.wid, intent.account_id, intent.request_id
                )
        result = _receipt(winner)
        db.flush()
        service.guard(db, intent.account_id, read=True)
        if not request.started_at <= service.now() < request.started_at + timedelta(seconds=60):
            raise unavailable()
        service.require_runtime()
        db.commit()
        return result
