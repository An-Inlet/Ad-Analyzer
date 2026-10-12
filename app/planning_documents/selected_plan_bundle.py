"""Pure exact selected-capture bundles; no SQL authority or active v4 capability."""

import re
from datetime import UTC, date, datetime, timezone
from decimal import Decimal
from typing import Any, Literal, cast
from zoneinfo import ZoneInfo

from pydantic import AwareDatetime, BaseModel, Field, field_validator, model_validator
from pydantic_core import TzInfo

from app.commerce.reporting import MeasurementWindow
from app.goals.progress_contracts import ClosedDayCoverageV1, GoalSalesProgressV1
from app.goals.schemas import GoalDefinition
from app.google_connections.selected_presence import PRODUCER, query_profile_digest
from app.meta import selected_profile as meta_profile
from app.planning_documents.common import (
    MAX_ACCOUNTS,
    MAX_EVIDENCE,
    Digest,
    Frozen,
    Id,
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
from app.planning_documents.creative_inputs import validate_creative_policy
from app.planning_documents.ports import (
    CatalogEvidence,
    CommerceEvidence,
    ContextEvidence,
    EvidenceGap,
    GenerationTicket,
)
from app.planning_documents.selected_plan_evidence import (
    SelectedPlanCaptureV1,
    SelectedPlanProjectionV1,
    SelectedPlanWindowV1,
)
from app.planning_documents.selected_plan_proof import SelectedRetainedProofV1
from app.planning_documents.selected_policy_contract import assert_selected_ticket_policy
from app.planning_documents.window_evidence import _target, _window_instants
from app.publication.contracts import fingerprint as source_fingerprint

MAX_BYTES = 32 * 1024 * 1024
METRIC_BASIS = "selected_provider_reported_event_count_and_value"
GapReason = Literal[
    "selected_capture_not_requested",
    "unsupported_selected_mapping",
    "campaign_outside_captured_mapping",
    "catalog_unavailable",
    "no_catalog_campaigns",
]


def selected_entry_key(account_id: int, campaign_id: int, window: ReportingWindow) -> str:
    if (
        type(account_id) is not int
        or account_id <= 0
        or type(campaign_id) is not int
        or campaign_id <= 0
    ):
        raise ValueError("positive exact local IDs required")
    start, end = _window_instants(window)
    return "selected_window:" + fingerprint(
        "selected-plan-window-entry",
        dict(
            account_id=account_id,
            campaign_id=campaign_id,
            starts_at=start.isoformat(),
            ends_at_exclusive=end.isoformat(),
        ),
    )


def supported(graph: SelectedPlanCaptureV1) -> bool:
    graph = SelectedPlanCaptureV1.model_validate(graph)
    req = graph.capture.request
    choice = req.selection
    if choice.scope.platform == "meta_ads":
        return (
            graph.capture.capability == "supported"
            and choice.api_version == "v26.0"
            and choice.metric_family == "actions"
            and choice.native_event_id == meta_profile.EVENT
            and choice.native_event_owner_id == choice.scope.native_account_id
            and req.producer_contract == meta_profile.PRODUCER
            and req.query_profile_digest
            == choice.query_profile_digest
            == meta_profile.query_profile_digest()
            and req.settings == meta_profile.settings()
            and all(f.selected_value_micros.presence == "unsupported" for f in graph.capture.facts)
        )
    if choice.metric_family not in {"conversions", "all_conversions"}:
        return False
    family: Literal["conversions", "all_conversions"] = (
        "conversions" if choice.metric_family == "conversions" else "all_conversions"
    )
    return (
        graph.capture.capability == "supported"
        and choice.scope.platform == "google_ads"
        and choice.api_version == "v24"
        and req.producer_contract == PRODUCER
        and req.query_profile_digest == choice.query_profile_digest == query_profile_digest(family)
        and choice.native_event_owner_id == choice.scope.native_account_id
        and re.fullmatch(
            rf"customers/{re.escape(choice.scope.native_account_id)}/conversionActions/[1-9][0-9]*",
            choice.native_event_id,
        )
        is not None
    )


class SelectedWindowEvidenceV1(Frozen):
    reference: EvidenceRef
    target: TargetRef
    document: SelectedPlanWindowV1

    @model_validator(mode="after")
    def binding(self) -> "SelectedWindowEvidenceV1":
        ref, target, doc = self.reference, self.target, self.document
        pin = doc.pin
        if (
            target.kind != "campaign"
            or ref.kind != "reported_metrics"
            or ref.account != target.account
            or target.account != pin.account
            or ref.workspace_id != pin.account.workspace_id
            or ref.privacy_revision != pin.source_fence.privacy_revision
            or ref.source_binding_digest != pin.source_fence.source_binding_digest
            or ref.source_revision != pin.source_fence.source_revision
            or target.provider_reference.entity_id != doc.summary.native_campaign_id
            or ref.reporting_window is None
            or _window_instants(ref.reporting_window) != _window_instants(doc.requested_window)
            or ref.document_schema != doc.schema_version
            or ref.document_digest
            != fingerprint("selected-plan-window", doc.model_dump(mode="json"))
            or ref.key
            != selected_entry_key(
                pin.account.account_id, doc.summary.campaign_id, doc.requested_window
            )
            or ref.metric_basis != METRIC_BASIS
        ):
            raise ValueError("exact selected window reference required")
        observed = doc.summary.conversions.present_days or doc.summary.value_micros.present_days
        if ref.coverage != ("partial" if observed else "unavailable") or not ref.reasons:
            raise ValueError("selected observation coverage cannot be upgraded")
        return self


class SelectedReportingGapV1(Frozen):
    account: AccountRef
    target: TargetRef | None
    requested_window: ReportingWindow
    reason: GapReason
    reporting_pin_digest: Digest
    explanation: Text

    @model_validator(mode="after")
    def scope(self) -> "SelectedReportingGapV1":
        if (self.reason in {"catalog_unavailable", "no_catalog_campaigns"}) != (
            self.target is None
        ):
            raise ValueError("catalog and campaign gap scopes differ")
        if self.target is not None and (
            self.target.account != self.account or self.target.kind != "campaign"
        ):
            raise ValueError("owned campaign gap required")
        return self


class SelectedPlanEvidenceBundleV1(NoAuthority):
    operation_id: Id
    input_digest: Digest
    privacy_revision: int = Field(strict=True, ge=0)
    collected_at: AwareDatetime
    catalogs: tuple[CatalogEvidence, ...] = Field(max_length=MAX_ACCOUNTS)
    performance: tuple[SelectedWindowEvidenceV1, ...] = Field(max_length=MAX_EVIDENCE)
    commerce: CommerceEvidence | None
    context: tuple[ContextEvidence, ...] = Field(max_length=2)
    gaps: tuple[EvidenceGap, ...] = Field(max_length=MAX_EVIDENCE)
    reporting_proof: SelectedRetainedProofV1
    selected_captures: tuple[SelectedPlanCaptureV1, ...] = Field(max_length=MAX_ACCOUNTS)
    window_gaps: tuple[SelectedReportingGapV1, ...] = Field(max_length=MAX_EVIDENCE)

    @field_validator("collected_at", mode="before")
    @classmethod
    def instant(cls, value: Any) -> datetime:
        if type(value) is str:
            try:
                value = datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                raise ValueError("aware collection instant required") from None
        if type(value) is not datetime or value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("aware collection instant required")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def capacity(self) -> "SelectedPlanEvidenceBundleV1":
        if len(self.performance) + len(self.window_gaps) > MAX_EVIDENCE:
            raise ValueError("selected slot capacity exceeded")
        if any(g.section == "reported_metrics" or g.reporting_pin is not None for g in self.gaps):
            raise ValueError("selected reporting gaps require exact window binding")
        if len(self.model_dump_json().encode()) > MAX_BYTES:
            raise ValueError("selected bundle byte capacity exceeded")
        SelectedPlanProjectionV1(
            captures=self.selected_captures, windows=tuple(p.document for p in self.performance)
        )
        return self

    def assert_ticket(self, ticket: GenerationTicket) -> None:
        self = type(self).model_validate(self)
        ticket = GenerationTicket.model_validate(ticket)
        _assert_selected_ticket_checked(self, ticket)

    def _references(self, ticket: GenerationTicket, accounts: set[AccountRef]) -> None:
        references = [c.reference for c in self.catalogs] + [p.reference for p in self.performance]
        dependent = [p.reference for p in self.performance]
        if self.commerce is not None:
            dependent.append(self.commerce.reference)
        if dependent and (
            not self.catalogs
            or any(
                r.expires_at.astimezone(UTC)
                > min(c.reference.expires_at.astimezone(UTC) for c in self.catalogs)
                for r in dependent
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
                c.reference.expires_at.astimezone(UTC)
                > min(r.expires_at.astimezone(UTC) for r in observed)
                for c in self.context
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
            or not r.observed_at.astimezone(UTC) <= self.collected_at < r.expires_at.astimezone(UTC)
            for r in references
        ):
            raise ValueError("evidence ownership/freshness changed")
        if any(g.account is not None and g.account not in accounts for g in self.gaps):
            raise ValueError("foreign evidence gap")


def _assert_selected_ticket_checked(
    self: SelectedPlanEvidenceBundleV1, ticket: GenerationTicket
) -> None:
    contract = assert_selected_ticket_policy(ticket.policy_version, ticket.policy_digest)
    validate_creative_policy(
        ticket.inputs.creative, contract.policy_version, contract.generator_version
    )
    if ticket.inputs.selected_reporting is None:
        raise ValueError("explicit selected reporting required")
    if (
        self.operation_id != ticket.operation_id
        or self.input_digest != ticket.inputs.digest()
        or self.privacy_revision != ticket.privacy_revision
        or self.collected_at < ticket.prepared_at.astimezone(UTC)
    ):
        raise ValueError("selected bundle generation mismatch")
    self.reporting_proof.assert_inputs(ticket.inputs, self.privacy_revision)
    accounts = set(ticket.inputs.accounts)
    fences = {f.account: f for f in ticket.sources}
    proofs = {p.source_fence.account: p for p in self.reporting_proof.accounts}
    if any(p.source_fence != fences[a] for a, p in proofs.items()):
        raise ValueError("retained proof source changed")
    graphs = {g.source_fence.account: g for g in self.selected_captures}
    if len(graphs) != len(self.selected_captures) or set(graphs) != {
        a for a, p in proofs.items() if p.capture_pin is not None
    }:
        raise ValueError("exact supplied capture graph set required")
    graph: SelectedPlanCaptureV1 | None
    for account, graph in graphs.items():
        if graph.pin() != proofs[account].capture_pin or graph.source_fence != fences[account]:
            raise ValueError("retained capture graph pin changed")
    catalogs: dict[AccountRef, CatalogEvidence] = {}
    catalog: CatalogEvidence | None
    for catalog in self.catalogs:
        catalog_account = catalog.reference.account
        if catalog_account is None:
            raise ValueError("catalog account required")
        account = catalog_account
        if account is None or account not in accounts or account in catalogs:
            raise ValueError("foreign or duplicate selected catalog")
        fence = fences[account]
        if (
            catalog.reference.source_binding_digest != fence.source_binding_digest
            or catalog.reference.source_revision != fence.source_revision
            or catalog.reference.reporting_window is None
            or _window_instants(catalog.reference.reporting_window)
            != _window_instants(ticket.inputs.reporting_window)
        ):
            raise ValueError("selected catalog source/window changed")
        if account in graphs:
            scope = graphs[account].capture.request.aggregate.scope
            native = catalog.catalog.native_observation
            if (scope.currency, scope.time_zone) != (native.currency, native.time_zone) or any(
                t.entity.reference.advertiser_id != scope.native_account_id
                for t in catalog.catalog.targets
            ):
                raise ValueError("selected catalog account identity or units differ")
        catalogs[account] = catalog
    absent = [g.account for g in self.gaps if g.section == "catalog"]
    unique(tuple(absent), "catalog gap")
    if None in absent or set(catalogs) & set(absent) or set(catalogs) | set(absent) != accounts:
        raise ValueError("exclusive exact catalog or gap set required")
    windows = (ticket.inputs.reporting_window,) + (
        (ticket.inputs.comparison_window,) if ticket.inputs.comparison_window else ()
    )
    required = set()
    for account in accounts:
        catalog = catalogs.get(account)
        campaigns = (
            []
            if catalog is None
            else [t for t in catalog.catalog.targets if t.entity.kind == "campaign"]
        )
        for key in [t.canonical_entity_key for t in campaigns] if campaigns else [None]:
            for window in windows:
                required.add((account, key, _window_instants(window)))
    if len(required) > MAX_EVIDENCE:
        raise ValueError("selected campaign/window product exceeds capacity")
    slots: list[tuple[AccountRef, str | None, tuple[datetime, datetime]]] = []
    for item in self.performance:
        account, target, doc = item.target.account, item.target, item.document
        catalog, graph = catalogs.get(account), graphs.get(account)
        if catalog is None or graph is None or not supported(graph):
            raise ValueError("selected observation requires recognized owned profile")
        _target(catalog, target)
        if (
            target.provider_reference.advertiser_id
            != graph.capture.request.aggregate.scope.native_account_id
        ):
            raise ValueError("selected catalog advertiser differs")
        native = catalog.catalog.native_observation
        scope = graph.capture.request.aggregate.scope
        if (scope.currency, scope.time_zone) != (native.currency, native.time_zone):
            raise ValueError("selected catalog units differ")
        if item.reference.observation_started_at.astimezone(
            UTC
        ) != graph.capture.request.started_at.astimezone(
            UTC
        ) or item.reference.observed_at.astimezone(UTC) != graph.capture.completed_at.astimezone(
            UTC
        ):
            raise ValueError("selected capture observation times changed")
        slots.append((account, target.canonical_entity_key, _window_instants(doc.requested_window)))
    for gap in self.window_gaps:
        if (
            gap.account not in proofs
            or gap.reporting_pin_digest != proofs[gap.account].state_digest()
        ):
            raise ValueError("selected gap retained pin mismatch")
        catalog, graph = catalogs.get(gap.account), graphs.get(gap.account)
        if gap.target is None:
            expected = "catalog_unavailable" if catalog is None else "no_catalog_campaigns"
        else:
            if catalog is None:
                raise ValueError("selected campaign gap lacks catalog")
            _target(catalog, gap.target)
            if (gap.account.platform != "google_ads" and graph is None) or (
                graph is not None and not supported(graph)
            ):
                expected = "unsupported_selected_mapping"
            elif graph is None:
                expected = "selected_capture_not_requested"
            elif gap.target.provider_reference.entity_id not in {
                c.native_campaign_id for c in graph.campaigns
            }:
                expected = "campaign_outside_captured_mapping"
            else:
                raise ValueError("supported mapped capture must project observed or missing cells")
        if gap.reason != expected:
            raise ValueError("selected gap reason differs from exact source")
        slots.append(
            (
                gap.account,
                gap.target.canonical_entity_key if gap.target else None,
                _window_instants(gap.requested_window),
            )
        )
    unique(tuple(slots), "selected window slot")
    if set(slots) != required:
        raise ValueError("exact selected campaign/window success or gap set required")
    self._references(ticket, accounts)


# These built-in descriptors bypass instance attribute overrides and shadowing properties.
_MODEL_VALUES = BaseModel.__dict__["__dict__"]
_DATETIME_ZONE = datetime.__dict__["tzinfo"]
_TYPE_MRO = type.__dict__["__mro__"]
_LEGACY_MODELS = (GoalDefinition, MeasurementWindow, GoalSalesProgressV1, ClosedDayCoverageV1)
_SCALAR_SCAN_LIMIT = 100_000


def _inert_selected_values(*values: object) -> bool:
    """Exclude custom behavior after mandatory validation; never a validation capability."""
    pending = list(values)
    seen: set[int] = set()
    visited = 0
    while pending:
        visited += 1
        if visited > _SCALAR_SCAN_LIMIT or len(pending) > _SCALAR_SCAN_LIMIT:
            return False
        value = pending.pop()
        kind = type(value)
        if (
            value is None
            or kind is str
            or kind is int
            or kind is bool
            or kind is Decimal
            or kind is date
        ):
            continue
        if kind is datetime:
            zone_kind = type(_DATETIME_ZONE.__get__(value))
            if zone_kind is not timezone and zone_kind is not ZoneInfo and zone_kind is not TzInfo:
                return False
            continue
        if kind is tuple:
            if not value:
                continue
            children = cast(tuple[object, ...], value)
        else:
            try:
                resident = _MODEL_VALUES.__get__(value)
            except TypeError:
                return False
            if type(resident) is not dict:
                return False
            mro = _TYPE_MRO.__get__(kind)
            for legacy in _LEGACY_MODELS:
                if any(parent is legacy for parent in mro) and kind is not legacy:
                    return False
            children = tuple(resident.values())
        marker = id(value)
        if marker in seen:
            return False
        seen.add(marker)
        if len(pending) + len(children) > _SCALAR_SCAN_LIMIT:
            return False
        pending.extend(children)
    return True


def _validate_selected_ticket_pair(
    bundle: SelectedPlanEvidenceBundleV1, ticket: GenerationTicket
) -> tuple[SelectedPlanEvidenceBundleV1, GenerationTicket]:
    ticket = GenerationTicket.model_validate(ticket)
    bundle = SelectedPlanEvidenceBundleV1.model_validate(bundle)
    if type(bundle) is SelectedPlanEvidenceBundleV1 and _inert_selected_values(bundle, ticket):
        _assert_selected_ticket_checked(bundle, ticket)
    else:
        bundle.assert_ticket(ticket)
    return bundle, ticket
