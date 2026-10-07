"""As-of store totals, never mature action effects or recommendation authority."""

from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import AwareDatetime, Field, model_validator

from app.outcomes.contracts import Code, Digest, Frozen, Observation, Positive


class DescriptiveRequest(Frozen):
    goal_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    expected_goal_revision: Positive
    publication_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    prior_publication_id: str | None = Field(default=None, pattern=r"^[a-f0-9]{32}$")
    before_start: date
    before_end: date
    after_start: date
    after_end: date

    @model_validator(mode="after")
    def windows(self) -> "DescriptiveRequest":
        if not (
            0 < (self.before_end - self.before_start).days <= 400
            and 0 < (self.after_end - self.after_start).days <= 400
            and self.before_end <= self.after_start
            and (self.after_end - self.before_start).days <= 400
        ):
            raise ValueError("invalid bounded local windows")
        return self


class PublicationLineage(Frozen):
    publication_id: str
    manifest_digest: Digest
    source_revision: int
    publication_revision: Positive
    published_at: AwareDatetime
    watermark: AwareDatetime


class Stability(Frozen):
    status: Literal["not_requested", "unchanged_observed", "revised_observed", "unavailable"]
    prior: PublicationLineage | None = None
    examined_days: int = Field(ge=0, le=400)
    reasons: tuple[Code, ...] = ()


class DescriptiveComparison(Frozen):
    schema_version: Literal["inlet.descriptive-comparison.v1"] = "inlet.descriptive-comparison.v1"
    workspace_id: Positive
    goal_id: str
    goal_revision: Positive
    goal_digest: Digest
    current: PublicationLineage
    generation: Positive
    privacy_epoch: Positive
    evaluated_at: AwareDatetime
    status: Literal["available_as_of", "insufficient"]
    before: Observation
    after: Observation
    absolute_difference: Decimal | None
    relative_difference: Decimal | None
    reasons: tuple[Code, ...]
    warnings: tuple[Code, ...]
    stability: Stability
    maturity: Literal["unqualified"] = "unqualified"
    action_attribution: Literal["unavailable"] = "unavailable"
    causal_lift: None = None
    recommendation_update: None = None
    spending_authority: Literal["none"] = "none"
