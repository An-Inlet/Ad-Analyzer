"""Configured native HTTP + actual consent; no candidate or execution record seeds."""

from pathlib import Path
from typing import Any

import pytest
from app.api import customer_candidates
from app.customers import identity
from app.production_runtime import candidate_assembly
from app.production_runtime.candidate_configuration import (
    CandidateAssemblyManifestV1,
    CandidateEvidenceDescriptorV1,
    CandidatePolicyBundleV1,
    FrozenCandidatePolicy,
)
from app.production_runtime.candidate_sources import (
    CandidateEvidenceBinding,
    RegisteredCandidateEvidenceSource,
)
from app.production_runtime.optimization_assembly import pinned
from app.settings import Settings, settings
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from tests.configured_candidate_current_wiring import configured_current_optimization
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_shopify_sales import configuration as configuration


def configured_current_candidates(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    replicas: Any,
    ids: Any,
    mode: str,
) -> Any:
    alice, base, query, wire, control = configured_current_optimization(
        customer_engine, configuration, tmp_path, monkeypatch, replicas, ids
    )
    wid = ids.workspace_id
    policies = CandidatePolicyBundleV1(
        environment="contract_test",
        automatic_policies=(),
        candidate_policies=(
            FrozenCandidatePolicy(
                workspace_id=wid,
                environment="contract_test",
                policy_id="a" * 32,
                revision=1,
                budget_step_micros=1_000_000,
                minimum_observations=2,
            ),
        ),
    )
    assert policies.digest() == ids.candidate_policy_digest
    descriptor = CandidateEvidenceDescriptorV1(
        source_id="unqualified_fixture",
        environment="contract_test",
        kind="contract_scenario" if mode == "scenario" else "unqualified_observation",
        source_schema="inlet.explicit-candidate-scenario.v1"
        if mode == "scenario"
        else "inlet.owned-reconciliation-observations.v1",
        policy_bundle_digest=policies.digest(),
        feedback_dependent=False,
        qualified_profiles=(),
        semantic_producer_families=(),
    )

    assert descriptor.digest() == ids.evidence_descriptor_digest

    def transform(db: Session, principal: Any, work: Any, observation: Any, now: Any) -> Any:
        return observation.model_copy(
            update={
                "evidence": observation.evidence.model_copy(
                    update={
                        "qualification": "contract_scenario",
                        "direction": "decrease",
                        "observation_count": 2,
                    }
                )
            }
        )

    source_registration = RegisteredCandidateEvidenceSource(
        descriptor,
        lambda *_: CandidateEvidenceBinding(
            descriptor.digest(),
            transform if mode == "scenario" else None,
            (lambda *_: None) if mode == "scenario" else None,
            (),
        ),
    )
    monkeypatch.setattr(
        candidate_assembly, "registered_candidate_source", lambda _: source_registration
    )
    optimization = pinned(
        settings.optimization_execution_manifest_path,
        settings.optimization_execution_manifest_digest,
        settings.optimization_operating_policy_path,
    )
    assert optimization
    manifest = CandidateAssemblyManifestV1(
        manifest_id="candidate_fixture",
        revision=1,
        environment="contract_test",
        optimization_manifest_digest=optimization[0].digest(),
        policy_bundle_digest=policies.digest(),
        evidence_source_id=descriptor.source_id,
        evidence_descriptor_digest=descriptor.digest(),
        mode="candidates_only",
    )
    assert manifest.digest() == ids.candidate_manifest_digest
    manifest_file, policy_file = (
        tmp_path / "candidate_manifest.json",
        tmp_path / "candidate_policy.json",
    )
    manifest_file.write_text(manifest.model_dump_json())
    policy_file.write_text(policies.model_dump_json())
    monkeypatch.setattr(settings, "candidate_assembly_manifest_path", str(manifest_file))
    monkeypatch.setattr(settings, "candidate_assembly_manifest_digest", manifest.digest())
    monkeypatch.setattr(settings, "candidate_policy_bundle_path", str(policy_file))
    monkeypatch.setattr(settings, "customer_candidate_reads_enabled", True)
    monkeypatch.setattr(identity, "get_identity_provider", lambda: replicas[2])
    from app.publication import clock

    monkeypatch.setattr(clock, "utc_now", lambda: control["now"])
    alice.app.include_router(customer_candidates.router)
    draft = dict(
        mandate_id=ids.mandate_id,
        revision=ids.mandate_revision,
        policy_digest=ids.policy_digest,
        preparation_digest=ids.preparation_digest,
    )
    return alice, base, wire, control, draft
