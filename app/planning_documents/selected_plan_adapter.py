"""Standalone owned selected collection; no v4 registry or runtime activation."""

from collections.abc import Callable
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.campaign_performance.presence_report import MAX_COLLECTION_BYTES
from app.collectors import account_diagnostics
from app.collectors.native_diagnostics import AccountDiagnosticRequest
from app.customers.access import CustomerPrincipal
from app.customers.identity import IdentityProvider
from app.goals.progress import _read_goal_progress_locked
from app.planning_catalog.projection_v2 import project_v2
from app.planning_documents.common import MAX_EVIDENCE, fingerprint
from app.planning_documents.composer import targets
from app.planning_documents.context import EvidenceRef, ReportingWindow, TargetRef
from app.planning_documents.creative_inputs import validate_creative_policy
from app.planning_documents.evidence_local import changed, commerce_binding
from app.planning_documents.ports import (
    CatalogEvidence,
    CommerceEvidence,
    ContextEvidence,
    EvidenceGap,
    GenerationTicket,
    PlanningCompositionPolicy,
)
from app.planning_documents.read_context import PlanningReadContexts, snapshot
from app.planning_documents.selected_plan_bundle import (
    METRIC_BASIS,
    SelectedPlanEvidenceBundleV1,
    SelectedReportingGapV1,
    SelectedWindowEvidenceV1,
    selected_entry_key,
    supported,
)
from app.planning_documents.selected_plan_evidence import (
    PreparedSelectedPlanProjection,
    SelectedPlanCaptureV1,
)
from app.planning_documents.selected_plan_local import (
    capture_selected_proof,
    check_selected_start,
    recheck_selected_sources,
    requested_windows,
    saved_catalogs,
)
from app.planning_documents.selected_plan_reader import (
    OwnedSelectedPlanContext,
    load_selected_plan_graph,
)
from app.planning_documents.selected_policy_contract import assert_selected_composition_policy
from app.publication import customer_intents


class OwnedSelectedEvidenceReader:
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

    def collect(self, ticket: GenerationTicket) -> SelectedPlanEvidenceBundleV1:
        ticket = GenerationTicket.model_validate(ticket)
        try:
            contract = assert_selected_composition_policy(
                self.policy,
                ticket_policy_version=ticket.policy_version,
                ticket_policy_digest=ticket.policy_digest,
            )
            validate_creative_policy(
                ticket.inputs.creative, contract.policy_version, contract.generator_version
            )
        except ValueError:
            raise changed() from None
        if ticket.inputs.selected_reporting is None:
            raise changed()
        wid, actor = ticket.inputs.workspace_id, ticket.actor_id
        reads = PlanningReadContexts(self.sessions, self.principal, self.provider, wid, actor)
        with reads.open() as db:
            check_selected_start(
                db,
                principal=self.principal,
                ticket=ticket,
                authorize=reads.authorize,
                clock=self.clock,
            )
            fences = ticket.sources
            reporting_proof = capture_selected_proof(
                db,
                principal=self.principal,
                ticket=ticket,
                authorize=reads.authorize,
                clock=self.clock,
            )
            retained_catalogs = saved_catalogs(db, self.principal, ticket, self.clock)
        retained_by_account = {
            c.reference.account.account_id: c
            for c in retained_catalogs
            if c.reference.account is not None
        }
        catalogs: list[CatalogEvidence] = []
        metrics: list[SelectedWindowEvidenceV1] = []
        gaps: list[EvidenceGap] = []
        window = ticket.inputs.reporting_window
        for fence in fences:
            account = fence.account
            if account.account_id in retained_by_account:
                catalogs.append(retained_by_account[account.account_id])
                continue
            if window.ends_at_exclusive - window.starts_at > timedelta(days=366):
                gaps.append(
                    EvidenceGap(
                        account=account,
                        section="catalog",
                        reason="unsupported_reporting_window",
                        explanation="Native inventory supports at most366days.",
                    )
                )
                continue
            with reads.open() as db:
                reads.authorize(db, wid, actor)
                scope = customer_intents.account(db, wid, account.account_id)
            request = AccountDiagnosticRequest(
                expected_account=scope,
                workspace_id=wid,
                actor=actor,
                account_id=account.account_id,
                starts_at=window.starts_at,
                ends_at=window.ends_at_exclusive,
            )
            # No caller transaction survives into any native provider IO.
            with account_diagnostics.get_native_account_diagnostic_service(
                reads.open, reads.authorize, account.platform, self.clock
            ) as service:
                native, metadata = service.read_catalog(request, self.clock())
            catalog = project_v2(native, metadata)
            complete = all(
                c.status == "complete" for c in catalog.native_observation.coverage
            ) and all(c.status == "complete" for c in metadata.coverage)
            ref = EvidenceRef(
                key=f"catalog:{account.account_id}",
                workspace_id=wid,
                kind="native_catalog",
                account=account,
                document_schema=catalog.schema_version,
                document_digest=catalog.composite_digest,
                source_binding_digest=metadata.source_binding_digest,
                source_revision=fence.source_revision,
                privacy_revision=ticket.privacy_revision,
                reporting_window=window,
                observation_started_at=min(
                    native.observation_started_at, metadata.observation_started_at
                ),
                observed_at=max(native.observed_at, metadata.observed_at),
                expires_at=catalog.expires_at,
                coverage="complete_in_declared_scope" if complete else "partial",
                declared_scope="Native inventory with separately declared provider coverage.",
                reasons=() if complete else ("limited_native_coverage",),
                metric_basis="Native settings, not performance or spending authority.",
            )
            catalogs.append(CatalogEvidence(reference=ref, catalog=catalog))
        if not catalogs:
            # Context and derived observations need an actual validity boundary.
            raise changed()
        deadline = min(c.reference.expires_at for c in catalogs)
        windows = requested_windows(ticket)
        by_account = {c.reference.account: c for c in catalogs}
        pins = {p.source_fence.account: p for p in reporting_proof.accounts}
        source_by_account = {f.account: f for f in fences}
        required = sum(
            max(1, sum(t.kind == "campaign" for t in targets(c))) * len(windows) for c in catalogs
        ) + len(gaps) * len(windows)
        if required > MAX_EVIDENCE:
            raise changed()
        window_gaps: list[SelectedReportingGapV1] = []
        captures: list[SelectedPlanCaptureV1] = []
        reporting_bytes = 0
        for account in ticket.inputs.accounts:
            cat = by_account.get(account)
            graph = None
            pin = pins[account].capture_pin
            if pin is not None:
                with reads.open() as db:
                    check_selected_start(
                        db,
                        principal=self.principal,
                        ticket=ticket,
                        authorize=reads.authorize,
                        clock=self.clock,
                    )
                    if cat is None:
                        graph = load_selected_plan_graph(
                            db,
                            account=account,
                            expected_source=source_by_account[account],
                            capture_id=pin.capture_id,
                        )
                    else:
                        with OwnedSelectedPlanContext(
                            db,
                            principal=self.principal,
                            account=account,
                            expected_source=source_by_account[account],
                            capture_id=pin.capture_id,
                            catalog=cat,
                            authorize=reads.authorize,
                            clock=self.clock,
                        ) as selected:
                            graph = selected.snapshot()
                    if graph.pin() != pin:
                        raise changed()
                    check_selected_start(
                        db,
                        principal=self.principal,
                        ticket=ticket,
                        authorize=reads.authorize,
                        clock=self.clock,
                    )
                reporting_bytes += len(graph.model_dump_json().encode())
                if reporting_bytes > MAX_COLLECTION_BYTES:
                    raise changed()
                captures.append(graph)
            campaign_targets = (
                [] if cat is None else [t for t in targets(cat) if t.kind == "campaign"]
            )
            slots: list[TargetRef | None] = list(campaign_targets) or [None]
            projection = PreparedSelectedPlanProjection(graph) if graph is not None else None
            mapping = (
                {}
                if graph is None
                else {c.native_campaign_id: c.campaign_id for c in graph.campaigns}
            )
            recognized = graph is not None and supported(graph)
            for target in slots:
                reason = None
                if target is None:
                    reason = "catalog_unavailable" if cat is None else "no_catalog_campaigns"
                elif (account.platform != "google_ads" and graph is None) or (
                    graph is not None and not recognized
                ):
                    reason = "unsupported_selected_mapping"
                elif graph is None:
                    reason = "selected_capture_not_requested"
                elif target.provider_reference.entity_id not in mapping:
                    reason = "campaign_outside_captured_mapping"
                if reason is not None:
                    for requested in windows:
                        window_gaps.append(
                            SelectedReportingGapV1(
                                account=account,
                                target=target,
                                requested_window=requested,
                                reason=reason,
                                reporting_pin_digest=pins[account].state_digest(),
                                explanation="Selected reporting unavailable: " + reason,
                            )
                        )
                    continue
                assert (
                    graph is not None
                    and target is not None
                    and pin is not None
                    and projection is not None
                )
                for requested in windows:
                    result = projection.read(
                        campaign_id=mapping[target.provider_reference.entity_id],
                        requested_window=requested,
                    )
                    observed = (
                        result.summary.conversions.present_days
                        or result.summary.value_micros.present_days
                    )
                    metrics.append(
                        SelectedWindowEvidenceV1(
                            target=target,
                            document=result,
                            reference=EvidenceRef(
                                key=selected_entry_key(
                                    account.account_id, result.summary.campaign_id, requested
                                ),
                                workspace_id=wid,
                                kind="reported_metrics",
                                account=account,
                                document_schema=result.schema_version,
                                document_digest=fingerprint(
                                    "selected-plan-window", result.model_dump(mode="json")
                                ),
                                source_binding_digest=pin.source_fence.source_binding_digest,
                                source_revision=pin.source_fence.source_revision,
                                privacy_revision=ticket.privacy_revision,
                                reporting_window=requested,
                                observation_started_at=graph.capture.request.started_at,
                                observed_at=graph.capture.completed_at,
                                expires_at=deadline,
                                coverage="partial" if observed else "unavailable",
                                declared_scope="Selected reporting in the requested window.",
                                reasons=("reported_rows_only", "attribution_unavailable"),
                                metric_basis=METRIC_BASIS,
                            ),
                        )
                    )
        with reads.open() as db:
            reads.authorize(db, wid, actor)
            doc_goal = _read_goal_progress_locked(
                db,
                self.principal,
                wid,
                ticket.inputs.goal.goal_id,
                ticket.inputs.goal.revision,
                clock=self.clock,
            )
            # No catch: ambiguous source/authority failures abort the generation.
            if (
                doc_goal.coverage is None
                and doc_goal.status != "not_started"
                and not (
                    doc_goal.source_revision is not None
                    and doc_goal.reasons in (("missing_history",), ("no_closed_days",))
                )
            ):
                # Missing coverage can conceal a disconnected/changed source.
                # Fail closed; no generic progress error is a missing-data gap.
                raise changed()
            else:
                coverage = doc_goal.coverage
                status = (
                    "unavailable"
                    if doc_goal.status != "available_as_of"
                    else (
                        "complete_in_declared_scope"
                        if coverage and coverage.extent == "full_window_as_of"
                        else "partial"
                    )
                )
                reasons = (
                    doc_goal.reasons
                    if doc_goal.status != "available_as_of"
                    else (("partial_goal_window",) if status == "partial" else ())
                )
                commerce = CommerceEvidence(
                    document=doc_goal,
                    reference=EvidenceRef(
                        key="commerce:goal",
                        workspace_id=wid,
                        kind="shopify_measurement",
                        account=None,
                        document_schema=doc_goal.schema_version,
                        document_digest=fingerprint(
                            "goal-progress", doc_goal.model_dump(mode="json")
                        ),
                        source_binding_digest=commerce_binding(doc_goal, ticket.privacy_revision),
                        source_revision=str(doc_goal.source_revision)
                        if doc_goal.source_revision is not None
                        else "unavailable",
                        privacy_revision=ticket.privacy_revision,
                        reporting_window=ReportingWindow(
                            starts_at=coverage.starts_at,
                            ends_at_exclusive=coverage.ends_at_exclusive,
                        )
                        if coverage
                        else None,
                        observation_started_at=doc_goal.as_of,
                        observed_at=doc_goal.as_of,
                        expires_at=deadline,
                        coverage=status,
                        declared_scope="Confirmed goal closed store-local day prefix.",
                        reasons=reasons,
                        metric_basis="Shopify net merchandise sales, not advertising attribution.",
                    ),
                )
        now = self.clock()
        context = tuple(
            ContextEvidence(
                document=document,
                reference=EvidenceRef(
                    key=f"context:{kind}",
                    workspace_id=wid,
                    kind=kind,
                    account=None,
                    document_schema="inlet.plan-input.v1"
                    if kind == "customer_context"
                    else "inlet.planning-policy.v1",
                    document_digest=document.digest(),
                    source_binding_digest=document.digest(),
                    source_revision=str(ticket.inputs.revision)
                    if kind == "customer_context"
                    else self.policy.version,
                    privacy_revision=ticket.privacy_revision,
                    reporting_window=None,
                    observation_started_at=now,
                    observed_at=now,
                    expires_at=deadline,
                    coverage="complete_in_declared_scope",
                    declared_scope="Exact server-owned planning context.",
                    reasons=(),
                    metric_basis="Customer input or composition policy, not measured performance.",
                ),
            )
            for kind, document in (
                ("customer_context", ticket.inputs),
                ("planning_policy", self.policy),
            )
        )
        bundle = SelectedPlanEvidenceBundleV1(
            operation_id=ticket.operation_id,
            input_digest=ticket.inputs.digest(),
            privacy_revision=ticket.privacy_revision,
            collected_at=now,
            catalogs=tuple(catalogs),
            performance=tuple(metrics),
            commerce=commerce,
            context=context,
            gaps=tuple(gaps),
            reporting_proof=reporting_proof,
            selected_captures=tuple(captures),
            window_gaps=tuple(window_gaps),
        )
        bundle.assert_ticket(ticket)
        with reads.open() as db:
            recheck_selected_sources(
                db,
                principal=self.principal,
                ticket=ticket,
                bundle=bundle,
                authorize=reads.authorize,
                clock=self.clock,
            )
        return bundle
