"""Explicit pure v3 invocation only; no service activation or live evidence claims."""

from datetime import timedelta
from decimal import Inexact, Overflow, localcontext
from typing import Any

import pytest
from app.planning_documents.common import fingerprint
from app.planning_documents.composer import PlanCompositionUnavailable, targets
from app.planning_documents.context import PlanInputRevision, ReportingWindow
from app.planning_documents.ports import ContextEvidence, GenerationTicket
from app.planning_documents.window_composer import WindowPlanComposer, grouped_window_gaps
from app.planning_documents.window_evidence import WindowEvidenceBundleV1

from tests.test_window_evidence_contract import gap_for, policy, ready


def contextual(ticket: GenerationTicket, bundle: WindowEvidenceBundleV1) -> WindowEvidenceBundleV1:
    contexts = []
    for key, kind, doc in (
        ("customer", "customer_context", ticket.inputs),
        ("policy", "planning_policy", policy()),
    ):
        ref = bundle.catalogs[0].reference.model_copy(
            update=dict(key=key, kind=kind, account=None, document_digest=doc.digest())
        )
        contexts.append(ContextEvidence(reference=ref, document=doc))
    return WindowEvidenceBundleV1.model_validate(
        bundle.model_copy(update=dict(input_digest=ticket.inputs.digest(), context=tuple(contexts)))
    )


def compose(ticket: GenerationTicket, bundle: WindowEvidenceBundleV1) -> Any:
    return WindowPlanComposer().compose(
        ticket=ticket,
        evidence=contextual(ticket, bundle),
        policy=policy(),
        generated_at=bundle.collected_at + timedelta(seconds=1),
    )


def revised(ticket: GenerationTicket, **updates: Any) -> GenerationTicket:
    inputs = PlanInputRevision.model_validate(ticket.inputs.model_copy(update=updates))
    return GenerationTicket.model_validate(ticket.model_copy(update=dict(inputs=inputs)))


@pytest.mark.parametrize("count", ["10", "0", None])
def test_requested_primary_comparison_and_no_original_total(count: str | None) -> None:
    ticket, bundle = ready(True, count)
    result = compose(ticket, bundle)
    action = result.actions[0]
    assert "Primary" in action.rationale and "Comparison" in action.rationale
    assert "selected conversions 20" not in action.rationale
    assert (
        "100 observed clicks" in action.rationale and "100 USD observed spend" in action.rationale
    )
    assert "200 observed clicks" not in action.rationale
    assert action.kind == ("retain" if count == "10" else "investigate")
    assert ("Observed zero selected conversions" in action.rationale) == (count == "0")
    expected = {p.reference.key for p in bundle.performance}
    assert expected <= set(action.evidence_keys)
    assert expected <= {ref.key for ref in result.evidence}
    assert result.version == ticket.expected_version + 1 and result.generated_by == ticket.actor_id
    assert result.inputs == ticket.inputs and result.spending_authority == "none"


def test_primary_classification_does_not_follow_comparison() -> None:
    from app.campaign_performance.presence_contracts import CountCellV1, presence_digest
    from app.campaign_performance.presence_report import CampaignPerformanceV3, campaign_summary
    from app.campaign_performance.window_projection import project_requested_window
    from app.planning_documents.window_evidence import WindowPerformanceEvidenceV1

    ticket, bundle = ready(True)
    original = bundle.performance[0].document.original
    rows = (
        original.campaign_facts[0],
        original.campaign_facts[1].model_copy(
            update=dict(selected_conversions=CountCellV1(presence="present", value="0"))
        ),
    )
    header = original.presence.model_copy(update=dict(fact_digest=presence_digest(rows)))
    original = CampaignPerformanceV3.model_validate(
        original.model_copy(
            update=dict(
                presence=header,
                campaign_facts=rows,
                summary=campaign_summary(header, rows, 1, original.native_campaign_id),
            )
        )
    )
    changed = []
    for p in bundle.performance:
        doc = project_requested_window(original, requested_window=p.document.requested_window)
        changed.append(
            WindowPerformanceEvidenceV1.model_validate(
                p.model_copy(
                    update=dict(
                        document=doc,
                        reference=p.reference.model_copy(
                            update=dict(
                                document_digest=fingerprint(
                                    "requested-window-performance", doc.model_dump(mode="json")
                                )
                            )
                        ),
                    )
                )
            )
        )
    result = compose(ticket, bundle.model_copy(update=dict(performance=tuple(changed))))
    assert result.actions[0].kind == "investigate"
    assert "selected conversions 0" in result.actions[0].rationale
    assert "selected conversions 10" in result.actions[0].rationale


def test_comparison_gap_is_retained_without_discarding_primary() -> None:
    ticket, bundle = ready(True)
    mixed = bundle.model_copy(
        update=dict(performance=bundle.performance[:1], window_gaps=(gap_for(bundle, 1),))
    )
    result = compose(ticket, mixed)
    assert result.actions[0].kind == "retain"
    assert (
        "Comparison" in result.actions[0].rationale
        and "outside_imported_window" in result.actions[0].rationale
    )
    assert len(result.section_limitations) >= 1
    gaptext = next(t for t in result.section_limitations if "Campaign IDs:" in t)
    assert mixed.window_gaps[0].target is not None
    assert mixed.window_gaps[0].target.provider_reference.entity_id in gaptext


@pytest.mark.parametrize(
    "change", ["policy", "ticket", "expired", "naive", "missingcontext", "missinggap"]
)
def test_reject_invalid_composition(change: str) -> None:
    ticket, bundle = ready(True)
    bundle = contextual(ticket, bundle)
    configured = policy()
    now = bundle.collected_at + timedelta(seconds=1)
    if change == "policy":
        configured = policy(2)
    if change == "ticket":
        ticket = ticket.model_copy(update=dict(actor_id=True))
    if change == "expired":
        now = bundle.catalogs[0].reference.expires_at
    if change == "naive":
        now = now.replace(tzinfo=None)
    if change == "missingcontext":
        bundle = bundle.model_copy(update=dict(context=()))
    if change == "missinggap":
        bundle = bundle.model_copy(update=dict(performance=bundle.performance[:1]))
    with pytest.raises(ValueError):
        WindowPlanComposer().compose(
            ticket=ticket, evidence=bundle, policy=configured, generated_at=now
        )


def test_customer_scenarios_fixed_exclusions_creative_constraints() -> None:
    ticket, bundle = ready(True)
    target = bundle.performance[0].target
    ceiling = ticket.inputs.total_ceiling_micros
    ticket = revised(
        ticket,
        fixed_allocations=(dict(target=target, amount_micros=1),),
        scenario_intents=(
            dict(
                key="alternative",
                title="Customer Alternative",
                allocations=(dict(target=target, amount_micros=1),),
                unallocated_micros=ceiling - 1,
            ),
        ),
        product_offer="Customer supplied product facts",
        maximum_creative_assets=1,
    )
    result = compose(ticket, bundle)
    assert len(result.scenarios) == 2
    assert all(s.allocations[0].amount_micros == 1 for s in result.scenarios)
    assert all(
        sum(a.amount_micros for a in s.allocations) + s.unallocated_micros == ceiling
        for s in result.scenarios
    )
    assert len(result.briefs) == 1 and result.briefs[0].product_facts == (
        ticket.inputs.product_offer,
    )
    constrained = compose(revised(ticket, constraints=("Customer must verify inventory",)), bundle)
    assert not constrained.briefs and all(a.kind == "investigate" for a in constrained.actions)
    zero_capacity = compose(revised(ticket, maximum_creative_assets=0), bundle)
    assert not zero_capacity.briefs
    excluded = revised(
        ticket,
        fixed_allocations=(),
        scenario_intents=(),
        excluded_entity_keys=(target.canonical_entity_key,),
    )
    omitted = compose(excluded, bundle)
    assert all(
        getattr(a.target, "canonical_entity_key", None) != target.canonical_entity_key
        for a in omitted.actions
    )
    assert {p.reference.key for p in bundle.performance} <= {r.key for r in omitted.evidence}


def test_hostile_decimal_context_and_parent_derivation() -> None:
    ticket, bundle = ready(True)
    ticket = GenerationTicket.model_validate(
        ticket.model_copy(update=dict(expected_version=2, expected_parent_digest="e" * 64))
    )
    baseline = compose(ticket, bundle)
    with localcontext() as ctx:
        ctx.prec = 1
        ctx.Emax = 1
        ctx.traps[Inexact] = True
        ctx.traps[Overflow] = True
        assert compose(ticket, bundle) == baseline
    assert baseline.version == 3 and baseline.parent_digest == "e" * 64


def many(
    platform: str, count: int, long_ids: bool = False
) -> tuple[GenerationTicket, WindowEvidenceBundleV1]:
    from app.planning_catalog.metadata_contracts import PlanningMetadataV1
    from app.planning_catalog.projection_v2 import project_v2
    from app.planning_documents.ports import CatalogEvidence, ReportingPresencePin, SourceFence
    from app.planning_documents.window_evidence import WindowReportingGapV1

    from tests.test_planning_composer import fixture
    from tests.test_planning_metadata_binding import bundle as native_bundle

    inputs, old, _ = fixture(platform)
    inventory, metadata = native_bundle(platform)
    raw = inventory.model_dump(mode="python")
    ids = [str(10**31 + i) if long_ids else str(1000 + i) for i in range(count)]
    raw["campaigns"] = [
        dict(
            raw["campaigns"][0],
            **(
                dict(resource_name=f"customers/1234567890/campaigns/{ident}")
                if platform == "google"
                else dict(id=ident)
                if platform == "meta"
                else dict(id=ident, campaign_id=ident)
            ),
        )
        for ident in ids
    ]
    if platform == "tiktok":
        raw["adgroups"] = []
    elif platform == "meta":
        raw["adsets"] = []
    inventory = type(inventory).model_validate(raw)
    changed = metadata.model_dump(mode="python")
    entity = next(e for e in changed["entities"] if e["kind"] == "campaign")
    changed["entities"] = [
        dict(entity, reference=dict(entity["reference"], entity_id=i)) for i in ids
    ]
    changed["native_inventory_digest"] = inventory.digest()
    for c in changed["coverage"]:
        c["count"] = count if c["kind"] == "campaign" else 0
    catalog = project_v2(inventory, PlanningMetadataV1.model_validate(changed))
    ref = old.catalogs[0].reference.model_copy(
        update=dict(document_digest=catalog.composite_digest)
    )
    catalog_evidence = CatalogEvidence(reference=ref, catalog=catalog)
    inputs = PlanInputRevision.model_validate(
        inputs.model_copy(
            update=dict(
                comparison_window=ReportingWindow(
                    starts_at=inputs.reporting_window.starts_at - timedelta(days=1),
                    ends_at_exclusive=inputs.reporting_window.starts_at,
                ),
                product_offer=None,
                maximum_creative_assets=0,
            )
        )
    )
    account = inputs.accounts[0]
    ticket = GenerationTicket(
        operation_id="e" * 32,
        actor_id="a" * 32,
        session_digest="f" * 64,
        inputs=inputs,
        expected_version=0,
        expected_parent_digest=None,
        privacy_revision=0,
        sources=(
            SourceFence(
                account=account,
                source_binding_digest=ref.source_binding_digest,
                source_revision=ref.source_revision,
                privacy_revision=0,
            ),
        ),
        policy_version=policy().version,
        policy_digest=policy().digest(),
        prepared_at=old.collected_at,
    )
    gaps = tuple(
        WindowReportingGapV1(
            account=account,
            target=target,
            requested_window=window,
            reason="reporting_presence_unavailable",
            reporting_pin_digest="d" * 64,
            explanation="No qualified presence sidecar.",
        )
        for target in targets(catalog_evidence)
        for window in (inputs.reporting_window, inputs.comparison_window)
        if window is not None
    )
    result = WindowEvidenceBundleV1(
        operation_id=ticket.operation_id,
        input_digest=inputs.digest(),
        privacy_revision=0,
        collected_at=old.collected_at,
        catalogs=(catalog_evidence,),
        performance=(),
        commerce=None,
        context=(),
        gaps=(),
        reporting_pins=(ReportingPresencePin(account=account, document_digest="d" * 64),),
        window_gaps=gaps,
    )
    result.assert_ticket(ticket)
    return ticket, result


@pytest.mark.parametrize("platform", ["google", "tiktok"])
def test_dozens_of_campaigns_with_comparison_are_representable(platform: str) -> None:
    ticket, bundle = many(platform, 40)
    result = compose(ticket, bundle)
    grouped = [text for text in result.section_limitations if "Campaign IDs:" in text]
    assert len(grouped) == 2 and len(result.actions) == 40
    for text in grouped:
        assert set(text.split("Campaign IDs: ")[1][:-1].split(", ")) == {
            str(1000 + i) for i in range(40)
        }
    assert all("Comparison" in a.rationale for a in result.actions)
    assert len(result.section_limitations) < 30


def test_gap_chunks_split_only_whole_ids_and_sort_deterministically() -> None:
    ticket, bundle = many("tiktok", 90, True)
    grouped = grouped_window_gaps(bundle)
    assert len(grouped) > 2 and all(len(text) <= 2000 for text in grouped)
    result = compose(ticket, bundle)
    assert len(result.actions) == 90
    ids = [part for text in grouped for part in text.split("Campaign IDs: ")[1][:-1].split(", ")]
    assert len(ids) == 180 and all(len(ident) == 32 for ident in ids)
    assert (
        grouped_window_gaps(
            bundle.model_copy(update=dict(window_gaps=tuple(reversed(bundle.window_gaps))))
        )
        == grouped
    )


def test_actual_action_capacity_refuses_without_truncating() -> None:
    ticket, bundle = many("tiktok", 101)
    with pytest.raises(PlanCompositionUnavailable, match="capacity"):
        compose(ticket, bundle)


def test_larger_original_56_day_totals_never_replace_requested_summary() -> None:
    from app.campaign_performance.presence_contracts import presence_digest
    from app.campaign_performance.presence_report import CampaignPerformanceV3, campaign_summary
    from app.campaign_performance.window_projection import project_requested_window
    from app.planning_documents.window_evidence import WindowPerformanceEvidenceV1

    from tests.test_reporting_presence_contracts import fact

    ticket, bundle = ready(True)
    original = bundle.performance[0].document.original
    first = original.campaign_facts[0]
    rows = (
        tuple(
            fact(
                workspace_id=first.workspace_id,
                account_id=first.account_id,
                campaign_id=first.campaign_id,
                native_campaign_id=first.native_campaign_id,
                metric_date=first.metric_date - timedelta(days=54 - i),
                clicks=dict(presence="present", value=9000),
            )
            for i in range(54)
        )
        + original.campaign_facts
    )
    h = original.presence.model_copy(
        update=dict(
            requested_starts_on=rows[0].metric_date,
            actual_starts_on=rows[0].metric_date,
            fact_count=56,
            fact_digest=presence_digest(rows),
        )
    )
    expanded = CampaignPerformanceV3.model_validate(
        original.model_copy(
            update=dict(
                presence=h,
                campaign_facts=rows,
                legacy=original.legacy.model_copy(
                    update=dict(starts_on=rows[0].metric_date, reported_day_count=56)
                ),
                summary=campaign_summary(h, rows, 1, original.native_campaign_id),
            )
        )
    )
    performance = []
    for p in bundle.performance:
        doc = project_requested_window(expanded, requested_window=p.document.requested_window)
        performance.append(
            WindowPerformanceEvidenceV1.model_validate(
                p.model_copy(
                    update=dict(
                        document=doc,
                        reference=p.reference.model_copy(
                            update=dict(
                                document_digest=fingerprint(
                                    "requested-window-performance", doc.model_dump(mode="json")
                                )
                            )
                        ),
                    )
                )
            )
        )
    result = compose(ticket, bundle.model_copy(update=dict(performance=tuple(performance))))
    text = result.actions[0].rationale
    assert text.count("100 observed clicks") == 2 and "486200" not in text
    assert text.count("selected conversions 10") == 2 and "selected conversions 560" not in text


def test_zero_budget_and_no_implicit_native_spending() -> None:
    ticket, bundle = ready()
    goal = ticket.inputs.goal.model_dump(mode="python")
    goal["definition"]["budget_micros"] = 0
    goal["definition_digest"] = fingerprint(
        "goal-definition",
        ticket.inputs.goal.definition.model_copy(update=dict(budget_micros=0)).model_dump(
            mode="json"
        ),
    )
    result = compose(revised(ticket, total_ceiling_micros=0, goal=goal), bundle)
    assert all(
        not scenario.allocations and scenario.unallocated_micros == 0
        for scenario in result.scenarios
    )
    assert all(
        action.kind == "investigate" and action.native_budget is None for action in result.actions
    )


def test_collection_gap_wording_is_past_tense_and_complete() -> None:
    from app.planning_documents.context import AccountRef
    from app.planning_documents.ports import EvidenceGap
    from app.planning_documents.window_evidence import WindowReportingGapV1

    ticket, bundle = ready(True)
    second = AccountRef(
        workspace_id=ticket.inputs.workspace_id,
        account_id=999,
        connection_id=998,
        connection_version="absent:v1",
        platform="tiktok_ads",
    )
    inputs = PlanInputRevision.model_validate(
        ticket.inputs.model_copy(update=dict(accounts=ticket.inputs.accounts + (second,)))
    )
    ticket = GenerationTicket.model_validate(
        ticket.model_copy(
            update=dict(
                inputs=inputs,
                sources=ticket.sources
                + (ticket.sources[0].model_copy(update=dict(account=second)),),
            )
        )
    )
    gaps = tuple(
        WindowReportingGapV1(
            account=second,
            target=None,
            requested_window=window,
            reason="catalog_unavailable",
            reporting_pin_digest="e" * 64,
            explanation="Collection-time gap",
        )
        for window in (inputs.reporting_window, inputs.comparison_window)
        if window is not None
    )
    bundle = bundle.model_copy(
        update=dict(
            reporting_pins=bundle.reporting_pins
            + (
                bundle.reporting_pins[0].model_copy(
                    update=dict(account=second, document_digest="e" * 64)
                ),
            ),
            gaps=(
                EvidenceGap(
                    account=second,
                    section="catalog",
                    reason="unavailable",
                    explanation="Catalog unavailable",
                ),
            ),
            window_gaps=gaps,
        )
    )
    result = compose(ticket, bundle)
    texts = [t for t in result.section_limitations if "Catalog scope." in t]
    assert len(texts) == 2
    assert all(
        "when this plan was prepared" in text
        and "current provider availability is not assessed" in text
        for text in texts
    )


def test_actual_section_limit_capacity_counts_every_group_and_constraint() -> None:
    ticket, bundle = many("tiktok", 40)
    # 40campaigns with unique reason/window groups still groupcompact; customer
    # constraints occupy their own slots and cannot be silently dropped.
    constraints = tuple(f"Customer constraint {i}" for i in range(20))
    ticket = revised(ticket, constraints=constraints)
    result = compose(ticket, bundle)
    assert all(c in result.section_limitations for c in constraints)
    from app.planning_documents.ports import EvidenceGap

    extra = tuple(
        EvidenceGap(
            account=None,
            section="creative_context",
            reason=f"gap_{i}",
            explanation=f"Independent creative context gap {i}",
        )
        for i in range(10)
    )
    with pytest.raises(PlanCompositionUnavailable, match="capacity"):
        compose(ticket, bundle.model_copy(update=dict(gaps=extra)))


def test_explicit_text_capacity_no_truncation() -> None:
    from app.planning_documents.window_composer import bounded_text

    assert bounded_text("x" * 2000) == "x" * 2000
    with pytest.raises(PlanCompositionUnavailable, match="capacity"):
        bounded_text("x" * 2001)


def test_multi_account_groups_never_merge_identical_native_ids() -> None:
    ticket, left = many("google", 40)
    other, right = many("tiktok", 40)
    assert ticket.inputs.reporting_window == other.inputs.reporting_window
    ticket = GenerationTicket.model_validate(
        ticket.model_copy(
            update=dict(
                inputs=ticket.inputs.model_copy(
                    update=dict(accounts=ticket.inputs.accounts + other.inputs.accounts)
                ),
                sources=ticket.sources + other.sources,
            )
        )
    )
    right_catalog = right.catalogs[0].model_copy(
        update=dict(
            reference=right.catalogs[0].reference.model_copy(update=dict(key="catalog_tiktok"))
        )
    )
    right_gaps = tuple(
        g.model_copy(
            update=dict(
                target=g.target.model_copy(update=dict(catalog_evidence_key="catalog_tiktok"))
            )
        )
        for g in right.window_gaps
        if g.target is not None
    )
    merged = left.model_copy(
        update=dict(
            catalogs=left.catalogs + (right_catalog,),
            reporting_pins=left.reporting_pins + right.reporting_pins,
            window_gaps=left.window_gaps + right_gaps,
        )
    )
    result = compose(ticket, merged)
    grouped = [s for s in result.section_limitations if "Campaign IDs:" in s]
    assert len(grouped) == 4 and len(result.actions) == 80
    assert sum("Google Ads" in s for s in grouped) == 2
    assert sum("TikTok Ads" in s for s in grouped) == 2
    assert all(len(s.split("Campaign IDs: ")[1][:-1].split(", ")) == 40 for s in grouped)


def test_400_successes_plus_context_catalog_refs_are_explicitly_over_document_cap() -> None:
    from app.campaign_performance.presence_contracts import presence_digest
    from app.campaign_performance.presence_report import CampaignPerformanceV3, campaign_summary
    from app.campaign_performance.window_projection import project_requested_window
    from app.planning_documents.window_evidence import (
        WindowPerformanceEvidenceV1,
        reporting_entry_key,
    )

    ticket, bundle = many("meta", 200)
    _, sample = ready(True)
    template = sample.performance[0]
    original = template.document.original
    catalog_targets = targets(bundle.catalogs[0])
    pairs = [
        (
            target,
            tuple(
                f.model_copy(
                    update=dict(
                        campaign_id=i + 1, native_campaign_id=target.provider_reference.entity_id
                    )
                )
                for f in original.campaign_facts
            ),
        )
        for i, target in enumerate(catalog_targets)
    ]
    allfacts = tuple(f for _, facts in pairs for f in facts)
    header = original.presence.model_copy(
        update=dict(fact_count=len(allfacts), fact_digest=presence_digest(allfacts))
    )
    performance = []
    for target, facts in pairs:
        native = target.provider_reference.entity_id
        source = CampaignPerformanceV3.model_validate(
            original.model_copy(
                update=dict(
                    presence=header,
                    native_campaign_id=native,
                    campaign_facts=facts,
                    legacy=original.legacy.model_copy(
                        update=dict(campaign_id=facts[0].campaign_id)
                    ),
                    summary=campaign_summary(header, facts, facts[0].campaign_id, native),
                )
            )
        )
        for window in (ticket.inputs.reporting_window, ticket.inputs.comparison_window):
            assert window is not None
            doc = project_requested_window(source, requested_window=window)
            ref = template.reference.model_copy(
                update=dict(
                    key=reporting_entry_key(
                        target.account.account_id, facts[0].campaign_id, window
                    ),
                    reporting_window=window,
                    document_digest=fingerprint(
                        "requested-window-performance", doc.model_dump(mode="json")
                    ),
                )
            )
            performance.append(
                WindowPerformanceEvidenceV1.model_validate(
                    template.model_copy(update=dict(target=target, document=doc, reference=ref))
                )
            )
    complete = contextual(
        ticket, bundle.model_copy(update=dict(performance=tuple(performance), window_gaps=()))
    )
    complete.assert_ticket(ticket)
    assert len(complete.performance) == 400
    with pytest.raises(PlanCompositionUnavailable, match="complete evidence set"):
        WindowPlanComposer().compose(
            ticket=ticket,
            evidence=complete,
            policy=policy(),
            generated_at=complete.collected_at + timedelta(seconds=1),
        )
