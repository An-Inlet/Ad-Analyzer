"""Pure explicit selected graphs; no owned reader or activated v4 runtime."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from app.campaign_performance.selected_contracts import (
    CustomerEventSelectionV1,
    SelectedCaptureRequestV1,
    SelectedCaptureV1,
    capture_request_digest,
    selection_digest,
)
from app.google_connections.selected_presence import PRODUCER, query_profile_digest
from app.planning_catalog.metadata_contracts import PlanningMetadataV1
from app.planning_catalog.projection_v2 import project_v2
from app.planning_documents.common import fingerprint
from app.planning_documents.context import AccountRef, EvidenceRef, ReportingWindow, TargetRef
from app.planning_documents.ports import (
    CatalogEvidence,
    GenerationTicket,
    PlanningCompositionPolicy,
    SourceFence,
)
from app.planning_documents.selected_plan_bundle import (
    METRIC_BASIS,
    SelectedPlanEvidenceBundleV1,
    SelectedReportingGapV1,
    SelectedWindowEvidenceV1,
    selected_entry_key,
)
from app.planning_documents.selected_plan_evidence import (
    SelectedPlanCaptureV1,
    project_selected_plan_window,
)
from app.planning_documents.selected_plan_proof import SelectedRetainedProofV1

from tests.test_planning_document_contracts import packet
from tests.test_planning_metadata_binding import bundle as native_bundle
from tests.test_selected_reporting_contracts import request as original_request


def ready(
    *, value: str | None = "10", profile: bool = True, complete: bool = False
) -> tuple[GenerationTicket, SelectedPlanEvidenceBundleV1]:
    inv, metadata = native_bundle("google")
    zone = ZoneInfo("America/New_York")
    windows = (
        ReportingWindow(
            starts_at=datetime(2026, 9, 1, tzinfo=zone),
            ends_at_exclusive=datetime(2026, 10, 1, tzinfo=zone),
        ),
        ReportingWindow(
            starts_at=datetime(2026, 8, 1, tzinfo=zone),
            ends_at_exclusive=datetime(2026, 9, 1, tzinfo=zone),
        ),
    )
    raw = inv.model_dump()
    raw["request"].update(
        period_start=windows[0].starts_at, period_end=windows[0].ends_at_exclusive
    )
    inv = type(inv).model_validate(raw)
    metadata = PlanningMetadataV1.model_validate(
        metadata.model_copy(
            update=dict(
                native_inventory_digest=inv.digest(),
                request_digest=inv.request.digest(),
                reporting_starts_at=windows[0].starts_at,
                reporting_ends_at=windows[0].ends_at_exclusive,
            )
        )
    )
    catalog = project_v2(inv, metadata)
    account = AccountRef(
        workspace_id=metadata.workspace_id,
        account_id=metadata.account_id,
        connection_id=metadata.connection_id,
        platform="google_ads",
        connection_version=metadata.connection_version,
    )
    fence = SourceFence(
        account=account,
        source_binding_digest=metadata.source_binding_digest,
        source_revision=account.connection_version,
        privacy_revision=0,
    )
    req = original_request().model_dump()
    scope = req["aggregate"]["scope"]
    scope.update(account_id=account.account_id, connection_id=account.connection_id)
    req["aggregate"].update(starts_on="2026-08-01", ends_on="2026-09-30")
    choice = req["selection"]
    choice["scope"] = scope
    choice["query_profile_digest"] = query_profile_digest("conversions") if profile else "c" * 64
    choice = CustomerEventSelectionV1.model_validate(choice)
    req.update(
        selection=choice,
        selection_digest=selection_digest(choice),
        requested_starts_on="2026-08-01",
        requested_ends_on="2026-09-30",
        producer_contract=PRODUCER if profile else "fixture.action.v1",
        query_profile_digest=choice.query_profile_digest,
    )
    req["attribution"]["producer_contract"] = req["producer_contract"]
    request = SelectedCaptureRequestV1.model_validate(req)
    digest = capture_request_digest(request)
    capture = SelectedCaptureV1.model_validate(
        dict(
            request=request,
            request_digest=digest,
            completed_at="2026-10-01T12:01:00Z",
            capability="supported",
            pagination_complete=True,
            page_count=1,
            facts=[
                dict(
                    capture_id=request.capture_id,
                    request_digest=digest,
                    campaign_id=5,
                    native_campaign_id="1",
                    metric_date="2026-09-30",
                    selected_conversions=dict(
                        presence="missing" if value is None else "present", value=value
                    ),
                    selected_value_micros=dict(presence="unsupported", value=None),
                )
            ],
        )
    )
    if complete:
        fact = capture.facts[0]
        facts = tuple(
            fact.model_copy(update={"metric_date": request.requested_starts_on + timedelta(days=n)})
            for n in range(61)
        )
        capture = SelectedCaptureV1.model_validate(capture.model_copy(update={"facts": facts}))
    graph = SelectedPlanCaptureV1(
        source_fence=fence,
        capture=capture,
        campaigns=(dict(campaign_id=5, native_campaign_id="1"),),
    )
    proof = SelectedRetainedProofV1(
        accounts=(
            dict(
                source_fence=fence,
                legacy_reporting_digest="9" * 64,
                selection_head=dict(
                    selection_id=request.selection.selection_id,
                    selection_digest=request.selection_digest,
                    invalidated=False,
                ),
                capture_pin=graph.pin(),
            ),
        )
    )
    data = packet("google_ads")["inputs"]
    data.update(
        accounts=(account,),
        reporting_window=windows[0],
        comparison_window=windows[1],
        created_at=metadata.observed_at,
        selected_reporting=(dict(account_id=account.account_id, capture_id=request.capture_id),),
    )
    policy = PlanningCompositionPolicy(
        version="inlet.descriptive-review.v4", generator_version="inlet.descriptive-planning.v4"
    )
    ticket = GenerationTicket(
        operation_id="e" * 32,
        actor_id="a" * 32,
        session_digest="b" * 64,
        inputs=data,
        expected_version=0,
        expected_parent_digest=None,
        privacy_revision=0,
        sources=(fence,),
        policy_version=policy.version,
        policy_digest=policy.digest(),
        prepared_at=metadata.observed_at,
    )
    ref = dict(
        key="catalog",
        workspace_id=account.workspace_id,
        account=account,
        kind="native_catalog",
        document_schema=catalog.schema_version,
        document_digest=catalog.composite_digest,
        source_binding_digest=fence.source_binding_digest,
        source_revision=fence.source_revision,
        privacy_revision=0,
        reporting_window=windows[0],
        observation_started_at=metadata.observation_started_at,
        observed_at=metadata.observed_at,
        expires_at=catalog.expires_at,
        coverage="complete_in_declared_scope"
        if all(c.status == "complete" for c in catalog.native_observation.coverage)
        and all(c.status == "complete" for c in catalog.metadata_observation.coverage)
        else "partial",
        declared_scope="Exact owned catalog",
        reasons=("attribution_unavailable",),
        metric_basis="Native settings",
    )
    cat = CatalogEvidence(reference=ref, catalog=catalog)
    entity = next(t for t in catalog.targets if t.entity.kind == "campaign")
    target = TargetRef(
        account=account,
        provider_reference=entity.entity.reference,
        canonical_entity_key=entity.canonical_entity_key,
        selection_key=entity.selection_key,
        catalog_evidence_key="catalog",
        kind="campaign",
        display_name=entity.entity.name,
        budget_owner_key=entity.budget_owner_key,
    )
    performance = []
    for window in windows:
        doc = project_selected_plan_window(graph, campaign_id=5, requested_window=window)
        r = ref | dict(
            key=selected_entry_key(account.account_id, 5, window),
            kind="reported_metrics",
            document_schema=doc.schema_version,
            document_digest=fingerprint("selected-plan-window", doc.model_dump(mode="json")),
            reporting_window=window,
            observation_started_at=request.started_at,
            observed_at=capture.completed_at,
            coverage="partial" if doc.summary.conversions.present_days else "unavailable",
            metric_basis=METRIC_BASIS,
        )
        performance.append(
            SelectedWindowEvidenceV1(
                reference=EvidenceRef.model_validate(r), target=target, document=doc
            )
        )
    result = SelectedPlanEvidenceBundleV1(
        operation_id=ticket.operation_id,
        input_digest=ticket.inputs.digest(),
        privacy_revision=0,
        collected_at=metadata.observed_at,
        catalogs=(cat,),
        performance=tuple(performance),
        commerce=None,
        context=(),
        gaps=(),
        reporting_proof=proof,
        selected_captures=(graph,),
        window_gaps=(),
    )
    return ticket, result


@pytest.mark.parametrize("value", ["10", "0", "0.123456", None])
def test_exact_requested_months_recompute_selected_cells(value: str | None) -> None:
    ticket, bundle = ready(value=value)
    bundle.assert_ticket(ticket)
    first, second = bundle.performance
    assert first.document.summary.conversions.value == (
        Decimal(value) if value is not None else None
    )
    assert second.document.summary.conversions.value is None
    assert not first.document.summary.zero_for_requested_window
    assert not second.document.summary.zero_for_requested_window
    assert SelectedPlanEvidenceBundleV1.model_validate_json(bundle.model_dump_json()) == bundle


@pytest.mark.parametrize(
    "change",
    [
        "missing_slot",
        "duplicate_slot",
        "capture_missing",
        "pin",
        "time",
        "policy",
        "native",
        "summary",
    ],
)
def test_tampered_graph_or_slot_rejected(change: str) -> None:
    ticket, bundle = ready()
    p = bundle.performance[0]
    if change == "missing_slot":
        bundle = bundle.model_copy(update={"performance": bundle.performance[:1]})
    elif change == "duplicate_slot":
        bundle = bundle.model_copy(update={"performance": (p, p)})
    elif change == "capture_missing":
        bundle = bundle.model_copy(update={"selected_captures": ()})
    elif change == "pin":
        bundle = bundle.model_copy(
            update={"reporting_proof": bundle.reporting_proof.model_copy(update={"accounts": ()})}
        )
    elif change == "time":
        bundle = bundle.model_copy(
            update={"collected_at": ticket.prepared_at - timedelta(seconds=1)}
        )
    elif change == "policy":
        ticket = ticket.model_copy(update={"policy_digest": "0" * 64})
    elif change == "native":
        bundle = bundle.model_copy(
            update={
                "performance": (
                    p.model_copy(
                        update={
                            "target": p.target.model_copy(
                                update={
                                    "provider_reference": p.target.provider_reference.model_copy(
                                        update={"entity_id": "999"}
                                    )
                                }
                            )
                        }
                    ),
                    bundle.performance[1],
                )
            }
        )
    else:
        bundle = bundle.model_copy(
            update={
                "performance": (
                    p.model_copy(
                        update={
                            "document": p.document.model_copy(
                                update={
                                    "summary": p.document.summary.model_copy(
                                        update={"zero_for_requested_window": True}
                                    )
                                }
                            )
                        }
                    ),
                    bundle.performance[1],
                )
            }
        )
    with pytest.raises(ValueError):
        bundle.assert_ticket(ticket)


def test_unknown_fixture_profile_requires_explicit_unsupported_gaps() -> None:
    ticket, bundle = ready(profile=False)
    with pytest.raises(ValueError, match="recognized"):
        bundle.assert_ticket(ticket)
    gaps = tuple(
        SelectedReportingGapV1(
            account=p.target.account,
            target=p.target,
            requested_window=p.document.requested_window,
            reason="unsupported_selected_mapping",
            reporting_pin_digest=bundle.reporting_proof.accounts[0].state_digest(),
            explanation="Profile is unsupported.",
        )
        for p in bundle.performance
    )
    bundle = bundle.model_copy(update={"performance": (), "window_gaps": gaps})
    bundle.assert_ticket(ticket)
    wrong = gaps[0].model_copy(update={"reason": "campaign_outside_captured_mapping"})
    with pytest.raises(ValueError):
        bundle.model_copy(update={"window_gaps": (wrong, gaps[1])}).assert_ticket(ticket)


def test_canonical_v4_is_not_registered() -> None:
    from app.planning_documents.policy_capabilities import reporting_capability

    with pytest.raises(ValueError):
        reporting_capability("inlet.descriptive-review.v4", "inlet.descriptive-planning.v4")


def gap_bundle(
    ticket: GenerationTicket, bundle: SelectedPlanEvidenceBundleV1, reason: str
) -> SelectedPlanEvidenceBundleV1:
    gaps = tuple(
        SelectedReportingGapV1.model_validate(
            dict(
                account=p.target.account,
                target=p.target,
                requested_window=p.document.requested_window,
                reason=reason,
                reporting_pin_digest=bundle.reporting_proof.accounts[0].state_digest(),
                explanation="Explicit bounded gap.",
            )
        )
        for p in bundle.performance
    )
    return SelectedPlanEvidenceBundleV1.model_validate(
        bundle.model_copy(update={"performance": (), "window_gaps": gaps})
    )


def test_explicit_no_capture_and_missing_campaign_have_distinct_exact_gaps() -> None:
    ticket, bundle = ready()
    source = bundle.selected_captures[0]
    empty_capture = SelectedCaptureV1.model_validate(
        source.capture.model_copy(update={"facts": ()})
    )
    empty = SelectedPlanCaptureV1(
        source_fence=source.source_fence, capture=empty_capture, campaigns=()
    )
    proof = SelectedRetainedProofV1(
        accounts=(
            bundle.reporting_proof.accounts[0].model_copy(update={"capture_pin": empty.pin()}),
        )
    )
    changed = bundle.model_copy(update={"selected_captures": (empty,), "reporting_proof": proof})
    changed = gap_bundle(ticket, changed, "campaign_outside_captured_mapping")
    changed.assert_ticket(ticket)
    wrong = changed.window_gaps[0].model_copy(update={"reason": "unsupported_selected_mapping"})
    with pytest.raises(ValueError):
        changed.model_copy(update={"window_gaps": (wrong, changed.window_gaps[1])}).assert_ticket(
            ticket
        )

    inputs = ticket.inputs.model_copy(update={"selected_reporting": ()})
    ticket = GenerationTicket.model_validate(ticket.model_copy(update={"inputs": inputs}))
    proof = SelectedRetainedProofV1(
        accounts=(bundle.reporting_proof.accounts[0].model_copy(update={"capture_pin": None}),)
    )
    changed = bundle.model_copy(
        update={"selected_captures": (), "reporting_proof": proof, "input_digest": inputs.digest()}
    )
    changed = gap_bundle(ticket, changed, "selected_capture_not_requested")
    changed.assert_ticket(ticket)
    with pytest.raises(ValueError):
        changed.model_copy(update={"window_gaps": changed.window_gaps[:1]}).assert_ticket(ticket)


@pytest.mark.parametrize(
    "field,value",
    [
        ("source_revision", "other"),
        ("privacy_revision", 1),
        ("metric_basis", "aggregate conversions"),
        ("coverage", "complete_in_declared_scope"),
        ("observed_at", datetime(2026, 10, 1, 13, tzinfo=UTC)),
    ],
)
def test_reference_cannot_relabel_or_restamp(field: str, value: Any) -> None:
    ticket, bundle = ready()
    p = bundle.performance[0]
    p = p.model_copy(update={"reference": p.reference.model_copy(update={field: value})})
    with pytest.raises(ValueError):
        bundle.model_copy(update={"performance": (p, bundle.performance[1])}).assert_ticket(ticket)


def test_capacity_and_collected_instant_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.planning_documents import selected_plan_bundle

    ticket, bundle = ready()
    from datetime import timezone

    offset = timezone(timedelta(hours=-4))
    bundle.model_copy(
        update={"collected_at": bundle.collected_at.astimezone(offset)}
    ).assert_ticket(ticket)
    with pytest.raises(ValueError):
        bundle.model_copy(update={"collected_at": bundle.collected_at.timestamp()}).assert_ticket(
            ticket
        )
    monkeypatch.setattr(selected_plan_bundle, "MAX_BYTES", 100)
    with pytest.raises(ValueError, match="byte capacity"):
        bundle.assert_ticket(ticket)


def test_complete_explicit_zero_is_not_missing_value_or_missing_day() -> None:
    ticket, bundle = ready(value="0", complete=True)
    bundle.assert_ticket(ticket)
    for item, days in zip(bundle.performance, (30, 31), strict=True):
        assert item.document.summary.zero_for_requested_window
        assert item.document.summary.conversions.value == Decimal(0)
        assert item.document.summary.conversions.present_days == days
        assert item.document.summary.value_micros.value is None
        assert item.reference.coverage == "partial"


@pytest.mark.parametrize("empty", [False, True])
def test_catalog_absence_and_actual_empty_catalog_require_null_slots(empty: bool) -> None:
    from app.planning_documents.ports import EvidenceGap

    ticket, bundle = ready()
    catalogs: tuple[CatalogEvidence, ...] = ()
    gaps: tuple[EvidenceGap, ...] = (
        EvidenceGap(
            account=ticket.inputs.accounts[0],
            section="catalog",
            reason="catalog_unavailable",
            explanation="Unavailable",
        ),
    )
    reason = "catalog_unavailable"
    if empty:
        inv, metadata = native_bundle("google")
        raw = inv.model_dump()
        raw["request"].update(
            period_start=ticket.inputs.reporting_window.starts_at,
            period_end=ticket.inputs.reporting_window.ends_at_exclusive,
        )
        raw["campaigns"] = ()
        inv = type(inv).model_validate(raw)
        changes = metadata.model_dump()
        changes.update(
            entities=(),
            native_inventory_digest=inv.digest(),
            request_digest=inv.request.digest(),
            reporting_starts_at=ticket.inputs.reporting_window.starts_at,
            reporting_ends_at=ticket.inputs.reporting_window.ends_at_exclusive,
        )
        for c in changes["coverage"]:
            c["count"] = 0
        catalog = project_v2(inv, PlanningMetadataV1.model_validate(changes))
        reference = bundle.catalogs[0].reference.model_copy(
            update={"document_digest": catalog.composite_digest}
        )
        catalogs = (CatalogEvidence(reference=reference, catalog=catalog),)
        gaps = ()
        reason = "no_catalog_campaigns"
    windows = tuple(
        SelectedReportingGapV1.model_validate(
            dict(
                account=p.target.account,
                target=None,
                requested_window=p.document.requested_window,
                reason=reason,
                reporting_pin_digest=bundle.reporting_proof.accounts[0].state_digest(),
                explanation="Explicit catalog gap.",
            )
        )
        for p in bundle.performance
    )
    changed = bundle.model_copy(
        update={"catalogs": catalogs, "performance": (), "gaps": gaps, "window_gaps": windows}
    )
    changed.assert_ticket(ticket)
    with pytest.raises(ValueError):
        changed.model_copy(update={"window_gaps": windows[:1]}).assert_ticket(ticket)
