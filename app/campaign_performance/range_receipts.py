"""Internal caller-transaction ports; caller establishes original-session authority."""

import json
from collections.abc import Mapping
from typing import Any

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.ads.enums import AdvertisingPlatform, JobRunStatus
from app.ads.models import JobRun
from app.campaign_performance.models import PerformanceCompletion
from app.campaign_performance.presence_contracts import _canonical
from app.campaign_performance.range_receipt_contracts import RangeReceiptV1 as RangeReceiptV1
from app.campaign_performance.range_receipt_models import RangeReceiptRow
from app.campaign_performance.selected_contracts import AggregateDependencyV1
from app.campaign_performance.selected_storage import (
    SelectedReportingUnavailable,
    _aggregate,
    lock_scope,
)
from app.shopify.security import utc


def values(receipt: RangeReceiptV1) -> dict[str, Any]:
    raw = _canonical(receipt)
    s = receipt.final_scope
    return dict(
        request_id=receipt.request_id,
        workspace_id=s.workspace_id,
        account_id=s.account_id,
        connection_id=s.connection_id,
        completion_id=receipt.completion_id,
        job_id=receipt.job_id,
        initiating_customer_id=receipt.initiating_customer_id,
        canonical_json=raw.decode(),
        payload_digest=receipt.digest(),
        payload_bytes=len(raw),
    )


def _dependencies(db: Session, receipt: RangeReceiptV1) -> None:
    s = receipt.final_scope
    c = db.get(PerformanceCompletion, receipt.completion_id, populate_existing=True)
    j = db.get(JobRun, receipt.job_id, populate_existing=True)
    if (
        c is None
        or c.selected_event is not None
        or c.semantics != "provider_aggregate_unspecified"
        or c.reporting_basis != "provider_defaults_unspecified"
        or (
            c.workspace_id,
            c.account_id,
            c.platform,
            c.source_connection_ref,
            c.generation,
            c.privacy_revision,
            c.currency,
            c.time_zone,
            c.starts_on,
            c.ends_on,
            c.manifest_digest,
            c.query_version,
            utc(c.completed_at),
            c.row_count,
        )
        != (
            s.workspace_id,
            s.account_id,
            s.platform,
            s.source_connection_ref,
            s.generation,
            s.privacy_revision,
            s.currency,
            s.time_zone,
            receipt.requested_starts_on,
            receipt.requested_ends_on,
            receipt.manifest_digest,
            receipt.query_version,
            receipt.completed_at,
            receipt.row_count,
        )
        or j is None
        or (
            j.workspace_id,
            j.account_id,
            j.connection_id,
            j.platform,
            j.status,
            j.job_name,
        )
        != (
            s.workspace_id,
            s.account_id,
            s.connection_id,
            AdvertisingPlatform.GOOGLE_ADS,
            JobRunStatus.SUCCEEDED,
            "google_customer_range_read",
        )
    ):
        raise SelectedReportingUnavailable("range receipt dependency unavailable")


def read_range_receipt(
    db: Session, workspace_id: int, account_id: int, request_id: str, require_current: bool = True
) -> RangeReceiptV1:
    row = db.get(RangeReceiptRow, request_id, populate_existing=True)
    if row is None or (row.workspace_id, row.account_id) != (workspace_id, account_id):
        raise SelectedReportingUnavailable("range receipt unavailable")
    try:
        receipt = RangeReceiptV1.model_validate_json(row.canonical_json)
        expected = values(receipt)
    except (ValueError, TypeError):
        raise SelectedReportingUnavailable("range receipt integrity unavailable") from None
    if expected != {key: getattr(row, key) for key in expected}:
        raise SelectedReportingUnavailable("range receipt integrity unavailable")
    _dependencies(db, receipt)
    if require_current:
        _aggregate(
            db,
            AggregateDependencyV1(
                completion_id=receipt.completion_id,
                manifest_digest=receipt.manifest_digest,
                scope=receipt.final_scope,
                starts_on=receipt.requested_starts_on,
                ends_on=receipt.requested_ends_on,
            ),
        )
    return receipt


def store_range_receipt(db: Session, receipt: RangeReceiptV1) -> None:
    value = RangeReceiptV1.model_validate(receipt)
    s = value.final_scope
    lock_scope(db, s.workspace_id, s.account_id)
    _dependencies(db, value)
    _aggregate(
        db,
        AggregateDependencyV1(
            completion_id=value.completion_id,
            manifest_digest=value.manifest_digest,
            scope=s,
            starts_on=value.requested_starts_on,
            ends_on=value.requested_ends_on,
        ),
    )
    existing = db.get(RangeReceiptRow, value.request_id, populate_existing=True)
    if existing is not None:
        prior = read_range_receipt(db, s.workspace_id, s.account_id, value.request_id)
        if prior != value:
            raise SelectedReportingUnavailable("range receipt replay differs")
        return
    with db.begin_nested():
        db.add(RangeReceiptRow(**values(value)))
        db.flush()
        read_range_receipt(db, s.workspace_id, s.account_id, value.request_id)


def erase_workspace_range_receipts(db: Session, workspace_id: int) -> None:
    """Caller owns workspace fence; no commit/semantic callback or new retention."""
    db.execute(delete(RangeReceiptRow).where(RangeReceiptRow.workspace_id == workspace_id))


def export_range_receipt(db: Session, supplied: Mapping[str, Any]) -> dict[str, Any]:
    from app.lifecycle.inventory import scalar

    receipt = read_range_receipt(
        db,
        supplied["workspace_id"],
        supplied["account_id"],
        supplied["request_id"],
        require_current=False,
    )
    expected = values(receipt)
    if set(supplied) != set(expected) or any(
        scalar(supplied[k]) != scalar(v) for k, v in expected.items()
    ):
        raise SelectedReportingUnavailable("range export row mismatch")
    return {
        **{k: scalar(v) for k, v in expected.items() if k != "canonical_json"},
        "document": json.loads(expected["canonical_json"]),
        "currentness": "historical_as_observed",
    }
