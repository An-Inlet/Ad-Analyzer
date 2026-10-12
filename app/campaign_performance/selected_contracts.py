"""Untrusted additive selected-event DTOs; never ownership or publication authority.

Legacy aggregate rows retain their meaning. A selected capture depends on an exact
aggregate completion, not an independently movable current pointer. Persistence
must establish these bindings under current authorization before using this data.
"""

import hashlib
import re
from datetime import UTC, date, datetime
from typing import Annotated, Any, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import (
    AwareDatetime,
    Field,
    SerializerFunctionWrapHandler,
    field_validator,
    model_serializer,
    model_validator,
)

from app.campaign_performance.capture_settings import CaptureSettingsV1
from app.campaign_performance.presence_contracts import (
    AttributionBasisV1,
    CountCellV1,
    Descriptor,
    Digest,
    Frozen,
    Id,
    MoneyCellV1,
    NativeId,
    Positive,
    _canonical,
    _date,
)

MAX_SELECTED_FACTS = 50_000
MAX_SELECTED_BYTES = 32 * 1024 * 1024
MAX_SELECTED_FACT_BYTES = 4096
MAX_SELECTED_HEADER_BYTES = 8192
Revision = Annotated[int, Field(strict=True, ge=0, le=2**31 - 1)]


def _instant(value: Any) -> Any:
    if type(value) is not datetime and not (
        type(value) is str and re.match(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T", value)
    ):
        raise ValueError("aware ISO instant required")
    return value


def _utc(value: datetime) -> datetime:
    return value.astimezone(UTC)


class ReportingScopeV1(Frozen):
    workspace_id: Positive
    connection_id: Positive
    account_id: Positive
    platform: Literal["google_ads", "meta_ads", "tiktok_ads"]
    source_connection_ref: Annotated[str, Field(strict=True, min_length=1, max_length=32)]
    generation: Positive
    privacy_revision: Revision
    native_account_id: NativeId
    currency: Annotated[str, Field(strict=True, pattern=r"^[A-Z]{3}$")]
    time_zone: Annotated[str, Field(strict=True, min_length=1, max_length=64)]

    @model_validator(mode="after")
    def native_scope(self) -> "ReportingScopeV1":
        if (
            self.platform == "google_ads"
            and re.fullmatch(r"[0-9]{10}", self.native_account_id) is None
        ):
            raise ValueError("Google advertiser identity must have ten digits")
        if self.platform in {"google_ads", "tiktok_ads"}:
            if re.fullmatch(r"[a-f0-9]{32}", self.source_connection_ref) is None:
                raise ValueError("invalid provider source reference")
        elif (
            re.fullmatch(r"[1-9][0-9]{0,9}", self.source_connection_ref) is None
            or int(self.source_connection_ref) > 2**31 - 1
        ):
            raise ValueError("invalid social source reference")
        try:
            ZoneInfo(self.time_zone)
        except (ValueError, ZoneInfoNotFoundError):
            raise ValueError("invalid account time zone") from None
        return self


class CustomerEventSelectionV1(Frozen):
    schema_version: Literal["inlet.customer-event-selection.v1"] = (
        "inlet.customer-event-selection.v1"
    )
    selection_id: Id
    scope: ReportingScopeV1
    confirmed_by_customer_id: Id
    confirmed_at: AwareDatetime
    event_namespace: Literal["google_conversion_action", "meta_action_type", "tiktok_event"]
    native_event_owner_id: NativeId
    native_event_id: Annotated[str, Field(strict=True, min_length=1, max_length=128)]
    metric_family: Literal["conversions", "all_conversions", "actions", "event_count"]
    api_version: Annotated[
        str, Field(strict=True, pattern=r"^v[1-9][0-9]*(?:\.[0-9]+)?$", max_length=16)
    ]
    query_profile_digest: Digest

    _confirmed = field_validator("confirmed_at", mode="before")(_instant)
    _confirmed_utc = field_validator("confirmed_at")(_utc)

    @model_validator(mode="after")
    def event_identity(self) -> "CustomerEventSelectionV1":
        namespaces = {
            "google_ads": "google_conversion_action",
            "meta_ads": "meta_action_type",
            "tiktok_ads": "tiktok_event",
        }
        if self.event_namespace != namespaces[self.scope.platform]:
            raise ValueError("event namespace does not match platform")
        families = {
            "google_ads": {"conversions", "all_conversions"},
            "meta_ads": {"actions"},
            "tiktok_ads": {"event_count"},
        }
        if self.metric_family not in families[self.scope.platform]:
            raise ValueError("metric family does not match platform")
        if self.scope.platform == "google_ads":
            # Conversion owner may differ from advertiser. This grammar does not
            # establish that relationship or authorize a manager-owned selection.
            if (
                re.fullmatch(
                    r"customers/[0-9]{10}/conversionActions/[0-9]{1,32}", self.native_event_id
                )
                is None
            ):
                raise ValueError("exact Google action resource required")
            if self.native_event_id.split("/")[1] != self.native_event_owner_id:
                raise ValueError("conversion owner does not match action resource")
        elif re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", self.native_event_id) is None:
            raise ValueError("invalid native event identity")
        return self


def selection_digest(selection: CustomerEventSelectionV1) -> str:
    checked = CustomerEventSelectionV1.model_validate(selection)
    return hashlib.sha256(
        b"inlet.customer-event-selection.v1\x00" + _canonical(checked)
    ).hexdigest()


class AggregateDependencyV1(Frozen):
    """Exact immutable parent; currentness still requires a database reread."""

    completion_id: Id
    manifest_digest: Digest
    scope: ReportingScopeV1
    starts_on: date
    ends_on: date

    _dates = field_validator("starts_on", "ends_on", mode="before")(_date)

    @model_validator(mode="after")
    def interval(self) -> "AggregateDependencyV1":
        if not 0 <= (self.ends_on - self.starts_on).days < 400:
            raise ValueError("aggregate interval outside bounds")
        return self


class SelectedCaptureRequestV1(Frozen):
    schema_version: Literal[
        "inlet.selected-capture-request.v1", "inlet.selected-capture-request.v2"
    ] = "inlet.selected-capture-request.v1"
    capture_id: Id
    aggregate: AggregateDependencyV1
    selection: CustomerEventSelectionV1
    selection_digest: Digest
    requested_starts_on: date
    requested_ends_on: date
    started_at: AwareDatetime
    producer_contract: Descriptor
    query_profile_digest: Digest
    attribution: AttributionBasisV1
    settings: CaptureSettingsV1 | None = None

    @model_serializer(mode="wrap")
    def omit_legacy_settings(self, handler: SerializerFunctionWrapHandler) -> dict[str, Any]:
        result: dict[str, Any] = handler(self)
        if self.settings is None:
            result.pop("settings", None)
        return result

    _dates = field_validator("requested_starts_on", "requested_ends_on", mode="before")(_date)
    _started = field_validator("started_at", mode="before")(_instant)
    _started_utc = field_validator("started_at")(_utc)

    @model_validator(mode="after")
    def binding(self) -> "SelectedCaptureRequestV1":
        if (self.schema_version == "inlet.selected-capture-request.v2") != (
            self.settings is not None
        ):
            raise ValueError("capture request settings version mismatch")
        if self.settings is not None:
            choice = self.selection
            self.settings.assert_binding(
                platform=choice.scope.platform,
                api=choice.api_version,
                event=choice.native_event_id,
                family=choice.metric_family,
                owner=choice.native_event_owner_id,
                advertiser=choice.scope.native_account_id,
                producer=self.producer_contract,
                query_digest=self.query_profile_digest,
                attribution=self.attribution,
            )
        if self.aggregate.scope != self.selection.scope:
            raise ValueError("selection and aggregate scope mismatch")
        if self.selection_digest != selection_digest(self.selection):
            raise ValueError("selection digest mismatch")
        if self.query_profile_digest != self.selection.query_profile_digest:
            raise ValueError("query differs from confirmed metric selection")
        if not (
            self.aggregate.starts_on
            <= self.requested_starts_on
            <= self.requested_ends_on
            <= self.aggregate.ends_on
        ):
            raise ValueError("requested dates outside aggregate dependency")
        if (
            self.requested_ends_on
            >= self.started_at.astimezone(ZoneInfo(self.aggregate.scope.time_zone)).date()
        ):
            raise ValueError("requested reporting dates must be closed")
        if self.selection.confirmed_at > self.started_at:
            raise ValueError("selection must be confirmed before capture")
        if self.attribution.producer_contract != self.producer_contract:
            raise ValueError("attribution producer mismatch")
        if len(_canonical(self)) > MAX_SELECTED_HEADER_BYTES:
            raise ValueError("selected request byte capacity exceeded")
        return self


def capture_request_digest(request: SelectedCaptureRequestV1) -> str:
    checked = SelectedCaptureRequestV1.model_validate(request)
    return hashlib.sha256(
        b"inlet.selected-capture-request.v1\x00" + _canonical(checked)
    ).hexdigest()


class SelectedCampaignDayV1(Frozen):
    """Returned observations only; absent rows are never synthesized as zeros."""

    schema_version: Literal["inlet.selected-campaign-day.v1"] = "inlet.selected-campaign-day.v1"
    capture_id: Id
    request_digest: Digest
    campaign_id: Positive
    native_campaign_id: NativeId
    metric_date: date
    selected_conversions: CountCellV1
    selected_value_micros: MoneyCellV1

    _date_field = field_validator("metric_date", mode="before")(_date)

    @model_validator(mode="after")
    def bounded(self) -> "SelectedCampaignDayV1":
        if len(_canonical(self)) > MAX_SELECTED_FACT_BYTES:
            raise ValueError("selected fact byte capacity exceeded")
        return self


class SelectedCaptureV1(Frozen):
    schema_version: Literal["inlet.selected-capture.v1", "inlet.selected-capture.v2"] = (
        "inlet.selected-capture.v1"
    )
    request: SelectedCaptureRequestV1
    request_digest: Digest
    completed_at: AwareDatetime
    # Explicit unsupported preserves the confirmed choice without claiming that
    # the platform/query actually supplied it. A partial run cannot construct a
    # completed capture; it belongs exclusively to bounded private staging.
    capability: Literal["supported", "unsupported", "unknown"]
    pagination_complete: Literal[True]
    page_count: Annotated[int, Field(strict=True, ge=1, le=100)]
    facts: tuple[SelectedCampaignDayV1, ...] = Field(max_length=MAX_SELECTED_FACTS)
    spending_authorized: Literal[False] = False

    _completed = field_validator("completed_at", mode="before")(_instant)
    _completed_utc = field_validator("completed_at")(_utc)

    @field_validator("pagination_complete", "spending_authorized", mode="before")
    @classmethod
    def strict_boolean(cls, value: Any) -> Any:
        if type(value) is not bool:
            raise ValueError("strict boolean required")
        return value

    @model_validator(mode="after")
    def graph(self) -> "SelectedCaptureV1":
        if self.schema_version.rsplit(".", 1)[1] != self.request.schema_version.rsplit(".", 1)[1]:
            raise ValueError("capture and request versions differ")
        settings = self.request.settings
        if settings is not None and settings.report_support in {"unverified", "unsupported"}:
            expected = "unsupported" if settings.report_support == "unsupported" else "unknown"
            if self.capability != expected:
                raise ValueError(
                    "unverified report combination cannot supply supported observations"
                )
        if (
            settings is not None
            and settings.value_unit == "unknown"
            and any(fact.selected_value_micros.presence == "present" for fact in self.facts)
        ):
            raise ValueError("unknown value units cannot supply monetary observations")
        if (
            settings is not None
            and settings.profile == "meta.website-purchase-count.campaign-day.v1"
            and any(f.selected_value_micros.presence != "unsupported" for f in self.facts)
        ):
            raise ValueError("count-only profile cannot provide money")
        if self.request_digest != capture_request_digest(self.request):
            raise ValueError("capture request digest mismatch")
        if self.completed_at < self.request.started_at:
            raise ValueError("capture completion precedes start")
        local: dict[int, str] = {}
        native: dict[str, int] = {}
        keys: set[tuple[int, date]] = set()
        byte_size = len(_canonical(self.request))
        for fact in self.facts:
            if (fact.capture_id, fact.request_digest) != (
                self.request.capture_id,
                self.request_digest,
            ):
                raise ValueError("selected fact request mismatch")
            if (
                not self.request.requested_starts_on
                <= fact.metric_date
                <= (self.request.requested_ends_on)
            ):
                raise ValueError("selected fact outside requested dates")
            key = (fact.campaign_id, fact.metric_date)
            if key in keys:
                raise ValueError("duplicate selected campaign/day")
            keys.add(key)
            if (
                local.setdefault(fact.campaign_id, fact.native_campaign_id)
                != (fact.native_campaign_id)
                or native.setdefault(fact.native_campaign_id, fact.campaign_id) != fact.campaign_id
            ):
                raise ValueError("selected campaign mapping is not one-to-one")
            if self.capability != "supported" and any(
                cell.presence
                != ("unsupported" if self.capability == "unsupported" else "legacy_unknown")
                for cell in (fact.selected_conversions, fact.selected_value_micros)
            ):
                raise ValueError("unqualified selected capability cannot supply observations")
            byte_size += len(_canonical(fact)) + 1
            if byte_size > MAX_SELECTED_BYTES:
                raise ValueError("selected capture byte capacity exceeded")
        if len(_canonical(self)) > MAX_SELECTED_BYTES:
            raise ValueError("selected capture byte capacity exceeded")
        return self


def selected_capture_digest(capture: SelectedCaptureV1) -> str:
    """Whole graph commitment, including absent/unsupported states and request."""
    checked = SelectedCaptureV1.model_validate(capture)
    ordered = checked.model_copy(
        update={"facts": tuple(sorted(checked.facts, key=lambda f: (f.campaign_id, f.metric_date)))}
    )
    return hashlib.sha256(b"inlet.selected-capture.v1\x00" + _canonical(ordered)).hexdigest()


def validate_selected_dependencies(
    capture: SelectedCaptureV1,
    current_aggregate: AggregateDependencyV1,
    current_selection: CustomerEventSelectionV1,
) -> None:
    """Pure equality only. Callers MUST load both dependencies under current access.

    Reconnect, correction, erasure and selection changes invalidate the whole
    graph, even for a smaller requested slice. No stale fallback is permitted.
    """
    checked = SelectedCaptureV1.model_validate(capture)
    aggregate = AggregateDependencyV1.model_validate(current_aggregate)
    selection = CustomerEventSelectionV1.model_validate(current_selection)
    if checked.request.aggregate != aggregate or checked.request.selection != selection:
        raise ValueError("selected capture dependencies changed")
