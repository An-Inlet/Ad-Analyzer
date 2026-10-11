"""Pure exact selected/traffic pairing; construction conveys no authority."""

from datetime import UTC, datetime
from typing import Literal

from pydantic import Field, model_validator

from app.planning_documents.common import Digest, Frozen, NoAuthority, Text, fingerprint
from app.planning_documents.context import AccountRef, EvidenceRef, ReportingWindow, TargetRef
from app.planning_documents.ports import GenerationTicket
from app.planning_documents.selected_plan_bundle import SelectedPlanEvidenceBundleV1
from app.planning_documents.selected_traffic import (
    PreparedRawRangeTrafficProjection,
    RawRangeTrafficGraphV1,
    SelectedTrafficWindowV1,
)

TrafficGapReason = Literal["range_traffic_provenance_unavailable", "unsupported_traffic_profile"]
METRIC_BASIS = "provider_reported_raw_traffic"


def instants(window: ReportingWindow) -> tuple[datetime, datetime]:
    return window.starts_at.astimezone(UTC), window.ends_at_exclusive.astimezone(UTC)


def traffic_window_key(account_id: int, campaign_id: int, window: ReportingWindow) -> str:
    if (
        type(account_id) is not int
        or account_id <= 0
        or type(campaign_id) is not int
        or campaign_id <= 0
    ):
        raise ValueError("exact positive traffic identity required")
    start, end = instants(ReportingWindow.model_validate(window))
    return "traffic_window:" + fingerprint(
        "selected-traffic-window-entry",
        dict(
            account_id=account_id,
            campaign_id=campaign_id,
            starts_at=start.isoformat(),
            ends_at_exclusive=end.isoformat(),
        ),
    )


class TrafficWindowEvidenceV1(Frozen):
    reference: EvidenceRef
    target: TargetRef
    document: SelectedTrafficWindowV1

    @model_validator(mode="after")
    def binding(self) -> "TrafficWindowEvidenceV1":
        ref, target, doc = self.reference, self.target, self.document
        fence = doc.pin.source_fence
        if (
            target.kind != "campaign"
            or target.account != fence.account
            or target.provider_reference.entity_id != doc.native_campaign_id
            or target.provider_reference.advertiser_id != doc.pin.aggregate.scope.native_account_id
            or ref.account != target.account
            or ref.workspace_id != target.account.workspace_id
            or ref.kind != "reported_metrics"
            or ref.document_schema != doc.schema_version
            or ref.document_digest
            != fingerprint("selected-traffic-window", doc.model_dump(mode="json"))
            or ref.key
            != traffic_window_key(target.account.account_id, doc.campaign_id, doc.requested_window)
            or ref.reporting_window is None
            or instants(ref.reporting_window) != instants(doc.requested_window)
            or ref.source_binding_digest != fence.source_binding_digest
            or ref.source_revision != fence.source_revision
            or ref.privacy_revision != fence.privacy_revision
            or ref.metric_basis != METRIC_BASIS
            or ref.coverage != ("partial" if doc.returned_days else "unavailable")
            or not ref.reasons
        ):
            raise ValueError("exact raw traffic reference required")
        return self


class TrafficWindowGapV1(Frozen):
    account: AccountRef
    target: TargetRef
    requested_window: ReportingWindow
    reason: TrafficGapReason
    reporting_pin_digest: Digest
    explanation: Text

    @model_validator(mode="after")
    def scope(self) -> "TrafficWindowGapV1":
        if self.target.kind != "campaign" or self.target.account != self.account:
            raise ValueError("traffic gap requires exact campaign scope")
        return self


class SelectedPairedEvidenceV1(NoAuthority):
    selected: SelectedPlanEvidenceBundleV1
    traffic_graphs: tuple[RawRangeTrafficGraphV1, ...] = Field(max_length=20)
    traffic: tuple[TrafficWindowEvidenceV1, ...] = Field(max_length=400)
    traffic_gaps: tuple[TrafficWindowGapV1, ...] = Field(max_length=400)

    @model_validator(mode="after")
    def bounded(self) -> "SelectedPairedEvidenceV1":
        if (
            len(self.traffic) + len(self.traffic_gaps) > 400
            or len(self.model_dump_json().encode()) > 32 * 1024 * 1024
        ):
            raise ValueError("paired evidence capacity exceeded")
        return self

    def assert_ticket(self, ticket: GenerationTicket) -> None:
        self = type(self).model_validate(self)
        ticket = GenerationTicket.model_validate(ticket)
        self.selected.assert_ticket(ticket)
        proofs = {p.source_fence.account: p for p in self.selected.reporting_proof.accounts}
        graphs = {g.source_fence.account: g for g in self.traffic_graphs}
        if len(graphs) != len(self.traffic_graphs) or set(graphs) != {
            a for a, p in proofs.items() if p.traffic_pin is not None
        }:
            raise ValueError("exact retained traffic graph set required")
        prepared = {a: PreparedRawRangeTrafficProjection(g) for a, g in graphs.items()}
        for account, projection in prepared.items():
            if projection.pin != proofs[account].traffic_pin:
                raise ValueError("retained traffic graph changed")

        def slot(
            target: TargetRef, window: ReportingWindow
        ) -> tuple[AccountRef, str, tuple[datetime, datetime]]:
            return target.account, target.canonical_entity_key, instants(window)

        selected = {
            slot(p.target, p.document.requested_window): p for p in self.selected.performance
        }
        catalogs = {c.reference.account: c for c in self.selected.catalogs}
        seen = set()
        all_refs = (
            [c.reference for c in self.selected.catalogs]
            + [p.reference for p in self.selected.performance]
            + [c.reference for c in self.selected.context]
        )
        if self.selected.commerce is not None:
            all_refs.append(self.selected.commerce.reference)
        for item in self.traffic:
            key = slot(item.target, item.document.requested_window)
            pair = selected.get(key)
            graph = graphs.get(item.target.account)
            if key in seen or pair is None or graph is None or pair.target != item.target:
                raise ValueError("unpaired or duplicate traffic window")
            seen.add(key)
            pin, chosen = item.document.pin, pair.document.pin
            if (
                pin != prepared[item.target.account].pin
                or (pin.source_fence, pin.aggregate, pin.campaign_map_digest)
                != (chosen.source_fence, chosen.aggregate, chosen.campaign_map_digest)
                or item.document.campaign_id != pair.document.summary.campaign_id
                or item.document.native_campaign_id != pair.document.summary.native_campaign_id
            ):
                raise ValueError("selected/traffic source, aggregate or mapping mismatch")
            actual = prepared[item.target.account].read(
                campaign_id=item.document.campaign_id,
                requested_window=item.document.requested_window,
            )
            if actual != item.document:
                raise ValueError("traffic arithmetic or coverage changed")
            ref = item.reference
            completed = graph.receipt.completed_at.astimezone(UTC)
            catalog = catalogs[item.target.account]
            if (
                ref.observation_started_at.astimezone(UTC) != completed
                or ref.observed_at.astimezone(UTC) != completed
                or not ref.observed_at.astimezone(UTC)
                <= self.selected.collected_at.astimezone(UTC)
                < ref.expires_at.astimezone(UTC)
                or ref.expires_at.astimezone(UTC)
                > min(
                    pair.reference.expires_at.astimezone(UTC),
                    catalog.reference.expires_at.astimezone(UTC),
                )
            ):
                raise ValueError("traffic publication observation or deadline changed")
            all_refs.append(ref)
        for gap in self.traffic_gaps:
            key = slot(gap.target, gap.requested_window)
            pair = selected.get(key)
            proof = proofs.get(gap.account)
            if (
                key in seen
                or pair is None
                or gap.target != pair.target
                or proof is None
                or proof.traffic_pin is not None
                or gap.reporting_pin_digest != proof.state_digest()
            ):
                raise ValueError("unpaired, duplicate or non-absent traffic gap")
            seen.add(key)
        if seen != set(selected):
            raise ValueError("every selected success requires a traffic observation or gap")
        keys = [r.key for r in all_refs]
        if len(keys) != len(set(keys)):
            raise ValueError("duplicate paired reference key")
