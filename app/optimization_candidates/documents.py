"""Strict version dispatch; operational reports never enter legacy learning contracts."""

import json
from typing import Annotated

from pydantic import Field, TypeAdapter

from app.initial_planning.automatic_contracts import (
    InitialReportedRuleCandidateV1,
    InitialReportedRulePolicyV1,
    InitialReportedRuleWorkV1,
)
from app.optimization_candidates.contracts import CandidateDecision, CandidatePolicy, CandidateWork
from app.optimization_candidates.selection_contracts import CandidateWorkV2
from app.reported_feedback.candidate_contracts import (
    ReportedRuleCandidateV1,
    ReportedRulePolicyV1,
    ReportedRuleWorkV1,
)

CandidatePolicyDocument = CandidatePolicy | ReportedRulePolicyV1 | InitialReportedRulePolicyV1
CandidateWorkDocument = (
    CandidateWork | CandidateWorkV2 | ReportedRuleWorkV1 | InitialReportedRuleWorkV1
)
CandidateDecisionDocument = (
    CandidateDecision | ReportedRuleCandidateV1 | InitialReportedRuleCandidateV1
)
WORK_DOCUMENT_ADAPTER: TypeAdapter[CandidateWorkDocument] = TypeAdapter(
    Annotated[CandidateWorkDocument, Field(discriminator="schema_version")]
)
DECISION_DOCUMENT_ADAPTER: TypeAdapter[CandidateDecisionDocument] = TypeAdapter(
    Annotated[CandidateDecisionDocument, Field(discriminator="schema_version")]
)
POLICY_DOCUMENT_ADAPTER: TypeAdapter[CandidatePolicyDocument] = TypeAdapter(
    Annotated[CandidatePolicyDocument, Field(discriminator="schema_version")]
)


def parse_work_document(value: object) -> CandidateWorkDocument:
    return WORK_DOCUMENT_ADAPTER.validate_json(json.dumps(value, allow_nan=False))


def parse_decision_document(value: object) -> CandidateDecisionDocument:
    return DECISION_DOCUMENT_ADAPTER.validate_json(json.dumps(value, allow_nan=False))


def parse_policy_document(value: object) -> CandidatePolicyDocument:
    return POLICY_DOCUMENT_ADAPTER.validate_json(json.dumps(value, allow_nan=False))
