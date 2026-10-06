"""Required-parameter contracts; neither configuration nor score creates facts."""

from decimal import Decimal
from typing import Literal

from pydantic import AwareDatetime, Field, model_validator

from app.commerce.evidence import digest
from app.outcome_feedback.snapshot import FeedbackSnapshotV1
from app.outcomes.contracts import Code, Digest, Frozen, Positive

Direction = Literal["increase", "decrease", "none"]


class DirectionalAssociationPolicyV1(Frozen):
    schema_version: Literal["inlet.directional-association-policy.v1"] = (
        "inlet.directional-association-policy.v1"
    )
    policy_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    family: str = Field(pattern=r"^[a-f0-9]{32}$")
    revision: Positive
    environment: Literal["contract_test", "live"]
    feedback_policy_digest: Digest
    candidate_policy_digest: Digest
    feedback_family: Code
    scope_digest: Digest
    calibration_digest: Digest
    qualification_profile: str = Field(pattern=r"^[a-f0-9]{32}$")
    negative_cutoff: Decimal = Field(ge=-1, lt=0)
    positive_cutoff: Decimal = Field(gt=0, le=1)
    original_change: Literal["increase", "decrease"]
    below_direction: Direction
    above_direction: Direction
    minimum_contributions: int = Field(strict=True, ge=1, le=64)
    minimum_qualified_completions: int = Field(strict=True, ge=1, le=2048)
    maximum_assessment_age_seconds: int = Field(strict=True, ge=0, le=366 * 86400)
    maximum_facts_age_seconds: int = Field(strict=True, ge=0, le=366 * 86400)
    decision_lifetime_seconds: int = Field(strict=True, ge=1, le=300)
    interpretation: Literal["calibrated_association_heuristic_not_causal"] = (
        "calibrated_association_heuristic_not_causal"
    )

    @property
    def policy_digest(self) -> str:
        return digest(self.model_dump(mode="json"))


class DirectionalQualificationV1(Frozen):
    schema_version: Literal["inlet.directional-qualification.v1"] = (
        "inlet.directional-qualification.v1"
    )
    profile_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    revision: Positive
    environment: Literal["contract_test", "live"]
    policy_digest: Digest
    calibration_digest: Digest
    scope_digest: Digest
    producer_family: str = Field(pattern=r"^[a-f0-9]{32}$")
    evidence_mode: Literal["contract_scenario", "qualified_server_producer"]
    starts_at: AwareDatetime
    ends_at: AwareDatetime
    count_kind: Literal["distinct_independent_reconciliation_completions"] = (
        "distinct_independent_reconciliation_completions"
    )

    @model_validator(mode="after")
    def interval(self) -> "DirectionalQualificationV1":
        if self.starts_at >= self.ends_at:
            raise ValueError("qualification interval required")
        return self

    @property
    def qualification_digest(self) -> str:
        return digest(self.model_dump(mode="json"))


class QualifiedDirectionalFactsV1(Frozen):
    schema_version: Literal["inlet.qualified-directional-facts.v1"] = (
        "inlet.qualified-directional-facts.v1"
    )
    environment: Literal["contract_test", "live"]
    snapshot_digest: Digest
    producer_family: str = Field(pattern=r"^[a-f0-9]{32}$")
    evidence_mode: Literal["contract_scenario", "qualified_server_producer"]
    completion_digests: tuple[Digest, ...] = Field(min_length=1, max_length=2048)
    assurance: Literal["independent_full_window"]
    correction_state: Literal["settled_as_of", "unresolved"]
    delivery_time: Literal["authoritative_interval", "unavailable"]
    fresh_through: AwareDatetime
    valid_until: AwareDatetime
    count_kind: Literal["distinct_independent_reconciliation_completions"] = (
        "distinct_independent_reconciliation_completions"
    )

    @model_validator(mode="after")
    def unique_complete(self) -> "QualifiedDirectionalFactsV1":
        if len(set(self.completion_digests)) != len(self.completion_digests):
            raise ValueError("completion count requires distinct commitments")
        if self.fresh_through >= self.valid_until:
            raise ValueError("bounded source facts required")
        return self


class DecisionOpportunityV1(Frozen):
    schema_version: Literal["inlet.original-action-opportunity.v1"] = (
        "inlet.original-action-opportunity.v1"
    )
    workspace_id: Positive
    environment: Literal["contract_test", "live"]
    ledger_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    original_attempt_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    original_request_digest: Digest
    native_account_digest: Digest
    budget_owner_key: str = Field(min_length=1, max_length=256)

    @property
    def semantic_digest(self) -> str:
        return digest(self.model_dump(mode="json"))


class DirectionalInputsV1(Frozen):
    snapshot: FeedbackSnapshotV1
    opportunity: DecisionOpportunityV1
    original_changes: tuple[Literal["increase", "decrease", "unchanged", "unsupported"], ...] = (
        Field(max_length=64)
    )
    facts: QualifiedDirectionalFactsV1 | None


class DirectionalRecommendationV1(Frozen):
    schema_version: Literal["inlet.directional-recommendation.v1"] = (
        "inlet.directional-recommendation.v1"
    )
    status: Literal["blocked", "no_change", "recommended"]
    direction: Direction
    reasons: tuple[Code, ...]
    snapshot_digest: Digest
    policy_digest: Digest | None
    qualification_digest: Digest | None
    facts_digest: Digest | None
    opportunity: DecisionOpportunityV1
    qualified_completion_count: int | None = Field(default=None, strict=True, ge=1, le=2048)
    evaluated_at: AwareDatetime
    expires_at: AwareDatetime | None
    interpretation: Literal["calibrated_association_heuristic_not_causal"] = (
        "calibrated_association_heuristic_not_causal"
    )
    spending_authority: Literal["none"] = "none"

    @model_validator(mode="after")
    def honest(self) -> "DirectionalRecommendationV1":
        if self.status == "blocked":
            if self.direction != "none" or not self.reasons or self.expires_at is not None:
                raise ValueError("blocked direction cannot authorize a suggestion")
        elif (
            self.reasons
            or self.policy_digest is None
            or self.qualification_digest is None
            or self.qualified_completion_count is None
            or self.expires_at is None
            or self.expires_at <= self.evaluated_at
        ):
            raise ValueError("qualified bounded result required")
        if (self.status == "recommended") != (self.direction != "none"):
            raise ValueError("direction does not match status")
        return self

    @property
    def decision_input_digest(self) -> str:
        # Audit/freshness commitment, not an automatic spending-opportunity epoch.
        return digest(
            [
                self.schema_version,
                self.snapshot_digest,
                self.policy_digest,
                self.qualification_digest,
                self.facts_digest,
                self.opportunity.model_dump(mode="json"),
            ]
        )

    @property
    def recommendation_digest(self) -> str:
        return digest(self.model_dump(mode="json"))
