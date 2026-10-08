"""Owned v3 collection, explicitly invoked only; no runtime policy activation."""

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
from app.planning_documents.context import EvidenceRef, ReportingWindow
from app.planning_documents.evidence_local import changed, commerce_binding
from app.planning_documents.ports import (
    CatalogEvidence,
    CommerceEvidence,
    ContextEvidence,
    EvidenceGap,
    GenerationTicket,
    PlanningCompositionPolicy,
    ReportingPresencePin,
)
from app.planning_documents.read_context import PlanningReadContexts, snapshot
from app.planning_documents.retained_sources import capture_reporting_presence_pin
from app.planning_documents.window_evidence import (
    KnownWindowGap,
    WindowEvidenceBundleV1,
    WindowPerformanceEvidenceV1,
    WindowReportingGapV1,
    reporting_entry_key,
)
from app.planning_documents.window_local import (
    check_start,
    recheck_window_sources,
    requested_windows,
    saved_catalogs,
)
from app.planning_documents.window_reader import prepare_owned_window_context
from app.publication import customer_intents


class OwnedWindowEvidenceReader:
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

    def collect(self, ticket: GenerationTicket) -> WindowEvidenceBundleV1:
        ticket = GenerationTicket.model_validate(ticket)
        policy = PlanningCompositionPolicy.model_validate(self.policy)
        if (ticket.policy_version, ticket.policy_digest) != (policy.version, policy.digest()):
            raise changed()
        wid, actor = ticket.inputs.workspace_id, ticket.actor_id
        reads = PlanningReadContexts(self.sessions, self.principal, self.provider, wid, actor)
        with reads.open() as db:
            check_start(
                db,
                principal=self.principal,
                ticket=ticket,
                authorize=reads.authorize,
                clock=self.clock,
            )
            fences = ticket.sources
            reporting_pins = tuple(
                ReportingPresencePin(
                    account=account,
                    document_digest=capture_reporting_presence_pin(
                        db, self.principal, account, ticket.privacy_revision
                    ),
                )
                for account in ticket.inputs.accounts
            )
            retained_catalogs = saved_catalogs(db, self.principal, ticket, self.clock)
        retained_by_account = {
            c.reference.account.account_id: c
            for c in retained_catalogs
            if c.reference.account is not None
        }
        catalogs: list[CatalogEvidence] = []
        metrics: list[WindowPerformanceEvidenceV1] = []
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
        pins = {p.account: p for p in reporting_pins}
        source_by_account = {f.account: f for f in fences}
        required = sum(
            max(1, sum(t.kind == "campaign" for t in targets(c))) * len(windows) for c in catalogs
        ) + len(gaps) * len(windows)
        if required > MAX_EVIDENCE:
            raise changed()
        window_gaps: list[WindowReportingGapV1] = []
        reporting_bytes = 0
        for account in ticket.inputs.accounts:
            cat = by_account.get(account)
            campaign_targets = (
                [] if cat is None else [t for t in targets(cat) if t.kind == "campaign"]
            )
            if not campaign_targets:
                for requested in windows:
                    window_gaps.append(
                        WindowReportingGapV1(
                            account=account,
                            target=None,
                            requested_window=requested,
                            reason="catalog_unavailable" if cat is None else "no_catalog_campaigns",
                            reporting_pin_digest=pins[account].document_digest,
                            explanation="Catalog collection unavailable when prepared."
                            if cat is None
                            else "No campaign targets in the collected catalog's declared scope.",
                        )
                    )
                continue
            assert cat is not None
            with (
                reads.open() as db,
                prepare_owned_window_context(
                    db,
                    principal=self.principal,
                    account=account,
                    expected_source=source_by_account[account],
                    expected_reporting_pin=pins[account],
                    catalog=cat,
                    authorize=reads.authorize,
                    clock=self.clock,
                ) as context_reader,
            ):
                for target in campaign_targets:
                    for requested in windows:
                        result = context_reader.read(target, requested)
                        if isinstance(result, KnownWindowGap):
                            window_gaps.append(
                                WindowReportingGapV1(
                                    account=account,
                                    target=target,
                                    requested_window=requested,
                                    reason=result.reason,
                                    reporting_pin_digest=pins[account].document_digest,
                                    explanation="Requested reporting unavailable: " + result.reason,
                                )
                            )
                            continue
                        reporting_bytes += len(result.model_dump_json().encode("utf-8"))
                        if reporting_bytes > MAX_COLLECTION_BYTES:
                            raise changed()
                        original = result.original
                        selected = (
                            original.presence.selected_event.provenance == "explicit_selected"
                            and result.summary.selected_conversions.value is not None
                        )
                        available = bool(result.selected_facts)
                        reasons: tuple[str, ...] = (
                            ("reported_rows_only", "attribution_unavailable")
                            if selected
                            else (
                                "reported_rows_only" if available else "no_reported_rows",
                                "goal_conversion_unqualified",
                                "attribution_unavailable",
                            )
                        )
                        metrics.append(
                            WindowPerformanceEvidenceV1(
                                target=target,
                                document=result,
                                completeness="reported_rows_only" if available else "unavailable",
                                conversion_qualification="reported_only"
                                if selected
                                else "unavailable",
                                reasons=reasons,
                                reference=EvidenceRef(
                                    key=reporting_entry_key(
                                        account.account_id, original.campaign_id, requested
                                    ),
                                    workspace_id=wid,
                                    kind="reported_metrics",
                                    account=account,
                                    document_schema=result.schema_version,
                                    document_digest=fingerprint(
                                        "requested-window-performance",
                                        result.model_dump(mode="json"),
                                    ),
                                    source_binding_digest=original.manifest_digest,
                                    source_revision=str(original.generation),
                                    privacy_revision=ticket.privacy_revision,
                                    reporting_window=requested,
                                    observation_started_at=original.completed_at,
                                    observed_at=original.completed_at,
                                    expires_at=deadline,
                                    coverage="partial" if available else "unavailable",
                                    declared_scope=(
                                        "Imported days projected into the requested window."
                                    ),
                                    reasons=reasons,
                                    metric_basis=(
                                        "Provider reported, not cross-platform comparable."
                                    ),
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
        bundle = WindowEvidenceBundleV1(
            operation_id=ticket.operation_id,
            input_digest=ticket.inputs.digest(),
            privacy_revision=ticket.privacy_revision,
            collected_at=now,
            catalogs=tuple(catalogs),
            performance=tuple(metrics),
            commerce=commerce,
            context=context,
            gaps=tuple(gaps),
            reporting_pins=reporting_pins,
            window_gaps=tuple(window_gaps),
        )
        bundle.assert_ticket(ticket)
        with reads.open() as db:
            recheck_window_sources(
                db,
                principal=self.principal,
                ticket=ticket,
                bundle=bundle,
                authorize=reads.authorize,
                clock=self.clock,
            )
        return bundle
