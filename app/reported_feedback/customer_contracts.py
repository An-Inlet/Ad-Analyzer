"""Safe customer descriptions of the separate operational rule, never authority."""

from datetime import date
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import AwareDatetime, Field, model_validator

from app.initial_planning.contracts import Frozen
from app.reported_feedback.automatic_contracts import ReportedRuleParametersViewV1
from app.reported_feedback.candidate_contracts import ReportedRuleCandidateV1, ReportedRulePolicyV1
from app.reported_feedback.contracts import OperationalReportedComparisonV1, ReportedWindowSummaryV1

CanonicalDecimal = Annotated[str, Field(pattern=r"^(0|[1-9][0-9]*)(\.[0-9]*[1-9])?$")]


def decimal_text(value: Decimal) -> str:
    if value == 0:
        return "0"
    raw = format(value, "f")
    return raw.rstrip("0").rstrip(".") if "." in raw else raw


def rule_parameters(policy: ReportedRulePolicyV1) -> ReportedRuleParametersViewV1:
    p = policy.feedback_policy
    return ReportedRuleParametersViewV1(
        original_change=p.original_change,
        favorable_direction=p.favorable_direction,
        unfavorable_direction=p.unfavorable_direction,
        neutral_band=decimal_text(p.neutral_band),
        weight=decimal_text(p.weight),
        contribution_clamp=decimal_text(p.contribution_clamp),
        aggregate_clamp=decimal_text(p.aggregate_clamp),
        maximum_nominal_adjustment_micros=p.maximum_preview_delta_micros,
        minimum_distinct_original_attempts=1,
        evidence_lifetime_seconds=p.lifetime_seconds,
    )


class ReportedWindowViewV1(Frozen):
    starts_on: date
    ends_on: date
    missing_dates: tuple[date, ...] = Field(max_length=56)
    spend_micros: Annotated[str, Field(pattern=r"^(0|[1-9][0-9]*)$")] | None
    conversions: CanonicalDecimal | None
    reported_cpa_micros: CanonicalDecimal | None
    revisions_within_tolerance: bool

    @model_validator(mode="after")
    def interval(self) -> "ReportedWindowViewV1":
        if (
            not 0 <= (self.ends_on - self.starts_on).days < 56
            or any(not self.starts_on <= day <= self.ends_on for day in self.missing_dates)
            or len(set(self.missing_dates)) != len(self.missing_dates)
        ):
            raise ValueError("invalid reported display interval")
        return self


class ReportedRuleBasisDetailsV1(Frozen):
    schema_version: Literal["inlet.reported-rule-basis-view.v1"] = (
        "inlet.reported-rule-basis-view.v1"
    )
    basis: Literal["operational_reported_efficiency_rule"] = "operational_reported_efficiency_rule"
    label: Literal["Reported-efficiency rule"] = "Reported-efficiency rule"
    environment: Literal["contract_test", "live"]
    rule_parameters: ReportedRuleParametersViewV1
    before: ReportedWindowViewV1
    after: ReportedWindowViewV1
    original_attempt_count: Literal[1] = 1
    reported_completion_count: int = Field(ge=4, le=16)
    nominal_before_micros: int = Field(gt=0, le=10**15)
    nominal_after_micros: int | None = Field(gt=0, le=10**15)
    proposed_delta_micros: int | None
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    account_timezone: str = Field(min_length=1, max_length=64)
    observed_at: AwareDatetime
    expires_at: AwareDatetime
    correction_status: Literal["as_observed_unsettled"] = "as_observed_unsettled"
    interpretation: Literal["configuration_associated_reported_efficiency_not_causal"] = (
        "configuration_associated_reported_efficiency_not_causal"
    )
    delivery_time: Literal["unavailable"] = "unavailable"
    causal_lift: Literal["unavailable"] = "unavailable"
    spending_authority: Literal["none"] = "none"

    @model_validator(mode="after")
    def exact_delta(self) -> "ReportedRuleBasisDetailsV1":
        expected = (
            self.nominal_after_micros - self.nominal_before_micros
            if self.nominal_after_micros is not None
            else None
        )
        if self.proposed_delta_micros != expected or self.expires_at <= self.observed_at:
            raise ValueError("invalid reported nominal proposal")
        return self


def basis_details(
    decision: ReportedRuleCandidateV1,
    comparison: OperationalReportedComparisonV1,
    policy: ReportedRulePolicyV1,
) -> ReportedRuleBasisDetailsV1:
    if (
        policy.digest() != decision.policy_digest
        or comparison.id != decision.evidence.comparison_id
        or comparison.digest() != decision.evidence.comparison_digest
        or comparison.before != decision.evidence.before
        or comparison.after != decision.evidence.after
    ):
        raise ValueError("reported display source changed")

    def window(value: ReportedWindowSummaryV1) -> ReportedWindowViewV1:
        return ReportedWindowViewV1(
            starts_on=value.window.starts_on,
            ends_on=value.window.ends_on,
            missing_dates=value.missing_dates,
            spend_micros=str(value.spend_micros) if value.spend_micros is not None else None,
            conversions=decimal_text(value.conversions) if value.conversions is not None else None,
            reported_cpa_micros=decimal_text(value.reported_cpa_micros)
            if value.reported_cpa_micros is not None
            else None,
            revisions_within_tolerance=value.revisions_within_tolerance,
        )

    return ReportedRuleBasisDetailsV1(
        environment=decision.evidence.environment,
        rule_parameters=rule_parameters(policy),
        before=window(decision.evidence.before),
        after=window(decision.evidence.after),
        reported_completion_count=decision.evidence.reported_completion_count,
        nominal_before_micros=decision.nominal_before_micros,
        nominal_after_micros=decision.nominal_after_micros,
        proposed_delta_micros=(decision.nominal_after_micros - decision.nominal_before_micros)
        if decision.nominal_after_micros is not None
        else None,
        currency=comparison.anchor.cohort.currency,
        account_timezone=comparison.anchor.cohort.time_zone,
        observed_at=decision.observed_at,
        expires_at=decision.expires_at,
    )
