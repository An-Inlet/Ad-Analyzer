"""Server-owned session automation contracts, distinct from exact human approval."""

from typing import Annotated, Literal

from pydantic import AwareDatetime, Field, model_validator

from app.goals.schemas import StrictModel
from app.optimization_candidates.selection_contracts import CandidatePolicyRef
from app.publication.contracts import fingerprint
from app.publication.execution_contracts import Environment, ProviderMandateBinding
from app.publication.provider_contracts import Digest, Id

BudgetOperation = Literal[
    "google_budget_set_v1", "meta_budget_set_v1", "tiktok_budget_set_v1"
]


class AutomaticPolicyRef(StrictModel):
    policy_id: Id
    revision: int = Field(strict=True, ge=1)


class SessionAutomaticPolicy(StrictModel):
    schema_version: Literal["inlet.session-automatic-policy.v1"] = (
        "inlet.session-automatic-policy.v1"
    )
    workspace_id: int = Field(strict=True, gt=0)
    environment: Environment
    policy_family: Id
    policy_id: Id
    revision: int = Field(strict=True, ge=1)
    candidate_policy: CandidatePolicyRef
    allowed_operations: list[BudgetOperation] = Field(min_length=1, max_length=3)
    semantic_producer_families: list[Id] = Field(min_length=1, max_length=8)
    lifetime_seconds: int = Field(strict=True, ge=1, le=86400)
    cadence_seconds: int = Field(strict=True, ge=1, le=86400)

    @model_validator(mode="after")
    def exact(self) -> "SessionAutomaticPolicy":
        if len(set(self.allowed_operations)) != len(self.allowed_operations) or len(
            set(self.semantic_producer_families)
        ) != len(self.semantic_producer_families):
            raise ValueError("duplicate policy operations or producer families")
        return self

    def digest(self) -> str:
        return fingerprint(self.schema_version, self.model_dump(mode="json"))


class SemanticDecisionEpoch(StrictModel):
    """Produced by a registered server source, never by refreshing observation time.

    Revisions, policy IDs, mandate IDs, connection versions, catalog snapshots and
    timestamps are deliberately absent. Producer family remains stable across its
    revisions; a producer must preserve semantic identity across source corrections.
    """

    schema_version: Literal["inlet.semantic-decision-epoch.v1"] = (
        "inlet.semantic-decision-epoch.v1"
    )
    producer_family: Id
    source_schema: str = Field(min_length=1, max_length=100)
    source_reference: Id
    semantic_digest: Digest

    def digest(self) -> str:
        return fingerprint(self.schema_version, self.model_dump(mode="json"))


class StartSessionAutomation(StrictModel):
    mandate: ProviderMandateBinding
    policy: AutomaticPolicyRef


class CustomerExactApprovalAuthority(StrictModel):
    kind: Literal["customer_exact_approval"] = "customer_exact_approval"


class SessionMandateDecisionAuthority(StrictModel):
    kind: Literal["mandate_automatic_decision"] = "mandate_automatic_decision"
    admission_id: Id


OptimizationAuthority = Annotated[
    CustomerExactApprovalAuthority | SessionMandateDecisionAuthority,
    Field(discriminator="kind"),
]

AutomationStatus = Literal["unavailable", "running", "waiting", "stopped", "expired", "blocked"]
AutomationReason = Literal[
    "automation_not_available",
    "policy_not_available",
    "evidence_not_ready",
    "financial_proof_unavailable",
    "original_session_ended",
    "mandate_changed",
    "source_changed",
    "decision_already_used",
    "awaiting_original_reconciliation",
    "customer_stopped",
    "ready",
]


class SessionAutomationStatus(StrictModel):
    run_id: Id | None
    status: AutomationStatus
    reason: AutomationReason
    environment: Environment | None
    session_bound: Literal[True] = True
    message: str = Field(min_length=1, max_length=300)


class AutomaticPolicyOption(StrictModel):
    """Only explicitly registered policies are selectable; never client numeric policy."""

    policy: AutomaticPolicyRef
    label: str = Field(min_length=1, max_length=100)
    environment: Environment


class AutomaticMandateOption(StrictModel):
    mandate: ProviderMandateBinding
    label: str = Field(min_length=1, max_length=100)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    total_limit_micros: int = Field(strict=True, gt=0, le=10**15)
    starts_at: AwareDatetime
    ends_at: AwareDatetime


class SessionAutomationCapabilities(StrictModel):
    available: bool
    reason: AutomationReason
    policies: list[AutomaticPolicyOption] = Field(max_length=20)
    mandates: list[AutomaticMandateOption] = Field(max_length=20)
    session_bound: Literal[True] = True
    message: str = Field(min_length=1, max_length=300)


class SessionAutomationHistory(StrictModel):
    runs: list[SessionAutomationStatus] = Field(max_length=20)
