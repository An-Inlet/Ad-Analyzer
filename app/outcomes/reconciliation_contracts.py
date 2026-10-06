"""Retained incremental import observations; never a maturity qualification."""

from datetime import date
from typing import Literal

from pydantic import AwareDatetime, Field, model_validator

from app.outcomes.contracts import Digest, Frozen, Observation, Positive
from app.outcomes.descriptive_contracts import PublicationLineage


class ReconciliationRequest(Frozen):
    goal_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    expected_goal_revision: Positive
    latest_publication_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    start: date
    end: date

    @model_validator(mode="after")
    def bounded(self) -> "ReconciliationRequest":
        if not 0 < (self.end - self.start).days <= 400:
            raise ValueError("invalid bounded local window")
        return self


class TerminalObservation(Frozen):
    lineage: PublicationLineage
    completion_digest: Digest
    source_window_start: AwareDatetime
    observation: Observation
    assurance: Literal["terminal_updated_at_import"] = "terminal_updated_at_import"


class DayRevisionObservation(Frozen):
    day: date
    comparable_pairs: int = Field(ge=0, le=15)
    changed_pairs: int = Field(ge=0, le=15)
    coverage_state_changes: int = Field(ge=0, le=15)
    maximum_absolute_value_change_micros: int | None = Field(default=None, ge=0)
    last_change_observed_at: AwareDatetime | None = None
    last_change_discovery_lag_seconds: int | None = Field(default=None, ge=0)
    status: Literal["unchanged_observed", "revised_observed", "insufficient_observations"]


class ReconciliationObservations(Frozen):
    schema_version: Literal["inlet.owned-reconciliation-observations.v1"] = (
        "inlet.owned-reconciliation-observations.v1"
    )
    workspace_id: Positive
    store_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    goal_id: str
    goal_revision: Positive
    goal_digest: Digest
    generation: Positive
    privacy_epoch: Positive
    evaluated_at: AwareDatetime
    source_current: bool
    source_age_seconds: int = Field(ge=0)
    observations: tuple[TerminalObservation, ...] = Field(max_length=16)
    days: tuple[DayRevisionObservation, ...] = Field(max_length=400)
    truncated: bool
    unreadable_observations: int = Field(ge=0, le=16)
    duplicate_completions_ignored: int = Field(ge=0, le=16)
    independent_reconciliation: Literal["unqualified"] = "unqualified"
    maturity: Literal["unqualified"] = "unqualified"
    authoritative_finality: Literal["unavailable"] = "unavailable"
    action_attribution: Literal["unavailable"] = "unavailable"
    recommendation_update: None = None
    spending_authority: Literal["none"] = "none"
