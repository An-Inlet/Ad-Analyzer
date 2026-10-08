"""Versioned metadata sidecar; legacy native observation schemas stay unchanged."""

from typing import Annotated, Literal

from pydantic import AwareDatetime, Field, model_validator

from app.planning_catalog.contracts import (
    Code,
    Digest,
    Frozen,
    Kind,
    NativeText,
    Platform,
    TargetCatalogV1,
)
from app.publication.contracts import fingerprint

NumericId = Annotated[str, Field(strict=True, pattern=r"^[0-9]{1,32}$")]


class ProviderReferenceV1(Frozen):
    platform: Platform
    advertiser_id: NumericId
    entity_id: NumericId
    parent_campaign_id: NumericId | None

    @model_validator(mode="after")
    def advertiser(self) -> "ProviderReferenceV1":
        if self.platform == "google_ads" and len(self.advertiser_id) != 10:
            raise ValueError("invalid Google customer reference")
        return self


class MetadataEntityV1(Frozen):
    kind: Kind
    reference: ProviderReferenceV1
    name: str | None = Field(strict=True, min_length=1, max_length=160)
    name_status: Literal["observed", "missing", "over_bound"]
    status: NativeText | None
    entity_type: NativeText | None

    @model_validator(mode="after")
    def consistent(self) -> "MetadataEntityV1":
        if (self.name is not None) != (self.name_status == "observed"):
            raise ValueError("name provenance invalid")
        if (self.kind == "campaign") != (self.reference.parent_campaign_id is None):
            raise ValueError("entity parent invalid")
        if self.kind == "adset" and self.reference.platform != "meta_ads":
            raise ValueError("entity platform invalid")
        if self.kind == "adgroup" and self.reference.platform == "meta_ads":
            raise ValueError("entity platform invalid")
        return self


class MetadataCoverageV1(Frozen):
    kind: Kind
    status: Literal["complete", "partial"]
    count: int = Field(strict=True, ge=0, le=200)
    scope: Literal[
        "provider_campaigns",
        "provider_adgroups",
        "sdk_known_effective_statuses",
        "regular_campaign_families",
    ]
    reasons: tuple[Code, ...] = Field(max_length=20)

    @model_validator(mode="after")
    def complete(self) -> "MetadataCoverageV1":
        if self.status == "complete" and self.scope not in {
            "provider_campaigns",
            "provider_adgroups",
        }:
            raise ValueError("limited scope cannot be complete")
        if self.status == "partial" and not self.reasons:
            raise ValueError("partial coverage needs reason")
        return self


class PlanningMetadataV1(Frozen):
    schema_version: Literal["inlet.planning-entity-metadata.v1"] = (
        "inlet.planning-entity-metadata.v1"
    )
    workspace_id: int = Field(strict=True, gt=0)
    account_id: int = Field(strict=True, gt=0)
    connection_id: int = Field(strict=True, gt=0)
    platform: Platform
    connection_version: NativeText
    source_binding_digest: Digest
    native_inventory_digest: Digest
    request_digest: Digest
    reporting_starts_at: AwareDatetime
    reporting_ends_at: AwareDatetime
    observation_started_at: AwareDatetime
    observed_at: AwareDatetime
    expires_at: AwareDatetime
    entities: tuple[MetadataEntityV1, ...] = Field(max_length=400)
    coverage: tuple[MetadataCoverageV1, ...] = Field(min_length=2, max_length=2)
    atomic_snapshot: Literal[False] = False

    @model_validator(mode="after")
    def consistent(self) -> "PlanningMetadataV1":
        if (
            not self.reporting_starts_at
            < self.reporting_ends_at
            <= self.observation_started_at
            <= self.observed_at
            < self.expires_at
        ):
            raise ValueError("metadata chronology invalid")
        kinds = {"campaign", "adset" if self.platform == "meta_ads" else "adgroup"}
        if {c.kind for c in self.coverage} != kinds:
            raise ValueError("metadata coverage invalid")
        keys = {(e.kind, e.reference.entity_id) for e in self.entities}
        parents = {e.reference.entity_id for e in self.entities if e.kind == "campaign"}
        if len(keys) != len(self.entities) or any(
            e.kind not in kinds
            or e.reference.platform != self.platform
            or (
                e.reference.parent_campaign_id is not None
                and e.reference.parent_campaign_id not in parents
            )
            for e in self.entities
        ):
            raise ValueError("metadata topology invalid")
        if len({e.reference.advertiser_id for e in self.entities}) > 1:
            raise ValueError("metadata account mismatch")
        if any(c.count != sum(e.kind == c.kind for e in self.entities) for c in self.coverage):
            raise ValueError("metadata count mismatch")
        return self

    def digest(self) -> str:
        return fingerprint(self.schema_version, self.model_dump(mode="json"))


class PlanningTargetV2(Frozen):
    canonical_entity_key: Digest
    selection_key: Digest
    entity: MetadataEntityV1
    native_settings_key: Digest | None
    budget_owner_key: Digest | None


class TargetCatalogV2(Frozen):
    schema_version: Literal["inlet.planning-target-catalog.v2"] = "inlet.planning-target-catalog.v2"
    native_observation: "TargetCatalogV1"
    metadata_observation: PlanningMetadataV1
    composite_digest: Digest
    expires_at: AwareDatetime
    targets: tuple[PlanningTargetV2, ...] = Field(max_length=400)
    advertising_writes_enabled: Literal[False] = False
    atomic_snapshot: Literal[False] = False
    spending_authority: Literal["none"] = "none"

    @model_validator(mode="after")
    def bound(self) -> "TargetCatalogV2":
        native, metadata = self.native_observation, self.metadata_observation
        for field in (
            "workspace_id",
            "account_id",
            "connection_id",
            "platform",
            "connection_version",
            "source_binding_digest",
            "reporting_starts_at",
            "reporting_ends_at",
        ):
            if getattr(native, field) != getattr(metadata, field):
                raise ValueError("composite source mismatch")
        if metadata.native_inventory_digest != native.inventory_digest or self.expires_at != min(
            native.expires_at, metadata.expires_at
        ):
            raise ValueError("composite observation mismatch")
        if self.composite_digest != fingerprint(
            "inlet.planning-catalog-composite.v1",
            dict(
                native_inventory_digest=native.inventory_digest, metadata_digest=metadata.digest()
            ),
        ):
            raise ValueError("composite digest mismatch")
        if tuple(t.entity for t in self.targets) != metadata.entities:
            raise ValueError("composite entity mismatch")
        if len({t.canonical_entity_key for t in self.targets}) != len(self.targets) or len(
            {t.selection_key for t in self.targets}
        ) != len(self.targets):
            raise ValueError("composite keys duplicate")
        settings = {t.selection_key for t in native.targets}
        if any(
            t.native_settings_key is not None and t.native_settings_key not in settings
            for t in self.targets
        ):
            raise ValueError("composite settings reference invalid")
        return self
