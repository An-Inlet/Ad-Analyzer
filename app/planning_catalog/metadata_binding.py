"""Freshly bind sidecar claims to the actual owned native observation."""

from datetime import datetime

from app.collectors.native_diagnostics import Inventory
from app.planning_catalog.metadata_contracts import PlanningMetadataV1
from app.publication.contracts import fingerprint


def validate_bound_metadata(
    inventory: Inventory, metadata: PlanningMetadataV1, now: datetime
) -> PlanningMetadataV1:
    metadata = PlanningMetadataV1.model_validate(metadata.model_dump())
    request = inventory.request
    source = request.account
    expected = dict(
        workspace_id=source.workspace_id,
        account_id=source.account.account_id,
        connection_id=source.account.connection_id,
        platform=source.account.platform,
        connection_version=source.connection_version,
        source_binding_digest=fingerprint(
            "inlet.planning-source.v1", source.model_dump(mode="json")
        ),
        native_inventory_digest=inventory.digest(),
        request_digest=request.digest(),
        reporting_starts_at=request.period_start,
        reporting_ends_at=request.period_end,
    )
    if any(getattr(metadata, field) != value for field, value in expected.items()):
        raise ValueError("metadata source binding changed")
    if any(
        entity.reference.advertiser_id != source.external_advertiser_id
        for entity in metadata.entities
    ):
        raise ValueError("metadata advertiser changed")
    if (
        metadata.expires_at > inventory.expires_at
        or not inventory.observed_at
        <= metadata.observation_started_at
        <= metadata.observed_at
        <= now
        < metadata.expires_at
    ):
        raise ValueError("metadata expired")
    # Validate exact entity/settings correspondence, including omitted targets.
    from app.planning_catalog.projection_v2 import project_v2

    project_v2(inventory, metadata)
    return metadata
