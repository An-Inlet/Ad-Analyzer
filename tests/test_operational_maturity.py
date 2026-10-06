"""Synthetic independent rescans exercise generic logic; no production installation."""

from datetime import UTC, date, datetime, timedelta

import pytest
from app.outcomes.maturity import (
    IndependentObservation,
    IndependentReconciliationEvidence,
    MaturityContext,
    MaturityScope,
    OperationalMaturityPolicy,
    ReconciledDay,
    evaluate_operational_maturity,
    evaluate_registered_maturity,
    policy_for,
    producer_for,
)
from pydantic import ValidationError


def fixture() -> tuple[
    OperationalMaturityPolicy, IndependentReconciliationEvidence, MaturityContext
]:
    scope = MaturityScope(
        workspace_id=1,
        store_id="1" * 32,
        generation=1,
        privacy_epoch=1,
        goal_id="2" * 32,
        goal_revision=1,
        goal_digest="3" * 64,
        metric_definition_digest="4" * 64,
        currency="USD",
        time_zone="America/New_York",
    )
    # Explicit test values, not proposed/installed operational defaults.
    policy = OperationalMaturityPolicy(
        policy_id="synthetic_fixture",
        version=1,
        metric_definition_digest="4" * 64,
        currency="USD",
        time_zone=scope.time_zone,
        allowed_assurance=("independent_full_window",),
        minimum_age_seconds=3600,
        minimum_observations=2,
        minimum_spacing_seconds=3600,
        maximum_source_age_seconds=7200,
        maximum_day_revision_micros=0,
    )
    at = datetime(2026, 3, 9, 6, tzinfo=UTC)
    day = ReconciledDay(day=date(2026, 3, 8), state="complete", value_micros=0, entry_count=0)
    evidence = IndependentReconciliationEvidence(
        environment="contract_test",
        scope=scope,
        start=day.day,
        end=date(2026, 3, 9),
        observations=tuple(
            IndependentObservation(
                completion_digest=str(i) * 64,
                observed_at=at + timedelta(hours=i - 1),
                fresh_through=at + timedelta(hours=i - 1),
                days=(day,),
                correction_state="settled_as_of",
            )
            for i in (1, 2)
        ),
        truncated=False,
        unreadable_observations=0,
    )
    context = MaturityContext(
        environment="contract_test",
        scope=scope,
        evaluated_at=at + timedelta(hours=2),
        source_current=True,
    )
    return policy, evidence, context


def test_exact_boundaries_dst_zero_and_disabled_registry() -> None:
    policy, evidence, context = fixture()
    result = evaluate_operational_maturity(policy, evidence, context)
    assert result.status == "operational_as_of" and result.environment == "contract_test"
    assert len(result.supporting_completions) == 2
    assert result.authoritative_finality == result.action_attribution == "unavailable"
    assert result.recommendation_update is None and result.spending_authority == "none"
    assert policy_for(context.scope) is None
    assert producer_for(context.scope) is None
    default = evaluate_registered_maturity(context, evidence.start, evidence.end)
    assert default.status == "insufficient"
    assert set(default.reasons) == {
        "maturity_policy_unavailable",
        "independent_producer_unavailable",
    }
    assert default.evidence_digest is None
    # Test server registration can reuse the exact evaluator, without installing anything globally.
    assert (
        evaluate_registered_maturity(
            context,
            evidence.start,
            evidence.end,
            policies=lambda _: policy,
            producers=lambda _: lambda *_: evidence,
        )
        == result
    )
    assert evaluate_operational_maturity(None, evidence, context).status == "insufficient"
    with pytest.raises(ValidationError):
        policy.version = 2  # type: ignore[misc]  # Deliberate frozen-model mutation test.


@pytest.mark.parametrize(
    "field,value",
    [
        ("workspace_id", 2),
        ("generation", 2),
        ("privacy_epoch", 2),
        ("goal_revision", 2),
        ("goal_digest", "5" * 64),
        ("store_id", "5" * 32),
    ],
)
def test_current_scope_fences(field: str, value: int | str) -> None:
    policy, evidence, context = fixture()
    context = context.model_copy(update={"scope": context.scope.model_copy(update={field: value})})
    assert "owned_scope_changed" in evaluate_operational_maturity(policy, evidence, context).reasons


@pytest.mark.parametrize(
    "case,reason",
    [
        ("live", "evidence_environment_mismatch"),
        ("stale", "source_stale"),
        ("closed", "window_not_closed"),
        ("inactive", "source_not_current"),
        ("truncated", "incomplete_observation_sample"),
        ("unreadable", "incomplete_observation_sample"),
        ("duplicate", "duplicate_completion"),
        ("order", "observation_order_invalid"),
        ("spacing", "minimum_spacing_unmet"),
        ("age", "minimum_age_unmet"),
        ("missing", "day_coverage_incomplete"),
        ("suppressed", "day_coverage_incomplete"),
        ("extra_day", "day_coverage_incomplete"),
        ("duplicate_day", "day_coverage_incomplete"),
        ("revision", "day_revision_exceeds_policy"),
        ("count", "entry_count_revised"),
        ("unresolved", "correction_unresolved"),
        ("future", "invalid_observation_time"),
        ("basis", "policy_basis_mismatch"),
        ("few", "insufficient_independent_observations"),
    ],
)
def test_unqualified_facts_fail_closed(case: str, reason: str) -> None:
    policy, evidence, context = fixture()
    records = list(evidence.observations)
    if case == "live":
        context = context.model_copy(update={"environment": "live"})
    elif case == "stale":
        context = context.model_copy(
            update={"evaluated_at": context.evaluated_at + timedelta(days=1)}
        )
    elif case == "closed":
        context = context.model_copy(
            update={"evaluated_at": context.evaluated_at - timedelta(days=1)}
        )
    elif case == "inactive":
        context = context.model_copy(update={"source_current": False})
    elif case in {"truncated", "unreadable"}:
        evidence = evidence.model_copy(
            update={
                "truncated": case == "truncated",
                "unreadable_observations": int(case == "unreadable"),
            }
        )
    elif case == "duplicate":
        records[1] = records[1].model_copy(
            update={"completion_digest": records[0].completion_digest}
        )
    elif case == "order":
        records.reverse()
    elif case == "spacing":
        policy = policy.model_copy(update={"minimum_spacing_seconds": 3601})
    elif case == "age":
        policy = policy.model_copy(update={"minimum_age_seconds": 7201})
    elif case in {"missing", "suppressed", "revision", "count", "extra_day", "duplicate_day"}:
        day = records[1].days[0]
        if case in {"missing", "suppressed"}:
            day = day.model_copy(update={"state": case, "value_micros": None, "entry_count": None})
        elif case == "revision":
            day = day.model_copy(update={"value_micros": -1})
        elif case == "count":
            day = day.model_copy(update={"entry_count": 1})
        days: tuple[ReconciledDay, ...] = (day,)
        if case in {"extra_day", "duplicate_day"}:
            days += (
                day.model_copy(update={"day": day.day + timedelta(days=1)})
                if case == "extra_day"
                else day,
            )
        records[1] = records[1].model_copy(update={"days": days})
    elif case == "unresolved":
        records[1] = records[1].model_copy(update={"correction_state": "unresolved"})
    elif case == "future":
        records[1] = records[1].model_copy(
            update={"fresh_through": context.evaluated_at + timedelta(seconds=1)}
        )
    elif case == "basis":
        policy = policy.model_copy(update={"currency": "EUR"})
    elif case == "few":
        records.pop()
    evidence = evidence.model_copy(update={"observations": tuple(records)})
    result = evaluate_operational_maturity(policy, evidence, context)
    assert result.status == "insufficient" and reason in result.reasons
    assert result.supporting_completions == ()


def test_policy_cannot_allow_weak_imports_and_full_envelope_prevents_drift() -> None:
    policy, evidence, context = fixture()
    with pytest.raises(ValidationError):
        OperationalMaturityPolicy.model_validate(
            {**policy.model_dump(), "allowed_assurance": ("terminal_updated_at_import",)}
        )
    policy = policy.model_copy(update={"maximum_day_revision_micros": 1})
    first, second = evidence.observations
    second = second.model_copy(
        update={"days": (second.days[0].model_copy(update={"value_micros": 1}),)}
    )
    third = second.model_copy(
        update={
            "completion_digest": "3" * 64,
            "observed_at": context.evaluated_at,
            "fresh_through": context.evaluated_at,
            "days": (second.days[0].model_copy(update={"value_micros": 2}),),
        }
    )
    evidence = evidence.model_copy(update={"observations": (first, second, third)})
    assert (
        "day_revision_exceeds_policy"
        in evaluate_operational_maturity(policy, evidence, context).reasons
    )


def test_registry_never_calls_source_without_policy_and_live_rejects_fixture() -> None:
    policy, evidence, context = fixture()
    calls: list[bool] = []

    def produce(*_: object) -> IndependentReconciliationEvidence:
        calls.append(True)
        return evidence

    result = evaluate_registered_maturity(
        context, evidence.start, evidence.end, producers=lambda _: produce
    )
    assert result.status == "insufficient" and calls == []
    live = context.model_copy(update={"environment": "live"})
    result = evaluate_registered_maturity(
        live,
        evidence.start,
        evidence.end,
        policies=lambda _: policy,
        producers=lambda _: produce,
    )
    assert calls == [True] and result.status == "insufficient"
    assert "evidence_environment_mismatch" in result.reasons
