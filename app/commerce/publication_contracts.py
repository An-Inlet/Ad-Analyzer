"""Strict historical manifest union; independent acquisition never implies maturity."""

from collections.abc import Mapping
from datetime import date
from typing import Annotated, Any, Literal, cast
from zoneinfo import ZoneInfo

from pydantic import AwareDatetime, Field, TypeAdapter, model_validator
from sqlalchemy.sql.elements import ColumnElement

from app.commerce.evidence import digest
from app.commerce.independent_contracts import ScanCompletion
from app.commerce.ledger import DEFINITION
from app.commerce.models import CommerceMeasurementPublication
from app.outcomes.contracts import Code, Digest, Frozen, Positive
from app.shopify.security import utc

V1: Literal["inlet.commerce-publication.v1"] = "inlet.commerce-publication.v1"
V2: Literal["inlet.commerce-independent-publication.v2"] = (
    "inlet.commerce-independent-publication.v2"
)


class Partition(Frozen):
    day: date
    state: Literal["complete_zero", "complete_nonzero", "missing", "suppressed"]
    net_sales_micros: int | None = Field(strict=True)
    entry_count: int | None = Field(strict=True, ge=0)

    @model_validator(mode="after")
    def coverage(self) -> "Partition":
        complete = self.state.startswith("complete_")
        if complete != (self.net_sales_micros is not None and self.entry_count is not None):
            raise ValueError("invalid partition coverage")
        if not complete and (self.net_sales_micros is not None or self.entry_count is not None):
            raise ValueError("unavailable partition has values")
        if complete and (self.net_sales_micros == 0) != (self.state == "complete_zero"):
            raise ValueError("invalid zero partition")
        return self


class ManifestBasis(Frozen):
    workspace_id: Positive
    store_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    generation: Positive
    privacy_epoch: Positive
    publication_revision: Positive
    source_revision: int = Field(strict=True, ge=0)
    source: Literal["shopify"]
    source_api_version: str = Field(pattern=r"^20[0-9]{2}-(01|04|07|10)$")
    source_window_start: AwareDatetime
    source_window_end: AwareDatetime
    as_of: AwareDatetime
    definition: Literal["shopify_merchandise_net_sales_v1"]
    definition_digest: Digest
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    time_zone: str = Field(min_length=1, max_length=64)
    unit: Literal["monetary_micros"]
    grain: Literal["store_local_day"]
    attribution: Literal["not_applicable_store_total"]

    @model_validator(mode="after")
    def basis(self) -> "ManifestBasis":
        ZoneInfo(self.time_zone)
        if self.definition_digest != digest(DEFINITION) or not (
            self.source_window_start <= self.source_window_end <= self.as_of
        ):
            raise ValueError("invalid publication basis")
        return self


class IncrementalManifest(ManifestBasis):
    schema_version: Literal["inlet.commerce-publication.v1"]
    source_range_semantics: Literal["updated_at_inclusive"]
    source_watermark: AwareDatetime
    maturity: Literal["unavailable"]
    comparison_reasons: tuple[Code, ...] = Field(max_length=20)
    partitions: tuple[Partition, ...] = Field(max_length=400)
    predecessor_digest: Digest | None
    correction_status: Literal["settled_as_of", "unknown"]

    @model_validator(mode="after")
    def historical(self) -> "IncrementalManifest":
        if self.source_watermark != self.source_window_end:
            raise ValueError("invalid incremental watermark")
        days = [p.day for p in self.partitions]
        if len(set(days)) != len(days) or days != sorted(days):
            raise ValueError("invalid partition ordering")
        return self


class IndependentManifest(ManifestBasis):
    schema_version: Literal["inlet.commerce-independent-publication.v2"] = V2
    source_range_semantics: Literal["full_accessible_order_history"] = (
        "full_accessible_order_history"
    )
    environment: Literal["contract_test", "live"]
    acquisition: ScanCompletion
    source_watermark: None = None
    maturity: Literal["unqualified"] = "unqualified"
    correction_status: Literal["unresolved"] = "unresolved"
    authoritative_finality: Literal["unavailable"] = "unavailable"
    spending_authority: Literal["none"] = "none"

    @model_validator(mode="after")
    def independent(self) -> "IndependentManifest":
        scan, scope = self.acquisition, self.acquisition.request.scope
        if (
            (
                self.workspace_id,
                self.store_id,
                self.generation,
                self.privacy_epoch,
                self.definition_digest,
                self.currency,
                self.time_zone,
            )
            != (
                scope.workspace_id,
                scope.store_id,
                scope.generation,
                scope.privacy_epoch,
                scope.metric_definition_digest,
                scope.currency,
                scope.time_zone,
            )
            or (self.source_window_start, self.source_window_end)
            != (scan.started_at, scan.completed_at)
            or self.source_api_version != scan.source_api_version
        ):
            raise ValueError("independent acquisition scope mismatch")
        return self

    @property
    def completion_digest(self) -> str:
        return digest(
            [
                "inlet.commerce-independent-completion.v2",
                self.acquisition.model_dump(mode="json"),
            ]
        )


MANIFEST: TypeAdapter[IncrementalManifest | IndependentManifest] = TypeAdapter(
    Annotated[IncrementalManifest | IndependentManifest, Field(discriminator="schema_version")]
)


def version_filter(version: str = V1) -> ColumnElement[bool]:
    """Filter in SQL before LIMIT, preserving usable v1 despite newer v2 records."""
    return cast(
        ColumnElement[bool],
        CommerceMeasurementPublication.manifest["schema_version"].as_string() == version,
    )


def bind_manifest(row: Mapping[str, Any], document: ManifestBasis, raw: Any) -> None:
    """Digest original bytes/values: do not silently reserialize historical v1."""
    fields = (
        "workspace_id",
        "store_id",
        "generation",
        "privacy_epoch",
        "publication_revision",
        "source_revision",
    )
    if any(row[key] != getattr(document, key) for key in fields):
        raise ValueError("publication row scope mismatch")
    if (
        any(
            utc(row[column]) != getattr(document, key)
            for column, key in (
                ("source_window_start", "source_window_start"),
                ("source_window_end", "source_window_end"),
                ("published_at", "as_of"),
            )
        )
        or digest(raw) != row["manifest_digest"]
    ):
        raise ValueError("publication row digest/time mismatch")
    if isinstance(document, IndependentManifest):
        if (
            row["completion_digest"] != document.completion_digest
            or row["earliest_source_day"] != document.acquisition.request.start
        ):
            raise ValueError("independent completion mismatch")
    elif isinstance(document, IncrementalManifest):
        expected = digest(
            [
                "inlet.commerce-completion.v1",
                document.store_id,
                document.generation,
                document.privacy_epoch,
                document.source_window_start.isoformat(),
                document.source_window_end.isoformat(),
                document.source_revision,
            ]
        )
        if row["completion_digest"] != expected:
            raise ValueError("incremental completion mismatch")


def parse_publication(
    row: CommerceMeasurementPublication,
) -> IncrementalManifest | IndependentManifest:
    document = MANIFEST.validate_python(row.manifest)
    bind_manifest(
        {column.name: getattr(row, column.name) for column in row.__table__.columns},
        document,
        row.manifest,
    )
    return document
