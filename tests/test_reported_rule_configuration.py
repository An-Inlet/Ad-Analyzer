"""Pinned operational config never becomes a legacy learning descriptor."""

from pathlib import Path

import pytest
from app.production_runtime.candidate_configuration import (
    CandidateAssemblyManifestV1,
    CandidateConfigurationError,
    CandidateEvidenceDescriptorV1,
    CandidatePolicyBundleV1,
    load_candidate_configuration,
    validate_candidate_source,
)
from app.production_runtime.candidate_sources import registered_candidate_source
from app.reported_feedback.candidate_configuration import (
    ReportedRuleAssemblyManifestV1,
    ReportedRuleEvidenceDescriptorV1,
    ReportedRulePolicyBundleV1,
)
from pydantic import ValidationError

from tests.test_candidate_configuration import documents as legacy_documents
from tests.test_optimization_runtime_contracts import manifest as native_manifest
from tests.test_reported_rule_candidates import fixture


def documents() -> tuple[
    ReportedRuleAssemblyManifestV1, ReportedRulePolicyBundleV1, ReportedRuleEvidenceDescriptorV1
]:
    _, policy, _, _ = fixture()
    bundle = ReportedRulePolicyBundleV1(
        environment="contract_test", candidate_policies=(policy,), automatic_policies=()
    )
    source = ReportedRuleEvidenceDescriptorV1(
        source_id="reported_fixture",
        environment="contract_test",
        kind="operational_reported_efficiency_rule",
        source_schema="inlet.operational-reported-comparison.v1",
        policy_bundle_digest=bundle.digest(),
        source_scope="one_current_owned_original_campaign_comparison",
        causal_lift="unavailable",
        financial_qualification="not_provided",
    )
    manifest = ReportedRuleAssemblyManifestV1(
        manifest_id="reported_fixture",
        revision=1,
        environment="contract_test",
        optimization_manifest_digest=native_manifest().digest(),
        policy_bundle_digest=bundle.digest(),
        evidence_source_id=source.source_id,
        evidence_descriptor_digest=source.digest(),
        mode="candidates_only",
    )
    return manifest, bundle, source


def test_distinct_pinned_bundle_loads_but_registers_nothing(tmp_path: Path) -> None:
    manifest, bundle, source = documents()
    mp, pp = tmp_path / "manifest.json", tmp_path / "policy.json"
    mp.write_text(manifest.model_dump_json())
    pp.write_text(bundle.model_dump_json())
    loaded = load_candidate_configuration(
        str(mp),
        manifest.digest(),
        str(pp),
        optimization_manifest=native_manifest(),
        source_descriptor=source,
    )
    assert loaded == (manifest, bundle)
    assert registered_candidate_source(source.source_id) is None
    old_manifest, old_bundle, old_source = legacy_documents()
    cases: list[
        tuple[
            CandidateAssemblyManifestV1 | ReportedRuleAssemblyManifestV1,
            CandidatePolicyBundleV1 | ReportedRulePolicyBundleV1,
            CandidateEvidenceDescriptorV1 | ReportedRuleEvidenceDescriptorV1,
        ]
    ] = [
        (manifest, bundle, old_source),
        (old_manifest, old_bundle, source),
        (manifest, old_bundle, source),
    ]
    for m, b, d in cases:
        with pytest.raises(CandidateConfigurationError):
            validate_candidate_source(m, b, d)
    with pytest.raises(ValidationError):
        type(old_source).model_validate_json(source.model_dump_json())


@pytest.mark.parametrize("change", ["digest", "duplicate", "missing", "wrong_mode"])
def test_operational_configuration_fails_closed(tmp_path: Path, change: str) -> None:
    manifest, bundle, _ = documents()
    if change == "wrong_mode":
        manifest = manifest.model_copy(update={"mode": "session_automatic"})
    mp, pp = tmp_path / "manifest.json", tmp_path / "policy.json"
    mp.write_text(manifest.model_dump_json())
    pp.write_text(bundle.model_dump_json())
    if change == "duplicate":
        mp.write_text(manifest.model_dump_json()[:-1] + ',"revision":2}')
    if change == "missing":
        pp.unlink()
    with pytest.raises(CandidateConfigurationError):
        load_candidate_configuration(
            str(mp),
            "0" * 64 if change == "digest" else manifest.digest(),
            str(pp),
            optimization_manifest=native_manifest(),
        )
