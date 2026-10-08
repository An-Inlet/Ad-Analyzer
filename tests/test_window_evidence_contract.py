"""Private pure evidence contracts; no owned reader or runtime v3 activation."""

from datetime import UTC, timedelta, timezone
from typing import Any

import pytest
from app.campaign_performance.presence_report import CampaignPerformanceV3, campaign_summary
from app.campaign_performance.window_projection import project_requested_window
from app.planning_documents.common import fingerprint
from app.planning_documents.context import EvidenceRef, ReportingWindow, TargetRef
from app.planning_documents.policy_capabilities import (
    reporting_capability,
    ticket_reporting_capability,
)
from app.planning_documents.ports import GenerationTicket, PlanningCompositionPolicy
from app.planning_documents.window_evidence import (
    WindowEvidenceBundleV1,
    WindowPerformanceEvidenceV1,
    WindowReportingGapV1,
    reporting_entry_key,
)
from pydantic import ValidationError

from tests.test_planning_document_ports import performance_data, ready_bundle
from tests.test_reporting_presence_contracts import fact, header


def policy(version: int = 3) -> PlanningCompositionPolicy:
    return PlanningCompositionPolicy(
        version=f"inlet.descriptive-review.v{version}",
        generator_version=f"inlet.descriptive-planning.v{version}",
    )


def ready(
    two: bool = False, count: str | None = "10"
) -> tuple[GenerationTicket, WindowEvidenceBundleV1]:
    ticket, old = ready_bundle()
    inputs = ticket.inputs.model_dump(mode="python")
    window = ticket.inputs.reporting_window
    if two:
        inputs["comparison_window"] = ReportingWindow(
            starts_at=window.starts_at - timedelta(days=1), ends_at_exclusive=window.starts_at
        )
    ticket = GenerationTicket.model_validate(
        ticket.model_copy(
            update=dict(
                inputs=inputs, policy_version=policy().version, policy_digest=policy().digest()
            )
        )
    )
    catalog = old.catalogs[0]
    raw = performance_data(old)
    target = TargetRef.model_validate(raw["target"])
    account = target.account
    start = (window.starts_at - timedelta(days=1)).date() if two else window.starts_at.date()
    end = (window.ends_at_exclusive - timedelta(days=1)).date()
    rows = tuple(
        fact(
            workspace_id=account.workspace_id,
            account_id=account.account_id,
            campaign_id=1,
            native_campaign_id=target.provider_reference.entity_id,
            metric_date=start + timedelta(days=i),
            selected_conversions=dict(
                presence="present" if count is not None else "missing", value=count
            ),
        )
        for i in range((end - start).days + 1)
    )
    h = header(
        rows,
        workspace_id=account.workspace_id,
        account_id=account.account_id,
        connection_id=account.connection_id,
        time_zone="UTC",
        requested_starts_on=start,
        requested_ends_on=end,
        actual_starts_on=start,
        actual_ends_on=end,
        completed_at=old.collected_at,
        legacy_manifest_digest=raw["document"].manifest_digest,
    )
    legacy = raw["document"].model_copy(
        update=dict(starts_on=start, ends_on=end, reported_day_count=len(rows), conversions=count)
    )
    original = CampaignPerformanceV3(
        legacy=legacy,
        presence=h,
        native_campaign_id=target.provider_reference.entity_id,
        campaign_facts=rows,
        summary=campaign_summary(h, rows, 1, target.provider_reference.entity_id),
    )
    performance = []
    for wanted in (window, ticket.inputs.comparison_window):
        if wanted is None:
            continue
        doc = project_requested_window(original, requested_window=wanted)
        reference = catalog.reference.model_dump(mode="python")
        reference.update(
            key=reporting_entry_key(account.account_id, 1, wanted),
            kind="reported_metrics",
            document_schema=doc.schema_version,
            document_digest=fingerprint(
                "requested-window-performance", doc.model_dump(mode="json")
            ),
            source_binding_digest=original.manifest_digest,
            source_revision="1",
            observation_started_at=original.completed_at,
            observed_at=original.completed_at,
            reporting_window=wanted,
            coverage="partial",
        )
        performance.append(
            WindowPerformanceEvidenceV1(
                reference=EvidenceRef.model_validate(reference),
                target=target,
                document=doc,
                completeness="reported_rows_only",
                conversion_qualification="reported_only" if count is not None else "unavailable",
                reasons=("attribution_unavailable",),
            )
        )
    bundle = WindowEvidenceBundleV1(
        operation_id=ticket.operation_id,
        input_digest=ticket.inputs.digest(),
        privacy_revision=0,
        collected_at=old.collected_at,
        catalogs=old.catalogs,
        performance=tuple(performance),
        commerce=None,
        context=(),
        gaps=(),
        reporting_pins=(dict(account=account, document_digest="d" * 64),),
        window_gaps=(),
    )
    bundle.assert_ticket(ticket)
    return ticket, bundle


def gap_for(bundle: WindowEvidenceBundleV1, index: int = 0, **updates: Any) -> WindowReportingGapV1:
    p = bundle.performance[index]
    return WindowReportingGapV1.model_validate(
        dict(
            account=p.target.account,
            target=p.target,
            requested_window=p.document.requested_window,
            reason="outside_imported_window",
            reporting_pin_digest=bundle.reporting_pins[0].document_digest,
            explanation="Requested period is outside this actual import.",
        )
        | updates
    )


@pytest.mark.parametrize(
    "version,mode,witness",
    [
        (1, "legacy_exact_window", "local_reporting_v1"),
        (2, "presence_exact_window", "local_reporting_v2"),
        (3, "presence_requested_window", "local_reporting_v2"),
    ],
)
def test_closed_canonical_policy_pairs(version: int, mode: str, witness: str) -> None:
    p = policy(version)
    original = p.model_dump_json()
    result = reporting_capability(p.version, p.generator_version)
    assert (result.mode, result.local_witness_kind) == (mode, witness)
    assert ticket_reporting_capability(p.version, p.digest()) == result
    assert p.model_dump_json() == original
    with pytest.raises(ValueError):
        reporting_capability(p.version, "inlet.descriptive-planning.v4")
    with pytest.raises(ValueError):
        ticket_reporting_capability(p.version, "0" * 64)
    with pytest.raises(ValueError):
        ticket_reporting_capability(p.version, policy(1 if version != 1 else 2).digest())


@pytest.mark.parametrize("two", [False, True])
@pytest.mark.parametrize("count", ["10", "0", None])
def test_exact_slots_positive_zero_and_missing(two: bool, count: str | None) -> None:
    ticket, bundle = ready(two, count)
    assert len(bundle.performance) == (2 if two else 1)
    for p in bundle.performance:
        assert p.document.summary.clicks.value == 100
        assert p.document.summary.spend_micros.value == 100_000_000
        assert p.document.summary.selected_conversions.value == count
        assert p.document.summary.selected_zero_for_requested_window == (count == "0")
    if two:
        mixed = bundle.model_copy(
            update=dict(performance=bundle.performance[:1], window_gaps=(gap_for(bundle, 1),))
        )
        mixed.assert_ticket(ticket)


def test_utc_equivalent_keys_and_no_coercive_ids() -> None:
    ticket, bundle = ready()
    window = ticket.inputs.reporting_window
    shifted = ReportingWindow(
        starts_at=window.starts_at.astimezone(timezone(timedelta(hours=3))),
        ends_at_exclusive=window.ends_at_exclusive.astimezone(UTC),
    )
    assert reporting_entry_key(
        bundle.performance[0].target.account.account_id, 1, window
    ) == reporting_entry_key(bundle.performance[0].target.account.account_id, 1, shifted)
    for bad in (True, "1", 1.0):
        with pytest.raises(ValueError):
            reporting_entry_key(bad, 1, window)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "change",
    [
        "omitted",
        "duplicate",
        "both",
        "wrongpin",
        "unrequested",
        "selector",
        "name",
        "context",
        "privacy",
        "expiry",
        "source",
        "ticketpolicy",
        "oldpolicy",
        "foreign",
        "authority",
    ],
)
def test_reject_slot_binding_and_ticket_mutations(change: str) -> None:
    ticket, bundle = ready(True)
    first = bundle.performance[0]
    if change == "omitted":
        bundle = bundle.model_copy(update=dict(performance=bundle.performance[:1]))
    elif change == "duplicate":
        bundle = bundle.model_copy(update=dict(performance=(first, first)))
    elif change == "both":
        bundle = bundle.model_copy(update=dict(window_gaps=(gap_for(bundle),)))
    elif change == "wrongpin":
        bundle = bundle.model_copy(
            update=dict(
                performance=bundle.performance[:1],
                window_gaps=(gap_for(bundle, 1, reporting_pin_digest="e" * 64),),
            )
        )
    elif change == "unrequested":
        bundle = bundle.model_copy(
            update=dict(
                performance=bundle.performance[:1],
                window_gaps=(
                    gap_for(
                        bundle,
                        1,
                        requested_window=ReportingWindow(
                            starts_at=ticket.inputs.reporting_window.starts_at - timedelta(days=5),
                            ends_at_exclusive=ticket.inputs.reporting_window.starts_at
                            - timedelta(days=4),
                        ),
                    ),
                ),
            )
        )
    elif change in {"selector", "name", "foreign"}:
        updates = (
            {"selection_key": "e" * 64} if change == "selector" else {"display_name": "Different"}
        )
        target = first.target.model_copy(update=updates)
        if change == "foreign":
            target = target.model_copy(
                update=dict(account=target.account.model_copy(update=dict(account_id=999)))
            )
        bundle = bundle.model_copy(
            update=dict(
                performance=(first.model_copy(update=dict(target=target)),) + bundle.performance[1:]
            )
        )
    elif change == "context":
        bundle = bundle.model_copy(update=dict(input_digest="0" * 64))
    elif change == "privacy":
        bundle = bundle.model_copy(update=dict(privacy_revision=1))
    elif change == "expiry":
        bundle = bundle.model_copy(
            update=dict(collected_at=bundle.catalogs[0].reference.expires_at)
        )
    elif change == "source":
        ticket = ticket.model_copy(
            update=dict(
                sources=(ticket.sources[0].model_copy(update=dict(source_binding_digest="0" * 64)),)
            )
        )
    elif change == "ticketpolicy":
        ticket = ticket.model_copy(update=dict(policy_digest="0" * 64))
    elif change == "oldpolicy":
        ticket = ticket.model_copy(
            update=dict(policy_version=policy(2).version, policy_digest=policy(2).digest())
        )
    elif change == "authority":
        bundle = bundle.model_copy(update=dict(advertising_writes_enabled=0))
    with pytest.raises(ValueError):
        bundle.assert_ticket(ticket)


def test_catalog_absence_and_conflicting_coverage() -> None:
    ticket, bundle = ready(True)
    account = ticket.inputs.accounts[0]
    from app.planning_documents.ports import EvidenceGap

    catalog_gap = EvidenceGap(
        account=account, section="catalog", reason="unavailable", explanation="No catalog."
    )
    empty = bundle.model_copy(
        update=dict(
            catalogs=(),
            performance=(),
            gaps=(catalog_gap,),
            window_gaps=tuple(
                gap_for(bundle, i, target=None, reason="catalog_unavailable") for i in range(2)
            ),
        )
    )
    empty.assert_ticket(ticket)
    for invalid in (
        empty.model_copy(update=dict(window_gaps=empty.window_gaps[:1])),
        bundle.model_copy(update=dict(gaps=(catalog_gap,))),
        bundle.model_copy(update=dict(performance=(), window_gaps=empty.window_gaps)),
    ):
        with pytest.raises(ValueError):
            invalid.assert_ticket(ticket)


@pytest.mark.parametrize(
    "field,value",
    [
        ("source_revision", "2"),
        ("key", "wrong"),
        ("document_digest", "0" * 64),
        ("coverage", "complete_in_declared_scope"),
        ("privacy_revision", 1),
    ],
)
def test_reference_claims_revalidated(field: str, value: Any) -> None:
    _, bundle = ready()
    p = bundle.performance[0]
    with pytest.raises(ValidationError):
        WindowPerformanceEvidenceV1.model_validate(
            p.model_copy(update=dict(reference=p.reference.model_copy(update={field: value})))
        )


def test_combined_slot_and_serialized_byte_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.planning_documents import window_evidence as module

    _, bundle = ready()
    gap = gap_for(bundle)
    # Construction cap is independent of later exact-set validation.
    at = WindowEvidenceBundleV1.model_validate(
        bundle.model_copy(update=dict(performance=(), window_gaps=(gap,) * 400))
    )
    with pytest.raises(ValueError, match="capacity"):
        WindowEvidenceBundleV1.model_validate(
            at.model_copy(update=dict(performance=bundle.performance))
        )
    size = len(bundle.model_dump_json().encode())
    monkeypatch.setattr(module, "MAX_COLLECTION_BYTES", size)
    assert WindowEvidenceBundleV1.model_validate(bundle) == bundle
    monkeypatch.setattr(module, "MAX_COLLECTION_BYTES", size - 1)
    with pytest.raises(ValueError, match="capacity"):
        WindowEvidenceBundleV1.model_validate(bundle)


def test_legacy_policy_digests_unchanged_and_legacy_composer_rejects_v3() -> None:
    from app.planning_documents.composer import DescriptivePlanComposer, PlanCompositionUnavailable

    from tests.test_planning_composer import fixture

    assert policy(1).digest() == "b322d9305633360ae46d2b94b038a5318fc654c0acf4b55aac8e5a7b34755458"
    assert policy(2).digest() == "866ee0ee39573fd7093eff1bfaaba880f3c7b182f558d0af2906c10082b8da8c"
    inputs, old, _ = fixture()
    with pytest.raises(PlanCompositionUnavailable):
        DescriptivePlanComposer().compose(
            inputs=inputs,
            evidence=old,
            policy=policy(),
            version=1,
            parent_digest=None,
            generated_by="a" * 32,
            generated_at=old.collected_at,
        )


def test_actual_empty_catalog_needs_exact_null_gaps() -> None:
    from app.planning_catalog.metadata_contracts import PlanningMetadataV1
    from app.planning_catalog.projection_v2 import project_v2
    from app.planning_documents.ports import CatalogEvidence

    from tests.test_planning_metadata_binding import bundle as native_bundle

    ticket, bundle = ready(True)
    inventory, metadata = native_bundle("meta")
    raw = inventory.model_dump(mode="python")
    raw.update(campaigns=(), adsets=())
    inventory = type(inventory).model_validate(raw)
    changed = metadata.model_dump(mode="python")
    changed.update(entities=(), native_inventory_digest=inventory.digest())
    for coverage in changed["coverage"]:
        coverage["count"] = 0
    metadata = PlanningMetadataV1.model_validate(changed)
    catalog = project_v2(inventory, metadata)
    reference = bundle.catalogs[0].reference.model_copy(
        update=dict(document_digest=catalog.composite_digest)
    )
    empty = bundle.model_copy(
        update=dict(
            catalogs=(CatalogEvidence(reference=reference, catalog=catalog),),
            performance=(),
            window_gaps=tuple(
                gap_for(bundle, i, target=None, reason="no_catalog_campaigns") for i in range(2)
            ),
        )
    )
    empty.assert_ticket(ticket)
    with pytest.raises(ValueError):
        empty.model_copy(
            update=dict(
                window_gaps=(
                    gap_for(bundle, 0, target=None, reason="catalog_unavailable"),
                    empty.window_gaps[1],
                )
            )
        ).assert_ticket(ticket)


def test_context_and_commerce_exact_binding_preserved() -> None:
    from app.planning_documents.ports import CommerceEvidence, ContextEvidence

    from tests.test_planning_document_ports import commerce_data

    ticket, bundle = ready()
    old_ticket, old = ready_bundle()
    commerce = CommerceEvidence.model_validate(commerce_data(old_ticket, old))
    contexts = []
    for key, kind, document in (
        ("customer", "customer_context", ticket.inputs),
        ("policy", "planning_policy", policy()),
    ):
        reference = bundle.catalogs[0].reference.model_copy(
            update=dict(key=key, kind=kind, account=None, document_digest=document.digest())
        )
        contexts.append(ContextEvidence(reference=reference, document=document))
    joined = bundle.model_copy(update=dict(context=tuple(contexts), commerce=commerce))
    joined.assert_ticket(ticket)
    for changed in (
        joined.model_copy(update=dict(context=(contexts[0], contexts[0]))),
        joined.model_copy(
            update=dict(context=(contexts[1].model_copy(update=dict(document=policy(2))),))
        ),
        joined.model_copy(
            update=dict(
                commerce=commerce.model_copy(
                    update=dict(
                        document=commerce.document.model_copy(update=dict(target_micros=999))
                    )
                )
            )
        ),
        joined.model_copy(
            update=dict(
                context=(
                    contexts[0].model_copy(
                        update=dict(
                            reference=contexts[0].reference.model_copy(
                                update=dict(
                                    expires_at=contexts[0].reference.expires_at
                                    + timedelta(seconds=1)
                                )
                            )
                        )
                    ),
                )
            )
        ),
    ):
        with pytest.raises(ValueError):
            changed.assert_ticket(ticket)


def test_selected_window_rows_not_original_rows_and_selected_missing_cannot_qualify() -> None:
    from app.campaign_performance.presence_contracts import presence_digest

    _, bundle = ready(True, None)
    p = bundle.performance[0]
    with pytest.raises(ValueError):
        WindowPerformanceEvidenceV1.model_validate(
            p.model_copy(update=dict(conversion_qualification="reported_only"))
        )
    original = p.document.original
    rows = original.campaign_facts[:1]  # comparison only; requested primary now has no row
    h = original.presence.model_copy(update=dict(fact_count=1, fact_digest=presence_digest(rows)))
    raw = original.model_copy(
        update=dict(
            presence=h,
            campaign_facts=rows,
            legacy=original.legacy.model_copy(update=dict(reported_day_count=1)),
            summary=campaign_summary(h, rows, 1, original.native_campaign_id),
        )
    )
    sliced = project_requested_window(raw, requested_window=p.document.requested_window)
    assert not sliced.selected_facts and sliced.original.campaign_facts
    changed = p.model_copy(
        update=dict(
            document=sliced,
            reference=p.reference.model_copy(
                update=dict(
                    document_digest=fingerprint(
                        "requested-window-performance", sliced.model_dump(mode="json")
                    )
                )
            ),
        )
    )
    with pytest.raises(ValueError, match="no returned"):
        WindowPerformanceEvidenceV1.model_validate(changed)
    unavailable = WindowPerformanceEvidenceV1.model_validate(
        changed.model_copy(
            update=dict(
                completeness="unavailable",
                reference=changed.reference.model_copy(update=dict(coverage="unavailable")),
            )
        )
    )
    assert unavailable.document.summary.selected_conversions.value is None


def test_exact_all_campaign_cross_window_slots_at_400() -> None:
    from app.planning_catalog.metadata_contracts import PlanningMetadataV1
    from app.planning_catalog.projection_v2 import project_v2
    from app.planning_documents.ports import CatalogEvidence

    from tests.test_planning_metadata_binding import bundle as native_bundle

    ticket, bundle = ready(True)
    inventory, metadata = native_bundle("meta")
    raw = inventory.model_dump(mode="python")
    raw["campaigns"] = [dict(raw["campaigns"][0], id=str(1000 + i)) for i in range(200)]
    raw["adsets"] = []
    inventory = type(inventory).model_validate(raw)
    changed = metadata.model_dump(mode="python")
    entity = next(e for e in changed["entities"] if e["kind"] == "campaign")
    changed["entities"] = [
        dict(entity, reference=dict(entity["reference"], entity_id=str(1000 + i)))
        for i in range(200)
    ]
    changed["native_inventory_digest"] = inventory.digest()
    for coverage in changed["coverage"]:
        coverage["count"] = 200 if coverage["kind"] == "campaign" else 0
    catalog = project_v2(inventory, PlanningMetadataV1.model_validate(changed))
    reference = bundle.catalogs[0].reference.model_copy(
        update=dict(document_digest=catalog.composite_digest)
    )
    gaps = []
    for actual in catalog.targets:
        target = TargetRef(
            account=ticket.inputs.accounts[0],
            provider_reference=actual.entity.reference,
            canonical_entity_key=actual.canonical_entity_key,
            selection_key=actual.selection_key,
            catalog_evidence_key=reference.key,
            kind=actual.entity.kind,
            display_name=actual.entity.name,
            budget_owner_key=actual.budget_owner_key,
        )
        for i in (0, 1):
            gaps.append(gap_for(bundle, i, target=target, reason="campaign_reporting_unavailable"))
    full = bundle.model_copy(
        update=dict(
            catalogs=(CatalogEvidence(reference=reference, catalog=catalog),),
            performance=(),
            window_gaps=tuple(gaps),
        )
    )
    full.assert_ticket(ticket)
    assert len(full.window_gaps) == 400
    for wrong in (full.window_gaps[:-1], full.window_gaps[:-1] + (full.window_gaps[0],)):
        with pytest.raises(ValueError):
            full.model_copy(update=dict(window_gaps=wrong)).assert_ticket(ticket)


def test_actual_32_mib_serialized_bundle_bound() -> None:
    from app.campaign_performance.window_projection import RequestedWindowPerformanceV1
    from app.planning_documents.window_evidence import MAX_COLLECTION_BYTES

    _, bundle = ready()
    p = bundle.performance[0]
    # Repeated entries are permitted at construction only, before assert_ticket's
    # exact-set check. Legacy decimal text padding keeps each full projection<2MiB.
    copies = 17
    base = bundle.model_copy(update=dict(performance=(p,) * copies))
    baseline = len(base.model_dump_json().encode())
    quotient, remainder = divmod(MAX_COLLECTION_BYTES - baseline, copies)

    def padded(extra: int) -> WindowPerformanceEvidenceV1:
        raw = p.document.original.model_dump(mode="python")
        raw["legacy"]["conversions"] = "10." + "0" * extra
        original = CampaignPerformanceV3.model_validate(raw)
        doc = project_requested_window(original, requested_window=p.document.requested_window)
        # Original fixture value is '10', adding a decimal point plus N zeros
        # adds exactly N+1 bytes. Adjust the requested increase accordingly.
        return WindowPerformanceEvidenceV1.model_validate(
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

    entries = tuple(padded(quotient + (1 if i < remainder else 0) - 1) for i in range(copies))
    at = WindowEvidenceBundleV1.model_validate(bundle.model_copy(update=dict(performance=entries)))
    assert len(at.model_dump_json().encode()) == MAX_COLLECTION_BYTES
    raw = entries[-1].document.model_dump(mode="python")
    raw["original"]["legacy"]["conversions"] += "0"
    original = CampaignPerformanceV3.model_validate(raw["original"])
    doc = project_requested_window(original, requested_window=p.document.requested_window)
    assert isinstance(doc, RequestedWindowPerformanceV1)
    extra = WindowPerformanceEvidenceV1.model_validate(
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
    with pytest.raises(ValueError, match="byte capacity"):
        WindowEvidenceBundleV1.model_validate(
            at.model_copy(update=dict(performance=entries[:-1] + (extra,)))
        )


def test_gap_slots_compare_actual_instants_not_same_zone_fold_equality() -> None:
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from app.planning_documents.ports import EvidenceGap

    ticket, bundle = ready()
    zone = ZoneInfo("America/Havana")
    first = ReportingWindow(
        starts_at=datetime(2020, 11, 1, tzinfo=zone, fold=0),
        ends_at_exclusive=datetime(2020, 11, 2, tzinfo=zone),
    )
    other = ReportingWindow(
        starts_at=datetime(2020, 11, 1, tzinfo=zone, fold=1),
        ends_at_exclusive=datetime(2020, 11, 2, tzinfo=zone),
    )
    assert first == other  # Python equality alone loses the one-hour distinction.
    inputs = ticket.inputs.model_copy(update=dict(reporting_window=first))
    ticket = GenerationTicket.model_validate(ticket.model_copy(update=dict(inputs=inputs)))
    account = ticket.inputs.accounts[0]
    gap = gap_for(bundle, target=None, reason="catalog_unavailable", requested_window=first)
    absent = bundle.model_copy(
        update=dict(
            input_digest=inputs.digest(),
            catalogs=(),
            performance=(),
            gaps=(
                EvidenceGap(
                    account=account,
                    section="catalog",
                    reason="unavailable",
                    explanation="Unavailable",
                ),
            ),
            window_gaps=(gap,),
        )
    )
    absent.assert_ticket(ticket)
    with pytest.raises(ValueError, match="exact campaign/window"):
        absent.model_copy(
            update=dict(window_gaps=(gap.model_copy(update=dict(requested_window=other)),))
        ).assert_ticket(ticket)


def test_production_service_default_stays_v2_with_separate_window_composer() -> None:
    from app.planning_documents.service import PlanningDocumentService
    from app.planning_documents.window_composer import WindowPlanComposer
    from sqlalchemy import create_engine

    from tests.test_customer_identity import FakeProvider

    engine = create_engine("sqlite://")
    try:
        service = PlanningDocumentService(engine, FakeProvider())
        assert service.policy == policy(2)
        assert isinstance(service.window_composer, WindowPlanComposer)
    finally:
        engine.dispose()
