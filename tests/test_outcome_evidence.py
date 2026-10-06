"""Pure synthetic observations and existing commerce snapshots; no provider access."""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, localcontext

import pytest
from app.commerce.models import CommerceSnapshot, CommerceStore
from app.outcomes.commerce import project_commerce_snapshot
from app.outcomes.contracts import (
    AccountScope,
    ActionBinding,
    ComparisonPolicy,
    Confounder,
    Coverage,
    EvaluationInput,
    MetricBasis,
    Observation,
    ReceiptInput,
    SourceScope,
    Window,
)
from app.outcomes.evaluator import canonical, evaluate, fingerprint
from pydantic import ValidationError

NOW = datetime(2026, 10, 6, tzinfo=UTC)


def fixture() -> EvaluationInput:
    account = AccountScope(
        workspace_id=1,
        platform="google_ads",
        connection_id=2,
        account_id=3,
        external_advertiser_id="1234567890",
        connection_version="generation_4",
        generation=4,
    )
    action = ActionBinding(
        action_id="action",
        action_digest="a" * 64,
        account=account,
        operation="budget_change",
        mandate_id="mandate",
        mandate_revision=1,
        mandate_digest="b" * 64,
        goal_id="goal",
        goal_revision=1,
        goal_digest="c" * 64,
    )
    receipt = ReceiptInput(
        mode="synthetic",
        binding=action,
        request_digest="d" * 64,
        receipt_digest="e" * 64,
        outcome="verified_effect",
        dispatched_at=datetime(2026, 10, 3, tzinfo=UTC),
        observed_at=datetime(2026, 10, 3, tzinfo=UTC),
        effective_upper_bound=datetime(2026, 10, 3, tzinfo=UTC),
    )
    basis = MetricBasis(
        definition="synthetic_revenue",
        definition_digest="f" * 64,
        currency="USD",
        unit="micros",
        grain="account",
        entity_id="3",
        time_zone="UTC",
        time_basis="cumulative",
        attribution="platform_reported",
        attribution_digest="1" * 64,
        maturity_policy="fixture_maturity",
    )
    source = SourceScope(
        workspace_id=1,
        provider="google_ads",
        connection_id=2,
        source_id="3",
        generation=4,
        account=account,
    )

    def observation(start: date, end: date, value: int) -> Observation:
        return Observation(
            source=source,
            basis=basis,
            window=Window.local(start, end, "UTC"),
            snapshot_id=start.isoformat(),
            snapshot_digest="2" * 64,
            data_revision=1,
            as_of=NOW,
            value=Decimal(value),
            privacy="available",
            coverage=Coverage(
                complete=True,
                covered_days=tuple(start + timedelta(days=i) for i in range((end - start).days)),
                zero_days=(),
                mature_through=end - timedelta(days=1),
                fresh_through=NOW,
                correction_state="settled_as_of",
            ),
        )

    return EvaluationInput(
        action=action,
        receipt=receipt,
        before=observation(date(2026, 10, 1), date(2026, 10, 3), 100),
        after=observation(date(2026, 10, 3), date(2026, 10, 5), 120),
        policy=ComparisonPolicy(
            version="fixture_v1",
            as_of=NOW,
            max_source_age_seconds=86400,
            washout_seconds=0,
            calendar_policy="equal_local_days",
        ),
    )


def change(item: EvaluationInput, *path: str, value: object) -> EvaluationInput:
    data = item.model_dump()
    target = data
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    return EvaluationInput.model_validate(data)


def test_deterministic_frozen_observation_without_causal_or_spend_claim() -> None:
    inputs = fixture()
    result = evaluate(inputs)
    assert result.status == "synthetic_comparable"
    assert result.absolute_difference == 20 and result.relative_difference == Decimal("0.2")
    assert result.causal_lift is None and result.spending_authority == "none"
    assert result.interpretation == "observational_only" and "synthetic_only" in result.warnings
    assert fingerprint(result) == fingerprint(
        evaluate(EvaluationInput.model_validate(inputs.model_dump()))
    )
    with pytest.raises(ValidationError):
        inputs.before.basis.currency = "EUR"  # type: ignore[misc]  # Prove runtime freezing.
    copy = inputs.model_dump()
    copy["before"]["basis"]["currency"] = "EUR"
    assert inputs.before.basis.currency == "USD"
    with localcontext() as context:
        context.prec = 2
        assert evaluate(inputs) == result


@pytest.mark.parametrize(
    ("path", "value", "reason"),
    [
        (("after", "source", "workspace_id"), 2, "scope_mismatch"),
        (("after", "source", "generation"), 5, "generation_changed"),
        (("after", "source", "generation"), None, "generation_unknown"),
        (("after", "basis", "currency"), "EUR", "currency_mismatch"),
        (("after", "basis", "definition"), "new_definition", "metric_definition_changed"),
        (("after", "basis", "attribution_digest"), "3" * 64, "attribution_changed"),
        (("after", "basis", "attribution_digest"), None, "measurement_contract_unavailable"),
        (("after", "coverage", "mature_through"), date(2026, 10, 3), "window_not_mature"),
        (("after", "coverage", "covered_days"), (date(2026, 10, 3),), "missing_coverage"),
        (("after", "coverage", "fresh_through"), NOW - timedelta(days=2), "stale_source"),
        (("after", "coverage", "correction_state"), "pending", "source_correction_pending"),
        (("after", "basis", "maturity_policy"), None, "maturity_policy_unavailable"),
        (("after", "as_of"), NOW - timedelta(seconds=1), "unequal_as_of"),
        (("after", "privacy"), "invalidated", "privacy_suppressed_source"),
        (("after", "value"), None, "measurement_unavailable"),
        (("receipt", "binding", "goal_revision"), 2, "scope_mismatch"),
    ],
)
def test_missing_or_changed_basis_fails_closed(
    path: tuple[str, ...], value: object, reason: str
) -> None:
    inputs = fixture()
    if path == ("after", "source", "workspace_id"):
        # Keep source model structurally valid while violating the action's owner.
        data = inputs.model_dump()
        data["after"]["source"]["account"]["workspace_id"] = 2
        data["after"]["source"]["workspace_id"] = 2
        modified = EvaluationInput.model_validate(data)
    else:
        modified = change(inputs, *path, value=value)
    result = evaluate(modified)
    assert result.status == "insufficient" and reason in result.reasons
    assert result.absolute_difference is None and result.relative_difference is None
    assert result.input_digest != evaluate(inputs).input_digest
    if reason in {"scope_mismatch", "privacy_suppressed_source"}:
        assert result.before_value is None and result.after_value is None


@pytest.mark.parametrize("value,warning", [(0, "baseline_zero"), (-10, "baseline_negative")])
def test_zero_and_negative_baselines_keep_absolute_values(value: int, warning: str) -> None:
    inputs = change(fixture(), "before", "value", value=value)
    result = evaluate(inputs)
    assert result.absolute_difference == 120 - value and result.relative_difference is None
    assert warning in result.warnings
    missing = evaluate(change(inputs, "before", "value", value=None))
    assert missing.absolute_difference is None and "measurement_unavailable" in missing.reasons


def test_production_receipt_not_invented_and_paused_creation_is_not_activation() -> None:
    inputs = fixture()
    unknown = ReceiptInput(mode="unavailable_production", binding=inputs.action, outcome="unknown")
    result = evaluate(inputs.model_copy(update={"receipt": unknown}))
    assert "production_receipt_lineage_unavailable" in result.reasons
    with pytest.raises(ValidationError):
        ReceiptInput(
            mode="unavailable_production", binding=inputs.action, outcome="verified_effect"
        )
    action = inputs.action.model_copy(update={"operation": "new_campaign"})
    created = inputs.model_copy(
        update={"action": action, "receipt": inputs.receipt.model_copy(update={"binding": action})}
    )
    assert "activation_unverified" in evaluate(created).reasons
    for outcome, reason in [
        ("unknown", "effect_unverified"),
        ("conflict", "effect_conflict"),
        ("verified_no_effect", "verified_no_effect"),
    ]:
        data = inputs.model_dump()
        data["receipt"].update(outcome=outcome, effective_upper_bound=None)
        assert reason in evaluate(EvaluationInput.model_validate(data)).reasons


def test_dst_uses_local_days_and_explicit_utc_boundaries() -> None:
    window = Window.local(date(2026, 3, 8), date(2026, 3, 9), "America/New_York")
    assert window.end_utc - window.start_utc == timedelta(hours=23)
    assert (window.end - window.start).days == 1
    data = window.model_dump()
    data["end_utc"] = window.start_utc + timedelta(days=1)
    with pytest.raises(ValidationError):
        Window.model_validate(data)


def test_corrections_confounders_and_semantic_hash_order() -> None:
    inputs = fixture()
    revised = change(inputs, "after", "data_revision", value=2)
    assert "source_revision_changed" in evaluate(revised).warnings
    assert evaluate(revised).input_digest != evaluate(inputs).input_digest
    superseded = revised.model_copy(update={"supersedes": evaluate(inputs).input_digest})
    assert evaluate(superseded).input_digest != evaluate(revised).input_digest
    overlap = inputs.model_copy(
        update={"confounders": (Confounder(code="overlapping_actions", evidence="observed"),)}
    )
    assert "overlapping_actions" in evaluate(overlap).reasons
    reordered = change(
        inputs,
        "before",
        "coverage",
        "covered_days",
        value=tuple(reversed(inputs.before.coverage.covered_days)),
    )
    assert fingerprint(reordered) == fingerprint(inputs)
    assert canonical(Decimal("-0.000")) == canonical(Decimal(0))


def test_existing_commerce_projection_is_context_not_manufactured_lineage() -> None:
    store = CommerceStore(
        id="a" * 32,
        workspace_id=1,
        connection_id=2,
        shop_key="shop",
        shop_domain="fixture.invalid",
        currency="USD",
        time_zone="UTC",
        status="active",
        revision=4,
    )
    window = {
        "start": "2026-10-01",
        "end": "2026-10-03",
        "time_basis": "cumulative",
        "currency": "USD",
        "time_zone": "UTC",
    }
    result = {
        "source": "shopify",
        "store_id": store.id,
        "definition": "shopify_merchandise_net_sales_v1",
        "window": window,
        "currency": "USD",
        "time_zone": "UTC",
        "revision": 4,
        "as_of": NOW.isoformat(),
        "source_watermark": NOW.isoformat(),
        "quality": "complete",
        "reasons": [],
        "net_sales_micros": 100,
        "raw_customer_secret": "must not copy",
    }
    snapshot = CommerceSnapshot(
        id="b" * 32,
        store_id=store.id,
        starts_at=datetime(2026, 10, 1, tzinfo=UTC),
        ends_at=datetime(2026, 10, 3, tzinfo=UTC),
        as_of=NOW,
        revision=4,
        result=result,
    )
    projected = project_commerce_snapshot(snapshot, store, workspace_id=1, privacy="available")
    assert projected.value == 100 and projected.basis.attribution == "not_applicable_store_total"
    assert projected.source.generation is None and projected.coverage.covered_days == ()
    assert "historical_manifest_unavailable" in projected.coverage.reasons
    assert projected.basis.maturity_policy is None
    assert "must not copy" not in projected.model_dump_json()
    assert (
        project_commerce_snapshot(snapshot, store, workspace_id=1, privacy="invalidated").value
        is None
    )
    store.revision = 5
    corrected = project_commerce_snapshot(snapshot, store, workspace_id=1, privacy="available")
    assert (
        corrected.data_revision == 4 and "source_correction_pending" in corrected.coverage.reasons
    )
    with pytest.raises(ValueError, match="owner mismatch"):
        project_commerce_snapshot(snapshot, store, workspace_id=2, privacy="available")


def test_temporal_misalignment_and_missing_watermark() -> None:
    inputs = fixture()
    delayed = change(inputs, "policy", "washout_seconds", value=1)
    assert "window_not_comparable" in evaluate(delayed).reasons
    future = change(inputs, "policy", "as_of", value=NOW - timedelta(days=2))
    assert "window_not_closed" in evaluate(future).reasons
    stale = change(inputs, "after", "coverage", "fresh_through", value=None)
    assert "stale_source" in evaluate(stale).reasons
    false_zero = change(
        inputs, "after", "coverage", "zero_days", value=inputs.after.coverage.covered_days
    )
    assert "contradictory_coverage" in evaluate(false_zero).reasons
    valid_zero = change(false_zero, "after", "value", value=0)
    assert evaluate(valid_zero).absolute_difference == -100
    bad = inputs.after.window.model_copy(update={"start_utc": NOW})
    with pytest.raises(ValidationError):
        evaluate(
            inputs.model_copy(update={"after": inputs.after.model_copy(update={"window": bad})})
        )


def test_calendar_months_preserve_actual_lengths_and_dst() -> None:
    inputs = fixture()
    data = inputs.model_dump()
    before = Window.local(date(2026, 2, 1), date(2026, 3, 1), "America/New_York")
    after = Window.local(date(2026, 3, 1), date(2026, 4, 1), "America/New_York")
    for key, window in [("before", before), ("after", after)]:
        data[key]["window"] = window.model_dump()
        data[key]["basis"].update(time_zone="America/New_York", time_basis="calendar_month")
        data[key]["coverage"].update(
            covered_days=tuple(
                window.start + timedelta(days=i) for i in range((window.end - window.start).days)
            ),
            mature_through=window.end - timedelta(days=1),
        )
    data["receipt"].update(
        dispatched_at=before.end_utc,
        observed_at=before.end_utc,
        effective_upper_bound=before.end_utc,
    )
    data["policy"]["calendar_policy"] = "whole_calendar_months"
    months = EvaluationInput.model_validate(data)
    result = evaluate(months)
    assert result.status == "synthetic_comparable" and "unequal_window_days" in result.warnings
    assert after.end_utc - after.start_utc == timedelta(days=31, hours=-1)
    assert (
        "unequal_window_days"
        in evaluate(change(months, "policy", "calendar_policy", value="equal_local_days")).reasons
    )


def test_currency_or_generation_does_not_hide_foreign_connection() -> None:
    inputs = fixture()
    altered = change(inputs, "after", "source", "connection_id", value=99)
    result = evaluate(altered)
    assert "scope_mismatch" in result.reasons and result.after_value is None
    altered = change(inputs, "after", "source", "provider", value="meta_ads")
    assert "scope_mismatch" in evaluate(altered).reasons


@pytest.mark.parametrize(
    "unit,value", [("decimal_count", Decimal("1.25")), ("micros", Decimal("1.25"))]
)
def test_fractional_conversion_counts_preserve_unit(unit: str, value: Decimal) -> None:
    data = fixture().model_dump()
    data["before"]["basis"]["unit"] = unit
    data["before"]["value"] = value
    if unit == "micros":
        with pytest.raises(ValidationError):
            EvaluationInput.model_validate(data)
    else:
        assert EvaluationInput.model_validate(data).before.value == value


def test_timezone_change_and_unknown_privacy_are_explicit() -> None:
    inputs = fixture()
    data = inputs.model_dump()
    data["after"]["basis"]["time_zone"] = "America/New_York"
    data["after"]["window"] = Window.local(
        date(2026, 10, 3), date(2026, 10, 5), "America/New_York"
    ).model_dump()
    assert "timezone_mismatch" in evaluate(EvaluationInput.model_validate(data)).reasons
    unknown = evaluate(change(inputs, "after", "privacy", value="unknown"))
    assert "privacy_state_unknown" in unknown.reasons
    assert unknown.after_value is None and unknown.before_value is None
    cross_entity = evaluate(change(inputs, "after", "basis", "entity_id", value="999"))
    assert "scope_mismatch" in cross_entity.reasons
