"""Deterministic aggregate comparison. No database, network or executor dependency."""

import hashlib
import json
from datetime import UTC, date, datetime, timedelta
from decimal import ROUND_HALF_EVEN, Decimal, localcontext
from typing import Any

from app.outcomes.contracts import Evaluation, EvaluationInput, Frozen


def canonical(value: Any) -> Any:
    if isinstance(value, Frozen):
        return canonical(value.model_dump())
    if isinstance(value, Decimal):
        if value == 0:
            return "0"
        decimal_text = format(value, "f")
        return (
            decimal_text.rstrip("0").rstrip(".") if "." in decimal_text else decimal_text
        ) or "0"
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        result = {key: canonical(item) for key, item in value.items()}
        for key in ("covered_days", "zero_days", "reasons", "warnings", "confounders"):
            if key in result:
                result[key] = sorted(result[key], key=lambda item: json.dumps(item, sort_keys=True))
        return result
    if isinstance(value, tuple | list):
        return [canonical(item) for item in value]
    return value


def fingerprint(value: Frozen) -> str:
    body = json.dumps(canonical(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(b"inlet.action-outcome-evidence.v1\0" + body.encode()).hexdigest()


def evaluate(inputs: EvaluationInput) -> Evaluation:
    # Revalidate detached values so unchecked model_copy/model_construct inputs
    # cannot bypass nested model invariants at this public consumer boundary.
    inputs = EvaluationInput.model_validate(inputs.model_dump())
    reasons: set[str] = set()
    warnings = {"synthetic_only", "confounder_coverage_unknown"}
    action, receipt = inputs.action, inputs.receipt
    before, after, policy = inputs.before, inputs.after, inputs.policy
    if receipt.mode == "unavailable_production":
        reasons.add("production_receipt_lineage_unavailable")
        warnings.discard("synthetic_only")
    if receipt.binding != action:
        reasons.add("scope_mismatch")
    if receipt.outcome != "verified_effect":
        reasons.add(
            {
                "unknown": "effect_unverified",
                "conflict": "effect_conflict",
                "verified_no_effect": "verified_no_effect",
            }[receipt.outcome]
        )
    if receipt.request_digest is None or receipt.receipt_digest is None:
        reasons.add("receipt_unavailable")
    if receipt.observed_at is None or receipt.observed_at > policy.as_of:
        reasons.add("receipt_unavailable")
    if action.operation in {"new_campaign", "creative"} and not receipt.activation_verified:
        reasons.add("activation_unverified")
    if receipt.effective_upper_bound is None or receipt.dispatched_at is None:
        reasons.add("effective_time_unknown")
    else:
        if (
            before.window.end_utc > receipt.dispatched_at
            or after.window.start_utc
            < receipt.effective_upper_bound + timedelta(seconds=policy.washout_seconds)
        ):
            reasons.add("window_not_comparable")
    if before.source != after.source:
        reasons.add("source_identity_changed")
    for observation in (before, after):
        if observation.source.workspace_id != action.account.workspace_id or (
            observation.source.account is not None and observation.source.account != action.account
        ):
            reasons.add("scope_mismatch")
        if observation.source.generation is None or action.account.generation is None:
            reasons.add("generation_unknown")
        if (
            observation.source.account
            and observation.source.generation != observation.source.account.generation
        ):
            reasons.add("generation_changed")
        if observation.source.account and (
            observation.source.connection_id != observation.source.account.connection_id
            or observation.source.provider not in {observation.source.account.platform, "unified"}
        ):
            reasons.add("scope_mismatch")
        if (
            observation.basis.grain == "store"
            and observation.basis.entity_id != observation.source.source_id
        ):
            reasons.add("scope_mismatch")
        if (
            observation.basis.grain == "account"
            and observation.source.account
            and observation.basis.entity_id != str(observation.source.account.account_id)
        ):
            reasons.add("scope_mismatch")
        if observation.privacy != "available":
            reasons.add(
                "privacy_suppressed_source"
                if observation.privacy == "invalidated"
                else "privacy_state_unknown"
            )
        if observation.as_of != policy.as_of:
            reasons.add("unequal_as_of")
        if observation.value is None:
            reasons.add("measurement_unavailable")
        window, coverage = observation.window, observation.coverage
        expected_days = {
            window.start + timedelta(days=n) for n in range((window.end - window.start).days)
        }
        if not coverage.complete or set(coverage.covered_days) != expected_days:
            reasons.add("missing_coverage")
        reasons.update(coverage.reasons)
        if set(coverage.zero_days) == expected_days and observation.value not in {None, Decimal(0)}:
            reasons.add("contradictory_coverage")
        if (
            observation.basis.attribution != "not_applicable_store_total"
            and observation.basis.attribution_digest is None
        ):
            reasons.add("measurement_contract_unavailable")
        if observation.basis.maturity_policy is None:
            reasons.add("maturity_policy_unavailable")
        if coverage.mature_through is None or coverage.mature_through < window.end - timedelta(
            days=1
        ):
            reasons.add("window_not_mature")
        if window.end_utc > policy.as_of:
            reasons.add("window_not_closed")
        if coverage.fresh_through is None or not timedelta(
            0
        ) <= policy.as_of - coverage.fresh_through <= timedelta(
            seconds=policy.max_source_age_seconds
        ):
            reasons.add("stale_source")
        elif coverage.fresh_through < window.end_utc:
            reasons.add("incomplete_window")
        if coverage.correction_state != "settled_as_of":
            reasons.add("source_correction_pending")
        if observation.basis.grain == "store":
            warnings.add("store_total_context_only")
        if observation.basis.time_basis == "calendar_month":
            next_month = (window.start.replace(day=28) + timedelta(days=4)).replace(day=1)
            if window.start.day != 1 or window.end != next_month:
                reasons.add("window_not_comparable")
        if policy.calendar_policy == "whole_calendar_months":
            next_month = (window.start.replace(day=28) + timedelta(days=4)).replace(day=1)
            if (
                window.start.day != 1
                or window.end != next_month
                or observation.basis.time_basis != "calendar_month"
            ):
                reasons.add("window_not_comparable")
    for field, reason in (
        ("definition", "metric_definition_changed"),
        ("definition_digest", "metric_definition_changed"),
        ("currency", "currency_mismatch"),
        ("unit", "metric_definition_changed"),
        ("grain", "scope_mismatch"),
        ("entity_id", "scope_mismatch"),
        ("time_zone", "timezone_mismatch"),
        ("time_basis", "window_not_comparable"),
        ("attribution", "attribution_changed"),
        ("attribution_digest", "attribution_changed"),
        ("maturity_policy", "maturity_policy_changed"),
    ):
        if getattr(before.basis, field) != getattr(after.basis, field):
            reasons.add(reason)
    if before.window.end_utc > after.window.start_utc:
        reasons.add("window_not_comparable")
    durations = (
        (before.window.end - before.window.start).days,
        (after.window.end - after.window.start).days,
    )
    if durations[0] != durations[1]:
        (reasons if policy.calendar_policy == "equal_local_days" else warnings).add(
            "unequal_window_days"
        )
    if before.data_revision != after.data_revision:
        warnings.add("source_revision_changed")
    for confounder in inputs.confounders:
        warnings.add(confounder.code)
        if confounder.code == "overlapping_actions" and confounder.evidence != "unknown":
            reasons.add("overlapping_actions")
    redact = bool(
        reasons & {"scope_mismatch", "privacy_suppressed_source", "privacy_state_unknown"}
    )
    prior, later = (None, None) if redact else (before.value, after.value)
    delta, ratio = None, None
    if not reasons and prior is not None and later is not None:
        # Fixed context makes results independent of the caller's Decimal context.
        with localcontext() as context:
            context.prec = 60
            context.rounding = ROUND_HALF_EVEN
            delta = later - prior
            if prior > 0:
                ratio = delta / prior
            else:
                warnings.add("baseline_zero" if prior == 0 else "baseline_negative")
    return Evaluation(
        input_digest=fingerprint(inputs),
        status="insufficient" if reasons else "synthetic_comparable",
        reasons=tuple(sorted(reasons)),
        warnings=tuple(sorted(warnings)),
        before_value=prior,
        after_value=later,
        absolute_difference=delta,
        relative_difference=ratio,
    )
