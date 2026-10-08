"""Caller-transaction finalized presence storage; no I/O, commit or authority grant."""

import hashlib
import json
from collections.abc import Sequence
from decimal import Decimal
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.ads.models import AdvertisingAccount, Campaign
from app.campaign_performance.models import CurrentPerformance, PerformanceCompletion
from app.campaign_performance.presence_contracts import (
    MAX_FACT_BYTES,
    MAX_FACTS,
    MAX_HEADER_BYTES,
    CountCellV1,
    IntegerCountCellV1,
    MoneyCellV1,
    ReportedMetricPresenceV1,
    ReportingSemanticsV1,
    validate_presence,
)
from app.campaign_performance.presence_models import MetricPresenceRow, ReportingSemanticsRow
from app.campaign_performance.service import manifest
from app.lifecycle.privacy import workspace_export_revision
from app.meta.security import utc
from app.workspaces.models import Workspace, WorkspaceIntegration

TABLES = frozenset({ReportingSemanticsRow.__tablename__, MetricPresenceRow.__tablename__})
HEADER_FIELDS = (
    "completion_id",
    "workspace_id",
    "account_id",
    "connection_id",
    "platform",
    "source_connection_ref",
    "generation",
    "privacy_revision",
    "requested_starts_on",
    "requested_ends_on",
    "legacy_manifest_digest",
    "fact_count",
    "fact_digest",
)
FACT_FIELDS = (
    "completion_id",
    "workspace_id",
    "account_id",
    "campaign_id",
    "metric_date",
    "native_campaign_id",
)


class ReportingPresenceUnavailable(ValueError):
    """Present-but-invalid provenance never silently becomes legacy/unavailable evidence."""


def canonical(document: ReportingSemanticsV1 | ReportedMetricPresenceV1) -> str:
    return json.dumps(
        document.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def payload_digest(raw: str, schema: str) -> str:
    return hashlib.sha256((schema + "\x00" + raw).encode()).hexdigest()


def _row(document: ReportingSemanticsV1 | ReportedMetricPresenceV1) -> dict[str, Any]:
    raw = canonical(document)
    fields = HEADER_FIELDS if isinstance(document, ReportingSemanticsV1) else FACT_FIELDS
    return {
        **{key: getattr(document, key) for key in fields},
        "canonical_json": raw,
        "payload_digest": payload_digest(raw, document.schema_version),
        "payload_bytes": len(raw.encode()),
    }


def _document(row: ReportingSemanticsRow | MetricPresenceRow) -> Any:
    model: type[ReportingSemanticsV1] | type[ReportedMetricPresenceV1]
    if isinstance(row, ReportingSemanticsRow):
        model, limit = ReportingSemanticsV1, MAX_HEADER_BYTES
    else:
        model, limit = ReportedMetricPresenceV1, MAX_FACT_BYTES
    if not 0 < len(row.canonical_json.encode()) <= limit:
        raise ReportingPresenceUnavailable("presence payload byte bound")
    value = model.model_validate_json(row.canonical_json)
    if any(getattr(row, key) != expected for key, expected in _row(value).items()):
        raise ReportingPresenceUnavailable("presence canonical/scalar binding mismatch")
    return value


def _completion_binding(header: ReportingSemanticsV1, item: PerformanceCompletion) -> None:
    pairs = (
        (header.completion_id, item.id),
        (header.workspace_id, item.workspace_id),
        (header.account_id, item.account_id),
        (header.platform, item.platform),
        (header.source_connection_ref, item.source_connection_ref),
        (header.generation, item.generation),
        (header.privacy_revision, item.privacy_revision),
        (header.requested_starts_on, item.starts_on),
        (header.requested_ends_on, item.ends_on),
        (header.legacy_manifest_digest, item.manifest_digest),
        (header.fact_count, item.row_count),
        (header.currency, item.currency),
        (header.time_zone, item.time_zone),
        (header.query_descriptor, item.query_version),
        (utc(header.completed_at), utc(item.completed_at)),
    )
    selected = header.selected_event
    if (
        any(a != b for a, b in pairs)
        or (
            selected.provenance == "explicit_selected"
            and selected.native_event_id != item.selected_event
        )
        or (selected.provenance != "explicit_selected" and item.selected_event is not None)
    ):
        raise ReportingPresenceUnavailable("presence completion binding mismatch")


def read_presence(
    db: Session,
    completion: PerformanceCompletion,
) -> tuple[ReportingSemanticsV1, tuple[ReportedMetricPresenceV1, ...]] | None:
    """Historical as-observed graph only; caller supplies current read/privacy authorization."""
    try:
        row = db.get(ReportingSemanticsRow, completion.id, populate_existing=True)
        facts = tuple(
            db.scalars(
                select(MetricPresenceRow)
                .where(MetricPresenceRow.completion_id == completion.id)
                .order_by(MetricPresenceRow.campaign_id, MetricPresenceRow.metric_date)
                .limit(MAX_FACTS + 1)
                .execution_options(populate_existing=True)
            )
        )
        if row is None:
            if facts:
                raise ReportingPresenceUnavailable("presence header missing")
            return None
        header = _document(row)
        assert isinstance(header, ReportingSemanticsV1)
        _completion_binding(header, completion)
        actual = db.get(PerformanceCompletion, completion.id, populate_existing=True)
        if actual is None:
            raise ReportingPresenceUnavailable("presence completion missing")
        _completion_binding(header, actual)
        if len(facts) > MAX_FACTS:
            raise ReportingPresenceUnavailable("presence fact capacity exceeded")
        documents = tuple(_document(fact) for fact in facts)
        validate_presence(header, documents)
        return header, documents
    except (ValueError, TypeError, KeyError, AssertionError) as error:
        if isinstance(error, ReportingPresenceUnavailable):
            raise
        raise ReportingPresenceUnavailable("presence graph integrity unavailable") from None


def store_presence(
    db: Session,
    header: ReportingSemanticsV1,
    facts: Sequence[ReportedMetricPresenceV1],
) -> None:
    """Validate before insertion; caller must roll back its transaction on failure."""
    try:
        header = ReportingSemanticsV1.model_validate(header)
        if len(facts) > MAX_FACTS:
            raise ReportingPresenceUnavailable("presence fact capacity exceeded")
        checked = tuple(ReportedMetricPresenceV1.model_validate(fact) for fact in facts)
        validate_presence(header, checked)
        item = db.get(PerformanceCompletion, header.completion_id, populate_existing=True)
        account = db.get(AdvertisingAccount, header.account_id, populate_existing=True)
        current = db.get(CurrentPerformance, header.account_id, populate_existing=True)
        if item is None or account is None or current is None:
            raise ReportingPresenceUnavailable("current reporting completion unavailable")
        _completion_binding(header, item)
        if (current.workspace_id, current.completion_id) != (
            header.workspace_id,
            header.completion_id,
        ) or (
            account.workspace_id,
            account.connection_id,
            account.platform.value,
            account.currency_code,
            account.time_zone,
        ) != (
            header.workspace_id,
            header.connection_id,
            header.platform,
            header.currency,
            header.time_zone,
        ):
            raise ReportingPresenceUnavailable("presence account/current scope changed")
        if workspace_export_revision(db, header.workspace_id) != header.privacy_revision:
            raise ReportingPresenceUnavailable("presence privacy revision changed")
        integration = db.get(WorkspaceIntegration, header.connection_id, populate_existing=True)
        workspace = db.get(Workspace, header.workspace_id, populate_existing=True)
        if (
            integration is None
            or workspace is None
            or (
                integration.workspace_id,
                integration.provider,
                integration.status,
                workspace.status,
            )
            != (header.workspace_id, header.platform, "active", "active")
        ):
            raise ReportingPresenceUnavailable("presence source ownership unavailable")
        digest, legacy = manifest(db, account, header.requested_starts_on, header.requested_ends_on)
        if digest != header.legacy_manifest_digest or len(legacy) != len(checked):
            raise ReportingPresenceUnavailable("legacy reporting manifest changed")
        mapped = {(row.campaign_id, row.metric_date): row for row in legacy}
        if len(mapped) != len(legacy):
            raise ReportingPresenceUnavailable("duplicate legacy campaign/day")
        campaigns = {
            row.id: row
            for row in db.scalars(
                select(Campaign)
                .where(
                    Campaign.account_id == header.account_id, Campaign.platform == header.platform
                )
                .limit(MAX_FACTS + 1)
                .execution_options(populate_existing=True)
            )
        }
        if len(campaigns) > MAX_FACTS:
            raise ReportingPresenceUnavailable("campaign mapping capacity exceeded")
        for fact in checked:
            row = mapped.pop((fact.campaign_id, fact.metric_date), None)
            campaign = campaigns.get(fact.campaign_id)
            if (
                row is None
                or campaign is None
                or campaign.external_campaign_id != fact.native_campaign_id
            ):
                raise ReportingPresenceUnavailable("presence native/local campaign mapping changed")
            values: tuple[tuple[CountCellV1 | IntegerCountCellV1 | MoneyCellV1, Any], ...] = (
                (fact.impressions, row.impressions),
                (fact.clicks, row.clicks),
                (fact.spend_micros, row.cost_micros),
                (fact.selected_conversions, Decimal(row.conversions)),
                (fact.selected_value_micros, row.conversion_value_micros),
            )
            if any(cell.presence == "present" and cell.value != value for cell, value in values):
                raise ReportingPresenceUnavailable("present cell differs from legacy numeric row")
        if mapped:
            raise ReportingPresenceUnavailable("legacy rows missing presence facts")
        existing = read_presence(db, item)
        if existing is not None:
            old_header, old_facts = existing
            if old_header != header or set(canonical(f) for f in old_facts) != set(
                canonical(f) for f in checked
            ):
                raise ReportingPresenceUnavailable("immutable presence graph differs")
            return
        # Header precedes dependent facts. No commit/rollback or caller-lock acquisition here.
        db.add(ReportingSemanticsRow(**_row(header)))
        db.flush()
        db.add_all(MetricPresenceRow(**_row(fact)) for fact in checked)
        db.flush()
    except (ValueError, TypeError, KeyError) as error:
        if isinstance(error, ReportingPresenceUnavailable):
            raise
        raise ReportingPresenceUnavailable("reporting presence cannot be finalized") from None


def erase_workspace_presence(db: Session, workspace_id: int) -> None:
    db.execute(delete(MetricPresenceRow).where(MetricPresenceRow.workspace_id == workspace_id))
    db.execute(
        delete(ReportingSemanticsRow).where(ReportingSemanticsRow.workspace_id == workspace_id)
    )
