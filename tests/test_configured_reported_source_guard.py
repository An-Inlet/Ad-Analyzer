"""Strict scalar source interchange; no child process or provider is required."""

import json
from pathlib import Path

import pytest

from tests.configured_reported_original_fixture import ConfiguredReportedOriginalIds, read_ids


def payload() -> dict[str, object]:
    result: dict[str, object] = {}
    for key in ConfiguredReportedOriginalIds.__dataclass_fields__:
        if key == "platform":
            result[key] = "meta_ads"
        elif key in {
            "workspace_id",
            "account_id",
            "goal_revision",
            "mandate_revision",
            "native_connection_id",
            "provider_posts",
        }:
            result[key] = 1
        else:
            result[key] = "a" * (64 if key.endswith("digest") else 32)
    return result


@pytest.mark.parametrize(
    "change",
    [
        "bool",
        "platform",
        "posts",
        "extra",
        "missing",
        "digest",
        "array",
        "oversized",
        "symlink",
    ],
)
def test_reported_source_rejects_unsafe_scalar_payload(tmp_path: Path, change: str) -> None:
    raw = payload()
    if change == "bool":
        raw["workspace_id"] = True
    elif change == "platform":
        raw["platform"] = "google_ads"
    elif change == "posts":
        raw["provider_posts"] = 0
    elif change == "extra":
        raw["runtime"] = "untrusted"
    elif change == "missing":
        del raw["receipt_id"]
    elif change == "digest":
        raw["receipt_digest"] = "invalid"
    path = tmp_path / "ids.json"
    path.write_text(json.dumps([] if change == "array" else raw))
    if change == "oversized":
        path.write_text(" " * 8193)
    elif change == "symlink":
        other = tmp_path / "other.json"
        path.rename(other)
        path.symlink_to(other)
    with pytest.raises(AssertionError):
        read_ids(path)


def test_reported_source_accepts_closed_scalar_shape(tmp_path: Path) -> None:
    path = tmp_path / "ids.json"
    path.write_text(json.dumps(payload()))
    result = read_ids(path)
    assert result.platform == "meta_ads" and result.provider_posts == 1


@pytest.mark.parametrize("change", ["query", "foreign", "relative", "missing", "symlink"])
def test_reported_child_rejects_unowned_sqlite_target(tmp_path: Path, change: str) -> None:
    from tests.fixtures.retired_execution.configured_reported_original_seed_driver import (
        owned_sqlite_target,
    )

    expected = tmp_path / "current.sqlite"
    expected.touch()
    target = f"sqlite:///{expected}"
    if change == "query":
        target += "?mode=ro"
    elif change == "foreign":
        foreign = tmp_path / "foreign.sqlite"
        foreign.touch()
        target = f"sqlite:///{foreign}"
    elif change == "relative":
        target = "sqlite:///current.sqlite"
    elif change == "missing":
        expected.unlink()
    elif change == "symlink":
        foreign = tmp_path / "foreign.sqlite"
        expected.rename(foreign)
        expected.symlink_to(foreign)
    with pytest.raises(AssertionError):
        owned_sqlite_target(target, expected)


@pytest.mark.parametrize(
    "change", ["none", "digest", "foreign", "symlink", "oversized", "wrong_stage"]
)
def test_reported_source_fixed_files_are_revalidated(tmp_path: Path, change: str) -> None:
    from dataclasses import replace

    from app.production_runtime.candidate_configuration import (
        CandidateAssemblyManifestV1,
        CandidatePolicyBundleV1,
        FrozenCandidatePolicy,
    )

    from tests.configured_reported_original_fixture import validate_files
    from tests.test_optimization_runtime_contracts import manifest, policy

    ids_path = tmp_path / "ids.json"
    ids_path.write_text(json.dumps(payload()))
    ids = read_ids(ids_path)
    operating = policy()
    optimization = manifest().model_copy(
        update={"replacement_enabled": True, "operating_policy_digest": operating.digest()}
    )
    policies = CandidatePolicyBundleV1(
        environment="contract_test",
        automatic_policies=(),
        candidate_policies=(
            FrozenCandidatePolicy(
                workspace_id=2 if change == "foreign" else 1,
                environment="contract_test",
                policy_id="a" * 32,
                revision=1,
                budget_step_micros=1_000_000,
                minimum_observations=2,
            ),
        ),
    )
    candidate = CandidateAssemblyManifestV1(
        manifest_id="fixture",
        revision=1,
        environment="contract_test",
        optimization_manifest_digest=(
            optimization
            if change == "wrong_stage"
            else optimization.model_copy(update={"replacement_enabled": False})
        ).digest(),
        policy_bundle_digest=policies.digest(),
        evidence_source_id="fixture",
        evidence_descriptor_digest="a" * 64,
        mode="candidates_only",
    )
    ids = replace(
        ids,
        operating_policy_digest=operating.digest(),
        optimization_manifest_digest=optimization.digest(),
        candidate_manifest_digest=candidate.digest(),
        candidate_policy_digest=policies.digest(),
    )
    for name, document in (
        ("optimization-policy.json", operating),
        ("optimization-manifest.json", optimization),
        ("candidate_manifest.json", candidate),
        ("candidate_policy.json", policies),
    ):
        (tmp_path / name).write_text(document.model_dump_json())
    target = tmp_path / "candidate_policy.json"
    if change == "digest":
        ids = replace(ids, candidate_policy_digest="b" * 64)
    elif change == "symlink":
        other = tmp_path / "other.json"
        target.rename(other)
        target.symlink_to(other)
    elif change == "oversized":
        target.write_text(" " * 65537)
    if change == "none":
        validate_files(tmp_path, ids)
    else:
        with pytest.raises(AssertionError):
            validate_files(tmp_path, ids)
