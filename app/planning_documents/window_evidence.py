"""Private window evidence values, not owned reader proof or active runtime policy."""

from datetime import UTC, datetime
from typing import Literal

from pydantic import AwareDatetime, Field, model_validator

from app.campaign_performance.window_projection import RequestedWindowPerformanceV1
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
from app.planning_documents.context import (
    AccountRef,
    EvidenceRef,
    PlanInputRevision,
    ReportingWindow,
    TargetRef,
)
from app.planning_documents.policy_capabilities import ticket_reporting_capability
from app.planning_documents.ports import (
    CatalogEvidence,
    CommerceEvidence,
    ContextEvidence,
    EvidenceGap,
    GenerationTicket,
    ReportingPresencePin,
)
from app.publication.contracts import fingerprint as source_fingerprint

MAX_COLLECTION_BYTES = 32 * 1024 * 1024
ReaderGapReason = Literal[
    "current_reporting_unavailable",
    "campaign_reporting_unavailable",
    "reporting_presence_unavailable",
    "outside_imported_window",
    "unaligned_local_days",
    "requested_days_not_closed",
]
WindowGapReason = Literal[ReaderGapReason, "catalog_unavailable", "no_catalog_campaigns"]


def _window_instants(window: ReportingWindow) -> tuple[datetime, datetime]:
    # Python same-zone datetime equality ignores fold; compare exact UTC instants.
    window = ReportingWindow.model_validate(window)
    return window.starts_at.astimezone(UTC), window.ends_at_exclusive.astimezone(UTC)


def reporting_entry_key(
    account_id: int, campaign_id: int, requested_window: ReportingWindow
) -> str:
    if (
        type(account_id) is not int
        or account_id <= 0
        or type(campaign_id) is not int
        or campaign_id <= 0
    ):
        raise ValueError("exact positive local account and campaign IDs required")
    window = ReportingWindow.model_validate(requested_window)
    normalized = dict(
        starts_at=window.starts_at.astimezone(UTC).isoformat(),
        ends_at_exclusive=window.ends_at_exclusive.astimezone(UTC).isoformat(),
    )
    return "performance_window:" + fingerprint(
        "requested-reporting-entry",
        dict(
            account_id=account_id,
            campaign_id=campaign_id,
            requested_window=normalized,
        ),
    )


class WindowPerformanceEvidenceV1(Frozen):
    reference: EvidenceRef
    target: TargetRef
    document: RequestedWindowPerformanceV1
    measurement_scope: Literal["provider_reported_not_cross_platform_comparable"] = (
        "provider_reported_not_cross_platform_comparable"
    )
    attribution_qualification: Literal["unavailable"] = "unavailable"
    completeness: Literal["reported_rows_only", "unavailable"]
    conversion_qualification: Literal["reported_only", "unavailable"]
    reasons: tuple[Key, ...] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def exact(self) -> "WindowPerformanceEvidenceV1":
        ref, target, doc = self.reference, self.target, self.document
        original, header = doc.original, doc.original.presence
        if (
            target.kind != "campaign"
            or ref.kind != "reported_metrics"
            or ref.account != target.account
            or (
                ref.workspace_id,
                target.account.workspace_id,
                target.account.account_id,
                target.account.connection_id,
                target.account.platform,
            )
            != (
                header.workspace_id,
                header.workspace_id,
                header.account_id,
                header.connection_id,
                header.platform,
            )
            or target.provider_reference.entity_id != original.native_campaign_id
            or ref.source_binding_digest != original.manifest_digest
            or ref.source_revision != str(original.generation)
            or ref.privacy_revision != original.privacy_revision
            or ref.observation_started_at != original.completed_at
            or ref.observed_at != original.completed_at
            or ref.reporting_window is None
            or _window_instants(ref.reporting_window) != _window_instants(doc.requested_window)
            or ref.document_schema != doc.schema_version
            or ref.document_digest
            != fingerprint("requested-window-performance", doc.model_dump(mode="json"))
            or ref.key
            != reporting_entry_key(original.account_id, original.campaign_id, doc.requested_window)
        ):
            raise ValueError("exact owned window report binding required")
        if ref.coverage != (
            "partial" if self.completeness == "reported_rows_only" else "unavailable"
        ):
            raise ValueError("window row coverage cannot be upgraded")
        if self.completeness == "reported_rows_only" and not doc.selected_facts:
            raise ValueError("requested window has no returned campaign rows")
        if self.conversion_qualification == "reported_only" and (
            header.selected_event.provenance != "explicit_selected"
            or doc.summary.selected_conversions.value is None
        ):
            raise ValueError("selected qualification requires observed selected cells")
        return self


class KnownWindowGap(Frozen):
    reason: ReaderGapReason


class WindowReportingGapV1(Frozen):
    account: AccountRef
    target: TargetRef | None
    requested_window: ReportingWindow
    reason: WindowGapReason
    reporting_pin_digest: Digest
    explanation: Text

    @model_validator(mode="after")
    def scope(self) -> "WindowReportingGapV1":
        if (self.reason in {"catalog_unavailable", "no_catalog_campaigns"}) != (
            self.target is None
        ):
            raise ValueError("catalog gap and campaign gap scopes differ")
        if self.target is not None and (
            self.target.account != self.account or self.target.kind != "campaign"
        ):
            raise ValueError("exact owned campaign gap required")
        return self


def _target(catalog: CatalogEvidence, target: TargetRef) -> None:
    matches = [
        t for t in catalog.catalog.targets if t.canonical_entity_key == target.canonical_entity_key
    ]
    if len(matches) != 1:
        raise ValueError("window target absent from catalog")
    actual = matches[0]
    if (
        target.account != catalog.reference.account
        or target.catalog_evidence_key != catalog.reference.key
        or target.provider_reference != actual.entity.reference
        or target.selection_key != actual.selection_key
        or target.kind != actual.entity.kind
        or target.display_name != actual.entity.name
        or target.budget_owner_key != actual.budget_owner_key
    ):
        raise ValueError("window target differs from actual catalog")


class WindowEvidenceBundleV1(NoAuthority):
    operation_id: Id
    input_digest: Digest
    privacy_revision: int = Field(strict=True, ge=0)
    collected_at: AwareDatetime
    catalogs: tuple[CatalogEvidence, ...] = Field(max_length=MAX_ACCOUNTS)
    performance: tuple[WindowPerformanceEvidenceV1, ...] = Field(max_length=MAX_EVIDENCE)
    commerce: CommerceEvidence | None
    context: tuple[ContextEvidence, ...] = Field(max_length=2)
    gaps: tuple[EvidenceGap, ...] = Field(max_length=MAX_EVIDENCE)
    reporting_pins: tuple[ReportingPresencePin, ...] = Field(max_length=MAX_ACCOUNTS)
    window_gaps: tuple[WindowReportingGapV1, ...] = Field(max_length=MAX_EVIDENCE)

    @model_validator(mode="after")
    def capacity(self) -> "WindowEvidenceBundleV1":
        if len(self.performance) + len(self.window_gaps) > MAX_EVIDENCE:
            raise ValueError("combined window slot capacity exceeded")
        if any(g.section == "reported_metrics" or g.reporting_pin is not None for g in self.gaps):
            raise ValueError("reporting gaps require versioned window binding")
        if len(self.model_dump_json().encode("utf-8")) > MAX_COLLECTION_BYTES:
            raise ValueError("window bundle byte capacity exceeded")
        return self

    def assert_ticket(self, ticket: GenerationTicket) -> None:
        self = type(self).model_validate(self)
        ticket = GenerationTicket.model_validate(ticket)
        if (
            ticket_reporting_capability(ticket.policy_version, ticket.policy_digest).mode
            != "presence_requested_window"
        ):
            raise ValueError("window bundle requires exact v3 policy")
        if (
            self.operation_id != ticket.operation_id
            or self.input_digest != ticket.inputs.digest()
            or self.privacy_revision != ticket.privacy_revision
            or self.collected_at < ticket.prepared_at
        ):
            raise ValueError("evidence belongs to another generation")
        accounts = set(ticket.inputs.accounts)
        if (
            len(self.reporting_pins) != len(accounts)
            or {p.account for p in self.reporting_pins} != accounts
        ):
            raise ValueError("exact reporting pin account set required")
        pins = {p.account: p.document_digest for p in self.reporting_pins}
        fences = {s.account: s for s in ticket.sources}
        catalog_by_account: dict[AccountRef, CatalogEvidence] = {}
        catalog: CatalogEvidence | None
        for catalog in self.catalogs:
            account = catalog.reference.account
            if account is None or account not in accounts or account in catalog_by_account:
                raise ValueError("foreign or duplicate catalog")
            fence = fences[account]
            if (
                catalog.reference.source_binding_digest != fence.source_binding_digest
                or catalog.reference.source_revision != fence.source_revision
                or catalog.reference.reporting_window is None
                or _window_instants(catalog.reference.reporting_window)
                != _window_instants(ticket.inputs.reporting_window)
            ):
                raise ValueError("catalog source/revision/window changed")
            catalog_by_account[account] = catalog
        catalog_gaps = [g.account for g in self.gaps if g.section == "catalog"]
        unique(tuple(catalog_gaps), "catalog gap account")
        if (
            set(catalog_by_account) & set(catalog_gaps)
            or None in catalog_gaps
            or set(catalog_by_account) | set(catalog_gaps) != accounts
        ):
            raise ValueError("exact exclusive catalog or gap required")
        windows = (ticket.inputs.reporting_window,) + (
            (ticket.inputs.comparison_window,)
            if ticket.inputs.comparison_window is not None
            else ()
        )
        required: set[tuple[AccountRef, str | None, tuple[datetime, datetime]]] = set()
        for account in accounts:
            catalog = catalog_by_account.get(account)
            campaigns = (
                []
                if catalog is None
                else [t for t in catalog.catalog.targets if t.entity.kind == "campaign"]
            )
            for key in [t.canonical_entity_key for t in campaigns] if campaigns else [None]:
                for window in windows:
                    required.add((account, key, _window_instants(window)))
        if len(required) > MAX_EVIDENCE:
            raise ValueError("requested campaign/window product exceeds capacity")
        slots: list[tuple[AccountRef, str | None, tuple[datetime, datetime]]] = []
        for performance in self.performance:
            target = performance.target
            catalog = catalog_by_account.get(target.account)
            if catalog is None:
                raise ValueError("window evidence needs actual catalog")
            _target(catalog, target)
            native = catalog.catalog.native_observation
            if (
                performance.document.original.currency,
                performance.document.original.time_zone,
            ) != (native.currency, native.time_zone):
                raise ValueError("window report currency/time zone differs from owned catalog")
            slots.append(
                (
                    target.account,
                    target.canonical_entity_key,
                    _window_instants(performance.document.requested_window),
                )
            )
        for gap in self.window_gaps:
            if gap.account not in pins or gap.reporting_pin_digest != pins[gap.account]:
                raise ValueError("window gap pin changed")
            catalog = catalog_by_account.get(gap.account)
            if gap.target is not None:
                if catalog is None:
                    raise ValueError("campaign gap requires catalog")
                _target(catalog, gap.target)
            elif gap.reason != (
                "catalog_unavailable" if catalog is None else "no_catalog_campaigns"
            ):
                raise ValueError("catalog gap reason differs from collected scope")
            slots.append(
                (
                    gap.account,
                    gap.target.canonical_entity_key if gap.target else None,
                    _window_instants(gap.requested_window),
                )
            )
        unique(tuple(slots), "window slot")
        if set(slots) != required:
            raise ValueError("exact campaign/window success or gap set required")
        self._references(ticket, accounts)

    def _references(self, ticket: GenerationTicket, accounts: set[AccountRef]) -> None:
        references = [c.reference for c in self.catalogs] + [p.reference for p in self.performance]
        dependent = [p.reference for p in self.performance]
        if self.commerce is not None:
            dependent.append(self.commerce.reference)
        if dependent and (
            not self.catalogs
            or any(
                r.expires_at > min(c.reference.expires_at for c in self.catalogs) for r in dependent
            )
        ):
            raise ValueError("derived evidence needs actual catalog deadline")
        for context in self.context:
            references.append(context.reference)
            if isinstance(context.document, PlanInputRevision):
                if context.document.digest() != ticket.inputs.digest():
                    raise ValueError("customer context differs from inputs")
            elif (
                context.document.version != ticket.policy_version
                or context.document.digest() != ticket.policy_digest
            ):
                raise ValueError("planning policy changed")
        unique(tuple(c.reference.kind for c in self.context), "context kind")
        if self.context:
            observed = [c.reference for c in self.catalogs] + [
                p.reference for p in self.performance
            ]
            if self.commerce is not None:
                observed.append(self.commerce.reference)
            if not observed or any(
                c.reference.expires_at > min(r.expires_at for r in observed) for c in self.context
            ):
                raise ValueError("context expiry needs actual source bound")
        if self.commerce is not None:
            references.append(self.commerce.reference)
            goal, expected = self.commerce.document, ticket.inputs.goal
            definition = expected.definition
            if (
                (goal.goal_id, goal.revision) != (expected.goal_id, expected.revision)
                or goal.definition_digest
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
        unique(tuple(r.key for r in references), "bundle evidence")
        if any(
            r.workspace_id != ticket.inputs.workspace_id
            or r.privacy_revision != self.privacy_revision
            or (r.account is not None and r.account not in accounts)
            or not r.observed_at <= self.collected_at < r.expires_at
            for r in references
        ):
            raise ValueError("evidence ownership/freshness changed")
        if any(g.account is not None and g.account not in accounts for g in self.gaps):
            raise ValueError("foreign evidence gap")
