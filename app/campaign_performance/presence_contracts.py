"""Additive reported-row presence facts; construction alone conveys no ownership proof."""

import hashlib
import json
import re
from collections.abc import Sequence
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
    field_validator,
    model_validator,
)

MAX_FACTS = 100_000
MAX_FACT_BYTES = 4096
MAX_FACT_SET_BYTES = 128 * 1024 * 1024
MAX_HEADER_BYTES = 8192
MAX_COUNT = Decimal("999999999999.999999")  # Existing Numeric(18, 6).
MAX_INTEGER_COUNT = 2**31 - 1  # Existing SQL Integer, not bigint.
MAX_MONEY_MICROS = 2**63 - 1
DIGEST_DOMAIN = b"inlet.metric-presence-set.v1\x00"

Id = Annotated[str, Field(strict=True, pattern=r"^[a-f0-9]{32}$")]
Digest = Annotated[str, Field(strict=True, pattern=r"^[a-f0-9]{64}$")]
Positive = Annotated[int, Field(strict=True, gt=0, le=2**31 - 1)]
Presence = Literal["present", "missing", "unsupported", "legacy_unknown"]
Descriptor = Annotated[str, Field(strict=True, min_length=1, max_length=200)]
NativeId = Annotated[str, Field(strict=True, pattern=r"^[0-9]{1,32}$")]


class Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, revalidate_instances="always")


def _present(presence: Presence, value: object) -> None:
    if (presence == "present") != (value is not None):
        raise ValueError("present cells require values; other presence states require null")


def _decimal_text(value: Decimal) -> str:
    if value == 0:
        return "0"
    rendered = format(value, "f")
    return rendered.rstrip("0").rstrip(".") if "." in rendered else rendered


class CountCellV1(Frozen):
    presence: Presence
    value: Decimal | None

    @field_validator("value", mode="before")
    @classmethod
    def exact_count(cls, value: Any) -> Decimal | None:
        if value is None:
            return None
        if type(value) not in (str, int, Decimal):
            raise ValueError("count must be exact Decimal, integer or plain decimal string")
        if isinstance(value, str) and (
            len(value) > 20 or re.fullmatch(r"(?:0|[1-9][0-9]*)(?:\.[0-9]{1,6})?", value) is None
        ):
            raise ValueError("invalid exact decimal count")
        result = Decimal(value)
        if not result.is_finite() or result < 0 or result > MAX_COUNT:
            raise ValueError("count outside Numeric(18,6)")
        exponent = result.as_tuple().exponent
        if not isinstance(exponent, int) or exponent < -6:
            raise ValueError("count exceeds six fractional places")
        return result

    @field_serializer("value", when_used="json")
    def decimal_json(self, value: Decimal | None) -> str | None:
        return None if value is None else _decimal_text(value)

    @model_validator(mode="after")
    def consistent(self) -> "CountCellV1":
        _present(self.presence, self.value)
        return self


class IntegerCountCellV1(Frozen):
    presence: Presence
    value: Annotated[int, Field(strict=True, ge=0, le=MAX_INTEGER_COUNT)] | None

    @model_validator(mode="after")
    def consistent(self) -> "IntegerCountCellV1":
        _present(self.presence, self.value)
        return self


class MoneyCellV1(Frozen):
    presence: Presence
    value: Annotated[int, Field(strict=True, ge=0, le=MAX_MONEY_MICROS)] | None

    @model_validator(mode="after")
    def consistent(self) -> "MoneyCellV1":
        _present(self.presence, self.value)
        return self


class SelectedEventV1(Frozen):
    provenance: Literal["explicit_selected", "generic", "unavailable"]
    native_event_id: Annotated[str, Field(strict=True, min_length=1, max_length=128)] | None
    label: Annotated[str, Field(strict=True, min_length=1, max_length=160)] | None

    @model_validator(mode="after")
    def identity(self) -> "SelectedEventV1":
        if self.provenance == "explicit_selected" and self.native_event_id is None:
            raise ValueError("explicit selection requires native event identity")
        if self.provenance == "unavailable" and (
            self.native_event_id is not None or self.label is not None
        ):
            raise ValueError("unavailable event has no identity or label")
        return self


class AttributionBasisV1(Frozen):
    click_window_days: Annotated[int, Field(strict=True, ge=0, le=400)] | None
    view_window_days: Annotated[int, Field(strict=True, ge=0, le=400)] | None
    report_time_basis: Literal["interaction", "conversion", "unknown"]
    provenance: Literal[
        "observed_response", "verified_request_contract", "provider_default_unknown"
    ]
    producer_contract: Descriptor

    @model_validator(mode="after")
    def unknown_defaults(self) -> "AttributionBasisV1":
        if self.provenance == "provider_default_unknown" and (
            self.click_window_days is not None
            or self.view_window_days is not None
            or self.report_time_basis != "unknown"
        ):
            raise ValueError("unknown provider defaults cannot claim attribution windows or time")
        return self


def _date(value: Any) -> date:
    if type(value) is date:
        return value
    if type(value) is str and re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
        return date.fromisoformat(value)
    raise ValueError("ISO date required, not timestamp or epoch")


def _canonical(value: Frozen) -> bytes:
    return json.dumps(
        value.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


class ReportedMetricPresenceV1(Frozen):
    schema_version: Literal["inlet.metric-presence.v1"] = "inlet.metric-presence.v1"
    completion_id: Id
    workspace_id: Positive
    account_id: Positive
    campaign_id: Positive
    native_campaign_id: NativeId
    metric_date: date
    impressions: IntegerCountCellV1
    clicks: IntegerCountCellV1
    spend_micros: MoneyCellV1
    selected_conversions: CountCellV1
    selected_value_micros: MoneyCellV1

    _metric_date = field_validator("metric_date", mode="before")(_date)

    @model_validator(mode="after")
    def size(self) -> "ReportedMetricPresenceV1":
        if len(_canonical(self)) > MAX_FACT_BYTES:
            raise ValueError("presence fact byte capacity exceeded")
        return self


class ReportingSemanticsV1(Frozen):
    schema_version: Literal["inlet.reporting-semantics.v1"] = "inlet.reporting-semantics.v1"
    workspace_id: Positive
    account_id: Positive
    connection_id: Positive
    platform: Literal["google_ads", "meta_ads", "tiktok_ads"]
    source_connection_ref: Annotated[str, Field(strict=True, min_length=1, max_length=32)]
    generation: Positive
    privacy_revision: Annotated[int, Field(strict=True, ge=0, le=2**31 - 1)]
    completion_id: Id
    legacy_manifest_digest: Digest
    producer_contract: Descriptor
    query_descriptor: Descriptor
    requested_starts_on: date
    requested_ends_on: date
    actual_starts_on: date
    actual_ends_on: date
    currency: Annotated[str, Field(strict=True, pattern=r"^[A-Z]{3}$")]
    time_zone: Annotated[str, Field(strict=True, min_length=1, max_length=64)]
    selected_event: SelectedEventV1
    attribution: AttributionBasisV1
    pagination_complete: Annotated[bool, Field(strict=True)]
    returned_rows_scope: Literal["returned_campaign_day_rows"] = "returned_campaign_day_rows"
    closed_requested_period: Annotated[bool, Field(strict=True)]
    completed_at: AwareDatetime
    fact_count: Annotated[int, Field(strict=True, ge=0, le=MAX_FACTS)]
    fact_digest: Digest

    _dates = field_validator(
        "requested_starts_on",
        "requested_ends_on",
        "actual_starts_on",
        "actual_ends_on",
        mode="before",
    )(_date)

    @field_validator("completed_at", mode="before")
    @classmethod
    def instant(cls, value: Any) -> Any:
        if not isinstance(value, datetime) and not (
            type(value) is str and re.match(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T", value)
        ):
            raise ValueError("aware ISO instant required")
        return value

    @model_validator(mode="after")
    def intervals(self) -> "ReportingSemanticsV1":
        if (
            not (
                self.requested_starts_on
                <= self.actual_starts_on
                <= self.actual_ends_on
                <= self.requested_ends_on
            )
            or (self.requested_ends_on - self.requested_starts_on).days >= 400
        ):
            raise ValueError("actual interval must lie in a requested interval of at most400 days")
        try:
            local = self.completed_at.astimezone(ZoneInfo(self.time_zone)).date()
        except (ValueError, ZoneInfoNotFoundError):
            raise ValueError("invalid reporting time zone") from None
        if self.closed_requested_period and self.requested_ends_on >= local:
            raise ValueError("closed requested interval must end before local completion date")
        if len(_canonical(self)) > MAX_HEADER_BYTES:
            raise ValueError("reporting header byte capacity exceeded")
        return self


def _facts(facts: Sequence[ReportedMetricPresenceV1]) -> list[ReportedMetricPresenceV1]:
    if len(facts) > MAX_FACTS:
        raise ValueError("presence fact count capacity exceeded")
    checked = [ReportedMetricPresenceV1.model_validate(fact) for fact in facts]
    keys: set[tuple[int, date]] = set()
    local: dict[int, str] = {}
    native: dict[str, int] = {}
    scope = None
    for fact in checked:
        current = (fact.completion_id, fact.workspace_id, fact.account_id)
        if scope is not None and scope != current:
            raise ValueError("mixed presence fact scope")
        scope = current
        key = (fact.campaign_id, fact.metric_date)
        if key in keys:
            raise ValueError("duplicate campaign/day presence fact")
        keys.add(key)
        if local.setdefault(fact.campaign_id, fact.native_campaign_id) != fact.native_campaign_id:
            raise ValueError("local campaign has inconsistent native identity")
        if native.setdefault(fact.native_campaign_id, fact.campaign_id) != fact.campaign_id:
            raise ValueError("native campaign maps to multiple local campaigns")
    return sorted(checked, key=lambda fact: (fact.campaign_id, fact.metric_date))


def _digest(facts: Sequence[ReportedMetricPresenceV1]) -> str:
    digest = hashlib.sha256(DIGEST_DOMAIN)
    digest.update(b"[")
    size = 2
    for index, fact in enumerate(facts):
        body = _canonical(fact)
        size += len(body) + bool(index)
        if size > MAX_FACT_SET_BYTES:
            raise ValueError("presence fact set byte capacity exceeded")
        if index:
            digest.update(b",")
        digest.update(body)
    digest.update(b"]")
    return digest.hexdigest()


def presence_digest(facts: Sequence[ReportedMetricPresenceV1]) -> str:
    """New domain over canonical sorted facts; never a legacy numeric manifest."""
    return _digest(_facts(facts))


def validate_presence(
    header: ReportingSemanticsV1, facts: Sequence[ReportedMetricPresenceV1]
) -> None:
    """Revalidate unsafe copies and exact set binding; publisher must still prove ownership."""
    header = ReportingSemanticsV1.model_validate(header)
    checked = _facts(facts)
    if header.fact_count != len(checked) or header.fact_digest != _digest(checked):
        raise ValueError("presence fact count or digest mismatch")
    for fact in checked:
        if (fact.completion_id, fact.workspace_id, fact.account_id) != (
            header.completion_id,
            header.workspace_id,
            header.account_id,
        ) or not header.actual_starts_on <= fact.metric_date <= header.actual_ends_on:
            raise ValueError("presence fact outside exact header scope or actual dates")
        if header.selected_event.provenance != "explicit_selected" and (
            fact.selected_conversions.presence == "present"
            or fact.selected_value_micros.presence == "present"
        ):
            raise ValueError("generic or unavailable events cannot qualify selected metrics")
