"""Initial operational suggestions retain ordinary mandate bounds and no authority."""

from datetime import datetime, timedelta

import pytest
from app.initial_planning.automatic_compiler import compile_initial_rule
from app.initial_planning.automatic_contracts import (
    InitialObservationReferenceV1,
    InitialReportedRuleCandidateV1,
    InitialReportedRuleEvidenceV1,
    InitialReportedRuleObservationV1,
    InitialReportedRulePolicyV1,
    InitialRuleBasisV1,
)
from app.optimization_candidates.contracts import CandidateEvidence
from app.publication.execution_contracts import ProviderMandatePolicy
from pydantic import ValidationError

from tests.test_initial_calibration import policy
from tests.test_reported_rule_candidates import fixture as native_fixture


def fixture() -> tuple[
    InitialReportedRuleObservationV1, InitialReportedRulePolicyV1, ProviderMandatePolicy, datetime
]:
    native, _, mandate, now = native_fixture()
    rule = InitialReportedRulePolicyV1(
        workspace_id=1,
        environment="contract_test",
        policy_id="c" * 32,
        revision=1,
        policy_family="d" * 32,
        planning_profile_digest="e" * 64,
        initial=policy(),
        allowed_operation="meta_budget_set_v1",
        maximum_candidate_age_seconds=120,
    )
    basis = InitialRuleBasisV1(
        preview_id="1" * 32,
        preview_digest="1" * 64,
        calibration_id="2" * 32,
        calibration_digest="2" * 64,
        selected_observation_id="3" * 32,
        objective_digest="3" * 64,
        goal_digest=native.scope.goal_digest,
        observation_references=(
            InitialObservationReferenceV1(
                observation_id="3" * 32,
                digest="4" * 64,
            ),
        ),
        opportunity_id="5" * 32,
        semantic_key_digest="5" * 64,
    )
    evidence = InitialReportedRuleEvidenceV1(
        scope_digest=native.scope.digest(),
        environment="contract_test",
        source_reference=basis.opportunity_id,
        basis=basis,
        rule_policy_digest=rule.digest(),
        direction="increase",
        signed_delta_micros=500_000,
        training_windows=1,
        holdout_windows=1,
        observed_at=now,
        expires_at=now + timedelta(seconds=120),
    )
    return (
        InitialReportedRuleObservationV1(
            scope=native.scope,
            state=native.state,
            evidence=evidence,
        ),
        rule,
        mandate,
        now,
    )


def test_initial_is_not_prior_action_learning_or_execution_authority() -> None:
    observation, rule, mandate, now = fixture()
    result = compile_initial_rule(observation, rule, mandate, 0, 0, now)
    assert result.status == "suggested" and result.action is not None
    assert result.action.amount_micros == 50_500_000
    assert observation.scope.source.attempt_id is None
    assert result.spending_authority == "none" and not result.dispatch_ready
    assert not result.evidence.empirical_qualification
    assert InitialReportedRuleCandidateV1.model_validate_json(result.model_dump_json()) == result
    with pytest.raises(ValidationError):
        CandidateEvidence.model_validate_json(result.evidence.model_dump_json())


@pytest.mark.parametrize("case", ["stale", "actions", "quantum", "partial", "policy"])
def test_existing_authority_and_precision_bounds(case: str) -> None:
    observation, rule, mandate, now = fixture()
    actions = 0
    if case == "stale":
        now = observation.evidence.expires_at
    elif case == "actions":
        actions = mandate.action_limit
    elif case == "quantum":
        observation = observation.model_copy(
            update={
                "evidence": observation.evidence.model_copy(
                    update={"signed_delta_micros": 500_001},
                )
            }
        )
    elif case == "partial":
        observation = observation.model_copy(
            update={
                "state": observation.state.model_copy(
                    update={"complete": False},
                )
            }
        )
    else:
        rule = rule.model_copy(update={"revision": 2})
        with pytest.raises(ValueError, match="policy commitment"):
            compile_initial_rule(observation, rule, mandate, 0, actions, now)
        return
    result = compile_initial_rule(observation, rule, mandate, 0, actions, now)
    assert result.status == "blocked" and result.action is None


def test_cumulative_clip_does_not_increase_overall_limit() -> None:
    observation, rule, mandate, now = fixture()
    original = mandate.model_dump_json()
    result = compile_initial_rule(
        observation,
        rule,
        mandate,
        mandate.positive_change_cap_micros - 100_000,
        0,
        now,
    )
    assert result.action is not None and result.action.amount_micros == 50_100_000
    assert mandate.model_dump_json() == original


@pytest.mark.parametrize(
    "field,value",
    [
        ("direction", "decrease"),
        ("signed_delta_micros", True),
        ("empirical_qualification", True),
        ("source_reference", "a" * 32),
    ],
)
def test_operational_evidence_rejects_false_claims(field: str, value: object) -> None:
    observation, _, _, _ = fixture()
    data = observation.evidence.model_dump()
    data[field] = value
    with pytest.raises(ValidationError):
        InitialReportedRuleEvidenceV1.model_validate(data)
