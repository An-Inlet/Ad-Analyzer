from datetime import timedelta
from typing import Any

import pytest
from app.planning_documents.common import fingerprint
from app.planning_documents.composer import (
    GENERATOR_VERSION,
    POLICY_VERSION,
    DescriptivePlanComposer,
    PlanCompositionUnavailable,
    targets,
)
from app.planning_documents.context import PlanInputRevision
from app.planning_documents.documents import PlanVersion
from app.planning_documents.ports import (
    CatalogEvidence,
    ContextEvidence,
    EvidenceBundle,
    PerformanceEvidence,
    PlanningCompositionPolicy,
)

from tests.test_planning_document_ports import performance_data, ready_bundle


def fixture(
    platform: str = "meta", **updates: Any
) -> tuple[PlanInputRevision, EvidenceBundle, PlanningCompositionPolicy]:
    ticket, bundle = ready_bundle()
    if platform != "meta":
        from app.planning_catalog.projection_v2 import project_v2

        from tests.test_planning_metadata_binding import bundle as native_bundle

        inventory, metadata = native_bundle(platform)
        catalog = project_v2(inventory, metadata)
        ref = bundle.catalogs[0].reference.model_dump(mode="python")
        account = dict(
            workspace_id=metadata.workspace_id,
            account_id=metadata.account_id,
            connection_id=metadata.connection_id,
            connection_version=metadata.connection_version,
            platform=metadata.platform,
        )
        ref.update(
            account=account,
            workspace_id=metadata.workspace_id,
            document_digest=catalog.composite_digest,
            source_binding_digest=metadata.source_binding_digest,
            coverage="complete_in_declared_scope"
            if (
                all(c.status == "complete" for c in catalog.native_observation.coverage)
                and all(c.status == "complete" for c in metadata.coverage)
            )
            else "partial",
            reporting_window=dict(
                starts_at=metadata.reporting_starts_at, ends_at_exclusive=metadata.reporting_ends_at
            ),
            observation_started_at=metadata.observation_started_at,
            observed_at=metadata.observed_at,
            expires_at=catalog.expires_at,
        )
        bundle = bundle.model_copy(
            update=dict(catalogs=(CatalogEvidence(reference=ref, catalog=catalog),))
        )
        changed = ticket.inputs.model_dump(mode="python")
        changed.update(
            accounts=[account],
            reporting_window=ref["reporting_window"],
            created_at=metadata.observed_at,
            workspace_id=metadata.workspace_id,
        )
        changed["goal"]["workspace_id"] = metadata.workspace_id
        ticket = ticket.model_copy(
            update=dict(
                inputs=PlanInputRevision.model_validate(changed),
                sources=(
                    ticket.sources[0].model_copy(
                        update=dict(
                            account=account, source_binding_digest=metadata.source_binding_digest
                        )
                    ),
                ),
            )
        )
    inputs = PlanInputRevision.model_validate(ticket.inputs.model_copy(update=updates))
    policy = PlanningCompositionPolicy(version=POLICY_VERSION, generator_version=GENERATOR_VERSION)
    contexts = []
    for key, kind, document in (
        ("customer", "customer_context", inputs),
        ("policy", "planning_policy", policy),
    ):
        reference = bundle.catalogs[0].reference.model_dump(mode="python")
        reference.update(key=key, kind=kind, account=None, document_digest=document.digest())
        contexts.append(ContextEvidence(reference=reference, document=document))
    bundle = bundle.model_copy(update=dict(input_digest=inputs.digest(), context=tuple(contexts)))
    ticket = ticket.model_copy(
        update=dict(inputs=inputs, policy_version=policy.version, policy_digest=policy.digest())
    )
    bundle.assert_ticket(ticket)
    return inputs, bundle, policy


def compose(
    inputs: PlanInputRevision, bundle: EvidenceBundle, policy: PlanningCompositionPolicy
) -> PlanVersion:
    return DescriptivePlanComposer().compose(
        inputs=inputs,
        evidence=bundle,
        policy=policy,
        version=1,
        parent_digest=None,
        generated_by="a" * 32,
        generated_at=bundle.collected_at + timedelta(seconds=1),
    )


@pytest.mark.parametrize("conversions", ["10", "0", None])
def test_conversion_claims_preserve_positive_and_unqualified_zero(conversions: str | None) -> None:
    inputs, bundle, policy = fixture()
    data = performance_data(bundle)
    doc = data["document"].model_copy(update=dict(conversions=conversions))
    data.update(
        document=doc,
        conversion_qualification="reported_only" if conversions == "10" else "unavailable",
    )
    data["reference"]["document_digest"] = fingerprint(
        "campaign-performance", doc.model_dump(mode="json")
    )
    bundle = bundle.model_copy(update=dict(performance=(PerformanceEvidence.model_validate(data),)))
    plan = compose(inputs, bundle, policy)
    review = plan.actions[0]
    assert "100 reported clicks" in review.rationale
    assert "100 USD reported spend" in review.rationale
    assert "spend without conversions" not in plan.model_dump_json().lower()
    if conversions == "10":
        assert "10 provider-reported conversions" in review.rationale
        assert review.kind == "retain"
    else:
        assert "missing is not zero" in review.rationale
        assert review.kind == "investigate"
    assert plan.quality_status == "not_expert_qualified"
    assert plan.readiness == "needs_input"
    assert all(action.native_budget is None for action in plan.actions)


def test_missing_performance_produces_locatable_manual_investigation() -> None:
    inputs, bundle, policy = fixture()
    plan = compose(inputs, bundle, policy)
    review = plan.actions[0]
    native = bundle.catalogs[0].catalog.targets[0].entity.reference
    assert review.kind == "investigate"
    assert "No matching campaign performance" in review.rationale
    assert native.advertiser_id in review.manual_steps[0]
    assert native.entity_id in review.manual_steps[0]
    assert review.evidence_keys
    assert plan.valid_until == bundle.catalogs[0].reference.expires_at
    assert compose(inputs, bundle, policy) == plan


@pytest.mark.parametrize("capacity,brief_count", [(None, 1), (0, 0), (1, 1)])
def test_product_facts_and_explicit_creative_capacity(
    capacity: int | None, brief_count: int
) -> None:
    fact = "Reusable green bottle, 500 ml capacity."
    inputs, bundle, policy = fixture(product_offer=fact, maximum_creative_assets=capacity)
    plan = compose(inputs, bundle, policy)
    assert len(plan.briefs) == brief_count
    for brief in plan.briefs:
        assert brief.product_facts == (fact,)
        assert brief.offer == fact
        assert brief.claim_evidence_keys == ("customer",)
        assert brief.hypotheses
        assert len(brief.required_assets) == 1
        assert "Image" in brief.format
    if capacity is None:
        assert any("capacity is unconfirmed" in item for item in plan.section_limitations)


def test_customer_alternatives_and_fixed_allocations_are_independent() -> None:
    _, source, _ = fixture()
    target = next(value for value in targets(source.catalogs[0]) if value.kind == "campaign")
    initial, _, _ = fixture()
    ceiling = initial.total_ceiling_micros
    fixed = dict(target=target, amount_micros=ceiling // 4)
    intent = dict(
        key="customer_a",
        title="Customer Alternative",
        allocations=[fixed],
        unallocated_micros=ceiling - ceiling // 4,
    )
    inputs, bundle, policy = fixture(fixed_allocations=(fixed,), scenario_intents=(intent,))
    plan = compose(inputs, bundle, policy)
    assert len(plan.scenarios) == 2
    for scenario in plan.scenarios:
        assert (
            sum(a.amount_micros for a in scenario.allocations) + scenario.unallocated_micros
            == ceiling
        )
        assert scenario.allocations[0].amount_micros == ceiling // 4
    assert plan.scenarios[1].customer_intent_key == "customer_a"
    assert plan.scenarios[1].provenance == "customer_supplied_hypothesis"


@pytest.mark.parametrize("change", ["expired", "policy", "input", "privacy"])
def test_stale_or_substituted_composition_is_rejected(change: str) -> None:
    inputs, bundle, policy = fixture()
    if change == "expired":
        bundle = bundle.model_copy(
            update=dict(collected_at=bundle.catalogs[0].reference.expires_at)
        )
    elif change == "policy":
        policy = policy.model_copy(update=dict(version="unknown"))
    elif change == "input":
        inputs = inputs.model_copy(update=dict(product_offer="Different product"))
    else:
        bundle = bundle.model_copy(update=dict(privacy_revision=1))
    with pytest.raises(PlanCompositionUnavailable):
        compose(inputs, bundle, policy)


@pytest.mark.parametrize(
    "platform,format_word", [("google", "Text"), ("meta", "Image"), ("tiktok", "Video")]
)
def test_single_platform_brand_gets_correct_native_location_and_concept(
    platform: str, format_word: str
) -> None:
    inputs, bundle, policy = fixture(platform=platform, product_offer="Reusable bottle.")
    plan = compose(inputs, bundle, policy)
    assert len(plan.inputs.accounts) == 1
    assert format_word in plan.briefs[0].format
    assert all(action.target.account == inputs.accounts[0] for action in plan.actions)
    for action in plan.actions:
        assert not action.proposed_fields
        assert action.native_budget is None


def test_excluded_campaign_is_not_reintroduced_in_account_fallback() -> None:
    _, source, _ = fixture()
    excluded = tuple(
        t.canonical_entity_key for t in targets(source.catalogs[0]) if t.kind == "campaign"
    )
    inputs, bundle, policy = fixture(excluded_entity_keys=excluded, product_offer="Bottle")
    plan = compose(inputs, bundle, policy)
    assert all(
        getattr(action.target, "canonical_entity_key", None) not in excluded
        for action in plan.actions
    )
    assert "No included native campaign" in plan.actions[0].rationale


def test_zero_budget_never_creates_positive_allocation() -> None:
    inputs, _, _ = fixture()
    goal = inputs.goal.model_dump(mode="python")
    goal["definition"]["budget_micros"] = 0
    goal["definition_digest"] = fingerprint(
        "goal-definition",
        inputs.goal.definition.model_copy(update=dict(budget_micros=0)).model_dump(mode="json"),
    )
    inputs, bundle, policy = fixture(total_ceiling_micros=0, goal=goal)
    plan = compose(inputs, bundle, policy)
    assert all(not s.allocations and s.unallocated_micros == 0 for s in plan.scenarios)
    assert all(a.native_budget is None for a in plan.actions)
