"""Original-session selected/traffic collection; no runtime registration."""

from collections.abc import Callable
from datetime import datetime

from sqlalchemy.orm import Session

from app.customers.access import CustomerPrincipal
from app.customers.identity import IdentityProvider
from app.planning_documents.common import fingerprint
from app.planning_documents.context import EvidenceRef
from app.planning_documents.ports import GenerationTicket, PlanningCompositionPolicy
from app.planning_documents.read_context import PlanningReadContexts, snapshot
from app.planning_documents.selected_paired_evidence import (
    METRIC_BASIS,
    SelectedPairedEvidenceV1,
    TrafficWindowEvidenceV1,
    TrafficWindowGapV1,
    traffic_window_key,
)
from app.planning_documents.selected_paired_local import (
    load_paired_traffic,
    recheck_selected_paired_sources,
)
from app.planning_documents.selected_plan_adapter import OwnedSelectedEvidenceReader
from app.planning_documents.selected_traffic import (
    PreparedRawRangeTrafficProjection,
    RawRangeTrafficGraphV1,
)
from app.planning_documents.selected_traffic_reader import KnownTrafficGap
from app.shopify.security import utc


class OwnedSelectedPairedReader:
    def __init__(
        self,
        sessions: Callable[[], Session],
        *,
        principal: CustomerPrincipal,
        provider: IdentityProvider,
        policy: PlanningCompositionPolicy,
        clock: Callable[[], datetime],
    ) -> None:
        self.sessions, self.principal, self.provider = sessions, snapshot(principal), provider
        self.policy, self.clock = policy, clock

    def collect(self, ticket: GenerationTicket) -> SelectedPairedEvidenceV1:
        ticket = GenerationTicket.model_validate(ticket)
        selected = OwnedSelectedEvidenceReader(
            self.sessions,
            principal=self.principal,
            provider=self.provider,
            policy=self.policy,
            clock=self.clock,
        ).collect(ticket)
        reads = PlanningReadContexts(
            self.sessions,
            self.principal,
            self.provider,
            ticket.inputs.workspace_id,
            ticket.actor_id,
        )
        with reads.open() as db:
            graphs = load_paired_traffic(
                db,
                principal=self.principal,
                ticket=ticket,
                selected=selected,
                authorize=reads.authorize,
                clock=self.clock,
            )
        prepared = {
            account: PreparedRawRangeTrafficProjection(graph)
            for account, graph in graphs.items()
            if isinstance(graph, RawRangeTrafficGraphV1)
        }
        proofs = {p.source_fence.account: p for p in selected.reporting_proof.accounts}
        catalogs = {c.reference.account: c for c in selected.catalogs}
        traffic: list[TrafficWindowEvidenceV1] = []
        gaps: list[TrafficWindowGapV1] = []
        for item in selected.performance:
            account = item.target.account
            graph = graphs[account]
            window = item.document.requested_window
            if isinstance(graph, KnownTrafficGap):
                gaps.append(
                    TrafficWindowGapV1(
                        account=account,
                        target=item.target,
                        requested_window=window,
                        reason=graph.reason,
                        reporting_pin_digest=proofs[account].state_digest(),
                        explanation=graph.explanation,
                    )
                )
                continue
            doc = prepared[account].read(item.document.summary.campaign_id, window)
            fence = graph.source_fence
            traffic.append(
                TrafficWindowEvidenceV1(
                    target=item.target,
                    document=doc,
                    reference=EvidenceRef(
                        key=traffic_window_key(account.account_id, doc.campaign_id, window),
                        workspace_id=account.workspace_id,
                        kind="reported_metrics",
                        account=account,
                        document_schema=doc.schema_version,
                        document_digest=fingerprint(
                            "selected-traffic-window", doc.model_dump(mode="json")
                        ),
                        source_binding_digest=fence.source_binding_digest,
                        source_revision=fence.source_revision,
                        privacy_revision=fence.privacy_revision,
                        reporting_window=window,
                        observation_started_at=graph.receipt.completed_at,
                        observed_at=graph.receipt.completed_at,
                        expires_at=min(
                            utc(item.reference.expires_at),
                            utc(catalogs[account].reference.expires_at),
                        ),
                        coverage="partial" if doc.returned_days else "unavailable",
                        declared_scope="Raw reported traffic in the requested local-day window.",
                        reasons=("reported_rows_only", "attribution_unavailable"),
                        metric_basis=METRIC_BASIS,
                    ),
                )
            )
        result = SelectedPairedEvidenceV1(
            selected=selected,
            traffic_graphs=tuple(p.snapshot() for p in prepared.values()),
            traffic=tuple(traffic),
            traffic_gaps=tuple(gaps),
        )
        result.assert_ticket(ticket)
        with reads.open() as db:
            recheck_selected_paired_sources(
                db,
                principal=self.principal,
                ticket=ticket,
                bundle=result,
                authorize=reads.authorize,
                clock=self.clock,
            )
        return result
