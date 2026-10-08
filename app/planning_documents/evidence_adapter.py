"""Server-owned read composition; no writes, execution anchors or inferred metrics."""

from collections.abc import Callable
from datetime import datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ads.models import Campaign
from app.campaign_performance import service as performance
from app.campaign_performance.contracts import CampaignPerformanceV1
from app.campaign_performance.models import CurrentPerformance, PerformanceCompletion
from app.collectors import account_diagnostics
from app.collectors.native_diagnostics import AccountDiagnosticRequest
from app.customers.access import CustomerPrincipal
from app.customers.identity import IdentityProvider
from app.goals.progress import boundary, read_goal_progress
from app.planning_catalog.projection_v2 import project_v2
from app.planning_documents.common import MAX_EVIDENCE, fingerprint
from app.planning_documents.context import EvidenceRef, ReportingWindow, TargetRef
from app.planning_documents.evidence_local import (
    changed,
    check_goal,
    commerce_binding,
    ordinary_meta,
    recheck_local_sources,
    resolve_source_fences,
)
from app.planning_documents.ports import (
    CatalogEvidence,
    CommerceEvidence,
    ContextEvidence,
    EvidenceBundle,
    EvidenceGap,
    GenerationTicket,
    PerformanceEvidence,
    PlanningCompositionPolicy,
)
from app.publication import customer_intents
from app.publication.customer_authority import bind_authority


class OwnedPlanningEvidenceReader:
    def __init__(
        self,
        sessions: Callable[[], Session],
        *,
        principal: CustomerPrincipal,
        provider: IdentityProvider,
        policy: PlanningCompositionPolicy,
        clock: Callable[[], datetime],
    ) -> None:
        self.sessions, self.principal, self.provider = sessions, principal, provider
        self.policy, self.clock = policy, clock
        self.authorize = bind_authority(principal, provider)

    def collect(self, ticket: GenerationTicket) -> EvidenceBundle:
        ticket = GenerationTicket.model_validate(ticket)
        wid, actor = ticket.inputs.workspace_id, ticket.actor_id
        if (actor, ticket.session_digest) != (
            self.principal.user.id,
            self.principal.session.digest,
        ):
            raise changed()
        if (ticket.policy_version, ticket.policy_digest) != (
            self.policy.version,
            self.policy.digest(),
        ):
            raise changed()
        with self.sessions() as db:
            self.authorize(db, wid, actor)
            check_goal(db, ticket)
            fences = resolve_source_fences(
                db, principal=self.principal, accounts=ticket.inputs.accounts, now=self.clock()
            )
            if {f.account.account_id: f for f in fences} != {
                f.account.account_id: f for f in ticket.sources
            }:
                raise changed()
        catalogs: list[CatalogEvidence] = []
        metrics: list[PerformanceEvidence] = []
        gaps: list[EvidenceGap] = []
        window = ticket.inputs.reporting_window
        for fence in fences:
            account = fence.account
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
            with self.sessions() as db:
                self.authorize(db, wid, actor)
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
                self.sessions, self.authorize, account.platform, self.clock
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
        for catalog_evidence in catalogs:
            assert catalog_evidence.reference.account is not None
            account = catalog_evidence.reference.account
            with self.sessions() as db:
                self.authorize(db, wid, actor)
                # Source/ownership is positively checked before any explicit no-data gap.
                resolve_source_fences(
                    db, principal=self.principal, accounts=(account,), now=self.clock()
                )
                current = db.get(CurrentPerformance, account.account_id, populate_existing=True)
                if current is None:
                    gaps.append(
                        EvidenceGap(
                            account=account,
                            section="reported_metrics",
                            reason="current_reporting_unavailable",
                            explanation="No current reporting completion exists.",
                        )
                    )
                    continue
                completion = db.get(
                    PerformanceCompletion, current.completion_id, populate_existing=True
                )
                if (
                    completion is None
                    or current.workspace_id != wid
                    or completion.workspace_id != wid
                ):
                    raise changed()
                # Establish completion integrity before classifying a known window gap.
                witness = db.scalar(
                    select(Campaign)
                    .where(
                        Campaign.account_id == account.account_id,
                        Campaign.platform == account.platform,
                    )
                    .order_by(Campaign.id)
                    .limit(1)
                )
                if witness is None:
                    raise changed()
                if account.platform == "meta_ads":
                    ordinary_meta(db, wid, account.account_id, completion)
                performance.read_current(
                    db,
                    wid,
                    actor,
                    account.account_id,
                    witness.id,
                    current.completion_id,
                    self.authorize,
                )
                actual_window = ReportingWindow(
                    starts_at=boundary(completion.starts_on, ZoneInfo(completion.time_zone)),
                    ends_at_exclusive=boundary(
                        completion.ends_on + timedelta(days=1), ZoneInfo(completion.time_zone)
                    ),
                )
                if actual_window not in (window, ticket.inputs.comparison_window):
                    gaps.append(
                        EvidenceGap(
                            account=account,
                            section="reported_metrics",
                            reason="reporting_window_mismatch",
                            explanation="Current reporting does not cover a requested window.",
                        )
                    )
                    continue
                if account.platform == "meta_ads":
                    ordinary_meta(db, wid, account.account_id, completion)
                for target in catalog_evidence.catalog.targets:
                    if target.entity.kind != "campaign":
                        continue
                    campaign = db.scalar(
                        select(Campaign).where(
                            Campaign.account_id == account.account_id,
                            Campaign.platform == account.platform,
                            Campaign.external_campaign_id == target.entity.reference.entity_id,
                        )
                    )
                    if campaign is None:
                        gaps.append(
                            EvidenceGap(
                                account=account,
                                section="reported_metrics",
                                reason="campaign_reporting_unavailable",
                                explanation="A native campaign has no imported campaign mapping.",
                            )
                        )
                        continue
                    doc = performance.read_current(
                        db,
                        wid,
                        actor,
                        account.account_id,
                        campaign.id,
                        current.completion_id,
                        self.authorize,
                    )
                    target_ref = TargetRef(
                        account=account,
                        provider_reference=target.entity.reference,
                        canonical_entity_key=target.canonical_entity_key,
                        selection_key=target.selection_key,
                        catalog_evidence_key=catalog_evidence.reference.key,
                        kind=target.entity.kind,
                        display_name=target.entity.name,
                        budget_owner_key=target.budget_owner_key,
                    )
                    positive = (
                        isinstance(doc, CampaignPerformanceV1)
                        and doc.selected_event is not None
                        and doc.conversions is not None
                        and Decimal(doc.conversions) > 0
                    )
                    reasons: tuple[str, ...] = (
                        ("reported_rows_only", "attribution_unavailable")
                        if positive
                        else (
                            "reported_rows_only"
                            if doc.campaign_rows_available
                            else "no_reported_rows",
                            "goal_conversion_unqualified",
                            "attribution_unavailable",
                        )
                    )
                    ref = EvidenceRef(
                        key=f"performance:{account.account_id}:{campaign.id}",
                        workspace_id=wid,
                        kind="reported_metrics",
                        account=account,
                        document_schema=doc.schema_version,
                        document_digest=fingerprint(
                            "campaign-performance", doc.model_dump(mode="json")
                        ),
                        source_binding_digest=doc.manifest_digest,
                        source_revision=str(doc.generation),
                        privacy_revision=ticket.privacy_revision,
                        reporting_window=actual_window,
                        observation_started_at=doc.completed_at,
                        observed_at=doc.completed_at,
                        expires_at=deadline,
                        coverage="partial" if doc.campaign_rows_available else "unavailable",
                        declared_scope="Reported rows; missing fields are not observed zero.",
                        reasons=reasons,
                        metric_basis="Provider reported, not cross-platform comparable.",
                    )
                    metrics.append(
                        PerformanceEvidence(
                            reference=ref,
                            target=target_ref,
                            document=doc,
                            native_campaign_id=target.entity.reference.entity_id,
                            completeness="reported_rows_only"
                            if doc.campaign_rows_available
                            else "unavailable",
                            conversion_qualification="reported_only" if positive else "unavailable",
                            reasons=reasons,
                        )
                    )
                    if len(metrics) > MAX_EVIDENCE:
                        raise changed()
                if ticket.inputs.comparison_window is not None:
                    gaps.append(
                        EvidenceGap(
                            account=account,
                            section="reported_metrics",
                            reason="only_current_reporting_window",
                            explanation="Only one current imported window is available.",
                        )
                    )
        with self.sessions() as db:
            self.authorize(db, wid, actor)
            doc_goal = read_goal_progress(
                db,
                self.principal,
                self.provider,
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
        bundle = EvidenceBundle(
            operation_id=ticket.operation_id,
            input_digest=ticket.inputs.digest(),
            privacy_revision=ticket.privacy_revision,
            collected_at=now,
            catalogs=tuple(catalogs),
            performance=tuple(metrics),
            commerce=commerce,
            context=context,
            gaps=tuple(gaps),
        )
        with self.sessions() as db:
            self.authorize(db, wid, actor)
            recheck_local_sources(
                db, principal=self.principal, ticket=ticket, bundle=bundle, now=self.clock()
            )
        return bundle
