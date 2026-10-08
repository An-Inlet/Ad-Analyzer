"""Entity correspondence and copied-digest attacks against the sidecar boundary."""

from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
from app.collectors.google_native_inventory import GoogleNativeInventory
from app.collectors.meta_native_inventory import MetaNativeInventory
from app.collectors.native_diagnostics import Inventory
from app.collectors.tiktok_native_inventory import TikTokNativeInventory
from app.planning_catalog.metadata_binding import validate_bound_metadata
from app.planning_catalog.metadata_contracts import PlanningMetadataV1, TargetCatalogV2
from app.planning_catalog.projection_v2 import project_v2
from app.publication.contracts import fingerprint
from pydantic import ValidationError


def bundle(platform: str) -> tuple[Inventory, PlanningMetadataV1]:
    models: dict[
        str, type[GoogleNativeInventory] | type[MetaNativeInventory] | type[TikTokNativeInventory]
    ] = {
        "google": GoogleNativeInventory,
        "meta": MetaNativeInventory,
        "tiktok": TikTokNativeInventory,
    }
    model = models[platform]
    path = Path(__file__).parent / "fixtures" / "planning_catalog_legacy" / (platform + ".json")
    original = model.model_validate_json(path.read_text())
    raw = original.model_dump()
    raw["request"]["period_start"] = original.observed_at - timedelta(days=1)
    raw["request"]["period_end"] = original.observed_at
    inventory = model.model_validate(raw)
    source = inventory.request.account
    entities: list[dict[str, Any]] = []
    items: list[tuple[str, str, str | None]]
    if isinstance(inventory, GoogleNativeInventory):
        items = [
            ("campaign", c.resource_name.rsplit("/", 1)[1], None) for c in inventory.campaigns
        ] + [("adgroup", "7", "1")]
    elif isinstance(inventory, MetaNativeInventory):
        items = [("campaign", c.id, None) for c in inventory.campaigns] + [
            ("adset", c.id, c.campaign_id) for c in inventory.adsets
        ]
    else:
        items = [("campaign", c.id, None) for c in inventory.campaigns] + [
            ("adgroup", c.id, c.campaign_id) for c in inventory.adgroups
        ]
    for kind, ident, parent in items:
        entities.append(
            dict(
                kind=kind,
                reference=dict(
                    platform=source.account.platform,
                    advertiser_id=source.external_advertiser_id,
                    entity_id=ident,
                    parent_campaign_id=parent,
                ),
                name="Owned",
                name_status="observed",
                status=None,
                entity_type=None,
            )
        )
    metadata = PlanningMetadataV1.model_validate(
        dict(
            workspace_id=source.workspace_id,
            account_id=source.account.account_id,
            connection_id=source.account.connection_id,
            platform=source.account.platform,
            connection_version=source.connection_version,
            source_binding_digest=fingerprint(
                "inlet.planning-source.v1", source.model_dump(mode="json")
            ),
            native_inventory_digest=inventory.digest(),
            request_digest=inventory.request.digest(),
            reporting_starts_at=inventory.request.period_start,
            reporting_ends_at=inventory.request.period_end,
            observation_started_at=inventory.observed_at,
            observed_at=inventory.observed_at,
            expires_at=inventory.expires_at,
            entities=entities,
            coverage=[
                dict(
                    kind=k,
                    status="complete" if platform == "google" else "partial",
                    count=sum(e["kind"] == k for e in entities),
                    scope=("provider_campaigns" if k == "campaign" else "provider_adgroups")
                    if platform == "google"
                    else "sdk_known_effective_statuses"
                    if platform == "meta"
                    else "regular_campaign_families",
                    reasons=[] if platform == "google" else ["native_scope_limited"],
                )
                for k in ("campaign", "adset" if platform == "meta" else "adgroup")
            ],
        )
    )
    return inventory, metadata


@pytest.mark.parametrize("platform", ["google", "meta", "tiktok"])
def test_copied_digests_do_not_bind_foreign_advertiser_or_scope(platform: str) -> None:
    inventory, metadata = bundle(platform)
    assert validate_bound_metadata(inventory, metadata, metadata.observed_at) == metadata
    foreign = metadata.model_dump()
    for entity in foreign["entities"]:
        entity["reference"]["advertiser_id"] = "9999999999"
    # Digests are deliberately copied unchanged from the owned observation.
    with pytest.raises(ValueError):
        validate_bound_metadata(
            inventory, PlanningMetadataV1.model_validate(foreign), metadata.observed_at
        )
    for field in ("workspace_id", "account_id", "connection_id"):
        with pytest.raises(ValueError):
            validate_bound_metadata(
                inventory, metadata.model_copy(update={field: 999}), metadata.observed_at
            )
    with pytest.raises(ValueError):
        validate_bound_metadata(inventory, metadata, metadata.expires_at)


@pytest.mark.parametrize("platform", ["google", "meta", "tiktok"])
def test_exact_settings_keys_owner_and_snapshot_binding(platform: str) -> None:
    inventory, metadata = bundle(platform)
    value = project_v2(inventory, metadata)
    raw = value.model_dump()
    changes: list[dict[str, Any]] = [
        dict(canonical_entity_key="c" * 64),
        dict(selection_key="d" * 64),
        dict(budget_owner_key="e" * 64),
        dict(native_settings_key=raw["targets"][0]["native_settings_key"]),
    ]
    for change in changes:
        altered = value.model_dump()
        altered["targets"][1].update(change)
        with pytest.raises(ValidationError):
            TargetCatalogV2.model_validate(altered)
    later = metadata.model_copy(update={"observed_at": metadata.observed_at + timedelta(seconds=1)})
    refreshed = project_v2(inventory, later)
    assert [t.canonical_entity_key for t in refreshed.targets] == [
        t.canonical_entity_key for t in value.targets
    ]
    assert all(
        a.selection_key != b.selection_key
        for a, b in zip(refreshed.targets, value.targets, strict=True)
    )


@pytest.mark.parametrize("platform", ["google", "meta", "tiktok"])
def test_platform_coverage_matrix_cannot_be_forged(platform: str) -> None:
    _, metadata = bundle(platform)
    raw = metadata.model_dump()
    raw["coverage"][0].update(scope="provider_adgroups", status="complete")
    with pytest.raises(ValidationError):
        PlanningMetadataV1.model_validate(raw)


@pytest.mark.parametrize("platform", ["google", "meta", "tiktok"])
@pytest.mark.parametrize("change", ["replace", "omit"])
def test_same_digest_cannot_substitute_or_omit_native_entity(platform: str, change: str) -> None:
    inventory, metadata = bundle(platform)
    raw = metadata.model_dump()
    if change == "replace":
        raw["entities"][0]["reference"]["entity_id"] = "999"
        for child in raw["entities"][1:]:
            child["reference"]["parent_campaign_id"] = "999"
    else:
        raw["entities"] = []
        for coverage in raw["coverage"]:
            coverage["count"] = 0
    altered = PlanningMetadataV1.model_validate(raw)
    with pytest.raises(ValueError):
        validate_bound_metadata(inventory, altered, altered.observed_at)
    with pytest.raises(ValueError):
        project_v2(inventory, altered)
