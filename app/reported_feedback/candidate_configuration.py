"""Pinned operational-rule assembly documents, separate from v1 learning claims."""

from typing import Literal

from pydantic import Field, model_validator

from app.initial_planning.contracts import Frozen
from app.publication.contracts import fingerprint
from app.publication.provider_contracts import Digest
from app.reported_feedback.automatic_contracts import ReportedRuleAutomaticPolicyV1
from app.reported_feedback.candidate_contracts import ReportedRulePolicyV1


class ReportedRulePolicyBundleV1(Frozen):
    schema_version: Literal["inlet.reported-rule-policy-bundle.v1"] = (
        "inlet.reported-rule-policy-bundle.v1"
    )
    environment: Literal["contract_test", "live"]
    candidate_policies: tuple[ReportedRulePolicyV1, ...] = Field(min_length=1, max_length=64)
    automatic_policies: tuple[ReportedRuleAutomaticPolicyV1, ...] = Field(max_length=64)

    @model_validator(mode="after")
    def exact(self) -> "ReportedRulePolicyBundleV1":
        candidates = {(p.workspace_id, p.policy_id, p.revision): p for p in self.candidate_policies}
        automatic = {(p.workspace_id, p.policy_id, p.revision) for p in self.automatic_policies}
        if len(candidates) != len(self.candidate_policies) or len(automatic) != len(
            self.automatic_policies
        ):
            raise ValueError("duplicate operational policies")
        if any(p.environment != self.environment for p in self.candidate_policies) or any(
            p.environment != self.environment for p in self.automatic_policies
        ):
            raise ValueError("operational policy environment changed")
        for policy in self.automatic_policies:
            ref = policy.candidate_policy
            candidate = candidates.get((policy.workspace_id, ref.policy_id, ref.revision))
            if candidate is None or candidate.digest() != policy.candidate_policy_digest:
                raise ValueError("operational automatic numeric policy mismatch")
        return self

    def digest(self) -> str:
        return fingerprint(self.schema_version, self.model_dump(mode="json"))


class ReportedRuleAssemblyManifestV1(Frozen):
    schema_version: Literal["inlet.reported-rule-assembly-manifest.v1"] = (
        "inlet.reported-rule-assembly-manifest.v1"
    )
    manifest_id: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    revision: int = Field(gt=0)
    environment: Literal["contract_test", "live"]
    optimization_manifest_digest: Digest
    policy_bundle_digest: Digest
    evidence_source_id: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    evidence_descriptor_digest: Digest
    mode: Literal["candidates_only", "session_automatic"]

    def digest(self) -> str:
        return fingerprint(self.schema_version, self.model_dump(mode="json"))


class ReportedRuleEvidenceDescriptorV1(Frozen):
    schema_version: Literal["inlet.reported-rule-source.v1"] = "inlet.reported-rule-source.v1"
    source_id: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    environment: Literal["contract_test", "live"]
    kind: Literal["operational_reported_efficiency_rule"]
    source_schema: Literal["inlet.operational-reported-comparison.v1"]
    policy_bundle_digest: Digest
    source_scope: Literal["one_current_owned_original_campaign_comparison"]
    causal_lift: Literal["unavailable"]
    financial_qualification: Literal["not_provided"]

    def digest(self) -> str:
        return fingerprint(self.schema_version, self.model_dump(mode="json"))
