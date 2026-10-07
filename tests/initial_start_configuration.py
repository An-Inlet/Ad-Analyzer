"""Pinned explicit initial policy and real configured runtime, only transport is fake."""

from pathlib import Path
from typing import Any

import pytest
from app.initial_planning.start_configuration import (
    InitialRuleAssemblyManifestV1,
    InitialRuleEvidenceDescriptorV1,
    InitialRulePolicyBundleV1,
)
from app.initial_planning.start_contracts import InitialRuleAutomaticPolicyV1
from app.production_runtime import candidate_assembly
from app.production_runtime.candidate_sources import RegisteredInitialRuleSource
from app.settings import settings


def configure(
    c: Any, policy: InitialRuleAutomaticPolicyV1, path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = InitialRulePolicyBundleV1(
        environment="contract_test", candidate_policies=(c.policy,), automatic_policies=(policy,)
    )
    descriptor = InitialRuleEvidenceDescriptorV1(
        source_id="initial_owned_fixture",
        environment="contract_test",
        kind="initial_reported_efficiency_rule",
        source_schema="inlet.initial-reported-efficiency-rule.v1",
        policy_bundle_digest=bundle.digest(),
        source_scope="one_current_owned_initial_preview",
        causal_lift="unavailable",
        financial_qualification="not_provided",
    )
    manifest = InitialRuleAssemblyManifestV1(
        manifest_id="initial_fixture",
        revision=1,
        environment="contract_test",
        optimization_manifest_digest=settings.optimization_execution_manifest_digest,
        policy_bundle_digest=bundle.digest(),
        evidence_source_id=descriptor.source_id,
        evidence_descriptor_digest=descriptor.digest(),
        mode="session_automatic",
    )
    bundle_path, manifest_path = path / "initial-policies.json", path / "initial-assembly.json"
    bundle_path.write_text(bundle.model_dump_json())
    manifest_path.write_text(manifest.model_dump_json())
    for name, value in (
        ("candidate_policy_bundle_path", str(bundle_path)),
        ("candidate_assembly_manifest_path", str(manifest_path)),
        ("candidate_assembly_manifest_digest", manifest.digest()),
        ("customer_candidate_reads_enabled", True),
        ("customer_session_automation_enabled", True),
    ):
        monkeypatch.setattr(settings, name, value)
    monkeypatch.setattr(
        candidate_assembly,
        "registered_candidate_source",
        lambda identifier: (
            RegisteredInitialRuleSource(descriptor) if identifier == descriptor.source_id else None
        ),
    )
