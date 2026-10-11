"""Cycle-free exact catalog evidence; public ports reexport the same class."""

from __future__ import annotations

from pydantic import model_validator

from app.planning_catalog.metadata_contracts import TargetCatalogV2
from app.planning_documents.common import Frozen
from app.planning_documents.context import EvidenceRef


class CatalogEvidence(Frozen):
    reference: EvidenceRef
    catalog: TargetCatalogV2

    @model_validator(mode="after")
    def exact(self) -> CatalogEvidence:
        ref, metadata = self.reference, self.catalog.metadata_observation
        native = self.catalog.native_observation
        complete = all(c.status == "complete" for c in native.coverage) and all(
            c.status == "complete" for c in metadata.coverage
        )
        if (
            ref.document_schema != self.catalog.schema_version
            or ref.observation_started_at
            != min(native.observation_started_at, metadata.observation_started_at)
            or ref.observed_at != max(native.observed_at, metadata.observed_at)
            or ref.reporting_window is None
            or (ref.reporting_window.starts_at, ref.reporting_window.ends_at_exclusive)
            != (metadata.reporting_starts_at, metadata.reporting_ends_at)
            or ref.coverage != ("complete_in_declared_scope" if complete else "partial")
        ):
            raise ValueError("catalog evidence summary must match actual composite")
        if (
            ref.kind != "native_catalog"
            or ref.account is None
            or (
                ref.workspace_id,
                ref.account.account_id,
                ref.account.connection_id,
                ref.account.platform,
                ref.account.connection_version,
            )
            != (
                metadata.workspace_id,
                metadata.account_id,
                metadata.connection_id,
                metadata.platform,
                metadata.connection_version,
            )
            or ref.document_digest != self.catalog.composite_digest
            or ref.source_binding_digest != metadata.source_binding_digest
            or ref.expires_at != self.catalog.expires_at
        ):
            raise ValueError("exact owned composite catalog binding required")
        return self
