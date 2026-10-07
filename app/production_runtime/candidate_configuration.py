"""Immutable candidate configuration; no source, runtime or numeric defaults installed."""

import hmac
import json
import re
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, model_validator

from app.initial_planning.start_configuration import (
    InitialRuleAssemblyManifestV1,
    InitialRuleEvidenceDescriptorV1,
    InitialRulePolicyBundleV1,
)
from app.optimization_candidates.contracts import CandidatePolicy
from app.optimization_candidates.service import ACTUAL_UNQUALIFIED_SCHEMAS
from app.planning_reporting.configuration import _unique_object
from app.production_runtime.optimization_contracts import OptimizationExecutionManifestV1
from app.publication.contracts import fingerprint
from app.publication.execution_contracts import Environment
from app.publication.provider_contracts import Digest, Id
from app.reported_feedback.candidate_configuration import (
    ReportedRuleAssemblyManifestV1,
    ReportedRuleEvidenceDescriptorV1,
    ReportedRulePolicyBundleV1,
)
from app.session_automation.contracts import BudgetOperation, SessionAutomaticPolicy

Name = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")]
Schema = Annotated[str, Field(min_length=1, max_length=100)]


class Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class FrozenCandidatePolicy(CandidatePolicy):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    def as_policy(self) -> CandidatePolicy:
        return CandidatePolicy.model_validate_json(self.model_dump_json())


class FrozenCandidatePolicyRef(Frozen):
    policy_id: Id
    revision: int = Field(ge=1)


class FrozenAutomaticPolicy(Frozen):
    # JSON field names/arrays and digest domain are exactly the existing v1 policy.
    schema_version: Literal["inlet.session-automatic-policy.v1"]
    workspace_id: int = Field(gt=0)
    environment: Environment
    policy_family: Id
    policy_id: Id
    revision: int = Field(ge=1)
    candidate_policy: FrozenCandidatePolicyRef
    candidate_policy_digest: Digest
    allowed_operations: tuple[BudgetOperation, ...] = Field(min_length=1, max_length=3)
    semantic_producer_families: tuple[Id, ...] = Field(min_length=1, max_length=8)
    lifetime_seconds: int = Field(ge=1, le=86400)
    cadence_seconds: int = Field(ge=1, le=86400)

    @model_validator(mode="after")
    def legacy_valid(self) -> "FrozenAutomaticPolicy":
        self.as_policy()
        return self

    def as_policy(self) -> SessionAutomaticPolicy:
        return SessionAutomaticPolicy.model_validate_json(self.model_dump_json())

    def digest(self) -> str:
        return fingerprint(self.schema_version, self.model_dump(mode="json"))


class CandidatePolicyBundleV1(Frozen):
    schema_version: Literal["inlet.candidate-policy-bundle.v1"] = "inlet.candidate-policy-bundle.v1"
    environment: Environment
    candidate_policies: tuple[FrozenCandidatePolicy, ...] = Field(max_length=64)
    automatic_policies: tuple[FrozenAutomaticPolicy, ...] = Field(max_length=64)

    @model_validator(mode="after")
    def references(self) -> "CandidatePolicyBundleV1":
        candidates = {(p.workspace_id, p.policy_id, p.revision): p for p in self.candidate_policies}
        automatic = {(p.workspace_id, p.policy_id, p.revision) for p in self.automatic_policies}
        if len(candidates) != len(self.candidate_policies) or len(automatic) != len(
            self.automatic_policies
        ):
            raise ValueError("duplicate policies")
        if any(p.environment != self.environment for p in self.candidate_policies) or any(
            p.environment != self.environment for p in self.automatic_policies
        ):
            raise ValueError("policy environment mismatch")
        for policy in self.automatic_policies:
            ref = policy.candidate_policy
            candidate = candidates.get((policy.workspace_id, ref.policy_id, ref.revision))
            if candidate is None or candidate.digest() != policy.candidate_policy_digest:
                raise ValueError("candidate policy commitment mismatch")
        return self

    def digest(self) -> str:
        return fingerprint(self.schema_version, self.model_dump(mode="json"))


class CandidateAssemblyManifestV1(Frozen):
    schema_version: Literal["inlet.candidate-assembly-manifest.v1"] = (
        "inlet.candidate-assembly-manifest.v1"
    )
    manifest_id: Name
    revision: int = Field(gt=0)
    environment: Environment
    optimization_manifest_digest: Digest
    policy_bundle_digest: Digest
    evidence_source_id: Name
    evidence_descriptor_digest: Digest
    mode: Literal["candidates_only", "session_automatic"]

    def digest(self) -> str:
        return fingerprint(self.schema_version, self.model_dump(mode="json"))


class CandidateLearningProfileV1(Frozen):
    source_schema: Schema
    profile: str = Field(min_length=1, max_length=100)
    revision: int = Field(gt=0)
    digest: Digest


class CandidateEvidenceDescriptorV1(Frozen):
    schema_version: Literal["inlet.candidate-evidence-descriptor.v1"] = (
        "inlet.candidate-evidence-descriptor.v1"
    )
    source_id: Name
    environment: Environment
    kind: Literal["unqualified_observation", "contract_scenario", "qualified_learning"]
    source_schema: Schema
    policy_bundle_digest: Digest
    feedback_dependent: bool
    qualified_profiles: tuple[CandidateLearningProfileV1, ...] = Field(max_length=32)
    semantic_producer_families: tuple[Id, ...] = Field(max_length=8)

    @model_validator(mode="after")
    def no_promotion(self) -> "CandidateEvidenceDescriptorV1":
        profiles = [(p.source_schema, p.profile, p.revision) for p in self.qualified_profiles]
        if (
            (self.kind == "contract_scenario" and self.environment != "contract_test")
            or len(set(profiles)) != len(profiles)
            or len(set(self.semantic_producer_families)) != len(self.semantic_producer_families)
            or (self.kind == "qualified_learning") != bool(self.qualified_profiles)
            or any(p.source_schema != self.source_schema for p in self.qualified_profiles)
            or (
                self.kind == "unqualified_observation"
                and (self.semantic_producer_families or self.feedback_dependent)
            )
            or (
                self.kind != "unqualified_observation"
                and self.source_schema
                in (ACTUAL_UNQUALIFIED_SCHEMAS | {"inlet.operational-reported-comparison.v1"})
            )
        ):
            raise ValueError("invalid evidence descriptor")
        return self

    def digest(self) -> str:
        return fingerprint(self.schema_version, self.model_dump(mode="json"))


class CandidateConfigurationError(ValueError):
    """Sanitized configuration failure; file contents and paths are never exposed."""


def validate_candidate_source(
    manifest: CandidateAssemblyManifestV1
    | ReportedRuleAssemblyManifestV1
    | InitialRuleAssemblyManifestV1,
    bundle: CandidatePolicyBundleV1 | ReportedRulePolicyBundleV1 | InitialRulePolicyBundleV1,
    descriptor: CandidateEvidenceDescriptorV1
    | ReportedRuleEvidenceDescriptorV1
    | InitialRuleEvidenceDescriptorV1,
) -> None:
    if isinstance(manifest, InitialRuleAssemblyManifestV1):
        manifest = InitialRuleAssemblyManifestV1.model_validate_json(manifest.model_dump_json())
        if isinstance(bundle, InitialRulePolicyBundleV1):
            bundle = InitialRulePolicyBundleV1.model_validate_json(bundle.model_dump_json())
        if isinstance(descriptor, InitialRuleEvidenceDescriptorV1):
            descriptor = InitialRuleEvidenceDescriptorV1.model_validate_json(
                descriptor.model_dump_json()
            )
        if (
            not isinstance(bundle, InitialRulePolicyBundleV1)
            or not isinstance(descriptor, InitialRuleEvidenceDescriptorV1)
            or manifest.policy_bundle_digest != bundle.digest()
            or manifest.environment != bundle.environment
            or manifest.environment != descriptor.environment
            or descriptor.source_id != manifest.evidence_source_id
            or descriptor.digest() != manifest.evidence_descriptor_digest
            or descriptor.policy_bundle_digest != bundle.digest()
            or (manifest.mode == "candidates_only" and bundle.automatic_policies)
            or (manifest.mode == "session_automatic" and not bundle.automatic_policies)
        ):
            raise CandidateConfigurationError("candidate_configuration_invalid")
        return
    if isinstance(manifest, ReportedRuleAssemblyManifestV1):
        manifest = ReportedRuleAssemblyManifestV1.model_validate_json(manifest.model_dump_json())
        if isinstance(bundle, ReportedRulePolicyBundleV1):
            bundle = ReportedRulePolicyBundleV1.model_validate_json(bundle.model_dump_json())
        if isinstance(descriptor, ReportedRuleEvidenceDescriptorV1):
            descriptor = ReportedRuleEvidenceDescriptorV1.model_validate_json(
                descriptor.model_dump_json()
            )
        if (
            not isinstance(bundle, ReportedRulePolicyBundleV1)
            or not isinstance(descriptor, ReportedRuleEvidenceDescriptorV1)
            or manifest.policy_bundle_digest != bundle.digest()
            or manifest.environment != bundle.environment
            or manifest.environment != descriptor.environment
            or descriptor.source_id != manifest.evidence_source_id
            or descriptor.digest() != manifest.evidence_descriptor_digest
            or descriptor.policy_bundle_digest != bundle.digest()
            or (manifest.mode == "candidates_only" and bundle.automatic_policies)
            or (manifest.mode == "session_automatic" and not bundle.automatic_policies)
        ):
            raise CandidateConfigurationError("candidate_configuration_invalid")
        return
    if not isinstance(bundle, CandidatePolicyBundleV1) or not isinstance(
        descriptor, CandidateEvidenceDescriptorV1
    ):
        raise CandidateConfigurationError("candidate_configuration_invalid")
    manifest = CandidateAssemblyManifestV1.model_validate_json(manifest.model_dump_json())
    bundle = CandidatePolicyBundleV1.model_validate_json(bundle.model_dump_json())
    descriptor = CandidateEvidenceDescriptorV1.model_validate_json(descriptor.model_dump_json())
    if (
        manifest.policy_bundle_digest != bundle.digest()
        or manifest.environment != bundle.environment
        or (manifest.mode == "candidates_only" and bundle.automatic_policies)
        or descriptor.source_id != manifest.evidence_source_id
        or descriptor.digest() != manifest.evidence_descriptor_digest
        or descriptor.environment != manifest.environment
        or descriptor.policy_bundle_digest != bundle.digest()
        or any(
            not set(policy.semantic_producer_families).issubset(
                descriptor.semantic_producer_families
            )
            for policy in bundle.automatic_policies
        )
    ):
        raise CandidateConfigurationError("candidate_configuration_invalid")


def load_candidate_configuration(
    manifest_path: str | None,
    expected_manifest_digest: str | None,
    policy_path: str | None,
    *,
    optimization_manifest: OptimizationExecutionManifestV1 | None,
    source_descriptor: CandidateEvidenceDescriptorV1
    | ReportedRuleEvidenceDescriptorV1
    | InitialRuleEvidenceDescriptorV1
    | None = None,
) -> (
    tuple[
        CandidateAssemblyManifestV1
        | ReportedRuleAssemblyManifestV1
        | InitialRuleAssemblyManifestV1,
        CandidatePolicyBundleV1 | ReportedRulePolicyBundleV1 | InitialRulePolicyBundleV1,
    ]
    | None
):
    """Parse/pin documents only; a result does not mean a source is registered.

    Source validation is mandatory when assembly resolves a real registration.
    Missing registration remains unavailable; this loader never builds a source.
    """
    if manifest_path is None and expected_manifest_digest is None and policy_path is None:
        return None

    def read(path: str, capacity: int) -> str:
        with Path(path).open("rb") as stream:
            raw = stream.read(capacity + 1)
        if len(raw) > capacity:
            raise ValueError("capacity")
        # Validate duplicate keys before JSON-mode strict parsing (which admits arrays as tuples).
        parsed = json.loads(raw, object_pairs_hook=_unique_object)
        return json.dumps(parsed, allow_nan=False)

    try:
        if (
            not manifest_path
            or not policy_path
            or not expected_manifest_digest
            or not re.fullmatch(r"[a-f0-9]{64}", expected_manifest_digest)
            or optimization_manifest is None
        ):
            raise ValueError("partial configuration")
        optimization = OptimizationExecutionManifestV1.model_validate_json(
            optimization_manifest.model_dump_json()
        )
        manifest: (
            CandidateAssemblyManifestV1
            | ReportedRuleAssemblyManifestV1
            | InitialRuleAssemblyManifestV1
        ) = TypeAdapter(
            Annotated[
                CandidateAssemblyManifestV1
                | ReportedRuleAssemblyManifestV1
                | InitialRuleAssemblyManifestV1,
                Field(discriminator="schema_version"),
            ]
        ).validate_json(read(manifest_path, 16384))
        bundle: CandidatePolicyBundleV1 | ReportedRulePolicyBundleV1 | InitialRulePolicyBundleV1 = (
            TypeAdapter(
                Annotated[
                    CandidatePolicyBundleV1
                    | ReportedRulePolicyBundleV1
                    | InitialRulePolicyBundleV1,
                    Field(discriminator="schema_version"),
                ]
            ).validate_json(read(policy_path, 65536))
        )
        if (
            isinstance(manifest, InitialRuleAssemblyManifestV1)
            != isinstance(bundle, InitialRulePolicyBundleV1)
            or isinstance(manifest, ReportedRuleAssemblyManifestV1)
            != isinstance(bundle, ReportedRulePolicyBundleV1)
            or not hmac.compare_digest(manifest.digest(), expected_manifest_digest)
            or manifest.optimization_manifest_digest != optimization.digest()
            or manifest.policy_bundle_digest != bundle.digest()
            or manifest.environment != bundle.environment
            or manifest.environment != optimization.environment
            or (
                isinstance(
                    manifest, (ReportedRuleAssemblyManifestV1, InitialRuleAssemblyManifestV1)
                )
                and "meta_ads" not in optimization.providers
            )
            or (
                isinstance(
                    manifest, (ReportedRuleAssemblyManifestV1, InitialRuleAssemblyManifestV1)
                )
                and manifest.mode == "session_automatic"
                and not bundle.automatic_policies
            )
            or (manifest.mode == "candidates_only" and bundle.automatic_policies)
            or any(
                {
                    "google_budget_set_v1": "google_ads",
                    "meta_budget_set_v1": "meta_ads",
                    "tiktok_budget_set_v1": "tiktok_ads",
                }[operation]
                not in optimization.providers
                for policy in bundle.automatic_policies
                for operation in policy.allowed_operations
            )
        ):
            raise ValueError("binding")
        if source_descriptor is not None:
            validate_candidate_source(manifest, bundle, source_descriptor)
    except (OSError, ValueError, TypeError, RecursionError):
        raise CandidateConfigurationError("candidate_configuration_invalid") from None
    return manifest, bundle
