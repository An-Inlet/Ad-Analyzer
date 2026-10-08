"""Versioned current owned reporting with explicit observed-field presence."""

import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Literal

from pydantic import Field, StrictInt, StrictStr, field_validator, model_validator
from sqlalchemy.orm import Session

from app.ads.models import Campaign
from app.campaign_performance.contracts import CampaignPerformanceV1, CampaignPerformanceV2
from app.campaign_performance.models import PerformanceCompletion
from app.campaign_performance.presence_contracts import (
    Frozen,
    NativeId,
    ReportedMetricPresenceV1,
    ReportingSemanticsV1,
    presence_digest,
)
from app.campaign_performance.presence_storage import read_presence
from app.campaign_performance.presence_summary import summarize_presence
from app.campaign_performance.service import Authorize, read_current, unavailable

MAX_DOCUMENT_BYTES = 2 * 1024 * 1024
MAX_COLLECTION_BYTES = 32 * 1024 * 1024
QUALIFIED_POLICY = "inlet.descriptive-review.v2"
QUALIFIED_GENERATOR = "inlet.descriptive-planning.v2"


class MetricSummaryV1(Frozen):
    value: StrictStr | StrictInt | None
    present_days: int = Field(strict=True, ge=0, le=400)
    missing_days: int = Field(strict=True, ge=0, le=400)
    unsupported_days: int = Field(strict=True, ge=0, le=400)
    legacy_unknown_days: int = Field(strict=True, ge=0, le=400)
    coverage: Literal["observed_requested_days", "partial", "unavailable"]


class CampaignSummaryV1(Frozen):
    requested_days: int = Field(strict=True, ge=1, le=400)
    returned_days: int = Field(strict=True, ge=0, le=400)
    missing_calendar_days: int = Field(strict=True, ge=0, le=400)
    impressions: MetricSummaryV1
    clicks: MetricSummaryV1
    spend_micros: MetricSummaryV1
    selected_conversions: MetricSummaryV1
    selected_value_micros: MetricSummaryV1
    selected_zero_for_requested_window: bool = Field(strict=True)


def campaign_summary(
    header: ReportingSemanticsV1,
    facts: tuple[ReportedMetricPresenceV1, ...],
    campaign_id: int,
    native_id: str,
) -> CampaignSummaryV1:
    # This derived subset commitment is ONLY for pure recomputation. It never
    # replaces or purports to validate the stored whole-completion commitment.
    subset = ReportingSemanticsV1.model_validate(
        header.model_copy(
            update={
                "fact_count": len(facts),
                "fact_digest": presence_digest(facts),
            }
        )
    )
    summary = summarize_presence(
        subset, facts, campaign_id=campaign_id, native_campaign_id=native_id
    )
    metrics: dict[str, Any] = {}
    for name in (
        "impressions",
        "clicks",
        "spend_micros",
        "selected_conversions",
        "selected_value_micros",
    ):
        metric = getattr(summary, name)
        value = metric.value
        if isinstance(value, Decimal):
            rendered = format(value, "f")
            value = rendered.rstrip("0").rstrip(".") if "." in rendered else rendered
        metrics[name] = MetricSummaryV1(
            value=value,
            present_days=metric.present_days,
            missing_days=metric.missing_days,
            unsupported_days=metric.unsupported_days,
            legacy_unknown_days=metric.legacy_unknown_days,
            coverage=metric.coverage,
        )
    return CampaignSummaryV1(
        requested_days=summary.requested_days,
        returned_days=summary.returned_days,
        missing_calendar_days=summary.missing_calendar_days,
        selected_zero_for_requested_window=summary.selected_zero_for_requested_window,
        **metrics,
    )


class CampaignPerformanceV3(Frozen):
    schema_version: Literal["inlet.owned-campaign-performance.v3"] = (
        "inlet.owned-campaign-performance.v3"
    )
    legacy: CampaignPerformanceV1 | CampaignPerformanceV2
    presence: ReportingSemanticsV1
    native_campaign_id: NativeId
    campaign_facts: tuple[ReportedMetricPresenceV1, ...] = Field(max_length=400)
    summary: CampaignSummaryV1
    causal_attribution: Literal["unavailable"] = "unavailable"
    spending_authorized: Literal[False] = False

    @field_validator("legacy", mode="before")
    @classmethod
    def reparse_legacy(cls, value: Any) -> Any:
        if isinstance(value, (CampaignPerformanceV1, CampaignPerformanceV2)):
            value = value.model_dump(mode="python")
        if isinstance(value, dict):
            for key in (
                "account_id",
                "campaign_id",
                "generation",
                "privacy_revision",
                "reported_day_count",
                "impressions",
                "clicks",
                "spend_micros",
                "conversion_value_micros",
            ):
                if value.get(key) is not None and type(value[key]) is not int:
                    raise ValueError("legacy numeric coercion forbidden")
            for key in (
                "schema_version",
                "completion_id",
                "manifest_digest",
                "currency",
                "time_zone",
                "semantics",
                "selected_event",
                "reporting_basis",
                "maturity",
                "causal_attribution",
                "platform",
                "conversion_basis",
            ):
                if value.get(key) is not None and type(value[key]) is not str:
                    raise ValueError("legacy text coercion forbidden")
            for key in ("starts_on", "ends_on"):
                if key in value and not (
                    type(value[key]) is date
                    or (
                        type(value[key]) is str
                        and re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value[key])
                    )
                ):
                    raise ValueError("legacy date coercion forbidden")
            instant = value.get("completed_at")
            if not (
                type(instant) is datetime
                or (type(instant) is str and re.match(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T", instant))
            ):
                raise ValueError("legacy instant coercion forbidden")
            for key in ("campaign_rows_available", "spending_authorized"):
                if key in value and type(value[key]) is not bool:
                    raise ValueError("legacy boolean coercion forbidden")
            for key in (
                "conversions",
                "cpa_micros",
                "reported_roas",
                "reported_generic_conversions",
            ):
                raw = value.get(key)
                if raw is not None:
                    try:
                        if type(raw) is not str or not Decimal(raw).is_finite() or Decimal(raw) < 0:
                            raise ValueError("invalid legacy reported decimal")
                    except InvalidOperation:
                        raise ValueError("invalid legacy reported decimal") from None
        return value

    @model_validator(mode="after")
    def consistent(self) -> "CampaignPerformanceV3":
        h, old = self.presence, self.legacy
        for left, right in (
            (h.completion_id, old.completion_id),
            (h.account_id, old.account_id),
            (h.legacy_manifest_digest, old.manifest_digest),
            (h.generation, old.generation),
            (h.privacy_revision, old.privacy_revision),
            (h.currency, old.currency),
            (h.time_zone, old.time_zone),
            (h.completed_at, old.completed_at),
            (h.requested_starts_on, old.starts_on),
            (h.requested_ends_on, old.ends_on),
        ):
            if left != right:
                raise ValueError("presence/legacy binding mismatch")
        platform = old.platform if isinstance(old, CampaignPerformanceV2) else "meta_ads"
        if (
            h.platform != platform
            or (
                h.selected_event.native_event_id
                if h.selected_event.provenance == "explicit_selected"
                else None
            )
            != old.selected_event
        ):
            raise ValueError("presence event/platform mismatch")
        if len(self.campaign_facts) > h.fact_count:
            raise ValueError("campaign subset exceeds full header count")
        for fact in self.campaign_facts:
            if (
                fact.completion_id,
                fact.workspace_id,
                fact.account_id,
                fact.campaign_id,
                fact.native_campaign_id,
            ) != (
                h.completion_id,
                h.workspace_id,
                h.account_id,
                old.campaign_id,
                self.native_campaign_id,
            ):
                raise ValueError("foreign campaign fact")
        if (
            len(self.campaign_facts) != old.reported_day_count
            or bool(self.campaign_facts) != old.campaign_rows_available
        ):
            raise ValueError("campaign row set differs from legacy report")
        if self.summary != campaign_summary(
            h, self.campaign_facts, old.campaign_id, self.native_campaign_id
        ):
            raise ValueError("summary is not derived from exact campaign facts")
        if len(self.model_dump_json().encode()) > MAX_DOCUMENT_BYTES:
            raise ValueError("presence report capacity exceeded")
        return self

    @property
    def completion_id(self) -> str:
        return self.legacy.completion_id

    @property
    def manifest_digest(self) -> str:
        return self.legacy.manifest_digest

    @property
    def account_id(self) -> int:
        return self.legacy.account_id

    @property
    def campaign_id(self) -> int:
        return self.legacy.campaign_id

    @property
    def generation(self) -> int:
        return self.legacy.generation

    @property
    def privacy_revision(self) -> int:
        return self.legacy.privacy_revision

    @property
    def starts_on(self) -> date:
        return self.legacy.starts_on

    @property
    def ends_on(self) -> date:
        return self.legacy.ends_on

    @property
    def currency(self) -> str:
        return self.legacy.currency

    @property
    def time_zone(self) -> str:
        return self.legacy.time_zone

    @property
    def completed_at(self) -> datetime:
        return self.legacy.completed_at

    @property
    def reported_day_count(self) -> int:
        return len(self.campaign_facts)

    @property
    def campaign_rows_available(self) -> bool:
        return bool(self.campaign_facts)

    @property
    def impressions(self) -> int | None:
        value = self.summary.impressions.value
        return value if isinstance(value, int) else None

    @property
    def clicks(self) -> int | None:
        value = self.summary.clicks.value
        return value if isinstance(value, int) else None

    @property
    def spend_micros(self) -> int | None:
        value = self.summary.spend_micros.value
        return value if isinstance(value, int) else None

    @property
    def conversions(self) -> str | None:
        value = self.summary.selected_conversions.value
        return str(value) if value is not None else None

    @property
    def conversion_value_micros(self) -> int | None:
        value = self.summary.selected_value_micros.value
        return value if isinstance(value, int) else None

    @property
    def cpa_micros(self) -> None:
        return None

    @property
    def reported_roas(self) -> None:
        return None


class PresenceReadContext:
    """Explicit read-operation cache; caller holds owned source locks, never global."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.transaction = db.get_transaction()
        self.completion_id: str | None = None
        self.campaigns: dict[int, tuple[ReportedMetricPresenceV1, ...]] = {}
        self.native_ids: dict[str, int] = {}
        self.graph: tuple[ReportingSemanticsV1, tuple[ReportedMetricPresenceV1, ...]] | None = None

    def read(
        self, item: PerformanceCompletion
    ) -> tuple[ReportingSemanticsV1, tuple[ReportedMetricPresenceV1, ...]] | None:
        transaction = self.db.get_transaction()
        if self.transaction is None:
            self.transaction = transaction
        if transaction is None or transaction is not self.transaction or not transaction.is_active:
            raise unavailable()
        if self.completion_id != item.id:
            self.graph = read_presence(self.db, item)
            grouped: dict[int, list[ReportedMetricPresenceV1]] = {}
            self.native_ids = {}
            if self.graph is not None:
                for fact in self.graph[1]:
                    grouped.setdefault(fact.campaign_id, []).append(fact)
                    self.native_ids[fact.native_campaign_id] = fact.campaign_id
            self.campaigns = {key: tuple(rows) for key, rows in grouped.items()}
            self.completion_id = item.id
        return self.graph


def read_current_with_presence(
    db: Session,
    workspace_id: int,
    actor: str,
    account_id: int,
    campaign_id: int,
    expected_completion_id: str | None,
    authorize: Authorize,
    *,
    context: PresenceReadContext | None = None,
) -> CampaignPerformanceV1 | CampaignPerformanceV2 | CampaignPerformanceV3:
    old = read_current(
        db, workspace_id, actor, account_id, campaign_id, expected_completion_id, authorize
    )
    try:
        item = db.get(PerformanceCompletion, old.completion_id, populate_existing=True)
        campaign = db.get(Campaign, campaign_id, populate_existing=True)
        if item is None or campaign is None or campaign.account_id != account_id:
            raise unavailable()
        context = context or PresenceReadContext(db)
        if context.db is not db:
            raise unavailable()
        graph = context.read(item)
        if graph is None:
            authorize(db, workspace_id, actor)
            return old
        header, _ = graph
        if header.workspace_id != workspace_id or header.account_id != account_id:
            raise unavailable()
        if context.native_ids.get(campaign.external_campaign_id, campaign_id) != campaign_id:
            raise unavailable()
        selected = context.campaigns.get(campaign_id, ())
        report = CampaignPerformanceV3(
            legacy=old,
            presence=header,
            native_campaign_id=campaign.external_campaign_id,
            campaign_facts=selected,
            summary=campaign_summary(header, selected, campaign_id, campaign.external_campaign_id),
        )
        authorize(db, workspace_id, actor)
        return report
    except (ValueError, TypeError, KeyError):
        raise unavailable() from None
