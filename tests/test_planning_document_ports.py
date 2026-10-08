from copy import deepcopy

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
