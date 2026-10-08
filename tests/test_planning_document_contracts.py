"""Pure structural acceptance; no claim of expert recommendation quality."""

from copy import deepcopy
from typing import Any

import pytest
from app.planning_documents.common import fingerprint
from app.planning_documents.documents import PlanVersion
from app.planning_documents.events import CustomerDecision, ManualAssertion, ReadObservedStatus
from pydantic import ValidationError


def packet(platform: str = "google_ads", ceiling: int = 100) -> dict[str, Any]:
    window = dict(
        start="2026-10-01",
        end="2026-11-01",
        currency="USD",
        time_zone="UTC",
        time_basis="calendar_month",
    )
    definition = dict(
        metric="shopify_merchandise_net_sales_v1",
        store_id="a" * 32,
        target_micros=1000,
        target_window=window,
        baseline_window={**window, "start": "2026-09-01", "end": "2026-10-01"},
        deadline="2026-10-31",
        budget_micros=ceiling,
        budget_start="2026-10-01",
        budget_end="2026-11-01",
        aggressiveness="balanced",
    )
    account = dict(
        workspace_id=1, account_id=1, connection_id=1, platform=platform, connection_version="v1"
    )
    period = dict(
        starts_on="2026-10-01", ends_on_exclusive="2026-11-01", currency="USD", time_zone="UTC"
    )
    target = dict(
        account=account,
        canonical_entity_key="a" * 64,
        selection_key="b" * 64,
        catalog_evidence_key="catalog",
        kind="campaign",
        display_name="Campaign",
        budget_owner_key=None,
    )
    inputs = dict(
        workspace_id=1,
        plan_id="b" * 32,
        revision=1,
        goal=dict(
            workspace_id=1,
            goal_id="c" * 32,
            revision=1,
            definition=definition,
            definition_digest=fingerprint("goal-definition", definition),
            confirmation_reference="d" * 32,
        ),
        accounts=[account],
        budget_period=period,
        total_ceiling_micros=ceiling,
        aggressiveness="balanced",
        reporting_window=dict(
            starts_at="2026-09-01T00:00:00Z", ends_at_exclusive="2026-10-01T00:00:00Z"
        ),
        comparison_window=None,
        milestone="Grow net sales",
        product_offer=None,
        constraints=[],
        fixed_allocations=[],
        assumptions=[],
        excluded_entity_keys=[],
        created_by="a" * 32,
        created_at="2026-10-01T01:00:00Z",
    )
    evidence = dict(
        key="catalog",
        workspace_id=1,
        kind="native_catalog",
        account=account,
        document_schema="inlet.planning-target-catalog.v2",
        document_digest="c" * 64,
        source_binding_digest="d" * 64,
        source_revision="v1",
        privacy_revision=0,
        reporting_window=None,
        observation_started_at="2026-10-01T01:00:00Z",
        observed_at="2026-10-01T01:00:01Z",
        expires_at="2026-10-01T02:00:00Z",
        coverage="partial",
        declared_scope="Campaigns",
        reasons=["partial_scope"],
        metric_basis="Native settings only; no performance inference",
    )
    action = dict(
        key="inspect",
        priority=1,
        kind="investigate",
        target=target,
        title="Inspect campaign",
        rationale="Partial scope requires customer review",
        evidence_keys=["catalog"],
        assumption_keys=[],
        prerequisites=[],
        manual_steps=["Inspect native settings"],
        expected_effect="Resolve uncertainty",
        limitations=["No forecast"],
        native_budget=None,
        proposed_fields=[],
        conflicts=[],
        measurement_criterion="Inspect settings",
    )
    scenario = dict(
        key="baseline",
        title="Hold allocation",
        period=period,
        ceiling_micros=ceiling,
        allocations=[],
        unallocated_micros=ceiling,
        assumptions=[],
    )
    return dict(
        inputs=inputs,
        version=1,
        parent_digest=None,
        generator_version="test-v1",
        policy_version="test-v1",
        readiness="needs_input",
        section_limitations=["Partial inventory"],
        generated_by="a" * 32,
        generated_at="2026-10-01T01:00:02Z",
        valid_until="2026-10-01T02:00:00Z",
        evidence=[evidence],
        actions=[action],
        scenarios=[scenario],
        briefs=[],
        summary="Review supported account",
        limitations=["Partial inventory"],
    )


@pytest.mark.parametrize("platform", ["google_ads", "meta_ads", "tiktok_ads"])
@pytest.mark.parametrize("ceiling", [0, 100])
def test_roundtrip_and_independent_alternatives(platform: str, ceiling: int) -> None:
    data = packet(platform, ceiling)
    data["scenarios"].append({**data["scenarios"][0], "key": "alternative"})
    value = PlanVersion.model_validate(data)
    assert PlanVersion.model_validate_json(value.model_dump_json()) == value
    assert value.spending_authority == "none"
    assert value.scenarios[1].ceiling_micros == ceiling


@pytest.mark.parametrize(
    "case",
    [
        "budget",
        "aggressiveness",
        "period",
        "workspace",
        "expiry",
        "missing_evidence",
        "cycle",
        "excluded",
        "scenario_sum",
        "scenario_currency",
        "authority",
        "forecast",
        "unsafe_nested",
        "ancestry",
    ],
)
def test_invalid_aggregate(case: str) -> None:
    data = packet()
    if case == "budget":
        data["inputs"]["total_ceiling_micros"] = 101
    elif case == "aggressiveness":
        data["inputs"]["aggressiveness"] = "assertive"
    elif case == "period":
        data["inputs"]["budget_period"]["ends_on_exclusive"] = "2026-11-02"
    elif case == "workspace":
        data["evidence"][0]["workspace_id"] = 2
    elif case == "expiry":
        data["valid_until"] = "2026-10-01T02:00:01Z"
    elif case == "missing_evidence":
        data["actions"][0]["evidence_keys"] = ["missing"]
    elif case == "cycle":
        data["actions"][0]["prerequisites"] = ["inspect"]
    elif case == "excluded":
        data["inputs"]["excluded_entity_keys"] = ["a" * 64]
    elif case == "scenario_sum":
        data["scenarios"][0]["unallocated_micros"] = 101
    elif case == "scenario_currency":
        data["scenarios"][0]["period"] = {**data["scenarios"][0]["period"], "currency": "EUR"}
    elif case == "authority":
        data["advertising_writes_enabled"] = True
    elif case == "forecast":
        data["scenarios"][0]["forecast"] = 200
    elif case == "unsafe_nested":
        good = PlanVersion.model_validate(data)
        data["inputs"] = good.inputs.model_copy(update={"total_ceiling_micros": True})
    elif case == "ancestry":
        data["version"] = 2
    with pytest.raises(ValidationError):
        PlanVersion.model_validate(data)


def test_shared_owner_cannot_be_allocated_twice() -> None:
    data = packet()
    target = {**data["actions"][0]["target"], "budget_owner_key": "f" * 64}
    allocation = dict(
        key="one",
        target=target,
        amount_micros=50,
        rationale="Explicit split",
        evidence_keys=["catalog"],
    )
    second = deepcopy(allocation)
    second.update(key="two", target={**target, "canonical_entity_key": "e" * 64})
    data["scenarios"][0].update(allocations=[allocation, second], unallocated_micros=0)
    with pytest.raises(ValidationError, match="shared budget"):
        PlanVersion.model_validate(data)


@pytest.mark.parametrize(
    "native",
    [
        dict(reason="Unknown unit", proposed_amount=20),
        dict(
            owner_key="f" * 64,
            evidence_key="catalog",
            unit="micros",
            currency="USD",
            cadence="daily",
            current_amount=10,
            proposed_amount=20,
            delta=10,
        ),
    ],
)
def test_unknown_native_owner_or_unit_never_synthesizes_amount(native: dict[str, Any]) -> None:
    data = packet()
    data["actions"][0].update(kind="budget_review", native_budget=native)
    with pytest.raises(ValidationError):
        PlanVersion.model_validate(data)


def test_decisions_assertions_and_observations_are_separate_exact_version_records() -> None:
    doc = PlanVersion.model_validate(packet())
    binding = dict(
        workspace_id=1,
        plan_id=doc.inputs.plan_id,
        version=1,
        document_digest=doc.digest(),
        action_key="inspect",
        action_digest=doc.actions[0].digest(),
    )
    decision = CustomerDecision.model_validate(
        dict(
            **binding,
            event_id="a" * 32,
            actor_id="a" * 32,
            recorded_at="2026-10-01T01:10:00Z",
            decision="accepted_for_manual_application",
            reason="Customer choice",
            supersedes_event_id=None,
        )
    )
    decision.assert_document(doc)
    with pytest.raises(ValueError, match="exact plan"):
        decision.model_copy(update={"document_digest": "0" * 64}).assert_document(doc)
    assertion = ManualAssertion.model_validate(
        dict(
            **binding,
            event_id="b" * 32,
            actor_id="a" * 32,
            recorded_at="2026-10-01T01:10:00Z",
            reported_applied_at="2026-10-01T01:09:00Z",
            assertion="customer_reports_applied",
            statement="I changed it",
            supersedes_event_id=None,
        )
    )
    assert assertion.verification == "customer_report_only"
    with pytest.raises(ValidationError):
        ReadObservedStatus.model_validate(
            dict(
                **binding,
                event_id="c" * 32,
                observed_at="2026-10-01T01:11:00Z",
                status="matching",
                comparisons=[],
                limitations=["No causal inference"],
            )
        )


def test_fixed_allocations_preserved_by_every_alternative() -> None:
    data = packet()
    target = data["actions"][0]["target"]
    data["inputs"]["fixed_allocations"] = [dict(target=target, amount_micros=40)]
    data["scenarios"][0].update(
        allocations=[
            dict(
                key="fixed",
                target=target,
                amount_micros=40,
                rationale="Customer fixed allocation",
                evidence_keys=["catalog"],
            )
        ],
        unallocated_micros=60,
    )
    PlanVersion.model_validate(data)
    data["scenarios"].append(
        dict(
            **{**data["scenarios"][0], "key": "other", "allocations": [], "unallocated_micros": 100}
        )
    )
    with pytest.raises(ValidationError, match="fixed allocations"):
        PlanVersion.model_validate(data)


def test_new_brand_account_prerequisites_need_no_fabricated_entity() -> None:
    data = packet()
    data["actions"][0]["target"] = dict(account=data["inputs"]["accounts"][0], scope="account")
    data["evidence"][0].update(coverage="unavailable", reasons=["empty_native_inventory"])
    doc = PlanVersion.model_validate(data)
    assert doc.readiness == "needs_input"


def test_typed_proposals_and_observed_status_bind_expected_value() -> None:
    data = packet()
    data["actions"][0].update(
        kind="status_review",
        proposed_fields=[
            dict(
                key="delivery",
                availability="supported",
                current=dict(field="delivery_status", value="enabled"),
                proposed=dict(field="delivery_status", value="paused"),
                evidence_key="catalog",
                verification_criterion="Refresh native status and compare",
            )
        ],
    )
    doc = PlanVersion.model_validate(data)
    observed: dict[str, Any] = dict(
        workspace_id=1,
        plan_id=doc.inputs.plan_id,
        version=1,
        document_digest=doc.digest(),
        action_key="inspect",
        action_digest=doc.actions[0].digest(),
        event_id="a" * 32,
        observed_at="2026-10-01T01:20:00Z",
        status="matching",
        comparisons=[
            dict(
                proposal_key="delivery",
                expected=dict(field="delivery_status", value="paused"),
                observed=dict(field="delivery_status", value="paused"),
                evidence=dict(key="later_status", document_digest="f" * 64),
                unavailable_reason=None,
            )
        ],
        limitations=["No attribution of who changed it"],
    )
    ReadObservedStatus.model_validate(observed).assert_document(doc)
    observed["comparisons"][0]["expected"]["value"] = "enabled"
    observed["status"] = "conflicting"
    with pytest.raises(ValueError, match="expected value"):
        ReadObservedStatus.model_validate(observed).assert_document(doc)


def test_major_native_unit_is_explicitly_unsupported_not_integer_coerced() -> None:
    data = packet("tiktok_ads")
    data["actions"][0]["target"]["budget_owner_key"] = "f" * 64
    data["actions"][0].update(
        kind="budget_review",
        native_budget=dict(
            owner_key="f" * 64,
            evidence_key="catalog",
            unit="major_units",
            currency="USD",
            cadence="daily",
            current_amount=10,
            proposed_amount=20,
            delta=10,
        ),
    )
    with pytest.raises(ValidationError):
        PlanVersion.model_validate(data)


@pytest.mark.parametrize("bad", [0, "false", None])
def test_no_authority_flag_rejects_coercion(bad: object) -> None:
    data = packet()
    data["advertising_writes_enabled"] = bad
    with pytest.raises(ValidationError):
        PlanVersion.model_validate(data)


def test_legacy_nested_goal_is_reparsed_on_reentry_and_digest() -> None:
    doc = PlanVersion.model_validate(packet())
    doc.inputs.goal.definition.budget_micros = True
    with pytest.raises(ValidationError):
        PlanVersion.model_validate(doc)
    with pytest.raises(ValidationError):
        doc.digest()


def test_operational_count_limit() -> None:
    data = packet()
    data["actions"] = [
        {**data["actions"][0], "key": f"action_{i}", "priority": i + 1} for i in range(101)
    ]
    with pytest.raises(ValidationError):
        PlanVersion.model_validate(data)
