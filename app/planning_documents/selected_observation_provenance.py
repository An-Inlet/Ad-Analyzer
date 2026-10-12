"""Original capture metadata only; no currentness, equivalence or read authority."""

import re
from datetime import date
from typing import Annotated, Literal
from zoneinfo import ZoneInfo

from pydantic import AwareDatetime, Field, field_validator, model_validator

from app.campaign_performance.presence_contracts import (
    AttributionBasisV1,
    Descriptor,
    NativeId,
    _date,
)
from app.campaign_performance.selected_contracts import (
    AggregateDependencyV1,
    SelectedCaptureV1,
    _instant,
    _utc,
)
from app.planning_documents.common import Digest, Frozen


class SelectedObservationProvenanceV1(Frozen):
    schema_version: Literal["inlet.selected-observation-provenance.v1"] = (
        "inlet.selected-observation-provenance.v1"
    )
    event_namespace: Literal["google_conversion_action", "meta_action_type", "tiktok_event"]
    native_event_owner_id: NativeId
    native_event_id: Annotated[str, Field(strict=True, min_length=1, max_length=128)]
    metric_family: Literal["conversions", "all_conversions", "actions", "event_count"]
    api_version: Annotated[
        str, Field(strict=True, pattern=r"^v[1-9][0-9]*(?:\.[0-9]+)?$", max_length=16)
    ]
    query_profile_digest: Digest
    producer_contract: Descriptor
    attribution: AttributionBasisV1
    requested_starts_on: date
    requested_ends_on: date
    started_at: AwareDatetime
    completed_at: AwareDatetime
    capability: Literal["supported", "unsupported", "unknown"]

    _dates = field_validator("requested_starts_on", "requested_ends_on", mode="before")(_date)
    _instants = field_validator("started_at", "completed_at", mode="before")(_instant)
    _utc_instants = field_validator("started_at", "completed_at")(_utc)

    @model_validator(mode="after")
    def identity(self) -> "SelectedObservationProvenanceV1":
        families = {
            "google_conversion_action": {"conversions", "all_conversions"},
            "meta_action_type": {"actions"},
            "tiktok_event": {"event_count"},
        }
        if self.metric_family not in families[self.event_namespace]:
            raise ValueError("retained event family mismatch")
        if self.event_namespace == "google_conversion_action":
            if (
                re.fullmatch(
                    r"customers/[0-9]{10}/conversionActions/[0-9]{1,32}", self.native_event_id
                )
                is None
                or self.native_event_id.split("/")[1] != self.native_event_owner_id
            ):
                raise ValueError("retained Google event owner mismatch")
        elif re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", self.native_event_id) is None:
            raise ValueError("invalid retained native event")
        if (
            self.attribution.producer_contract != self.producer_contract
            or self.completed_at < self.started_at
            or not 0 <= (self.requested_ends_on - self.requested_starts_on).days < 400
        ):
            raise ValueError("retained attribution or acquisition mismatch")
        return self

    def assert_aggregate(self, aggregate: AggregateDependencyV1) -> None:
        value = type(self).model_validate(self)
        aggregate = AggregateDependencyV1.model_validate(aggregate)
        namespace = {
            "google_ads": "google_conversion_action",
            "meta_ads": "meta_action_type",
            "tiktok_ads": "tiktok_event",
        }[aggregate.scope.platform]
        if (
            value.event_namespace != namespace
            or not aggregate.starts_on
            <= value.requested_starts_on
            <= value.requested_ends_on
            <= aggregate.ends_on
            or value.requested_ends_on
            >= value.started_at.astimezone(ZoneInfo(aggregate.scope.time_zone)).date()
        ):
            raise ValueError("retained observation scope or closed interval mismatch")


def selected_observation_provenance(capture: SelectedCaptureV1) -> SelectedObservationProvenanceV1:
    """Project exact validated original request; never infer from totals or prose."""
    capture = SelectedCaptureV1.model_validate(capture)
    request, selection = capture.request, capture.request.selection
    value = SelectedObservationProvenanceV1(
        event_namespace=selection.event_namespace,
        native_event_owner_id=selection.native_event_owner_id,
        native_event_id=selection.native_event_id,
        metric_family=selection.metric_family,
        api_version=selection.api_version,
        query_profile_digest=request.query_profile_digest,
        producer_contract=request.producer_contract,
        attribution=request.attribution,
        requested_starts_on=request.requested_starts_on,
        requested_ends_on=request.requested_ends_on,
        started_at=request.started_at,
        completed_at=capture.completed_at,
        capability=capture.capability,
    )
    value.assert_aggregate(request.aggregate)
    return value
