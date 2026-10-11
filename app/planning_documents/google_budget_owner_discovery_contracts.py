"""Bounded review-only receipt projections; no source/session secrets."""

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from app.planning_documents.common import Amount, Currency, Digest, Frozen, NoAuthority, Positive
from app.planning_documents.context import ReportingWindow, TargetRef
from app.planning_documents.google_budget_owner_contracts import _originals


class GoogleBudgetOwnersRequestV1(Frozen):
    account_id: Positive
    catalog_composite_digest: Digest
    reporting_window: ReportingWindow

    @model_validator(mode="before")
    @classmethod
    def originals(cls, value: Any) -> Any:
        _originals(value)
        return value

    @model_validator(mode="after")
    def window(self) -> "GoogleBudgetOwnersRequestV1":
        if self.reporting_window.starts_at.astimezone(
            UTC
        ) >= self.reporting_window.ends_at_exclusive.astimezone(UTC):
            raise ValueError("ordered reporting instants required")
        return self


class GoogleBudgetOwnerOptionV1(NoAuthority):
    account_id: Positive
    owner_selection_id: Digest
    expected_observation_digest: Digest
    expected_owner_facts_digest: Digest
    representative: TargetRef
    affected_campaigns: tuple[TargetRef, ...] = Field(min_length=2, max_length=200)
    current_amount_micros: Amount
    currency: Currency
    cadence: Literal["daily"] = "daily"
    unit: Literal["micros"] = "micros"
    observation_started_at: datetime
    observed_at: datetime
    expires_at: datetime
    economic_qualification: Literal["not_assessed"] = "not_assessed"
    review_only: Literal[True] = True

    @model_validator(mode="before")
    @classmethod
    def originals(cls, value: Any) -> Any:
        _originals(value)
        raw = value.__dict__ if isinstance(value, BaseModel) else value
        if isinstance(raw, dict) and "review_only" in raw and raw["review_only"] is not True:
            raise ValueError("review only required")
        return value

    @model_validator(mode="after")
    def coherent(self) -> "GoogleBudgetOwnerOptionV1":
        times = (self.observation_started_at, self.observed_at, self.expires_at)
        if any(t.tzinfo is None or t.utcoffset() is None for t in times):
            raise ValueError("aware instants required")
        start, observed, expiry = (t.astimezone(UTC) for t in times)
        members = self.affected_campaigns
        if not start <= observed < expiry or self.review_only is not True:
            raise ValueError("bounded review interval required")
        if self.representative != members[0] or len(
            {t.canonical_entity_key for t in members}
        ) != len(members):
            raise ValueError("exact unique owner members required")
        if any(
            t.account != self.representative.account
            or t.account.account_id != self.account_id
            or t.account.platform != "google_ads"
            or t.kind != "campaign"
            or t.budget_owner_key != self.representative.budget_owner_key
            or t.catalog_evidence_key != self.representative.catalog_evidence_key
            for t in members
        ):
            raise ValueError("exact owned campaign group required")
        return self


class GoogleBudgetOwnersViewV1(NoAuthority):
    account_id: Positive
    status: Literal["available", "unavailable"]
    owners: tuple[GoogleBudgetOwnerOptionV1, ...] = Field(max_length=20)
    reason: Literal["google_budget_owner_unavailable"] | None = None
    recovery: Literal["Read fresh targets and review the full affected campaigns."] = (
        "Read fresh targets and review the full affected campaigns."
    )

    @model_validator(mode="after")
    def coherent(self) -> "GoogleBudgetOwnersViewV1":
        if (self.status == "available") != bool(self.owners) or (self.reason is None) != bool(
            self.owners
        ):
            raise ValueError("exact availability required")
        if any(o.account_id != self.account_id for o in self.owners):
            raise ValueError("owned options required")
        if len({o.owner_selection_id for o in self.owners}) != len(self.owners) or len(
            {o.representative.budget_owner_key for o in self.owners}
        ) != len(self.owners):
            raise ValueError("duplicate owner options")
        if len(self.model_dump_json().encode()) > 1_048_576:
            raise ValueError("owner response exceeds byte bound")
        return self
