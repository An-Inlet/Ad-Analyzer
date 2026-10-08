from copy import deepcopy
from typing import Any

import pytest
from app.planning_documents.common import fingerprint
from app.planning_documents.documents import PlanVersion
from app.planning_documents.ports import (
    EvidenceBundle,
    GenerationTicket,
    PerformanceEvidence,
    PlanningCompositionPolicy,
)
from pydantic import ValidationError

from tests.test_planning_document_contracts import packet


def ticket() -> GenerationTicket:
    inputs = PlanVersion.model_validate(packet()).inputs
    return GenerationTicket.model_validate(
        dict(
            operation_id="e" * 32,
            actor_id="a" * 32,
            session_digest="f" * 64,
            inputs=inputs,
            expected_version=0,
            expected_parent_digest=None,
            privacy_revision=0,
            sources=[
                dict(
                    account=inputs.accounts[0],
                    source_binding_digest="d" * 64,
                    source_revision="v1",
                    privacy_revision=0,
                )
            ],
            policy_version="test-v1",
            policy_digest=PlanningCompositionPolicy(
                version="test-v1", generator_version="test-v1"
            ).digest(),
            prepared_at="2026-10-01T01:00:00Z",
        )
    )


def test_bundle_explicit_gap_and_no_authority() -> None:
    intent = ticket()
    data = dict(
        operation_id=intent.operation_id,
        input_digest=intent.inputs.digest(),
        privacy_revision=0,
        collected_at="2026-10-01T01:01:00Z",
        catalogs=[],
        performance=[],
        commerce=None,
        context=[],
        gaps=[
            dict(
                account=intent.inputs.accounts[0],
                section="catalog",
                reason="native_unavailable",
                explanation="No native response",
            )
        ],
    )
    bundle = EvidenceBundle.model_validate(data)
    bundle.assert_ticket(intent)
    assert PlanningCompositionPolicy(version="v1", generator_version="v1").forecast == "unavailable"
    for field, bad in (
        ("input_digest", "0" * 64),
        ("operation_id", "0" * 32),
        ("privacy_revision", 1),
        ("gaps", ()),
    ):
        with pytest.raises(ValueError):
            bundle.model_copy(update={field: bad}).assert_ticket(intent)


@pytest.mark.parametrize("conversions", [None, "0", "10"])
def test_reported_metrics_preserve_missing_zero_positive_without_attribution(
    conversions: str | None,
) -> None:
    doc = PlanVersion.model_validate(packet("meta_ads"))
    raw = dict(
        schema_version="inlet.owned-campaign-performance.v1",
        completion_id="a" * 32,
        manifest_digest="d" * 64,
        account_id=1,
        campaign_id=1,
        generation=1,
        privacy_revision=0,
        starts_on="2026-09-01",
        ends_on="2026-09-30",
        currency="USD",
        time_zone="UTC",
        completed_at="2026-10-01T01:00:01Z",
        semantics="explicit_platform_event",
        selected_event="purchase",
        reporting_basis="provider_defaults_unspecified",
        reported_day_count=30,
        campaign_rows_available=True,
        impressions=1000,
        clicks=100,
        spend_micros=100000000,
        conversions=conversions,
        conversion_value_micros=None,
        cpa_micros=None,
        reported_roas=None,
    )
    from app.campaign_performance.contracts import CampaignPerformanceV1

    parsed = CampaignPerformanceV1.model_validate(raw)
    reference = doc.evidence[0].model_dump(mode="json")
    reference.update(
        kind="reported_metrics",
        document_schema=parsed.schema_version,
        reporting_window=dict(
            starts_at="2026-09-01T00:00:00Z", ends_at_exclusive="2026-10-01T00:00:00Z"
        ),
        document_digest=fingerprint("campaign-performance", parsed.model_dump(mode="json")),
    )
    data = dict(
        reference=reference,
        target=doc.actions[0].target,
        document=parsed,
        native_campaign_id="123",
        completeness="reported_rows_only",
        conversion_qualification="reported_only" if conversions == "10" else "unavailable",
        reasons=["attribution_window_unspecified"],
    )
    value = PerformanceEvidence.model_validate(data)
    assert value.document.conversions == conversions
    assert value.attribution_qualification == "unavailable"
    bad = deepcopy(data)
    bad["document"] = parsed.model_copy(update={"clicks": True})
    with pytest.raises(ValidationError):
        PerformanceEvidence.model_validate(bad)
    bad = {**data, "native_campaign_id": "456"}
    with pytest.raises(ValidationError):
        PerformanceEvidence.model_validate(bad)


@pytest.mark.parametrize("platform", ["google", "meta", "tiktok"])
def test_actual_catalog_reference_summary_cannot_forge_scope_or_time(platform: str) -> None:
    from datetime import timedelta

    from app.planning_catalog.projection_v2 import project_v2
    from app.planning_documents.ports import CatalogEvidence

    from tests.test_planning_metadata_binding import bundle

    inventory, metadata = bundle(platform)
    catalog = project_v2(inventory, metadata)
    account = dict(
        workspace_id=metadata.workspace_id,
        account_id=metadata.account_id,
        connection_id=metadata.connection_id,
        connection_version=metadata.connection_version,
        platform=metadata.platform,
    )
    ref = dict(
        key="catalog",
        workspace_id=metadata.workspace_id,
        account=account,
        kind="native_catalog",
        document_schema=catalog.schema_version,
        document_digest=catalog.composite_digest,
        source_binding_digest=metadata.source_binding_digest,
        source_revision="v1",
        privacy_revision=0,
        reporting_window=dict(
            starts_at=metadata.reporting_starts_at, ends_at_exclusive=metadata.reporting_ends_at
        ),
        observation_started_at=metadata.observation_started_at,
        observed_at=metadata.observed_at,
        expires_at=catalog.expires_at,
        coverage="partial",
        declared_scope="Exact native scope",
        reasons=["partial_scope"],
        metric_basis="Native settings only",
    )
    value = CatalogEvidence.model_validate(dict(reference=ref, catalog=catalog))
    assert value.catalog == catalog
    for change in (
        dict(observed_at=metadata.observed_at + timedelta(seconds=1)),
        dict(coverage="complete_in_declared_scope"),
        dict(document_schema="wrong"),
        dict(source_binding_digest="0" * 64),
    ):
        with pytest.raises(ValidationError):
            CatalogEvidence.model_validate(dict(reference={**ref, **change}, catalog=catalog))


def ready_bundle() -> tuple[GenerationTicket, EvidenceBundle]:
    from app.planning_catalog.projection_v2 import project_v2

    from tests.test_planning_metadata_binding import bundle as native_bundle

    inventory, metadata = native_bundle("meta")
    catalog = project_v2(inventory, metadata)
    account = dict(
        workspace_id=metadata.workspace_id,
        account_id=metadata.account_id,
        connection_id=metadata.connection_id,
        connection_version=metadata.connection_version,
        platform=metadata.platform,
    )
    data = packet("meta_ads")["inputs"]
    data.update(
        workspace_id=metadata.workspace_id,
        accounts=[account],
        reporting_window=dict(
            starts_at=metadata.reporting_starts_at, ends_at_exclusive=metadata.reporting_ends_at
        ),
        created_at=metadata.observed_at,
    )
    data["goal"]["workspace_id"] = metadata.workspace_id
    intent = GenerationTicket.model_validate(
        dict(
            operation_id="e" * 32,
            actor_id="a" * 32,
            session_digest="f" * 64,
            inputs=data,
            expected_version=0,
            expected_parent_digest=None,
            privacy_revision=0,
            sources=[
                dict(
                    account=account,
                    source_binding_digest=metadata.source_binding_digest,
                    source_revision="v1",
                    privacy_revision=0,
                )
            ],
            policy_version="test-v1",
            policy_digest=PlanningCompositionPolicy(
                version="test-v1", generator_version="test-v1"
            ).digest(),
            prepared_at=metadata.observed_at,
        )
    )
    reference = dict(
        key="catalog",
        workspace_id=metadata.workspace_id,
        account=account,
        kind="native_catalog",
        document_schema=catalog.schema_version,
        document_digest=catalog.composite_digest,
        source_binding_digest=metadata.source_binding_digest,
        source_revision="v1",
        privacy_revision=0,
        reporting_window=data["reporting_window"],
        observation_started_at=metadata.observation_started_at,
        observed_at=metadata.observed_at,
        expires_at=catalog.expires_at,
        coverage="partial",
        declared_scope="Exact native scope",
        reasons=["partial_scope"],
        metric_basis="Native settings only",
    )
    result = EvidenceBundle.model_validate(
        dict(
            operation_id=intent.operation_id,
            input_digest=intent.inputs.digest(),
            privacy_revision=0,
            collected_at=metadata.observed_at,
            catalogs=[dict(reference=reference, catalog=catalog)],
            performance=[],
            commerce=None,
            context=[],
            gaps=[],
        )
    )
    result.assert_ticket(intent)
    return intent, result


def commerce_data(intent: GenerationTicket, result: EvidenceBundle) -> dict[str, Any]:
    from app.goals.progress_contracts import GoalSalesProgressV1
    from app.publication.contracts import fingerprint as source_fingerprint

    definition = intent.inputs.goal.definition
    progress = GoalSalesProgressV1.model_validate(
        dict(
            workspace_id=intent.inputs.workspace_id,
            goal_id=intent.inputs.goal.goal_id,
            revision=intent.inputs.goal.revision,
            definition_digest=source_fingerprint(
                "inlet.goal-progress-definition.v1", definition.model_dump(mode="json")
            ),
            status="not_started",
            target_window=definition.target_window,
            target_micros=definition.target_micros,
            store_id=definition.store_id,
            currency="USD",
            time_zone="UTC",
            coverage=None,
            net_sales_micros=None,
            source_watermark=None,
            source_revision=None,
            import_in_progress=None,
            as_of=result.collected_at,
            reasons=["no_closed_days"],
        )
    )
    ref = result.catalogs[0].reference.model_dump(mode="python")
    ref.update(
        key="commerce",
        account=None,
        kind="shopify_measurement",
        document_schema=progress.schema_version,
        document_digest=fingerprint("goal-progress", progress.model_dump(mode="json")),
        source_revision="unavailable",
        reporting_window=None,
        coverage="unavailable",
        reasons=["no_closed_days"],
    )
    return dict(reference=ref, document=progress)


@pytest.mark.parametrize(
    "field,value", [("store_id", "e" * 32), ("target_micros", 999), ("definition_digest", "e" * 64)]
)
def test_commerce_same_revision_cannot_substitute_confirmed_definition(
    field: str, value: object
) -> None:
    from app.planning_documents.ports import CommerceEvidence

    intent, result = ready_bundle()
    data = commerce_data(intent, result)
    progress = data["document"]
    assert hasattr(progress, "model_copy")
    changed = progress.model_copy(update={field: value})
    ref = dict(data["reference"])
    ref["document_digest"] = fingerprint("goal-progress", changed.model_dump(mode="json"))
    evidence = CommerceEvidence.model_validate(dict(reference=ref, document=changed))
    with pytest.raises(ValueError, match="confirmed definition"):
        result.model_copy(update={"commerce": evidence}).assert_ticket(intent)


def test_commerce_summary_and_exact_policy_digest() -> None:
    from app.planning_documents.ports import CommerceEvidence, ContextEvidence

    intent, result = ready_bundle()
    data = commerce_data(intent, result)
    evidence = CommerceEvidence.model_validate(data)
    result.model_copy(update={"commerce": evidence}).assert_ticket(intent)
    ref = dict(data["reference"])
    for field, value in (
        ("coverage", "complete_in_declared_scope"),
        ("source_revision", "9"),
        ("document_schema", "wrong"),
    ):
        with pytest.raises(ValidationError):
            CommerceEvidence.model_validate(
                dict(reference={**ref, field: value}, document=data["document"])
            )
    policy = PlanningCompositionPolicy(version="test-v1", generator_version="changed")
    context_ref = result.catalogs[0].reference.model_dump(mode="python")
    context_ref.update(
        key="policy", kind="planning_policy", account=None, document_digest=policy.digest()
    )
    context = ContextEvidence.model_validate(dict(reference=context_ref, document=policy))
    with pytest.raises(ValueError, match="policy version"):
        result.model_copy(update={"context": (context,)}).assert_ticket(intent)


def performance_data(result: EvidenceBundle) -> dict[str, Any]:
    from datetime import timedelta

    from app.campaign_performance.contracts import CampaignPerformanceV1

    catalog = result.catalogs[0]
    entity = next(t for t in catalog.catalog.targets if t.entity.kind == "campaign")
    window = catalog.reference.reporting_window
    assert window is not None
    target = dict(
        account=catalog.reference.account,
        provider_reference=entity.entity.reference,
        canonical_entity_key=entity.canonical_entity_key,
        selection_key=entity.selection_key,
        catalog_evidence_key=catalog.reference.key,
        kind=entity.entity.kind,
        display_name=entity.entity.name,
        budget_owner_key=entity.budget_owner_key,
    )
    document = CampaignPerformanceV1.model_validate(
        dict(
            completion_id="a" * 32,
            manifest_digest="a" * 64,
            account_id=catalog.catalog.metadata_observation.account_id,
            campaign_id=1,
            generation=1,
            privacy_revision=0,
            starts_on=window.starts_at.date(),
            ends_on=(window.ends_at_exclusive - timedelta(days=1)).date(),
            currency="USD",
            time_zone="UTC",
            completed_at=result.collected_at,
            semantics="explicit_platform_event",
            selected_event="purchase",
            reporting_basis="provider_defaults_unspecified",
            reported_day_count=1,
            campaign_rows_available=True,
            impressions=1000,
            clicks=100,
            spend_micros=100000000,
            conversions="10",
            conversion_value_micros=None,
            cpa_micros=None,
            reported_roas=None,
        )
    )
    ref = catalog.reference.model_dump(mode="python")
    ref.update(
        key="performance",
        kind="reported_metrics",
        document_schema=document.schema_version,
        document_digest=fingerprint("campaign-performance", document.model_dump(mode="json")),
        source_binding_digest=document.manifest_digest,
    )
    return dict(
        reference=ref,
        target=target,
        document=document,
        native_campaign_id=entity.entity.reference.entity_id,
        completeness="reported_rows_only",
        conversion_qualification="reported_only",
        reasons=["attribution_window_unspecified"],
    )


def test_performance_window_must_be_requested_primary_or_comparison() -> None:
    from datetime import timedelta

    intent, result = ready_bundle()
    data = performance_data(result)
    evidence = PerformanceEvidence.model_validate(data)
    result.model_copy(update={"performance": (evidence,)}).assert_ticket(intent)
    old_window = evidence.reference.reporting_window
    assert old_window is not None
    changed_window = old_window.model_copy(
        update=dict(
            starts_at=old_window.starts_at - timedelta(days=2),
            ends_at_exclusive=old_window.ends_at_exclusive - timedelta(days=2),
        )
    )
    changed_document = evidence.document.model_copy(
        update=dict(
            starts_on=evidence.document.starts_on - timedelta(days=2),
            ends_on=evidence.document.ends_on - timedelta(days=2),
        )
    )
    data.update(
        document=changed_document,
        reference=evidence.reference.model_copy(
            update=dict(
                reporting_window=changed_window,
                document_digest=fingerprint(
                    "campaign-performance", changed_document.model_dump(mode="json")
                ),
            )
        ),
    )
    changed = PerformanceEvidence.model_validate(data)
    with pytest.raises(ValueError, match="window was not requested"):
        result.model_copy(update={"performance": (changed,)}).assert_ticket(intent)
    revised_inputs = intent.inputs.model_copy(update={"comparison_window": changed_window})
    revised = intent.model_copy(update={"inputs": revised_inputs})
    result.model_copy(
        update={"input_digest": revised_inputs.digest(), "performance": (changed,)}
    ).assert_ticket(revised)


@pytest.mark.parametrize("change", [dict(time_zone="No/SuchZone"), dict()])
def test_performance_summary_cannot_upgrade_coverage_and_bad_zone_is_validation_error(
    change: dict[str, str],
) -> None:
    _, result = ready_bundle()
    data = performance_data(result)
    if change:
        document = data["document"].model_copy(update=change)
        data.update(document=document)
        data["reference"]["document_digest"] = fingerprint(
            "campaign-performance", document.model_dump(mode="json")
        )
    else:
        data["reference"]["coverage"] = "complete_in_declared_scope"
    with pytest.raises(ValidationError):
        PerformanceEvidence.model_validate(data)


@pytest.mark.parametrize("raw", ["NaN", "Infinity", "-1"])
def test_tiktok_generic_decimal_rejects_nonfinite_and_negative(raw: str) -> None:
    from app.campaign_performance.contracts import CampaignPerformanceV2

    _, result = ready_bundle()
    data = performance_data(result)
    doc = data["document"].model_dump(mode="python")
    doc.update(
        schema_version="inlet.owned-campaign-performance.v2",
        platform="tiktok_ads",
        semantics="provider_aggregate_unspecified",
        selected_event=None,
        conversion_basis="tiktok_generic_conversion",
        reported_generic_conversions=raw,
        conversions=None,
    )
    value = CampaignPerformanceV2.model_validate(doc)
    data["document"] = value
    data["reference"]["document_digest"] = fingerprint(
        "campaign-performance", value.model_dump(mode="json")
    )
    with pytest.raises(ValidationError, match="invalid reported decimal"):
        PerformanceEvidence.model_validate(data)
