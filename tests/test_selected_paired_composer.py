"""Pure fixture evidence, not empirical qualification or registered generation."""

from datetime import timedelta
from typing import Any, Literal

import pytest
from app.campaign_performance.presence_contracts import (
    ReportedMetricPresenceV1,
    ReportingSemanticsV1,
    presence_digest,
)
from app.campaign_performance.range_receipt_contracts import RangeReceiptV1
from app.campaign_performance.selected_contracts import (
    CustomerEventSelectionV1,
    SelectedCaptureRequestV1,
    SelectedCaptureV1,
    capture_request_digest,
    selection_digest,
)
from app.google_connections.selected_presence import query_profile_digest
from app.planning_documents.common import fingerprint
from app.planning_documents.ports import ContextEvidence, PlanningCompositionPolicy
from app.planning_documents.selected_composer import SelectedPlanComposer
from app.planning_documents.selected_paired_evidence import (
    METRIC_BASIS,
    SelectedPairedEvidenceV1,
    TrafficWindowEvidenceV1,
    TrafficWindowGapV1,
    traffic_window_key,
)
from app.planning_documents.selected_plan_bundle import SelectedPlanEvidenceBundleV1
from app.planning_documents.selected_plan_evidence import (
    SelectedPlanCaptureV1,
    project_selected_plan_window,
)
from app.planning_documents.selected_plan_proof import SelectedRetainedProofV1
from app.planning_documents.selected_traffic import (
    RawRangeTrafficGraphV1,
    project_raw_range_traffic,
)

from tests.test_selected_plan_bundle import ready as selected_ready


def ready(
    value: str | None = "10",
    *,
    family: Literal["conversions", "all_conversions"] = "conversions",
    complete: bool = True,
    traffic: bool = True,
    traffic_complete: bool = True,
) -> tuple[Any, Any, Any]:
    ticket, selected = selected_ready(value=value)
    graph = selected.selected_captures[0]
    original = graph.capture
    choice = CustomerEventSelectionV1.model_validate(
        original.request.selection.model_copy(
            update={"metric_family": family, "query_profile_digest": query_profile_digest(family)}
        )
    )
    request = SelectedCaptureRequestV1.model_validate(
        original.request.model_copy(
            update={
                "selection": choice,
                "selection_digest": selection_digest(choice),
                "query_profile_digest": choice.query_profile_digest,
            }
        )
    )
    request_digest = capture_request_digest(request)
    days = (request.requested_ends_on - request.requested_starts_on).days + 1
    dates = (
        [request.requested_starts_on + timedelta(days=n) for n in range(days)]
        if complete
        else [request.requested_ends_on]
    )
    facts = tuple(
        original.facts[0].model_copy(
            update={
                "metric_date": day,
                "request_digest": request_digest,
                "selected_conversions": {
                    "presence": "missing" if value is None else "present",
                    "value": value
                    if day == request.requested_ends_on
                    else None
                    if value is None
                    else "0",
                },
            }
        )
        for day in dates
    )
    capture = SelectedCaptureV1.model_validate(
        original.model_copy(
            update={"request": request, "request_digest": request_digest, "facts": facts}
        )
    )
    graph = SelectedPlanCaptureV1.model_validate(graph.model_copy(update={"capture": capture}))
    aggregate = request.aggregate
    completed = capture.completed_at - timedelta(seconds=1)
    receipt = RangeReceiptV1(
        request_id="b" * 32,
        initiating_customer_id=ticket.actor_id,
        requested_starts_on=aggregate.starts_on,
        requested_ends_on=aggregate.ends_on,
        original_scope=aggregate.scope,
        final_scope=aggregate.scope,
        completion_id=aggregate.completion_id,
        manifest_digest=aggregate.manifest_digest,
        query_version="google.v24.campaign-day.metrics-conversions.v1",
        completed_at=completed,
        row_count=days,
        acquisition_digest="c" * 64,
        job_id=1,
    )
    raw_facts = tuple(
        ReportedMetricPresenceV1(
            completion_id=receipt.completion_id,
            workspace_id=aggregate.scope.workspace_id,
            account_id=aggregate.scope.account_id,
            campaign_id=graph.campaigns[0].campaign_id,
            native_campaign_id=graph.campaigns[0].native_campaign_id,
            metric_date=receipt.requested_starts_on + timedelta(days=n),
            impressions={"presence": "present", "value": 1000 if n == days - 1 else 0},
            clicks={"presence": "present", "value": 100 if n == days - 1 else 0},
            spend_micros={"presence": "present", "value": 100_000_000 if n == days - 1 else 0},
            selected_conversions={"presence": "unsupported", "value": None},
            selected_value_micros={"presence": "unsupported", "value": None},
        )
        for n in range(days)
    )
    if not traffic_complete:
        raw_facts = raw_facts[-1:]
        receipt = receipt.model_copy(update={"row_count": len(raw_facts)})
    profile = "google.v24.campaign-day.raw-required-traffic.v1"
    header = ReportingSemanticsV1(
        **aggregate.scope.model_dump(exclude={"native_account_id"}),
        completion_id=receipt.completion_id,
        legacy_manifest_digest=receipt.manifest_digest,
        producer_contract=profile,
        query_descriptor=receipt.query_version,
        requested_starts_on=receipt.requested_starts_on,
        requested_ends_on=receipt.requested_ends_on,
        actual_starts_on=receipt.requested_starts_on,
        actual_ends_on=receipt.requested_ends_on,
        selected_event={"provenance": "generic", "native_event_id": None, "label": None},
        attribution={
            "click_window_days": None,
            "view_window_days": None,
            "report_time_basis": "unknown",
            "provenance": "provider_default_unknown",
            "producer_contract": profile,
        },
        pagination_complete=True,
        closed_requested_period=True,
        completed_at=completed,
        fact_count=len(raw_facts),
        fact_digest=presence_digest(raw_facts),
    )
    raw = RawRangeTrafficGraphV1(
        receipt=receipt,
        header=header,
        facts=raw_facts,
        campaigns=graph.campaigns,
        source_fence=graph.source_fence,
    )
    old_proof = selected.reporting_proof.accounts[0]
    assert old_proof.selection_head is not None
    proof = SelectedRetainedProofV1(
        accounts=(
            old_proof.model_copy(
                update={
                    "capture_pin": graph.pin(),
                    "selection_head": old_proof.selection_head.model_copy(
                        update={"selection_digest": selection_digest(choice)}
                    ),
                    "traffic_pin": raw.pin() if traffic else None,
                }
            ),
        )
    )
    performance = []
    paired = []
    gaps = []
    for old in selected.performance:
        doc = project_selected_plan_window(
            graph,
            campaign_id=graph.campaigns[0].campaign_id,
            requested_window=old.document.requested_window,
        )
        performance.append(
            old.model_copy(
                update={
                    "document": doc,
                    "reference": old.reference.model_copy(
                        update={
                            "document_digest": fingerprint(
                                "selected-plan-window", doc.model_dump(mode="json")
                            ),
                            "coverage": "partial"
                            if doc.summary.conversions.present_days
                            or doc.summary.value_micros.present_days
                            else "unavailable",
                        }
                    ),
                }
            )
        )
        if traffic:
            report = project_raw_range_traffic(
                raw, campaign_id=doc.summary.campaign_id, requested_window=doc.requested_window
            )
            paired.append(
                TrafficWindowEvidenceV1(
                    target=old.target,
                    document=report,
                    reference=old.reference.model_copy(
                        update={
                            "key": traffic_window_key(
                                old.target.account.account_id,
                                doc.summary.campaign_id,
                                doc.requested_window,
                            ),
                            "document_schema": report.schema_version,
                            "document_digest": fingerprint(
                                "selected-traffic-window", report.model_dump(mode="json")
                            ),
                            "observation_started_at": completed,
                            "observed_at": completed,
                            "metric_basis": METRIC_BASIS,
                            "coverage": "partial" if report.returned_days else "unavailable",
                        }
                    ),
                )
            )
        else:
            gaps.append(
                TrafficWindowGapV1(
                    account=old.target.account,
                    target=old.target,
                    requested_window=doc.requested_window,
                    reason="range_traffic_provenance_unavailable",
                    reporting_pin_digest=proof.accounts[0].state_digest(),
                    explanation="No retained raw traffic receipt.",
                )
            )
    policy = PlanningCompositionPolicy(
        version=ticket.policy_version, generator_version="inlet.descriptive-planning.v4"
    )
    context = tuple(
        ContextEvidence(
            document=document,
            reference=selected.catalogs[0].reference.model_copy(
                update={
                    "key": f"context:{kind}",
                    "kind": kind,
                    "account": None,
                    "document_digest": document.digest(),
                    "source_binding_digest": document.digest(),
                    "document_schema": "inlet.plan-input.v1"
                    if kind == "customer_context"
                    else "inlet.planning-policy.v1",
                }
            ),
        )
        for kind, document in (("customer_context", ticket.inputs), ("planning_policy", policy))
    )
    selected = SelectedPlanEvidenceBundleV1.model_validate(
        selected.model_copy(
            update={
                "selected_captures": (graph,),
                "performance": tuple(performance),
                "reporting_proof": proof,
                "context": context,
            }
        )
    )
    result = SelectedPairedEvidenceV1(
        selected=selected,
        traffic_graphs=(raw,) if traffic else (),
        traffic=tuple(paired),
        traffic_gaps=tuple(gaps),
    )
    result.assert_ticket(ticket)
    return ticket, result, policy


def compose(ticket: Any, evidence: Any, policy: Any) -> Any:
    return SelectedPlanComposer().compose(
        ticket=ticket,
        evidence=evidence,
        policy=policy,
        generated_at=evidence.selected.collected_at + timedelta(seconds=1),
    )


@pytest.mark.parametrize("family", ["conversions", "all_conversions"])
@pytest.mark.parametrize("value,complete", [("10", True), ("0", True), ("0", False), (None, True)])
def test_selected_counts_and_separate_raw_traffic(
    family: Literal["conversions", "all_conversions"], value: str | None, complete: bool
) -> None:
    ticket, evidence, policy = ready(value, family=family, complete=complete)
    plan = compose(ticket, evidence, policy)
    text = plan.actions[0].rationale
    assert "100 observed clicks" in text and "100 USD observed spend" in text
    assert f"metric family {family}" in text
    assert evidence.selected.selected_captures[0].capture.request.selection.native_event_id in text
    assert ("Observed zero selected conversions" in text.split("Comparison")[0]) is (
        value == "0" and complete
    )
    assert plan.actions[0].kind == ("retain" if value == "10" else "investigate")
    assert plan.selected_reporting_proof == evidence.selected.reporting_proof
    assert {x.reference.key for x in evidence.traffic} <= set(plan.actions[0].evidence_keys)
    assert {x.reference.key for x in evidence.traffic} <= {x.key for x in plan.evidence}
    assert plan.spending_authority == "none"


def test_missing_traffic_is_not_zero() -> None:
    ticket, evidence, policy = ready(traffic=False)
    text = compose(ticket, evidence, policy).actions[0].rationale
    assert "Clicks and spend unavailable" in text
    assert "0 observed clicks" not in text and "0 USD observed spend" not in text
    assert "selected count 10" in text


@pytest.mark.parametrize(
    "attack",
    [
        "missing_graph",
        "extra_graph",
        "missing_slot",
        "duplicate_slot",
        "missing_pin",
        "restamp",
        "expiry",
        "arithmetic",
        "map",
        "receipt",
        "wrong_gap_pin",
        "gap_with_graph",
        "missing_selected",
        "selected_gap_traffic",
    ],
)
def test_copied_pairing_attacks(attack: str) -> None:
    ticket, evidence, _ = ready(traffic=attack != "wrong_gap_pin")
    graph = evidence.traffic_graphs[0] if evidence.traffic_graphs else None
    item = evidence.traffic[0] if evidence.traffic else None
    updates: dict[str, Any] = {}
    if attack == "missing_graph":
        updates["traffic_graphs"] = ()
    elif attack == "extra_graph":
        updates["traffic_graphs"] = evidence.traffic_graphs * 2
    elif attack == "missing_slot":
        updates["traffic"] = evidence.traffic[1:]
    elif attack == "duplicate_slot":
        updates["traffic"] = evidence.traffic + evidence.traffic[:1]
    elif attack == "missing_pin":
        proof = evidence.selected.reporting_proof
        updates["selected"] = evidence.selected.model_copy(
            update={
                "reporting_proof": proof.model_copy(
                    update={
                        "accounts": (proof.accounts[0].model_copy(update={"traffic_pin": None}),)
                    }
                )
            }
        )
    elif attack in {"restamp", "expiry", "arithmetic"}:
        assert item is not None
        doc = item.document
        ref = item.reference
        if attack == "restamp":
            ref = ref.model_copy(
                update={"observed_at": ref.observed_at + timedelta(microseconds=1)}
            )
        elif attack == "expiry":
            ref = ref.model_copy(update={"expires_at": ref.expires_at + timedelta(seconds=1)})
        else:
            doc = doc.model_copy(update={"clicks": doc.clicks.model_copy(update={"value": 101})})
            ref = ref.model_copy(
                update={
                    "document_digest": fingerprint(
                        "selected-traffic-window", doc.model_dump(mode="json")
                    )
                }
            )
        updates["traffic"] = (
            item.model_copy(update={"document": doc, "reference": ref}),
            *evidence.traffic[1:],
        )
    elif attack in {"map", "receipt"}:
        assert graph is not None
        bad = (
            graph.model_copy(
                update={
                    "campaigns": (
                        graph.campaigns[0].model_copy(update={"native_campaign_id": "9"}),
                    )
                }
            )
            if attack == "map"
            else graph.model_copy(
                update={
                    "receipt": graph.receipt.model_copy(update={"acquisition_digest": "f" * 64})
                }
            )
        )
        updates["traffic_graphs"] = (bad,)
    elif attack == "wrong_gap_pin":
        updates["traffic_gaps"] = (
            evidence.traffic_gaps[0].model_copy(update={"reporting_pin_digest": "f" * 64}),
            *evidence.traffic_gaps[1:],
        )
    elif attack == "gap_with_graph":
        assert item is not None
        updates["traffic"] = evidence.traffic[1:]
        updates["traffic_gaps"] = (
            TrafficWindowGapV1(
                account=item.target.account,
                target=item.target,
                requested_window=item.document.requested_window,
                reason="unsupported_traffic_profile",
                reporting_pin_digest=evidence.selected.reporting_proof.accounts[0].state_digest(),
                explanation="Cannot turn present evidence into gap.",
            ),
        )
    elif attack == "missing_selected":
        updates["selected"] = evidence.selected.model_copy(
            update={"performance": evidence.selected.performance[1:]}
        )
    else:
        ticket = ticket.model_copy(
            update={"inputs": ticket.inputs.model_copy(update={"comparison_window": None})}
        )
    with pytest.raises(ValueError):
        evidence.model_copy(update=updates).assert_ticket(ticket)


def test_partial_traffic_is_subtotal_and_decimal_context_independent() -> None:
    from decimal import Inexact, Overflow, localcontext

    ticket, evidence, policy = ready(traffic_complete=False)
    result = compose(ticket, evidence, policy)
    assert "Spend is an observed subtotal" in result.actions[0].rationale
    with localcontext() as ctx:
        ctx.prec = 1
        ctx.Emax = 1
        ctx.traps[Inexact] = True
        ctx.traps[Overflow] = True
        assert compose(ticket, evidence, policy) == result


def revised(ticket: Any, evidence: Any, **changes: Any) -> tuple[Any, Any]:
    inputs = type(ticket.inputs).model_validate(ticket.inputs.model_copy(update=changes))
    ticket = type(ticket).model_validate(ticket.model_copy(update={"inputs": inputs}))
    selected = evidence.selected
    context = tuple(
        x.model_copy(
            update={
                "document": inputs,
                "reference": x.reference.model_copy(
                    update={
                        "document_digest": inputs.digest(),
                        "source_binding_digest": inputs.digest(),
                    }
                ),
            }
        )
        if x.reference.kind == "customer_context"
        else x
        for x in selected.context
    )
    selected = selected.model_copy(update={"input_digest": inputs.digest(), "context": context})
    return ticket, evidence.model_copy(update={"selected": selected})


def test_manual_constraints_scenarios_ceiling_and_exclusions() -> None:
    ticket, evidence, policy = ready()
    target = evidence.selected.performance[0].target
    ceiling = ticket.inputs.total_ceiling_micros
    ticket, evidence = revised(
        ticket,
        evidence,
        fixed_allocations=(dict(target=target, amount_micros=1),),
        scenario_intents=(
            dict(
                key="alternative",
                title="Customer Alternative",
                allocations=(dict(target=target, amount_micros=1),),
                unallocated_micros=ceiling - 1,
            ),
        ),
        product_offer="Customer product fact",
        maximum_creative_assets=1,
    )
    result = compose(ticket, evidence, policy)
    assert len(result.scenarios) == 2 and len(result.briefs) == 1
    assert all(
        sum(a.amount_micros for a in s.allocations) + s.unallocated_micros == ceiling
        for s in result.scenarios
    )
    constrained = compose(*revised(ticket, evidence, constraints=("Verify inventory",)), policy)
    assert not constrained.briefs and all(a.kind == "investigate" for a in constrained.actions)
    omitted = compose(
        *revised(
            ticket,
            evidence,
            fixed_allocations=(),
            scenario_intents=(),
            excluded_entity_keys=(target.canonical_entity_key,),
        ),
        policy,
    )
    assert all(
        getattr(a.target, "canonical_entity_key", None) != target.canonical_entity_key
        for a in omitted.actions
    )
    assert {x.reference.key for x in evidence.traffic} <= {x.key for x in omitted.evidence}


def test_expired_evidence_and_noncanonical_policy_rejected() -> None:
    from app.planning_documents.composer import PlanCompositionUnavailable

    ticket, evidence, policy = ready()
    with pytest.raises(PlanCompositionUnavailable):
        SelectedPlanComposer().compose(
            ticket=ticket,
            evidence=evidence,
            policy=policy,
            generated_at=evidence.selected.catalogs[0].reference.expires_at,
        )
    with pytest.raises(PlanCompositionUnavailable):
        compose(ticket, evidence, policy.model_copy(update={"generator_version": "old"}))


def test_graphs_retained_even_without_selected_success_or_catalog() -> None:
    from app.planning_documents.ports import EvidenceGap
    from app.planning_documents.selected_plan_bundle import SelectedReportingGapV1

    ticket, evidence, _ = ready()
    account = ticket.inputs.accounts[0]
    selected = evidence.selected
    gaps = tuple(
        SelectedReportingGapV1(
            account=account,
            target=None,
            requested_window=window,
            reason="catalog_unavailable",
            reporting_pin_digest=selected.reporting_proof.accounts[0].state_digest(),
            explanation="Pure unavailable catalog fixture.",
        )
        for window in (ticket.inputs.reporting_window, ticket.inputs.comparison_window)
    )
    selected = SelectedPlanEvidenceBundleV1.model_validate(
        selected.model_copy(
            update={
                "catalogs": (),
                "performance": (),
                "context": (),
                "gaps": (
                    EvidenceGap(
                        account=account,
                        section="catalog",
                        reason="unsupported_reporting_window",
                        explanation="Pure unavailable catalog fixture.",
                    ),
                ),
                "window_gaps": gaps,
            }
        )
    )
    retained = SelectedPairedEvidenceV1(
        selected=selected, traffic_graphs=evidence.traffic_graphs, traffic=(), traffic_gaps=()
    )
    retained.assert_ticket(ticket)
    with pytest.raises(ValueError):
        retained.model_copy(update={"traffic_graphs": ()}).assert_ticket(ticket)


def test_pairing_prepares_each_graph_once(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.planning_documents import selected_paired_evidence as module

    ticket, evidence, _ = ready()
    from app.planning_documents.selected_traffic import PreparedRawRangeTrafficProjection

    original = PreparedRawRangeTrafficProjection
    prepared = []

    def counted(graph: RawRangeTrafficGraphV1) -> Any:
        prepared.append(graph.receipt.request_id)
        return original(graph)

    monkeypatch.setattr(module, "PreparedRawRangeTrafficProjection", counted)
    assert len(evidence.traffic) == 2
    evidence.assert_ticket(ticket)
    assert prepared == [evidence.traffic_graphs[0].receipt.request_id]


def test_positive_selected_counts_do_not_override_zero_ceiling() -> None:
    ticket, evidence, policy = ready()
    goal = ticket.inputs.goal.model_dump(mode="python")
    goal["definition"]["budget_micros"] = 0
    goal["definition_digest"] = fingerprint(
        "goal-definition",
        ticket.inputs.goal.definition.model_copy(update=dict(budget_micros=0)).model_dump(
            mode="json"
        ),
    )
    ticket, evidence = revised(ticket, evidence, total_ceiling_micros=0, goal=goal)
    result = compose(ticket, evidence, policy)
    assert all(
        action.kind == "investigate" and action.native_budget is None for action in result.actions
    )
    assert all(s.ceiling_micros == 0 for s in result.scenarios)
    assert "selected count 10" in result.actions[0].rationale


def fold_ready(monkeypatch: pytest.MonkeyPatch) -> tuple[Any, Any, Any]:
    from datetime import UTC, datetime
    from zoneinfo import ZoneInfo

    from tests import test_selected_plan_bundle as fixture
    from tests.test_planning_metadata_binding import bundle

    original = bundle
    expiry = datetime(2026, 11, 1, 1, 45, tzinfo=ZoneInfo("America/New_York"), fold=0)
    observed = expiry.astimezone(UTC) - timedelta(minutes=4)

    def native(platform: str) -> Any:
        inventory, metadata = original(platform)
        inventory = type(inventory).model_validate(
            inventory.model_copy(
                update={
                    "observation_started_at": observed,
                    "observed_at": observed,
                    "expires_at": expiry,
                }
            )
        )
        metadata = type(metadata).model_validate(
            metadata.model_copy(
                update={
                    "observation_started_at": observed,
                    "observed_at": observed,
                    "expires_at": expiry,
                    "native_inventory_digest": inventory.digest(),
                }
            )
        )
        return inventory, metadata

    monkeypatch.setattr(fixture, "native_bundle", native)
    return ready()


def test_fold_traffic_deadline_cannot_exceed_selected_deadline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from datetime import datetime
    from zoneinfo import ZoneInfo

    ticket, evidence, _ = fold_ready(monkeypatch)
    later = datetime(2026, 11, 1, 1, 15, tzinfo=ZoneInfo("America/New_York"), fold=1)
    assert later < evidence.selected.catalogs[0].reference.expires_at
    evidence = evidence.model_copy(
        update={
            "traffic": tuple(
                x.model_copy(
                    update={"reference": x.reference.model_copy(update={"expires_at": later})}
                )
                for x in evidence.traffic
            )
        }
    )
    with pytest.raises(ValueError, match="deadline changed"):
        evidence.assert_ticket(ticket)


def test_fold_generation_after_expiry_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from app.planning_documents.composer import PlanCompositionUnavailable

    ticket, evidence, policy = fold_ready(monkeypatch)
    generated = datetime(2026, 11, 1, 1, 30, tzinfo=ZoneInfo("America/New_York"), fold=1)
    assert generated < evidence.selected.catalogs[0].reference.expires_at
    with pytest.raises(PlanCompositionUnavailable, match="expired"):
        SelectedPlanComposer().compose(
            ticket=ticket, evidence=evidence, policy=policy, generated_at=generated
        )


def test_offset_equivalent_generation_is_identical(monkeypatch: pytest.MonkeyPatch) -> None:
    from datetime import UTC, timezone

    ticket, evidence, policy = fold_ready(monkeypatch)
    expiry = evidence.selected.catalogs[0].reference.expires_at
    generated = expiry.astimezone(UTC) - timedelta(minutes=1)
    first = SelectedPlanComposer().compose(
        ticket=ticket,
        evidence=evidence,
        policy=policy,
        generated_at=generated.astimezone(timezone(timedelta(hours=9))),
    )
    second = SelectedPlanComposer().compose(
        ticket=ticket, evidence=evidence, policy=policy, generated_at=generated
    )
    assert first.model_dump(mode="json") == second.model_dump(mode="json")
    assert first.digest() == second.digest()
    assert first.valid_until == expiry.astimezone(UTC)
