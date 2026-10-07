"""Pinned configuration boundaries; no runtime construction or provider calls."""

import json
from pathlib import Path

import pytest
from app.optimization_candidates.contracts import CandidatePolicy
from app.optimization_candidates.selection_contracts import CandidatePolicyRef
from app.production_runtime.candidate_configuration import (
    CandidateAssemblyManifestV1,
    CandidateConfigurationError,
    CandidateEvidenceDescriptorV1,
    CandidatePolicyBundleV1,
    FrozenAutomaticPolicy,
    FrozenCandidatePolicy,
    load_candidate_configuration,
    validate_candidate_source,
)
from app.production_runtime.candidate_sources import (
    CandidateEvidenceBinding,
    registered_candidate_source,
    validate_candidate_binding,
)
from app.session_automation.contracts import SessionAutomaticPolicy
from pydantic import ValidationError

from tests.test_optimization_runtime_contracts import manifest as optimization_manifest


def documents(
    automatic: bool = False,
) -> tuple[CandidateAssemblyManifestV1, CandidatePolicyBundleV1, CandidateEvidenceDescriptorV1]:
    candidate = CandidatePolicy(
        workspace_id=1, environment="contract_test", policy_id="a" * 32, revision=1
    )
    auto = SessionAutomaticPolicy(
        workspace_id=1,
        environment="contract_test",
        policy_family="b" * 32,
        policy_id="c" * 32,
        revision=1,
        candidate_policy=CandidatePolicyRef(policy_id=candidate.policy_id, revision=1),
        candidate_policy_digest=candidate.digest(),
        allowed_operations=["meta_budget_set_v1"],
        semantic_producer_families=["d" * 32],
        lifetime_seconds=300,
        cadence_seconds=60,
    )
    bundle = CandidatePolicyBundleV1.model_validate_json(
        json.dumps(
            {
                "environment": "contract_test",
                "candidate_policies": [candidate.model_dump(mode="json")],
                "automatic_policies": [auto.model_dump(mode="json")] if automatic else [],
            }
        )
    )
    descriptor = CandidateEvidenceDescriptorV1(
        source_id="explicit_fixture",
        environment="contract_test",
        kind="contract_scenario",
        source_schema="inlet.explicit-test-evidence.v1",
        policy_bundle_digest=bundle.digest(),
        feedback_dependent=True,
        qualified_profiles=(),
        semantic_producer_families=("d" * 32,) if automatic else (),
    )
    manifest = CandidateAssemblyManifestV1(
        manifest_id="explicit_fixture",
        revision=1,
        environment="contract_test",
        optimization_manifest_digest=optimization_manifest().digest(),
        policy_bundle_digest=bundle.digest(),
        evidence_source_id=descriptor.source_id,
        evidence_descriptor_digest=descriptor.digest(),
        mode="session_automatic" if automatic else "candidates_only",
    )
    return manifest, bundle, descriptor


def save(path: Path, automatic: bool = False) -> tuple[Path, Path]:
    manifest, bundle, _ = documents(automatic)
    left, right = path / "manifest.json", path / "policy.json"
    left.write_text(manifest.model_dump_json())
    right.write_text(bundle.model_dump_json())
    return left, right


def test_exact_legacy_policy_bytes_optional_defaults_and_defensive_copies() -> None:
    _, bundle, _ = documents(True)
    stored = bundle.candidate_policies[0]
    original = stored.as_policy()
    assert original.budget_step_micros is None and original.minimum_observations is None
    assert stored.model_dump_json() == original.model_dump_json()
    assert stored.digest() == original.digest()
    automatic = bundle.automatic_policies[0]
    mutable = automatic.as_policy()
    assert automatic.model_dump_json() == mutable.model_dump_json()
    assert automatic.digest() == mutable.digest()
    mutable.allowed_operations.clear()
    mutable.candidate_policy.revision = 9
    assert automatic.allowed_operations == ("meta_budget_set_v1",)
    assert automatic.as_policy().candidate_policy.revision == 1
    original.budget_step_micros = 999
    assert stored.as_policy().budget_step_micros is None
    with pytest.raises(ValidationError):
        automatic.candidate_policy.revision = 2  # type: ignore[misc]
    with pytest.raises(ValidationError):
        stored.revision = 2  # type: ignore[misc]
    raw = original.model_dump(mode="json")
    raw["minimum_observations"] = 7
    frozen = FrozenCandidatePolicy.model_validate(raw)
    assert frozen.digest() == CandidatePolicy.model_validate(raw).digest()
    assert FrozenAutomaticPolicy.model_validate_json(automatic.model_dump_json()) == automatic


@pytest.mark.parametrize("automatic", [False, True])
def test_pinned_loader_and_missing_source_never_registration(
    tmp_path: Path, automatic: bool
) -> None:
    manifest, bundle, descriptor = documents(automatic)
    left, right = save(tmp_path, automatic)
    result = load_candidate_configuration(
        str(left),
        manifest.digest(),
        str(right),
        optimization_manifest=optimization_manifest(),
        source_descriptor=descriptor,
    )
    assert result == (manifest, bundle)
    assert registered_candidate_source(descriptor.source_id) is None
    assert load_candidate_configuration(None, None, None, optimization_manifest=None) is None
    # Parsing without a registration is allowed; availability is NOT implied.
    assert (
        load_candidate_configuration(
            str(left), manifest.digest(), str(right), optimization_manifest=optimization_manifest()
        )
        == result
    )


@pytest.mark.parametrize(
    "change",
    [
        "manifest_pin",
        "bundle_pin",
        "optimization_pin",
        "source_pin",
        "source_id",
        "environment",
        "mode",
        "duplicate",
        "reference",
        "candidate_digest",
        "cross_workspace",
        "missing",
        "numeric_bool",
    ],
)
def test_bad_pins_references_and_policy_inputs(tmp_path: Path, change: str) -> None:
    manifest, bundle, descriptor = documents(True)
    raw, policies = manifest.model_dump(mode="json"), bundle.model_dump(mode="json")
    if change == "manifest_pin":
        raw["revision"] = 2
    elif change in {"bundle_pin", "optimization_pin", "source_pin"}:
        key = {
            "bundle_pin": "policy_bundle_digest",
            "optimization_pin": "optimization_manifest_digest",
            "source_pin": "evidence_descriptor_digest",
        }[change]
        raw[key] = "0" * 64
    elif change == "source_id":
        raw["evidence_source_id"] = "different"
    elif change == "environment":
        raw["environment"] = "live"
    elif change == "mode":
        raw["mode"] = "candidates_only"
    elif change == "duplicate":
        policies["candidate_policies"] *= 2
    elif change == "reference":
        policies["automatic_policies"][0]["candidate_policy"]["revision"] = 2
    elif change == "candidate_digest":
        policies["automatic_policies"][0]["candidate_policy_digest"] = "0" * 64
    elif change == "cross_workspace":
        policies["automatic_policies"][0]["workspace_id"] = 2
    elif change == "missing":
        del policies["automatic_policies"][0]["cadence_seconds"]
    elif change == "numeric_bool":
        policies["candidate_policies"][0]["minimum_observations"] = True
    left, right = tmp_path / "manifest.json", tmp_path / "policy.json"
    left.write_text(json.dumps(raw))
    right.write_text(json.dumps(policies))
    # Re-pin structural negatives so the tested failure cannot be just the outer pin.
    expected = (
        manifest.digest()
        if change == "manifest_pin"
        else (CandidateAssemblyManifestV1.model_validate(raw).digest())
    )
    with pytest.raises(CandidateConfigurationError, match="^candidate_configuration_invalid$"):
        load_candidate_configuration(
            str(left),
            expected,
            str(right),
            optimization_manifest=optimization_manifest(),
            source_descriptor=descriptor,
        )


@pytest.mark.parametrize("bad", ["duplicate", "nested_duplicate", "oversize", "nan", "missing"])
def test_bounded_unique_json_and_sanitized_failures(tmp_path: Path, bad: str) -> None:
    manifest, _, _ = documents()
    left, right = save(tmp_path)
    if bad == "duplicate":
        left.write_text('{"environment":"live",' + left.read_text()[1:])
    elif bad == "nested_duplicate":
        right.write_text(
            right.read_text().replace('"workspace_id":1', '"workspace_id":1,"workspace_id":1')
        )
    elif bad == "oversize":
        right.write_text(" " * 65537)
    elif bad == "nan":
        right.write_text('{"secret":NaN}')
    else:
        right.unlink()
    with pytest.raises(CandidateConfigurationError) as caught:
        load_candidate_configuration(
            str(left), manifest.digest(), str(right), optimization_manifest=optimization_manifest()
        )
    assert str(caught.value) == "candidate_configuration_invalid"
    assert str(tmp_path) not in str(caught.value)


@pytest.mark.parametrize(
    "schema", ["inlet.owned-outcome-assessment.v3", "inlet.operational-reported-comparison.v1"]
)
def test_no_descriptor_promotes_known_unqualified_facts(schema: str) -> None:
    _, _, descriptor = documents()
    with pytest.raises(ValidationError):
        CandidateEvidenceDescriptorV1.model_validate(
            {**descriptor.model_dump(), "source_schema": schema}
        )


def test_live_scenario_and_unqualified_epochs_rejected() -> None:
    manifest, bundle, descriptor = documents()
    with pytest.raises(ValidationError):
        CandidateEvidenceDescriptorV1.model_validate(
            {**descriptor.model_dump(), "environment": "live"}
        )
    with pytest.raises(ValidationError):
        CandidateEvidenceDescriptorV1.model_validate(
            {
                **descriptor.model_dump(),
                "kind": "unqualified_observation",
                "feedback_dependent": False,
                "semantic_producer_families": ("d" * 32,),
            }
        )
    with pytest.raises(ValueError):
        validate_candidate_binding(
            descriptor, CandidateEvidenceBinding(descriptor.digest(), None, None, ())
        )
    with pytest.raises(CandidateConfigurationError):
        validate_candidate_source(
            manifest.model_copy(update={"evidence_descriptor_digest": "0" * 64}), bundle, descriptor
        )


def test_callbacks_and_semantic_families_are_explicit() -> None:
    from dataclasses import replace
    from typing import Any

    from app.production_runtime.candidate_sources import RegisteredCandidateEvidenceSource
    from app.session_automation.runtime import SemanticEpochProducer

    _, _, descriptor = documents(True)

    def transform(*args: Any) -> Any:
        return args[-2]

    def final(*args: Any) -> None:
        return None

    def epoch(*args: Any) -> Any:
        raise AssertionError("configuration must not call producer")

    producer = SemanticEpochProducer(
        family="d" * 32,
        source_schema=descriptor.source_schema,
        environment="contract_test",
        authorized_read=epoch,
    )
    binding = CandidateEvidenceBinding(descriptor.digest(), transform, final, (producer,))
    validate_candidate_binding(descriptor, binding)
    registration = RegisteredCandidateEvidenceSource(descriptor, lambda *args: binding)
    assert registration.descriptor == descriptor and registration.descriptor is not descriptor
    for invalid in (
        replace(binding, authorized_transform=None),
        replace(binding, authorized_final_current=None),
        replace(binding, descriptor_digest="0" * 64),
        replace(binding, epoch_producers=()),
        replace(binding, epoch_producers=(producer, producer)),
        replace(binding, epoch_producers=(replace(producer, environment="live"),)),
        replace(binding, epoch_producers=(replace(producer, authorized_read=None, read=epoch),)),
    ):
        with pytest.raises(ValueError, match="candidate_source_binding_invalid"):
            validate_candidate_binding(descriptor, invalid)
    unqualified = CandidateEvidenceDescriptorV1.model_validate(
        {
            **descriptor.model_dump(),
            "kind": "unqualified_observation",
            "feedback_dependent": False,
            "semantic_producer_families": (),
        }
    )
    validate_candidate_binding(
        unqualified, CandidateEvidenceBinding(unqualified.digest(), None, None, ())
    )
    with pytest.raises(ValueError):
        validate_candidate_binding(
            unqualified, CandidateEvidenceBinding(unqualified.digest(), transform, final, ())
        )


def test_conflicting_learning_profile_pins_cannot_share_identity() -> None:
    _, _, descriptor = documents()
    profile = {
        "source_schema": descriptor.source_schema,
        "profile": "explicit_fixture",
        "revision": 1,
        "digest": "a" * 64,
    }
    value = {
        **descriptor.model_dump(mode="json"),
        "kind": "qualified_learning",
        "qualified_profiles": [profile],
    }
    checked = CandidateEvidenceDescriptorV1.model_validate_json(json.dumps(value))
    assert checked.qualified_profiles[0].digest == "a" * 64
    value["qualified_profiles"] = [profile, {**profile, "digest": "b" * 64}]
    with pytest.raises(ValidationError):
        CandidateEvidenceDescriptorV1.model_validate_json(json.dumps(value))


@pytest.mark.parametrize("field", ["manifest_path", "expected_manifest_digest", "policy_path"])
def test_partial_configuration_never_disabled_silently(tmp_path: Path, field: str) -> None:
    manifest, _, _ = documents()
    left, right = save(tmp_path)
    values: dict[str, str | None] = {
        "manifest_path": str(left),
        "expected_manifest_digest": manifest.digest(),
        "policy_path": str(right),
    }
    values[field] = None
    with pytest.raises(CandidateConfigurationError):
        load_candidate_configuration(
            values["manifest_path"],
            values["expected_manifest_digest"],
            values["policy_path"],
            optimization_manifest=optimization_manifest(),
        )


def test_automatic_operations_cannot_exceed_configured_providers(tmp_path: Path) -> None:
    manifest, bundle, descriptor = documents(True)
    body = bundle.model_dump(mode="json")
    body["automatic_policies"][0]["allowed_operations"] = ["tiktok_budget_set_v1"]
    bundle = CandidatePolicyBundleV1.model_validate_json(json.dumps(body))
    descriptor = descriptor.model_copy(update={"policy_bundle_digest": bundle.digest()})
    manifest = manifest.model_copy(
        update={
            "policy_bundle_digest": bundle.digest(),
            "evidence_descriptor_digest": descriptor.digest(),
        }
    )
    left, right = tmp_path / "manifest.json", tmp_path / "policy.json"
    left.write_text(manifest.model_dump_json())
    right.write_text(bundle.model_dump_json())
    with pytest.raises(CandidateConfigurationError):
        load_candidate_configuration(
            str(left),
            manifest.digest(),
            str(right),
            optimization_manifest=optimization_manifest(),
            source_descriptor=descriptor,
        )
