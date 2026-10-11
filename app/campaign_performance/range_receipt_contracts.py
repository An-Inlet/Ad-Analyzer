"""Immutable audit receipt for one actual owned Google aggregate range publication."""

import hashlib
from datetime import date
from typing import Annotated, Literal
from zoneinfo import ZoneInfo

from pydantic import AwareDatetime, Field, field_validator, model_validator

from app.campaign_performance.presence_contracts import (
    Digest,
    Frozen,
    Id,
    Positive,
    _canonical,
    _date,
)
from app.campaign_performance.selected_contracts import ReportingScopeV1, _instant, _utc


class RangeReceiptV1(Frozen):
    schema_version: Literal["inlet.google-reporting-range-receipt.v1"] = (
        "inlet.google-reporting-range-receipt.v1"
    )
    request_id: Id
    initiating_customer_id: Id
    requested_starts_on: date
    requested_ends_on: date
    original_scope: ReportingScopeV1
    final_scope: ReportingScopeV1
    completion_id: Id
    manifest_digest: Digest
    query_version: Literal["google.v24.campaign-day.metrics-conversions.v1"]
    completed_at: AwareDatetime
    row_count: Annotated[int, Field(strict=True, ge=0, le=50_000)]
    acquisition_digest: Digest
    job_id: Positive

    _dates = field_validator("requested_starts_on", "requested_ends_on", mode="before")(_date)
    _time = field_validator("completed_at", mode="before")(_instant)
    _utc_time = field_validator("completed_at")(_utc)

    @model_validator(mode="after")
    def binding(self) -> "RangeReceiptV1":
        original, final = self.original_scope, self.final_scope
        if (
            original.platform != "google_ads"
            or final.platform != "google_ads"
            or original.model_dump(exclude={"privacy_revision"})
            != final.model_dump(exclude={"privacy_revision"})
            or final.privacy_revision < original.privacy_revision
        ):
            raise ValueError("range scope changed")
        if (
            not 0 <= (self.requested_ends_on - self.requested_starts_on).days < 400
            or self.requested_ends_on
            >= self.completed_at.astimezone(ZoneInfo(final.time_zone)).date()
        ):
            raise ValueError("closed range required")
        if len(_canonical(self)) > 16 * 1024:
            raise ValueError("range receipt bound exceeded")
        return self

    def digest(self) -> str:
        return hashlib.sha256(
            b"inlet.google-reporting-range-receipt.v1\0" + _canonical(self)
        ).hexdigest()
