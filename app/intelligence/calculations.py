from datetime import date, timedelta
from decimal import Decimal
from math import sqrt
from typing import Any

from app.intelligence.schemas import Experiment, ScenarioRequest, Strategy


def divide(numerator: int | float | Decimal, denominator: int | float | Decimal) -> float | None:
    return float(numerator) / float(denominator) if denominator else None


def budget_pacing(
    strategy: Strategy,
    today: date,
    spend_micros: int | None,
    reserve_micros: int,
    *,
    data_complete: bool,
) -> dict[str, Any]:
    total_days = (strategy.period_end - strategy.period_start).days + 1
    elapsed_days = max(0, min(total_days, (today - strategy.period_start).days))
    remaining_days = total_days - elapsed_days
    remaining = None if spend_micros is None else max(0, strategy.budget_micros - spend_micros)
    available = None if remaining is None else max(0, remaining - reserve_micros)
    projected = (
        round(spend_micros / elapsed_days * total_days)
        if data_complete and elapsed_days and spend_micros is not None
        else None
    )
    return {
        "currency_code": strategy.currency_code,
        "period_start": strategy.period_start.isoformat(),
        "period_end": strategy.period_end.isoformat(),
        "budget_micros": strategy.budget_micros,
        "spend_micros": spend_micros,
        "remaining_micros": remaining,
        "reserved_micros": reserve_micros,
        "available_micros": available,
        "reserve_shortfall_micros": max(0, reserve_micros - remaining)
        if remaining is not None
        else None,
        "overspend_micros": max(0, spend_micros - strategy.budget_micros)
        if spend_micros is not None
        else None,
        "elapsed_days": elapsed_days,
        "remaining_days": remaining_days,
        "time_elapsed_ratio": elapsed_days / total_days,
        "spend_ratio": divide(spend_micros, strategy.budget_micros)
        if spend_micros is not None
        else None,
        "projected_spend_micros": projected,
        "suggested_daily_ceiling_micros": round(available / remaining_days)
        if available is not None and remaining_days
        else None,
        "data_complete": data_complete,
        "basis": (
            "Completed advertising days in the plan period; today's partial spend is excluded."
        ),
        "projection_basis": (
            "Current daily pace held constant; this is an estimate, not a spending cap."
        ),
    }


def scenario_forecast(
    strategy: Strategy,
    pacing: dict[str, Any],
    request: ScenarioRequest,
    *,
    historical_value: float | None,
    historical_cost_micros: int,
    sample_size: int,
    ready: bool,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "proposed_budget_micros": request.proposed_budget_micros,
        "budget_change_micros": request.proposed_budget_micros - strategy.budget_micros,
        "requires_financial_approval": request.proposed_budget_micros > strategy.budget_micros,
        "primary_metric": strategy.primary_metric,
        "currency_code": strategy.currency_code,
        "response_elasticity": float(request.response_elasticity),
        "uncertainty_bps": request.uncertainty_bps,
        "basis": (
            "Future outcomes from the remaining unreserved budget, using historical mature cohorts."
        ),
        "range_basis": (
            "Operator-selected sensitivity range; not a statistical confidence interval."
        ),
        "expected": None,
        "low": None,
        "high": None,
        "status": "insufficient_evidence",
        "changes_applied": False,
    }
    spent = pacing["spend_micros"]
    if spent is None:
        result["status"] = "currency_or_spend_unavailable"
        return result
    if request.proposed_budget_micros < spent + pacing["reserved_micros"]:
        result["status"] = "below_spend_and_reservations"
        return result
    if not pacing["remaining_days"]:
        result.update(status="period_complete", expected=0, low=0, high=0)
        return result
    if not ready or not pacing["data_complete"] or sample_size < strategy.minimum_outcomes:
        return result
    if historical_value is None or historical_cost_micros <= 0:
        return result
    baseline_remaining = pacing["available_micros"]
    proposed_remaining = request.proposed_budget_micros - spent - pacing["reserved_micros"]
    if proposed_remaining == 0:
        result.update(status="modeled", expected=0, low=0, high=0)
        return result
    if not baseline_remaining:
        result["status"] = "no_baseline_budget"
        return result
    multiplier = (proposed_remaining / baseline_remaining) ** float(request.response_elasticity)
    expected = historical_value / historical_cost_micros * baseline_remaining * multiplier
    if strategy.primary_metric == "contribution_profit":
        # Revenue responds to spend; the proposed spend itself is a known cost.
        historical_contribution = historical_value + historical_cost_micros / 1_000_000
        expected = (
            historical_contribution / historical_cost_micros * baseline_remaining * multiplier
            - proposed_remaining / 1_000_000
        )
    uncertainty = request.uncertainty_bps / 10_000
    low, high = sorted((expected * (1 - uncertainty), expected * (1 + uncertainty)))
    result.update(
        status="modeled", expected=round(expected, 2), low=round(low, 2), high=round(high, 2)
    )
    return result


def allocation_preview(
    strategy: Strategy,
    pacing: dict[str, Any],
    campaigns: list[dict[str, Any]],
    *,
    ready: bool,
) -> dict[str, Any]:
    """A bounded hypothesis for a fixed budget, never a live campaign budget edit."""
    result: dict[str, Any] = {
        "status": "insufficient_evidence",
        "rows": [],
        "changes_applied": False,
        "budget_change_micros": 0,
        "approval_required": True,
        "basis": (
            "Baseline shares follow mature historical campaign spend, not live budget settings. "
            "Preview moves at most 10% of a donor allocation and 10% of a recipient allocation. "
            "It holds the total unreserved budget constant; future improvement is unproven."
        ),
    }
    available = pacing["available_micros"]
    candidates = [c for c in campaigns if c["spend_micros"] > 0]
    if not ready or not pacing["data_complete"] or not available or not pacing["remaining_days"]:
        return result
    if len(candidates) < 2:
        return result
    total_spend = sum(c["spend_micros"] for c in candidates)
    rows = []
    for candidate in candidates:
        amount = available * candidate["spend_micros"] // total_spend
        rows.append({**candidate, "baseline_micros": amount, "proposed_micros": amount})
    remainder = available - sum(r["baseline_micros"] for r in rows)
    rows[0]["baseline_micros"] += remainder
    rows[0]["proposed_micros"] += remainder
    eligible = sorted(
        [r for r in rows if r["sample"] >= strategy.minimum_outcomes],
        key=lambda r: (r["goal_value"] / r["spend_micros"], r["id"]),
    )
    result.update(rows=rows, status="maintain_shares")
    if len(eligible) < 2:
        result["status"] = "insufficient_campaign_outcomes"
        return result
    donor, recipient = eligible[0], eligible[-1]
    donor_return = donor["goal_value"] / donor["spend_micros"]
    recipient_return = recipient["goal_value"] / recipient["spend_micros"]
    if recipient_return <= max(0, donor_return) * 1.25:
        return result
    transfer = min(donor["baseline_micros"], recipient["baseline_micros"]) // 10
    if transfer:
        donor["proposed_micros"] -= transfer
        recipient["proposed_micros"] += transfer
        result.update(status="review_transfer", transfer_micros=transfer)
    return result


def _wilson(successes: int, units: int) -> tuple[float, float]:
    if not units:
        return 0.0, 1.0
    z = 1.959963984540054
    rate = successes / units
    denominator = 1 + z * z / units
    center = (rate + z * z / (2 * units)) / denominator
    half = z * sqrt(rate * (1 - rate) / units + z * z / (4 * units * units)) / denominator
    return max(0, center - half), min(1, center + half)


def experiment_result(experiment: Experiment, today: date) -> dict[str, Any]:
    review_on = experiment.ends_on + timedelta(days=experiment.measurement_delay_days)
    control_rate = divide(experiment.control_outcomes, experiment.control_units)
    treatment_rate = divide(experiment.treatment_outcomes, experiment.treatment_units)
    result: dict[str, Any] = {
        "status": "collecting",
        "review_on": review_on.isoformat(),
        "control_rate": control_rate,
        "treatment_rate": treatment_rate,
        "absolute_lift": None,
        "relative_lift": None,
        "interval_low": None,
        "interval_high": None,
        "evidence_basis": (
            "Operator-supplied aggregate counts of unique assigned units "
            "with at most one outcome per unit."
        ),
        "causal_status": (
            "Randomization declared by the operator; assignment has not "
            "been independently verified."
        )
        if experiment.randomized_assignment
        else "Observational comparison; cannot establish causality.",
    }
    if experiment.status == "cancelled":
        result["status"] = "cancelled"
        return result
    if control_rate is None or treatment_rate is None:
        return result
    difference = treatment_rate - control_rate
    result.update(absolute_lift=difference, relative_lift=divide(difference, control_rate))
    if experiment.status != "completed" or today < review_on:
        result["status"] = "awaiting_completion_and_maturity"
        return result
    if experiment.observed_through is None or not review_on <= experiment.observed_through <= today:
        result["status"] = "observation_period_incomplete"
        return result
    if not experiment.randomized_assignment:
        result["status"] = "observational_only"
        return result
    if (
        min(experiment.control_units, experiment.treatment_units)
        < experiment.minimum_sample_per_arm
    ):
        result["status"] = "insufficient_sample"
        return result
    if min(experiment.control_outcomes, experiment.treatment_outcomes) < 5:
        result["status"] = "insufficient_outcomes"
        return result
    control_low, control_high = _wilson(experiment.control_outcomes, experiment.control_units)
    treatment_low, treatment_high = _wilson(
        experiment.treatment_outcomes, experiment.treatment_units
    )
    # Newcombe interval for the difference between two independent proportions.
    lower = difference - sqrt(
        (treatment_rate - treatment_low) ** 2 + (control_high - control_rate) ** 2
    )
    upper = difference + sqrt(
        (treatment_high - treatment_rate) ** 2 + (control_rate - control_low) ** 2
    )
    minimum_effect = experiment.minimum_lift_bps / 10_000
    status = "inconclusive"
    if lower > minimum_effect:
        status = "treatment_promising"
    elif upper < -minimum_effect:
        status = "control_promising"
    result.update(
        status=status,
        interval_low=lower,
        interval_high=upper,
        interval_basis=(
            "95% interval for the absolute rate difference; independent randomized units assumed."
        ),
    )
    return result
