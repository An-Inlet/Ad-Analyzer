"""Original-window presence capture. Callers own locks, rollback and commit."""

import hashlib
import json
from datetime import date, datetime
from typing import Annotated, Any, Literal
from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import AwareDatetime, Field, field_validator, model_validator
from sqlalchemy import delete, inspect, select
from sqlalchemy.orm import Session

from app.ads.models import AdvertisingAccount, Campaign
from app.campaign_performance.models import PerformanceCompletion
from app.campaign_performance.presence_contracts import (
    AttributionBasisV1,
    Frozen,
    Id,
    NativeId,
    Positive,
    ReportedMetricPresenceV1,
    ReportingSemanticsV1,
    SelectedEventV1,
    presence_digest,
)
from app.campaign_performance.presence_storage import store_presence
from app.lifecycle.privacy import workspace_export_revision
from app.meta.models import MetaConnection, MetaStagedMetric
from app.meta.presence import (
    PRESENCE_PRODUCER_CONTRACT,
    QUERY_DESCRIPTOR,
    UNKNOWN_ATTRIBUTION,
    MetaPresenceCellsV1,
    parse_meta_presence,
)
from app.meta.presence_models import MetaPresenceStageContext
from app.meta.security import MetaError, utc


class MetaPresenceWindowV1(Frozen):
    schema_version: Literal["inlet.meta-presence-window.v1"] = "inlet.meta-presence-window.v1"
    window_token: Id
    nativeconnection_id: Positive
    workspace_id: Positive
    account_id: Positive
    integration_id: Positive
    native_advertiser_id: NativeId
    generation: Positive
    privacy_revision: Annotated[int, Field(strict=True, ge=0, le=2**31 - 1)]
    starts_on: date
    ends_on: date
    currency: Annotated[str, Field(strict=True, pattern=r"^[A-Z]{3}$")]
    time_zone: Annotated[str, Field(strict=True, min_length=1, max_length=64)]
    selected_event: SelectedEventV1
    attribution: AttributionBasisV1
    producer_contract: Literal["meta.campaign-day.presence.v1"]
    query_descriptor: str
    captured_at: AwareDatetime

    @field_validator("starts_on", "ends_on", mode="before")
    @classmethod
    def day(cls, value: Any) -> date:
        return MetaPresenceCellsV1.exact_day(value)

    @field_validator("captured_at", mode="before")
    @classmethod
    def instant(cls, value: Any) -> Any:
        return ReportingSemanticsV1.instant(value)

    @model_validator(mode="after")
    def valid(self) -> "MetaPresenceWindowV1":
        try:
            ZoneInfo(self.time_zone)
        except (ValueError, ZoneInfoNotFoundError):
            raise ValueError("invalid time zone") from None
        if (
            not 0 <= (self.ends_on - self.starts_on).days < 400
            or self.query_descriptor != QUERY_DESCRIPTOR
            or self.attribution != UNKNOWN_ATTRIBUTION
        ):
            raise ValueError("invalid original reporting profile")
        if len(canonical(self).encode()) > 8192:
            raise ValueError("window context capacity exceeded")
        return self


class PreparedMetaPresence(Frozen):
    context: MetaPresenceWindowV1
    facts: Annotated[tuple[tuple[Positive, MetaPresenceCellsV1], ...], Field(max_length=100_000)]


def canonical(value: Frozen) -> str:
    return json.dumps(
        value.model_dump(mode="json"), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )


def _values(context: MetaPresenceWindowV1) -> dict[str, Any]:
    raw = canonical(context)
    names = (
        "window_token",
        "workspace_id",
        "account_id",
        "integration_id",
        "native_advertiser_id",
        "generation",
        "privacy_revision",
        "starts_on",
        "ends_on",
        "captured_at",
    )
    return {
        **{name: getattr(context, name) for name in names},
        "connection_id": context.nativeconnection_id,
        "canonical_json": raw,
        "payload_bytes": len(raw.encode()),
        "payload_digest": hashlib.sha256(
            b"inlet.meta-presence-window.v1\0" + raw.encode()
        ).hexdigest(),
    }


def _context(
    db: Session, source: MetaConnection, account: AdvertisingAccount
) -> MetaPresenceWindowV1 | None:
    row = db.get(MetaPresenceStageContext, source.id, populate_existing=True)
    if row is None:
        return None
    try:
        if len(row.canonical_json.encode()) > 8192:
            raise ValueError("context too large")
        context = MetaPresenceWindowV1.model_validate_json(row.canonical_json)
        for name, value in _values(context).items():
            actual = getattr(row, name)
            if name == "captured_at":
                actual = utc(actual)
            if actual != value:
                raise ValueError("context scalar mismatch")
        event = source.conversion_action_type or None
        if (
            (
                context.nativeconnection_id,
                context.workspace_id,
                context.account_id,
                context.integration_id,
                context.native_advertiser_id,
                context.generation,
                context.privacy_revision,
                context.starts_on,
                context.ends_on,
                context.currency,
                context.time_zone,
                context.selected_event.native_event_id,
            )
            != (
                source.id,
                source.workspace_id,
                source.account_id,
                source.workspace_integration_id,
                source.external_account_id,
                source.generation,
                workspace_export_revision(db, source.workspace_id),
                source.window_start,
                source.window_end,
                account.currency_code,
                account.time_zone,
                event,
            )
            or account.id != source.account_id
            or account.workspace_id != source.workspace_id
            or account.connection_id != source.workspace_integration_id
            or account.external_account_id != source.external_account_id
            or account.platform.value != "meta_ads"
            or source.status != "connected"
        ):
            raise ValueError("original context changed")
        return context
    except (ValueError, TypeError):
        raise MetaError("meta_presence_context_changed") from None


def clear_presence_context(db: Session, native_connection_id: int) -> None:
    db.execute(
        delete(MetaPresenceStageContext).where(
            MetaPresenceStageContext.connection_id == native_connection_id
        )
    )


def clear_campaign_presence(db: Session, native_connection_id: int) -> None:
    db.execute(
        delete(MetaStagedMetric).where(MetaStagedMetric.connection_id == native_connection_id)
    )
    clear_presence_context(db, native_connection_id)


def erase_workspace_staging(db: Session, workspace_id: int) -> None:
    ids = select(MetaConnection.id).where(MetaConnection.workspace_id == workspace_id)
    db.execute(delete(MetaStagedMetric).where(MetaStagedMetric.connection_id.in_(ids)))
    db.execute(
        delete(MetaPresenceStageContext).where(
            MetaPresenceStageContext.workspace_id == workspace_id
        )
    )


def begin_presence(
    db: Session, source: MetaConnection, account: AdvertisingAccount, now: datetime
) -> None:
    clear_campaign_presence(db, source.id)
    context = MetaPresenceWindowV1.model_validate(
        dict(
            window_token=uuid4().hex,
            nativeconnection_id=source.id,
            workspace_id=source.workspace_id,
            account_id=account.id,
            integration_id=source.workspace_integration_id,
            native_advertiser_id=source.external_account_id,
            generation=source.generation,
            privacy_revision=workspace_export_revision(db, source.workspace_id),
            starts_on=source.window_start,
            ends_on=source.window_end,
            currency=account.currency_code,
            time_zone=account.time_zone,
            selected_event=SelectedEventV1(
                provenance="explicit_selected" if source.conversion_action_type else "unavailable",
                native_event_id=source.conversion_action_type or None,
                label=None,
            ),
            attribution=UNKNOWN_ATTRIBUTION,
            producer_contract=PRESENCE_PRODUCER_CONTRACT,
            query_descriptor=QUERY_DESCRIPTOR,
            captured_at=now,
        )
    )
    db.flush()  # Persist assigned native window before its insert binding guard.
    db.add(MetaPresenceStageContext(**_values(context)))
    db.flush()
    _context(db, source, account)


def _check_numeric(
    db: Session, context: MetaPresenceWindowV1, row: MetaStagedMetric, cells: MetaPresenceCellsV1
) -> None:
    campaign = db.get(Campaign, row.campaign_id)
    if (
        campaign is None
        or campaign.account_id != context.account_id
        or campaign.platform.value != "meta_ads"
        or campaign.external_campaign_id != cells.native_campaign_id
        or row.metric_date != cells.metric_date
        or cells.selected_event != context.selected_event
        or not context.starts_on <= row.metric_date <= context.ends_on
    ):
        raise MetaError("meta_presence_stage_changed")
    for field, cell in (
        ("impressions", cells.impressions),
        ("clicks", cells.clicks),
        ("cost_micros", cells.spend_micros),
        ("conversions", cells.selected_conversions),
        ("conversion_value_micros", cells.selected_value_micros),
    ):
        # Legacy missing/unsupported defaults must still match normalization; this
        # numeric comparison never changes the recorded presence state.
        expected = cell.value if cell.value is not None else 0
        if getattr(row, field) != expected:
            raise MetaError("meta_presence_stage_changed")


def stage_presence(
    db: Session,
    source: MetaConnection,
    account: AdvertisingAccount,
    staged_metric: MetaStagedMetric,
    raw_source: dict[str, Any],
) -> None:
    with db.no_autoflush:
        context = _context(db, source, account)
        if context is None:
            if (
                staged_metric.presence_context_token is not None
                or staged_metric.presence_json is not None
            ):
                raise MetaError("meta_presence_context_changed")
            return
        if (staged_metric.presence_context_token is None) != (staged_metric.presence_json is None):
            raise MetaError("meta_presence_stage_changed")
        if inspect(staged_metric).persistent and staged_metric.presence_json is None:
            raise MetaError("meta_presence_stage_changed")
        cells = parse_meta_presence(
            raw_source,
            expected_advertiser=context.native_advertiser_id,
            currency=context.currency,
            starts_on=context.starts_on,
            ends_on=context.ends_on,
            selected_event=context.selected_event.native_event_id,
        )
        raw = canonical(cells)
        if len(raw.encode()) > 4096:
            raise MetaError("meta_import_capacity_exceeded")
        if staged_metric.presence_json is not None and (
            staged_metric.presence_context_token != context.window_token
            or staged_metric.presence_json != raw
        ):
            raise MetaError("meta_presence_conflicting_duplicate")
        _check_numeric(db, context, staged_metric, cells)
        staged_metric.presence_context_token, staged_metric.presence_json = (
            context.window_token,
            raw,
        )


def capture_presence(
    db: Session, source: MetaConnection, account: AdvertisingAccount
) -> PreparedMetaPresence | None:
    context = _context(db, source, account)
    rows = list(
        db.scalars(
            select(MetaStagedMetric)
            .where(MetaStagedMetric.connection_id == source.id)
            .order_by(MetaStagedMetric.campaign_id, MetaStagedMetric.metric_date)
            .limit(100001)
        )
    )
    if len(rows) > 100000:
        raise MetaError("meta_import_capacity_exceeded")
    if context is None:
        if any(
            row.presence_context_token is not None or row.presence_json is not None for row in rows
        ):
            raise MetaError("meta_presence_context_changed")
        return None
    facts = []
    size = 0
    for row in rows:
        raw = row.presence_json
        if (
            raw is None
            or row.presence_context_token != context.window_token
            or len(raw.encode()) > 4096
        ):
            raise MetaError("meta_presence_stage_changed")
        cells = MetaPresenceCellsV1.model_validate_json(raw)
        if canonical(cells) != raw:
            raise MetaError("meta_presence_stage_changed")
        size += len(raw.encode())
        if size > 128 * 1024 * 1024:
            raise MetaError("meta_import_capacity_exceeded")
        _check_numeric(db, context, row, cells)
        facts.append((row.campaign_id, cells))
    return PreparedMetaPresence(context=context, facts=tuple(facts))


def publish_presence(
    db: Session, prepared: PreparedMetaPresence | None, completion: PerformanceCompletion
) -> None:
    if prepared is None:
        return
    prepared = PreparedMetaPresence.model_validate(prepared)
    context = prepared.context
    # The context must survive until attachment. Semantic erasure removes it;
    # terminal calibration invalidation only advances the export revision.
    retained = db.get(MetaPresenceStageContext, context.nativeconnection_id, populate_existing=True)
    if retained is None or any(
        (utc(getattr(retained, name)) if name == "captured_at" else getattr(retained, name))
        != value
        for name, value in _values(context).items()
    ):
        raise MetaError("meta_presence_context_changed")
    facts = tuple(
        ReportedMetricPresenceV1(
            completion_id=completion.id,
            workspace_id=context.workspace_id,
            account_id=context.account_id,
            campaign_id=campaign_id,
            **cells.model_dump(exclude={"selected_event"}),
        )
        for campaign_id, cells in prepared.facts
    )
    header = ReportingSemanticsV1(
        workspace_id=context.workspace_id,
        account_id=context.account_id,
        connection_id=context.integration_id,
        platform="meta_ads",
        source_connection_ref=str(context.nativeconnection_id),
        generation=context.generation,
        privacy_revision=completion.privacy_revision,
        completion_id=completion.id,
        legacy_manifest_digest=completion.manifest_digest,
        producer_contract=context.producer_contract,
        query_descriptor=context.query_descriptor,
        requested_starts_on=context.starts_on,
        requested_ends_on=context.ends_on,
        actual_starts_on=context.starts_on,
        actual_ends_on=context.ends_on,
        currency=context.currency,
        time_zone=context.time_zone,
        selected_event=context.selected_event,
        attribution=context.attribution,
        pagination_complete=True,
        closed_requested_period=context.ends_on
        < utc(completion.completed_at).astimezone(ZoneInfo(context.time_zone)).date(),
        completed_at=utc(completion.completed_at),
        fact_count=len(facts),
        fact_digest=presence_digest(facts),
    )
    store_presence(db, header, facts)
