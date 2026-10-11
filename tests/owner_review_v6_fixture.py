"""Synthetic pure V6 packets; no authenticated acquisition or persisted-plan claim."""

from datetime import timedelta
from typing import Any

from app.planning_catalog.projection_v2 import project_v2
from app.planning_documents.catalog_evidence import CatalogEvidence
from app.planning_documents.composer import targets
from app.planning_documents.context import PlanInputRevision
from app.planning_documents.creative_basis import CreativeBasisV1
from app.planning_documents.creative_image_collection import CollectedCreativeBasisV1
from app.planning_documents.creative_plan_bundle import CreativePairedEvidenceV1
from app.planning_documents.owner_review_policy import (
    OWNER_REVIEW_GENERATOR_VERSION,
    OWNER_REVIEW_POLICY_VERSION,
)
from app.planning_documents.ports import (
    ContextEvidence,
    GenerationTicket,
    PlanningCompositionPolicy,
)
from app.planning_documents.selected_paired_evidence import SelectedPairedEvidenceV1
from app.planning_documents.selected_plan_bundle import SelectedPlanEvidenceBundleV1
from app.planning_documents.selected_plan_proof import SelectedRetainedProofV1

from tests.test_google_budget_owner_review import ready as owner_ready
from tests.test_planning_creative_basis import basis as image_basis
from tests.test_planning_metadata_binding import bundle


def social_catalog(
    template: CatalogEvidence, platform: str, *, renamed: bool = False
) -> CatalogEvidence:
    native, metadata = bundle(platform)
    if renamed:
        metadata = type(metadata).model_validate(
            metadata.model_copy(
                update={
                    "entities": tuple(
                        entity.model_copy(update={"name": "Renamed"})
                        for entity in metadata.entities
                    )
                }
            )
        )
    catalog = project_v2(native, metadata)
    ref = template.reference.model_dump(mode="python")
    ref.update(
        key="catalog:" + platform,
        account=dict(
            workspace_id=metadata.workspace_id,
            account_id=metadata.account_id,
            connection_id=metadata.connection_id,
            connection_version=metadata.connection_version,
            platform=metadata.platform,
        ),
        document_digest=catalog.composite_digest,
        source_revision=metadata.connection_version,
        source_binding_digest=metadata.source_binding_digest,
        coverage="partial",
        expires_at=catalog.expires_at,
        observation_started_at=min(
            catalog.native_observation.observation_started_at, metadata.observation_started_at
        ),
        observed_at=max(catalog.native_observation.observed_at, metadata.observed_at),
        reporting_window=dict(
            starts_at=metadata.reporting_starts_at, ends_at_exclusive=metadata.reporting_ends_at
        ),
    )
    return CatalogEvidence(reference=ref, catalog=catalog)


def ready(
    *,
    zero: bool = False,
    empty: bool = False,
    social: str | None = None,
    usage: str = "scenario",
    no_links: bool = False,
) -> Any:
    values = owner_ready(zero=zero, empty=empty)
    inputs, catalogs = values["inputs"], values["catalogs"]
    raw = inputs.model_dump(mode="python")
    if social is not None:
        other = social_catalog(catalogs[0], social)
        catalogs += (other,)
        raw["accounts"] += (other.reference.account,)
        target = next(t for t in targets(other) if t.kind == "campaign")
        if usage == "scenario":
            raw["scenario_intents"][0]["allocations"] += (dict(target=target, amount_micros=0),)
        elif usage == "exclusion":
            raw["excluded_entity_keys"] = (target.canonical_entity_key,)
        elif usage == "fixed":
            raw["fixed_allocations"] = (dict(target=target, amount_micros=0),)
            raw["scenario_intents"][0]["allocations"] += (dict(target=target, amount_micros=0),)
    if no_links:
        raw["scenario_intents"] = ()
        raw["fixed_allocations"] = ()
        raw["excluded_entity_keys"] = ()
    basis_raw = image_basis(1).model_dump(mode="python")
    basis_raw.update(workspace_id=inputs.workspace_id, privacy_revision=values["privacy_revision"])
    prepared = inputs.created_at
    for image in basis_raw["images"]:
        image.update(
            workspace_id=inputs.workspace_id,
            privacy_revision=values["privacy_revision"],
            created_at=prepared,
            observed_at=prepared,
        )
    basis = CreativeBasisV1.model_validate(basis_raw)
    raw.update(creative=basis.requested, selected_reporting=(), maximum_creative_assets=1)
    inputs = PlanInputRevision.model_validate(raw)
    policy = PlanningCompositionPolicy(
        version=OWNER_REVIEW_POLICY_VERSION, generator_version=OWNER_REVIEW_GENERATOR_VERSION
    )
    proof = SelectedRetainedProofV1(
        accounts=tuple(
            dict(
                source_fence=dict(
                    account=c.reference.account,
                    source_binding_digest=c.reference.source_binding_digest,
                    source_revision=c.reference.source_revision,
                    privacy_revision=c.reference.privacy_revision,
                ),
                legacy_reporting_digest="a" * 64,
                selection_head=None,
                capture_pin=None,
            )
            for c in catalogs
        )
    )
    ticket = GenerationTicket(
        operation_id="e" * 32,
        actor_id="a" * 32,
        session_digest="b" * 64,
        inputs=inputs,
        expected_version=0,
        expected_parent_digest=None,
        privacy_revision=values["privacy_revision"],
        sources=tuple(a.source_fence for a in proof.accounts),
        policy_version=policy.version,
        policy_digest=policy.digest(),
        prepared_at=prepared,
    )
    contexts = tuple(
        ContextEvidence(
            reference=catalogs[0].reference.model_copy(
                update=dict(key=key, kind=kind, account=None, document_digest=doc.digest())
            ),
            document=doc,
        )
        for key, kind, doc in (
            ("context:inputs", "customer_context", inputs),
            ("context:policy", "planning_policy", policy),
        )
    )
    windows = (inputs.reporting_window,) + (
        (inputs.comparison_window,) if inputs.comparison_window else ()
    )
    selected = SelectedPlanEvidenceBundleV1(
        operation_id=ticket.operation_id,
        input_digest=inputs.digest(),
        privacy_revision=ticket.privacy_revision,
        collected_at=prepared + timedelta(seconds=1),
        reporting_proof=proof,
        catalogs=catalogs,
        selected_captures=(),
        performance=(),
        commerce=None,
        context=contexts,
        gaps=(),
        window_gaps=tuple(
            dict(
                account=c.reference.account,
                target=target,
                requested_window=window,
                reason="selected_capture_not_requested"
                if target.account.platform == "google_ads"
                else "unsupported_selected_mapping",
                reporting_pin_digest=pin.state_digest(),
                explanation="No selected metric observation supplied in this pure fixture.",
            )
            for c, pin in zip(catalogs, proof.accounts, strict=True)
            for target in targets(c)
            if target.kind == "campaign"
            for window in windows
        ),
    )
    evidence = CreativePairedEvidenceV1(
        reporting=SelectedPairedEvidenceV1(
            selected=selected, traffic_graphs=(), traffic=(), traffic_gaps=()
        ),
        creative=CollectedCreativeBasisV1(
            basis=basis,
            rows=tuple(dict(witness=image, created_by=ticket.actor_id) for image in basis.images),
            ticket_digest=ticket.digest(),
        ),
    )
    evidence.assert_ticket(ticket)
    return ticket, evidence, policy, prepared + timedelta(seconds=2)
