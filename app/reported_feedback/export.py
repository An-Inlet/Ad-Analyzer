"""Explicit versioned JSON bindings; authentication session correlations stay internal."""

import json
from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel

from app.reported_feedback.contracts import (
    OperationalReportedComparisonV1,
    ReportedAcquisitionRequestV1,
    ReportedFeedbackPreviewV1,
    ReportedWindowCapsuleV1,
)
from app.shopify.security import utc

TYPES = {
    "reported_feedback_jobs": ReportedAcquisitionRequestV1,
    "reported_window_capsules": ReportedWindowCapsuleV1,
    "reported_action_comparisons": OperationalReportedComparisonV1,
    "reported_feedback_slots": ReportedFeedbackPreviewV1,
}


def bind_reported_document(
    table: str,
    field: str,
    row: Mapping[str, Any],
    document: BaseModel,
) -> bool:
    if table not in TYPES:
        return False
    if field != "document" or type(document) is not TYPES[table]:
        raise ValueError("unknown reported feedback document")
    if len(json.dumps(document.model_dump(mode="json"), allow_nan=False).encode()) > 256 * 1024:
        raise ValueError("reported document exceeds bounded export")
    assert isinstance(
        document,
        (
            ReportedAcquisitionRequestV1,
            ReportedWindowCapsuleV1,
            OperationalReportedComparisonV1,
            ReportedFeedbackPreviewV1,
        ),
    )
    if (
        document.id != row["id"]
        or document.digest() != row["document_digest"]
        or document.expires_at != utc(row["expires_at"])
    ):
        raise ValueError("reported document binding mismatch")
    if isinstance(document, ReportedAcquisitionRequestV1):
        cohort, environment = document.anchor.cohort, document.anchor.environment
        exact = dict(
            original_attempt_id=document.anchor.original_attempt_id,
            source_connection_id=document.anchor.source_connection_id,
            source_generation=document.anchor.source_generation,
            policy_family=document.policy.family,
            policy_digest=document.policy.digest(),
            opportunity_digest=document.anchor.opportunity_digest(document.policy.family),
        )
        times = dict(created_at=document.created_at)
    elif isinstance(document, ReportedWindowCapsuleV1):
        cohort, environment = document.cohort, document.environment
        exact = dict(
            job_id=document.job_id,
            completion_id=document.completion_id,
            acquisition_run_id=document.acquisition_run_id,
            source_generation=document.source_generation,
            starts_on=document.window.starts_on,
            ends_on=document.window.ends_on,
        )
        times = dict(
            acquisition_started_at=document.acquisition_started_at,
            acquisition_completed_at=document.acquisition_completed_at,
            captured_at=document.captured_at,
        )
    elif isinstance(document, OperationalReportedComparisonV1):
        cohort, environment = document.anchor.cohort, document.anchor.environment
        if document.objective.cohort != cohort:
            raise ValueError("reported objective scope mismatch")
        exact = dict(
            job_id=document.job_id,
            original_attempt_id=document.anchor.original_attempt_id,
            receipt_id=document.anchor.latest_receipt_id,
            receipt_sequence=document.anchor.latest_receipt_sequence,
            policy_family=document.policy_family,
        )
        times = dict(assessed_at=document.assessed_at)
    else:
        cohort, environment = document.cohort, document.environment
        exact = dict(
            comparison_id=document.comparison_id,
            baseline_preview_id=document.baseline_preview_id,
            opportunity_digest=document.opportunity_digest,
            cohort_digest=cohort.digest(),
            policy_family=document.policy.family,
        )
        times = dict(created_at=document.created_at)
    if (cohort.workspace_id, cohort.account_id, cohort.campaign_id, environment) != (
        row["workspace_id"],
        row["account_id"],
        row["campaign_id"],
        row["environment"],
    ):
        raise ValueError("reported document ownership mismatch")
    if any(row[key] != value for key, value in exact.items()) or any(
        utc(row[key]) != value for key, value in times.items()
    ):
        raise ValueError("reported document scalar mismatch")
    return True


def numeric_dependency_stamp(db: "Session", workspace_id: int, *, validate: bool) -> str:
    """Snapshot commitment, or fresh local active-set validation under workspace fence.

    No identity/provider IO here. Expired/deleted original dependencies cannot keep
    an already-built numeric archive deliverable merely because its bytes exist.
    """
    import hashlib
    import time
    from datetime import UTC, datetime

    from fastapi import HTTPException
    from sqlalchemy import select

    from app.lifecycle.archive import MAX_ROWS
    from app.lifecycle.privacy import database_utc_now
    from app.reported_feedback.models import (
        ReportedActionComparison,
        ReportedFeedbackCurrent,
        ReportedFeedbackSlot,
    )
    from app.reported_feedback.service import (
        validate_comparison_dependencies,
        validate_preview_dependencies,
    )

    digest = hashlib.sha256(b"inlet.reported-export-numeric.v1\0")
    start = time.monotonic()
    count = 0
    for model in (ReportedActionComparison, ReportedFeedbackSlot):
        rows = db.scalars(
            select(model)
            .where(model.workspace_id == workspace_id)
            .order_by(model.id)
            .limit(MAX_ROWS + 1)
        ).yield_per(64)
        digest.update(model.__tablename__.encode())
        for row in rows:
            assert isinstance(row, (ReportedActionComparison, ReportedFeedbackSlot))
            count += 1
            if count > MAX_ROWS or time.monotonic() - start > 10:
                raise HTTPException(409, "reported feedback export validation bound exceeded")
            if validate:
                if isinstance(row, ReportedActionComparison):
                    validate_comparison_dependencies(
                        db, row, max(datetime.now(UTC), database_utc_now(db))
                    )
                else:
                    validate_preview_dependencies(
                        db, row, max(datetime.now(UTC), database_utc_now(db))
                    )
            digest.update(row.id.encode())
            digest.update(row.document_digest.encode())
    for pointer in db.scalars(
        select(ReportedFeedbackCurrent)
        .where(ReportedFeedbackCurrent.workspace_id == workspace_id)
        .order_by(ReportedFeedbackCurrent.id)
        .limit(MAX_ROWS + 1)
    ):
        count += 1
        if count > MAX_ROWS or time.monotonic() - start > 10:
            raise HTTPException(409, "reported feedback export validation bound exceeded")
        if validate:
            from app.reported_feedback.revisions import require_current_slot

            pointed_row = db.get(ReportedFeedbackSlot, pointer.slot_id, populate_existing=True)
            if pointed_row is None:
                raise HTTPException(409, "reported feedback export pointer unavailable")
            require_current_slot(db, pointed_row)
        digest.update(
            json.dumps(
                [pointer.id, pointer.slot_id, pointer.revision, pointer.opportunity_digest],
                separators=(",", ":"),
            ).encode()
        )
    return digest.hexdigest()


from sqlalchemy.orm import Session  # noqa: E402
