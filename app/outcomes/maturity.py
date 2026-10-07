"""Disabled production policy registry and pure operational qualification.

No HTTP/client proof, provider producer, action timing or recommendation authority.
"""

from collections.abc import Callable
from datetime import date, timedelta
from typing import Annotated, Literal
from zoneinfo import ZoneInfo

from pydantic import AwareDatetime, Field, model_validator

from app.commerce.evidence import digest
from app.outcomes.contracts import Code, Digest, Frozen, Positive, Window
from app.outcomes.reconciliation_contracts import ReconciliationObservations

Seconds = Annotated[int, Field(strict=True, ge=0, le=366 * 86400)]


class OperationalMaturityPolicy(Frozen):
    schema_version: Literal["inlet.operational-maturity-policy.v1"] = (
        "inlet.operational-maturity-policy.v1"
    )
    policy_id: Code
    version: Positive
    metric_definition_digest: Digest
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    time_zone: str = Field(min_length=1, max_length=64)
    allowed_assurance: tuple[Literal["independent_full_window"], ...] = Field(
        min_length=1, max_length=1
    )
    minimum_age_seconds: Seconds
    minimum_observations: int = Field(strict=True, ge=2, le=16)
    minimum_spacing_seconds: int = Field(strict=True, ge=1, le=366 * 86400)
    maximum_source_age_seconds: Seconds
    maximum_day_revision_micros: int = Field(strict=True, ge=0, le=10**18)

    @model_validator(mode="after")
    def valid_zone(self) -> "OperationalMaturityPolicy":
        ZoneInfo(self.time_zone)
        return self

    @property
    def policy_digest(self) -> str:
        return digest(self.model_dump(mode="json"))


class MaturityScope(Frozen):
    workspace_id: Positive
    store_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    generation: Positive
    privacy_epoch: Positive
    goal_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    goal_revision: Positive
    goal_digest: Digest
    metric_definition_digest: Digest
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    time_zone: str = Field(min_length=1, max_length=64)


class MaturityContext(Frozen):
    environment: Literal["contract_test", "live"]
    scope: MaturityScope
    evaluated_at: AwareDatetime
    source_current: bool


class ReconciledDay(Frozen):
    day: date
    state: Literal["complete", "missing", "suppressed"]
    value_micros: int | None = Field(strict=True)
    entry_count: int | None = Field(strict=True, ge=0)

    @model_validator(mode="after")
    def complete_value(self) -> "ReconciledDay":
        if (self.state == "complete") != (
            self.value_micros is not None and self.entry_count is not None
        ):
            raise ValueError("complete days require factual value and count")
        if self.state != "complete" and (
            self.value_micros is not None or self.entry_count is not None
        ):
            raise ValueError("missing days cannot carry values")
        return self


class IndependentObservation(Frozen):
    completion_digest: Digest
    observed_at: AwareDatetime
    fresh_through: AwareDatetime
    days: tuple[ReconciledDay, ...] = Field(min_length=1, max_length=400)
    correction_state: Literal["settled_as_of", "unresolved"]


class IndependentReconciliationEvidence(Frozen):
    schema_version: Literal["inlet.independent-reconciliation-facts.v1"] = (
        "inlet.independent-reconciliation-facts.v1"
    )
    # Server-produced facts only; never accepted by a customer HTTP endpoint.
    environment: Literal["contract_test", "live"]
    assurance: Literal["independent_full_window"] = "independent_full_window"
    scope: MaturityScope
    start: date
    end: date
    observations: tuple[IndependentObservation, ...] = Field(max_length=16)
    truncated: bool
    unreadable_observations: int = Field(strict=True, ge=0, le=16)

    @model_validator(mode="after")
    def bounded(self) -> "IndependentReconciliationEvidence":
        if not 0 < (self.end - self.start).days <= 400:
            raise ValueError("invalid bounded local window")
        return self


class OperationalMaturityResult(Frozen):
    schema_version: Literal["inlet.operational-maturity-evaluation.v1"] = (
        "inlet.operational-maturity-evaluation.v1"
    )
    status: Literal["operational_as_of", "insufficient"]
    environment: Literal["contract_test", "live"]
    policy_digest: Digest | None
    evidence_digest: Digest | None
    context_digest: Digest
    evaluated_at: AwareDatetime
    supporting_completions: tuple[Digest, ...] = Field(max_length=16)
    reasons: tuple[Code, ...]
    authoritative_finality: Literal["unavailable"] = "unavailable"
    action_attribution: Literal["unavailable"] = "unavailable"
    recommendation_update: None = None
    spending_authority: Literal["none"] = "none"


def policy_for(scope: MaturityScope) -> OperationalMaturityPolicy | None:
    """Production registry deliberately contains no installed policy."""
    return None


def evaluate_operational_maturity(
    policy: OperationalMaturityPolicy | None,
    evidence: IndependentReconciliationEvidence | ReconciliationObservations,
    context: MaturityContext,
) -> OperationalMaturityResult:
    context = MaturityContext.model_validate(context.model_dump())
    if policy is not None:
        policy = OperationalMaturityPolicy.model_validate(policy.model_dump())
    evidence = type(evidence).model_validate(evidence.model_dump())
    reasons: set[str] = set()
    completions: tuple[str, ...] = ()
    if policy is None:
        reasons.add("maturity_policy_unavailable")
    if isinstance(evidence, ReconciliationObservations):
        # Hard boundary: no permissive policy can upgrade incremental imports.
        reasons.add("independent_reconciliation_unavailable")
    else:
        if evidence.environment != context.environment:
            reasons.add("evidence_environment_mismatch")
        if evidence.scope != context.scope:
            reasons.add("owned_scope_changed")
        if not context.source_current:
            reasons.add("source_not_current")
        if evidence.truncated or evidence.unreadable_observations:
            reasons.add("incomplete_observation_sample")
        window = Window.local(evidence.start, evidence.end, context.scope.time_zone)
        expected_days = {
            evidence.start + timedelta(days=i) for i in range((evidence.end - evidence.start).days)
        }
        if window.end_utc > context.evaluated_at:
            reasons.add("window_not_closed")
        records = evidence.observations
        completions = tuple(item.completion_digest for item in records)
        if len(set(completions)) != len(completions):
            reasons.add("duplicate_completion")
        if policy is not None:
            if (policy.metric_definition_digest, policy.currency, policy.time_zone) != (
                context.scope.metric_definition_digest,
                context.scope.currency,
                context.scope.time_zone,
            ):
                reasons.add("policy_basis_mismatch")
            if evidence.assurance not in policy.allowed_assurance:
                reasons.add("unsupported_assurance")
            if len(records) < policy.minimum_observations:
                reasons.add("insufficient_independent_observations")
        for index, record in enumerate(records):
            days = {day.day: day for day in record.days}
            if (
                len(days) != len(record.days)
                or set(days) != expected_days
                or any(day.state != "complete" for day in record.days)
            ):
                reasons.add("day_coverage_incomplete")
            if record.correction_state != "settled_as_of":
                reasons.add("correction_unresolved")
            if (
                not window.end_utc
                <= record.fresh_through
                <= record.observed_at
                <= context.evaluated_at
            ):
                reasons.add("invalid_observation_time")
            if policy is not None:
                if (
                    record.observed_at - window.end_utc
                ).total_seconds() < policy.minimum_age_seconds:
                    reasons.add("minimum_age_unmet")
                # Each claimed independent rescan must have timely factual coverage.
                if (
                    record.observed_at - record.fresh_through
                ).total_seconds() > policy.maximum_source_age_seconds:
                    reasons.add("stale_observation")
            if index:
                prior = records[index - 1]
                spacing = (record.observed_at - prior.observed_at).total_seconds()
                if spacing <= 0 or record.fresh_through <= prior.fresh_through:
                    reasons.add("observation_order_invalid")
                if policy is not None and spacing < policy.minimum_spacing_seconds:
                    reasons.add("minimum_spacing_unmet")
        if records and policy is not None:
            if (
                context.evaluated_at - records[-1].fresh_through
            ).total_seconds() > policy.maximum_source_age_seconds:
                reasons.add("source_stale")
            # Compare the full sampled envelope, not merely adjacent deltas that can drift.
            for day in expected_days:
                values = [
                    item.value_micros
                    for record in records
                    for item in record.days
                    if item.day == day
                    and item.state == "complete"
                    and item.value_micros is not None
                ]
                counts = {
                    item.entry_count
                    for record in records
                    for item in record.days
                    if item.day == day and item.state == "complete"
                }
                if values and max(values) - min(values) > policy.maximum_day_revision_micros:
                    reasons.add("day_revision_exceeds_policy")
                if len(counts) > 1:
                    reasons.add("entry_count_revised")
    return OperationalMaturityResult(
        status="insufficient" if reasons else "operational_as_of",
        environment=context.environment,
        policy_digest=policy.policy_digest if policy else None,
        evidence_digest=digest(evidence.model_dump(mode="json")),
        context_digest=digest(context.model_dump(mode="json")),
        evaluated_at=context.evaluated_at,
        supporting_completions=completions if not reasons else (),
        reasons=tuple(sorted(reasons)),
    )


EvidenceProducer = Callable[[MaturityContext, date, date], IndependentReconciliationEvidence]
PolicyLookup = Callable[[MaturityScope], OperationalMaturityPolicy | None]
ProducerLookup = Callable[[MaturityScope], EvidenceProducer | None]


def producer_for(scope: MaturityScope) -> EvidenceProducer | None:
    """No genuine independent-reconciliation producer is registered."""
    return None


def evaluate_registered_maturity(
    context: MaturityContext,
    start: date,
    end: date,
    *,
    policies: PolicyLookup = policy_for,
    producers: ProducerLookup = producer_for,
) -> OperationalMaturityResult:
    """Server-only dependency boundary; live registrations are currently absent.

    A future owned producer must reauthorize and fence current source/goal/privacy
    through collection and return. This pure package provides no DB/auth adapter.
    """
    context = MaturityContext.model_validate(context.model_dump())
    if not 0 < (end - start).days <= 400:
        raise ValueError("invalid bounded local window")
    policy, producer = policies(context.scope), producers(context.scope)
    if policy is None or producer is None:
        return OperationalMaturityResult(
            status="insufficient",
            environment=context.environment,
            policy_digest=policy.policy_digest if policy else None,
            evidence_digest=None,
            context_digest=digest(context.model_dump(mode="json")),
            evaluated_at=context.evaluated_at,
            supporting_completions=(),
            reasons=tuple(
                reason
                for reason, absent in (
                    ("maturity_policy_unavailable", policy is None),
                    ("independent_producer_unavailable", producer is None),
                )
                if absent
            ),
        )
    evidence = producer(context, start, end)
    if (evidence.start, evidence.end) != (start, end):
        raise ValueError("producer window mismatch")
    return evaluate_operational_maturity(policy, evidence, context)
