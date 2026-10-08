"""Server-only planning composition ports. Values confer no access or spending authority."""

from __future__ import annotations

from datetime import datetime, time, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any, Literal, Protocol
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import AwareDatetime, Field, field_validator, model_validator

from app.campaign_performance.contracts import CampaignPerformanceV1, CampaignPerformanceV2
from app.goals.progress_contracts import GoalSalesProgressV1
from app.planning_catalog.metadata_contracts import TargetCatalogV2
from app.planning_documents.common import (
    MAX_ACCOUNTS,
    MAX_EVIDENCE,
    Digest,
    Frozen,
    Id,
    Key,
    NoAuthority,
    Text,
    fingerprint,
    unique,
)
from app.planning_documents.context import AccountRef, EvidenceRef, PlanInputRevision, TargetRef
from app.planning_documents.documents import PlanVersion
from app.publication.contracts import fingerprint as source_fingerprint


class SourceFence(Frozen):
    """Private owned local source tuple, checked again after all external reads."""

    account: AccountRef
    source_binding_digest: Digest
    source_revision: Text
    privacy_revision: int = Field(strict=True, ge=0)


class GenerationTicket(NoAuthority):
    """Server creates this; never deserialize a ticket from a customer request."""

    operation_id: Id
    actor_id: Id
    session_digest: Digest
    inputs: PlanInputRevision
    expected_version: int = Field(strict=True, ge=0)
    expected_parent_digest: Digest | None
    privacy_revision: int = Field(strict=True, ge=0)
    sources: tuple[SourceFence, ...] = Field(min_length=1, max_length=MAX_ACCOUNTS)
    policy_version: Text
    policy_digest: Digest
    prepared_at: AwareDatetime

    @model_validator(mode="after")
    def exact(self) -> GenerationTicket:
        if (self.expected_version == 0) != (self.expected_parent_digest is None):
            raise ValueError("exact parent version binding required")
        if self.prepared_at < self.inputs.created_at:
            raise ValueError("ticket predates inputs")
        if {s.account for s in self.sources} != set(self.inputs.accounts):
            raise ValueError("exact selected source set required")
        unique(tuple(s.account.account_id for s in self.sources), "source fence")
        if any(s.privacy_revision != self.privacy_revision for s in self.sources):
            raise ValueError("source privacy fence mismatch")
        return self


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


class PerformanceEvidence(Frozen):
    reference: EvidenceRef
    target: TargetRef
    document: CampaignPerformanceV1 | CampaignPerformanceV2
    native_campaign_id: str = Field(strict=True, pattern=r"^[0-9]{1,32}$")
    measurement_scope: Literal["provider_reported_not_cross_platform_comparable"] = (
        "provider_reported_not_cross_platform_comparable"
    )
    attribution_qualification: Literal["unavailable"] = "unavailable"
    completeness: Literal["reported_rows_only", "unavailable"]
    conversion_qualification: Literal["reported_only", "unavailable"]
    reasons: tuple[Key, ...] = Field(min_length=1, max_length=20)

    @field_validator("document", mode="before")
    @classmethod
    def reparse(cls, value: Any) -> Any:
        if isinstance(value, (CampaignPerformanceV1, CampaignPerformanceV2)):
            value = value.model_dump(mode="python")
        if isinstance(value, dict):
            for name in (
                "account_id",
                "campaign_id",
                "generation",
                "privacy_revision",
                "impressions",
                "clicks",
                "spend_micros",
                "conversion_value_micros",
                "reported_day_count",
            ):
                if value.get(name) is not None and type(value[name]) is not int:
                    raise ValueError("reported integers must not be coerced")
        return value

    @model_validator(mode="after")
    def exact(self) -> PerformanceEvidence:
        if (
            self.target.kind != "campaign"
            or self.native_campaign_id != self.target.provider_reference.entity_id
            or self.reference.document_digest
            != fingerprint("campaign-performance", self.document.model_dump(mode="json"))
        ):
            raise ValueError("exact native campaign/document binding required")
        for field in (
            "account_id",
            "campaign_id",
            "generation",
            "privacy_revision",
            "impressions",
            "clicks",
            "spend_micros",
            "conversion_value_micros",
            "reported_day_count",
        ):
            value = getattr(self.document, field)
            if value is not None and type(value) is not int:
                raise ValueError("reported integers must not be coerced")
        for raw in (
            self.document.conversions,
            self.document.cpa_micros,
            self.document.reported_roas,
            self.document.reported_generic_conversions
            if isinstance(self.document, CampaignPerformanceV2)
            else None,
        ):
            if raw is not None:
                try:
                    value_decimal = Decimal(raw)
                except (InvalidOperation, ValueError):
                    raise ValueError("invalid reported decimal") from None
                if not value_decimal.is_finite() or value_decimal < 0:
                    raise ValueError("invalid reported decimal")
        window = self.reference.reporting_window
        try:
            zone = ZoneInfo(self.document.time_zone)
        except (ValueError, ZoneInfoNotFoundError):
            raise ValueError("invalid reported time zone") from None
        expected_start = datetime.combine(self.document.starts_on, time.min, zone)
        expected_end = datetime.combine(self.document.ends_on + timedelta(days=1), time.min, zone)
        if (
            window is None
            or window.starts_at != expected_start
            or window.ends_at_exclusive != expected_end
            or self.reference.document_schema != self.document.schema_version
            or self.reference.observed_at != self.document.completed_at
        ):
            raise ValueError("reported window/schema/time mismatch")
        if isinstance(self.document, CampaignPerformanceV2):
            if self.document.platform != self.target.account.platform:
                raise ValueError("reported provider mismatch")
        elif self.target.account.platform != "meta_ads":
            raise ValueError("V1 selected-event reporting requires Meta source")
        if self.conversion_qualification == "reported_only" and (
            not isinstance(self.document, CampaignPerformanceV1)
            or self.document.semantics != "explicit_platform_event"
            or not self.document.selected_event
            or self.document.conversions is None
            or Decimal(self.document.conversions) <= 0
        ):
            raise ValueError(
                "reported conversion qualification requires positive explicit-event evidence"
            )
        expected_coverage = (
            "partial" if self.completeness == "reported_rows_only" else "unavailable"
        )
        if self.reference.coverage != expected_coverage:
            raise ValueError("reported row coverage cannot be upgraded")
        if self.completeness == "reported_rows_only" and not self.document.campaign_rows_available:
            raise ValueError("missing campaign rows")
        if (
            self.reference.kind != "reported_metrics"
            or self.reference.account != self.target.account
            or self.document.account_id != self.target.account.account_id
            or self.document.privacy_revision != self.reference.privacy_revision
            or self.document.manifest_digest != self.reference.source_binding_digest
        ):
            raise ValueError("owned reported metric binding required")
        return self


class CommerceEvidence(Frozen):
    reference: EvidenceRef
    document: GoalSalesProgressV1

    @field_validator("document", mode="before")
    @classmethod
    def reparse(cls, value: Any) -> Any:
        return value.model_dump(mode="python") if isinstance(value, GoalSalesProgressV1) else value

    @model_validator(mode="after")
    def exact(self) -> CommerceEvidence:
        if (
            self.reference.kind != "shopify_measurement"
            or self.reference.workspace_id != self.document.workspace_id
            or self.reference.account is not None
        ):
            raise ValueError("owned commerce evidence required")
        if self.reference.document_digest != fingerprint(
            "goal-progress", self.document.model_dump(mode="json")
        ):
            raise ValueError("exact commerce document digest required")
        document, reference = self.document, self.reference
        coverage = document.coverage
        expected_coverage = (
            "unavailable"
            if document.status != "available_as_of"
            else "complete_in_declared_scope"
            if coverage is not None and coverage.extent == "full_window_as_of"
            else "partial"
        )
        expected_reasons = (
            document.reasons
            if document.status != "available_as_of"
            else ("partial_goal_window",)
            if expected_coverage == "partial"
            else ()
        )
        if (
            reference.reasons != expected_reasons
            or reference.document_schema != document.schema_version
            or reference.observation_started_at != document.as_of
            or reference.observed_at != document.as_of
            or reference.coverage != expected_coverage
            or reference.source_revision
            != (
                str(document.source_revision)
                if document.source_revision is not None
                else "unavailable"
            )
            or (coverage is None) != (reference.reporting_window is None)
        ):
            raise ValueError("commerce summary differs from actual progress")
        if (
            coverage is not None
            and reference.reporting_window is not None
            and (reference.reporting_window.starts_at, reference.reporting_window.ends_at_exclusive)
            != (coverage.starts_at, coverage.ends_at_exclusive)
        ):
            raise ValueError("commerce coverage window changed")
        return self


class EvidenceGap(Frozen):
    account: AccountRef | None
    section: Literal["catalog", "reported_metrics", "commerce", "creative_context"]
    reason: Key
    explanation: Text


class ContextEvidence(Frozen):
    reference: EvidenceRef
    document: PlanInputRevision | PlanningCompositionPolicy

    @model_validator(mode="after")
    def exact(self) -> ContextEvidence:
        kind = (
            "customer_context"
            if isinstance(self.document, PlanInputRevision)
            else "planning_policy"
        )
        if (
            self.reference.kind != kind
            or self.reference.account is not None
            or self.reference.document_digest != self.document.digest()
        ):
            raise ValueError("exact server-owned context document required")
        return self


class EvidenceBundle(NoAuthority):
    operation_id: Id
    input_digest: Digest
    privacy_revision: int = Field(strict=True, ge=0)
    collected_at: AwareDatetime
    catalogs: tuple[CatalogEvidence, ...] = Field(max_length=MAX_ACCOUNTS)
    performance: tuple[PerformanceEvidence, ...] = Field(max_length=MAX_EVIDENCE)
    commerce: CommerceEvidence | None
    context: tuple[ContextEvidence, ...] = Field(max_length=2)
    gaps: tuple[EvidenceGap, ...] = Field(max_length=MAX_EVIDENCE)

    def assert_ticket(self, ticket: GenerationTicket) -> None:
        self = type(self).model_validate(self)
        ticket = GenerationTicket.model_validate(ticket)
        if (
            self.operation_id != ticket.operation_id
            or self.input_digest != ticket.inputs.digest()
            or self.privacy_revision != ticket.privacy_revision
            or self.collected_at < ticket.prepared_at
        ):
            raise ValueError("evidence belongs to another generation")
        accounts = set(ticket.inputs.accounts)
        fences = {source.account.account_id: source for source in ticket.sources}
        for catalog in self.catalogs:
            account = catalog.reference.account
            if account is None or account not in accounts:
                raise ValueError("foreign catalog")
            if (
                catalog.reference.source_binding_digest
                != fences[account.account_id].source_binding_digest
            ):
                raise ValueError("catalog source fence changed")
            if (
                catalog.reference.source_revision != fences[account.account_id].source_revision
                or catalog.reference.reporting_window != ticket.inputs.reporting_window
            ):
                raise ValueError("catalog revision/reporting window changed")
        covered = {catalog.reference.account for catalog in self.catalogs}
        covered.update(gap.account for gap in self.gaps if gap.section == "catalog")
        if not accounts <= covered:
            raise ValueError("selected account needs catalog or explicit gap")
        catalog_by_account = {
            c.reference.account.account_id: c
            for c in self.catalogs
            if c.reference.account is not None
        }
        unique(
            tuple(
                (
                    p.target.account.account_id,
                    p.native_campaign_id,
                    p.document.starts_on,
                    p.document.ends_on,
                )
                for p in self.performance
            ),
            "performance campaign/window",
        )
        for performance in self.performance:
            if performance.reference.reporting_window not in (
                ticket.inputs.reporting_window,
                ticket.inputs.comparison_window,
            ):
                raise ValueError("performance window was not requested")
            actual_catalog = catalog_by_account.get(performance.target.account.account_id)
            if actual_catalog is None:
                raise ValueError("performance requires corresponding catalog")
            matching = [
                t
                for t in actual_catalog.catalog.targets
                if t.canonical_entity_key == performance.target.canonical_entity_key
            ]
            if len(matching) != 1:
                raise ValueError("performance target absent from catalog")
            actual, target = matching[0], performance.target
            if (
                target.catalog_evidence_key != actual_catalog.reference.key
                or target.provider_reference != actual.entity.reference
                or target.selection_key != actual.selection_key
                or target.kind != actual.entity.kind
                or target.display_name != actual.entity.name
                or target.budget_owner_key != actual.budget_owner_key
            ):
                raise ValueError("performance target differs from actual catalog")
        references = [c.reference for c in self.catalogs] + [p.reference for p in self.performance]
        dependent_refs = [p.reference for p in self.performance]
        if self.commerce is not None:
            dependent_refs.append(self.commerce.reference)
        if dependent_refs and (
            not self.catalogs
            or any(
                ref.expires_at > min(c.reference.expires_at for c in self.catalogs)
                for ref in dependent_refs
            )
        ):
            raise ValueError("derived evidence requires actual catalog deadline bound")
        for context in self.context:
            references.append(context.reference)
            if isinstance(context.document, PlanInputRevision):
                if context.document.digest() != ticket.inputs.digest():
                    raise ValueError("customer context differs from exact inputs")
            elif (
                context.document.version != ticket.policy_version
                or context.document.digest() != ticket.policy_digest
            ):
                raise ValueError("planning policy version changed")
        unique(tuple(c.reference.kind for c in self.context), "context kind")
        if self.context:
            observed_refs = [c.reference for c in self.catalogs] + [
                p.reference for p in self.performance
            ]
            if self.commerce is not None:
                observed_refs.append(self.commerce.reference)
            if not observed_refs or any(
                c.reference.expires_at > min(r.expires_at for r in observed_refs)
                for c in self.context
            ):
                raise ValueError("context expiry needs actual source evidence bound")
        if self.commerce is not None:
            references.append(self.commerce.reference)
            goal = self.commerce.document
            if (goal.goal_id, goal.revision) != (
                ticket.inputs.goal.goal_id,
                ticket.inputs.goal.revision,
            ):
                raise ValueError("commerce evidence goal changed")
            definition = ticket.inputs.goal.definition
            if (
                goal.definition_digest
                != source_fingerprint(
                    "inlet.goal-progress-definition.v1", definition.model_dump(mode="json")
                )
                or goal.store_id != definition.store_id
                or goal.target_micros != definition.target_micros
                or goal.target_window != definition.target_window
                or goal.currency != definition.target_window.currency
                or goal.time_zone != definition.target_window.time_zone
            ):
                raise ValueError("commerce confirmed definition changed")
        unique(tuple(ref.key for ref in references), "bundle evidence")
        unique(
            tuple(c.catalog.metadata_observation.account_id for c in self.catalogs),
            "catalog account",
        )
        if any(
            ref.workspace_id != ticket.inputs.workspace_id
            or ref.privacy_revision != self.privacy_revision
            or (ref.account is not None and ref.account not in accounts)
            or not ref.observed_at <= self.collected_at < ref.expires_at
            for ref in references
        ):
            raise ValueError("evidence ownership/freshness changed")
        if any(gap.account is not None and gap.account not in accounts for gap in self.gaps):
            raise ValueError("foreign evidence gap")


class PlanningCompositionPolicy(NoAuthority):
    version: Text
    generator_version: Text
    unsupported_data: Literal["explicit_gap_no_imputation"] = "explicit_gap_no_imputation"
    forecast: Literal["unavailable"] = "unavailable"
    native_writes: Literal["unavailable"] = "unavailable"


class PlanningEvidenceReader(Protocol):
    def collect(self, ticket: GenerationTicket) -> EvidenceBundle:
        """Read only through server-owned adapters; no transaction may span this call."""
        ...


class PlanComposer(Protocol):
    def compose(
        self,
        *,
        inputs: PlanInputRevision,
        evidence: EvidenceBundle,
        policy: PlanningCompositionPolicy,
        version: int,
        parent_digest: str | None,
        generated_by: str,
        generated_at: datetime,
    ) -> PlanVersion:
        """Pure composition only; caller rebinds candidate to current evidence at commit."""
        ...


ContextEvidence.model_rebuild()
EvidenceBundle.model_rebuild()
