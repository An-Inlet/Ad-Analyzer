"""Owned human references and snapshot selectors; neither is permission."""

from app.collectors.native_diagnostics import Inventory
from app.planning_catalog.metadata_contracts import (
    PlanningMetadataV1,
    TargetCatalogV2,
    canonical_key,
    selection_key,
    settings_key,
)
from app.planning_catalog.projection import project
from app.publication.contracts import fingerprint


def project_v2(inventory: Inventory, metadata: PlanningMetadataV1) -> TargetCatalogV2:
    native = project(inventory)
    composite = fingerprint(
        "inlet.planning-catalog-composite.v1",
        dict(native_inventory_digest=inventory.digest(), metadata_digest=metadata.digest()),
    )
    native_targets = {t.selection_key: t for t in native.targets}
    rows = []
    for entity in metadata.entities:
        canonical = canonical_key(metadata, entity)
        old_key = settings_key(native.source_binding_digest, entity)
        old = native_targets.get(old_key)
        rows.append(
            dict(
                canonical_entity_key=canonical,
                selection_key=selection_key(canonical, native.source_binding_digest, composite),
                entity=entity,
                native_settings_key=old_key if old else None,
                budget_owner_key=old.budget_owner_key if old else None,
            )
        )
    return TargetCatalogV2.model_validate(
        dict(
            native_observation=native,
            metadata_observation=metadata,
            composite_digest=composite,
            expires_at=min(native.expires_at, metadata.expires_at),
            targets=rows,
        )
    )
