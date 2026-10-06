"""Typed owned reporting evidence; no adapter for customer-supplied provider evidence."""

from datetime import date
from typing import Literal

from pydantic import AwareDatetime, Field, model_validator

from app.outcomes.contracts import Code, Digest, Frozen, Observation, Positive


class AssessmentRequest(Frozen):
    attempt_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    publication_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    before_start: date
    before_end: date
    after_start: date
    after_end: date
    policy_id: Literal["commerce_as_of_v1"] = "commerce_as_of_v1"

    @model_validator(mode="after")
    def windows(self) -> "AssessmentRequest":
        if not (
            0 < (self.before_end - self.before_start).days <= 400
            and 0 < (self.after_end - self.after_start).days <= 400
            and self.before_end <= self.after_start
        ):
            raise ValueError("invalid observation windows")
        return self


class OwnedReceiptLineage(Frozen):
    receipt_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    attempt_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    sequence: Positive
    receipt_digest: Digest
    projection_digest: Digest
    request_digest: Digest
    review_digest: Digest
    plan_digest: Digest
    fence: str = Field(pattern=r"^[a-f0-9]{32}$")
    goal_id: str = Field(min_length=1, max_length=128)
    goal_revision: Positive
    goal_digest: Digest | None
    mandate_id: str = Field(min_length=1, max_length=128)
    mandate_revision: Positive
    consent_id: str = Field(min_length=1, max_length=128)
    mandate_digest: Digest
    account_id: Positive
    connection_id: Positive
    connection_version: str = Field(min_length=1, max_length=100)
    platform: Literal["google_ads", "meta_ads", "tiktok_ads"]
    purpose: Literal["create_paused", "activate", "existing_campaign_optimize"]
    outcome: Literal[
        "verified_effect", "verified_target_state", "verified_no_effect", "unknown", "conflict"
    ]
    observed_at: AwareDatetime
    effective_time_evidence: Literal["unavailable", "authoritative_interval"]


class OwnedAssessment(Frozen):
    schema_version: Literal["inlet.owned-outcome-assessment.v2"] = (
        "inlet.owned-outcome-assessment.v2"
    )
    workspace_id: Positive
    environment: Literal["contract_test", "live"]
    receipt: OwnedReceiptLineage
    publication_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    publication_digest: Digest
    generation: Positive
    privacy_epoch: Positive
    policy_id: Literal["commerce_as_of_v1"]
    policy_digest: Digest
    input_digest: Digest
    before: Observation
    after: Observation
    evaluated_at: AwareDatetime
    # This installed producer has no approved maturity policy. No success back door.
    status: Literal["insufficient"] = "insufficient"
    reasons: tuple[Code, ...] = Field(min_length=1, max_length=40)
    warnings: tuple[Code, ...] = Field(max_length=40)
    absolute_difference: None = None
    relative_difference: None = None
    causal_lift: None = None
    spending_authority: Literal["none"] = "none"

    @model_validator(mode="after")
    def owned_observations(self) -> "OwnedAssessment":
        for observation in (self.before, self.after):
            if (
                observation.source.workspace_id != self.workspace_id
                or observation.source.provider != "shopify"
                or observation.source.generation != self.generation
                or observation.snapshot_id != self.publication_id
                or observation.snapshot_digest != self.publication_digest
                or observation.basis.maturity_policy is not None
                or observation.coverage.mature_through is not None
            ):
                raise ValueError("observation does not match owned publication")
        if (
            self.before.source != self.after.source
            or self.before.basis != self.after.basis
            or self.before.window.end > self.after.window.start
            or "maturity_policy_unavailable" not in self.reasons
        ):
            raise ValueError("inconsistent measurement basis")
        return self
