"""Distinct authority documents never permit scope widening or timestamp epochs."""

import pytest
from app.session_automation.contracts import (
    CustomerExactApprovalAuthority,
    OptimizationAuthority,
    SemanticDecisionEpoch,
    SessionAutomaticPolicy,
    SessionMandateDecisionAuthority,
)
from pydantic import TypeAdapter, ValidationError


def test_authority_union_cannot_manufacture_manual_approval() -> None:
    parser: TypeAdapter[CustomerExactApprovalAuthority | SessionMandateDecisionAuthority] = (
        TypeAdapter(OptimizationAuthority)
    )
    manual = parser.validate_python({"kind": "customer_exact_approval"})
    automatic = parser.validate_python(
        {"kind": "mandate_automatic_decision", "admission_id": "a" * 32}
    )
    assert isinstance(manual, CustomerExactApprovalAuthority)
    assert isinstance(automatic, SessionMandateDecisionAuthority)
    with pytest.raises(ValidationError):
        parser.validate_python({"kind": "mandate_automatic_decision"})
    with pytest.raises(ValidationError):
        parser.validate_python({"kind": "customer_exact_approval", "admission_id": "a" * 32})


def test_semantic_epoch_has_no_revision_or_timestamp_reset() -> None:
    values = {
        "producer_family": "1" * 32,
        "source_schema": "qualified-source.v1",
        "source_reference": "2" * 32,
        "semantic_digest": "a" * 64,
    }
    epoch = SemanticDecisionEpoch.model_validate(values)
    assert epoch.digest() == SemanticDecisionEpoch.model_validate(values).digest()
    for key in ("observed_at", "policy_revision", "mandate_revision", "connection_version"):
        with pytest.raises(ValidationError):
            SemanticDecisionEpoch.model_validate({**values, key: "new"})


def test_policy_has_no_numeric_defaults_and_budget_only_scope() -> None:
    values = {
        "workspace_id": 1,
        "environment": "contract_test",
        "policy_family": "3" * 32,
        "policy_id": "4" * 32,
        "revision": 1,
        "candidate_policy": {"policy_id": "5" * 32, "revision": 1},
        "candidate_policy_digest": "d" * 64,
        "allowed_operations": ["google_budget_set_v1"],
        "semantic_producer_families": ["6" * 32],
        "lifetime_seconds": 60,
        "cadence_seconds": 10,
    }
    assert SessionAutomaticPolicy.model_validate(values).cadence_seconds == 10
    for key in ("lifetime_seconds", "cadence_seconds", "semantic_producer_families"):
        with pytest.raises(ValidationError):
            SessionAutomaticPolicy.model_validate({k: v for k, v in values.items() if k != key})
    for action in ("google_status_set_v1", "meta_status_set_v1", "create", "activate"):
        with pytest.raises(ValidationError):
            SessionAutomaticPolicy.model_validate({**values, "allowed_operations": [action]})
