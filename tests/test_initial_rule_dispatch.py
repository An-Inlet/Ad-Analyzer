"""Initial operational documents cannot be parsed as prior-action or learning evidence."""

from datetime import timedelta

import pytest
from app.initial_planning.automatic_compiler import compile_initial_rule
from app.initial_planning.automatic_contracts import InitialReportedRuleWorkV1
from app.optimization_candidates.contracts import CandidateDecision, CandidatePolicy, CandidateWork
from app.optimization_candidates.documents import (
    parse_decision_document,
    parse_policy_document,
    parse_work_document,
)
from app.optimization_candidates.selection_contracts import SelectionProvenance
from app.reported_feedback.candidate_contracts import ReportedRuleCandidateV1, ReportedRuleWorkV1
from pydantic import BaseModel, ValidationError

from tests.test_initial_rule_candidates import fixture


def test_strict_initial_dispatch_preserves_exact_documents_and_rejects_aliases() -> None:
    observation, policy, mandate, now = fixture()
    work = InitialReportedRuleWorkV1(
        scope=observation.scope,
        policy=policy,
        basis=observation.evidence.basis,
        selection=SelectionProvenance(
            actor_id="a" * 32,
            scope_digest=observation.scope.digest(),
            policy_digest=policy.digest(),
            catalog_digest="b" * 64,
            option_id="c" * 64,
            state_digest=observation.state.digest(),
            manifest_digest="d" * 64,
            observed_at=now,
            expires_at=now + timedelta(seconds=60),
        ),
    )
    decision = compile_initial_rule(observation, policy, mandate, 0, 0, now)
    for value, parser in [
        (work, parse_work_document),
        (policy, parse_policy_document),
        (decision, parse_decision_document),
    ]:
        parsed = parser(value.model_dump(mode="json"))
        assert parsed == value and parsed.model_dump_json() == value.model_dump_json()
        assert parsed.digest() == value.digest()
    incompatible: list[tuple[type[BaseModel], BaseModel]] = [
        (CandidateDecision, decision),
        (ReportedRuleCandidateV1, decision),
        (CandidateWork, work),
        (ReportedRuleWorkV1, work),
        (CandidatePolicy, policy),
    ]
    for model, incompatible_value in incompatible:
        with pytest.raises(ValidationError):
            model.model_validate_json(incompatible_value.model_dump_json())
    body = work.model_dump(mode="json")
    body["schema_version"] = "inlet.reported-rule-work.v1"
    with pytest.raises(ValidationError):
        parse_work_document(body)
