"""Standalone recognition must not register a runtime or coerce policy identity."""

import subprocess
import sys
from typing import Any

import pytest
from app.planning_documents.policy_capabilities import reporting_capability
from app.planning_documents.ports import PlanningCompositionPolicy
from app.planning_documents.selected_policy_contract import (
    SelectedPolicyContractV1,
    assert_selected_composition_policy,
    assert_selected_ticket_policy,
    selected_policy_contract,
)


def policy(version: int) -> PlanningCompositionPolicy:
    return PlanningCompositionPolicy(
        version=f"inlet.descriptive-review.v{version}",
        generator_version=f"inlet.descriptive-planning.v{version}",
    )


@pytest.mark.parametrize("version", [4, 5])
def test_exact_complete_policy(version: int) -> None:
    p = policy(version)
    expected = selected_policy_contract(p.version, p.generator_version)
    assert expected.requires_creative is (version == 5)
    assert expected.reporting_witness_kind == "local_reporting_v3"
    assert assert_selected_ticket_policy(p.version, p.digest()) == expected
    assert (
        assert_selected_composition_policy(
            p, ticket_policy_version=p.version, ticket_policy_digest=p.digest()
        )
        == expected
    )
    assert SelectedPolicyContractV1.model_validate_json(expected.model_dump_json()) == expected


@pytest.mark.parametrize("version,generator", [(3, 3), (4, 5), (5, 4), (6, 6)])
def test_unknown_mixed(version: int, generator: int) -> None:
    with pytest.raises(ValueError):
        selected_policy_contract(policy(version).version, policy(generator).generator_version)


@pytest.mark.parametrize("value", [True, 4, b"inlet.descriptive-review.v4", None])
def test_non_string_identity(value: Any) -> None:
    p = policy(4)
    with pytest.raises(ValueError):
        selected_policy_contract(value, p.generator_version)
    with pytest.raises(ValueError):
        selected_policy_contract(p.version, value)
    with pytest.raises(ValueError):
        assert_selected_ticket_policy(value, p.digest())
    with pytest.raises(ValueError):
        assert_selected_ticket_policy(p.version, value)


@pytest.mark.parametrize(
    "field,value",
    [
        ("requires_creative", 0),
        ("requires_creative", True),
        ("policy_version", b"inlet.descriptive-review.v4"),
        ("generator_version", "inlet.descriptive-planning.v5"),
        ("reporting_witness_kind", "local_reporting_v2"),
    ],
)
def test_copied_descriptor(field: str, value: Any) -> None:
    p = policy(4)
    descriptor = selected_policy_contract(p.version, p.generator_version)
    with pytest.raises(ValueError):
        SelectedPolicyContractV1.model_validate(descriptor.model_copy(update={field: value}))


@pytest.mark.parametrize(
    "field,value",
    [
        ("unsupported_data", "impute"),
        ("forecast", "available"),
        ("native_writes", "available"),
        ("advertising_writes_enabled", True),
        ("version", b"inlet.descriptive-review.v4"),
        ("generator_version", "inlet.descriptive-planning.v5"),
        ("spending_authority", "approved"),
    ],
)
def test_copied_policy(field: str, value: Any) -> None:
    p = policy(4)
    with pytest.raises(ValueError):
        assert_selected_composition_policy(
            p.model_copy(update={field: value}),
            ticket_policy_version=p.version,
            ticket_policy_digest=p.digest(),
        )


def test_wrong_digest_and_other_canonical_policy() -> None:
    p = policy(4)
    for digest in ("0" * 64, p.digest().encode(), policy(5).digest()):
        with pytest.raises(ValueError):
            assert_selected_ticket_policy(p.version, digest)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        assert_selected_composition_policy(
            policy(5), ticket_policy_version=p.version, ticket_policy_digest=p.digest()
        )


def test_registration_unchanged() -> None:
    assert (
        reporting_capability(policy(4).version, policy(4).generator_version).local_witness_kind
        == "local_reporting_v3"
    )
    with pytest.raises(ValueError):
        reporting_capability(policy(5).version, policy(5).generator_version)


@pytest.mark.parametrize("first", ["documents", "selected_policy_contract"])
def test_fresh_import_order(first: str) -> None:
    second = "documents" if first == "selected_policy_contract" else "selected_policy_contract"
    subprocess.run(
        [
            sys.executable,
            "-c",
            f"import app.planning_documents.{first}; import app.planning_documents.{second}",
        ],
        check=True,
        capture_output=True,
        timeout=30,
    )
