"""Pure selected/traffic v4 composition; no registration or spending authority."""

from datetime import UTC, datetime
from decimal import Context, Decimal, localcontext
from typing import Literal

from pydantic import ValidationError

from app.campaign_performance.selected_contracts import CustomerEventSelectionV1
from app.planning_documents.actions import Allocation, BudgetScenario, CreativeBrief, ManualAction
from app.planning_documents.common import MAX_ACTIONS, MAX_BRIEFS, MAX_EVIDENCE, MAX_SCENARIOS
from app.planning_documents.composer import PLATFORMS, PlanCompositionUnavailable, location, targets
from app.planning_documents.context import (
    AccountRef,
    AccountTarget,
    PlanInputRevision,
    ReportingWindow,
    TargetRef,
)
from app.planning_documents.creative_composition import (
    CreativeCompositionReferencesV1,
    compose_creative_proposals,
)
from app.planning_documents.creative_image_collection import CollectedCreativeBasisV1
from app.planning_documents.creative_inputs import validate_creative_policy
from app.planning_documents.creative_plan_bundle import assert_creative_collection_time
from app.planning_documents.creative_plan_document import creative_basis_reference
from app.planning_documents.creative_retained_proof import creative_proof_from_collection
from app.planning_documents.documents import PlanVersion
from app.planning_documents.ports import GenerationTicket, PlanningCompositionPolicy
from app.planning_documents.selected_inputs import (
    SELECTED_GENERATOR_VERSION,
    SELECTED_POLICY_VERSION,
)
from app.planning_documents.selected_paired_evidence import (
    SelectedPairedEvidenceV1,
    TrafficWindowEvidenceV1,
)
from app.planning_documents.selected_plan_bundle import (
    SelectedPlanEvidenceBundleV1,
    SelectedWindowEvidenceV1,
)
from app.planning_documents.selected_policy_contract import assert_selected_composition_policy


def bounded_text(value: str) -> str:
    if not 1 <= len(value) <= 2000:
        raise PlanCompositionUnavailable("complete descriptive text exceeds document capacity")
    return value


def observed_child_steps(
    target: TargetRef | AccountTarget,
    observed: tuple[TargetRef, ...],
    excluded_keys: tuple[str, ...],
) -> tuple[str, ...]:
    """Location-only projection from an already validated owned catalog, never metrics."""
    if not isinstance(target, TargetRef) or target.kind != "campaign":
        return ()
    children = sorted(
        (
            child
            for child in observed
            if child.kind in {"adgroup", "adset"}
            and child.account == target.account
            and child.catalog_evidence_key == target.catalog_evidence_key
            and child.provider_reference.platform == target.provider_reference.platform
            and child.provider_reference.advertiser_id == target.provider_reference.advertiser_id
            and child.provider_reference.parent_campaign_id == target.provider_reference.entity_id
            and child.canonical_entity_key not in excluded_keys
        ),
        key=lambda child: child.canonical_entity_key,
    )
    if len(children) > 15 or len({child.canonical_entity_key for child in children}) != len(
        children
    ):
        raise PlanCompositionUnavailable(
            "complete observed child locations exceed document capacity"
        )
    return tuple(
        bounded_text(
            f"Observed catalog location only: {location(child)}. "
            "Campaign metrics are not child metrics; no child change is proposed."
        )
        for child in children
    )


def instants(window: ReportingWindow) -> tuple[datetime, datetime]:
    return window.starts_at.astimezone(UTC), window.ends_at_exclusive.astimezone(UTC)


GapGroup = tuple[AccountRef, tuple[datetime, datetime], str]


def grouped_window_gaps(evidence: SelectedPlanEvidenceBundleV1) -> tuple[str, ...]:
    """Lossless deterministic grouping; caller first validates exact ticket slot set."""
    groups: dict[GapGroup, list[str | None]] = {}
    original: set[tuple[GapGroup, str | None]] = set()
    for gap in evidence.window_gaps:
        key: GapGroup = (gap.account, instants(gap.requested_window), gap.reason)
        native_id = gap.target.provider_reference.entity_id if gap.target else None
        groups.setdefault(key, []).append(native_id)
        original.add((key, native_id))
    expanded: set[tuple[GapGroup, str | None]] = set()
    rendered = []
    for key in sorted(
        groups, key=lambda k: (k[0].workspace_id, k[0].account_id, k[0].connection_id, k[1], k[2])
    ):
        account, window, reason = key
        prefix = (
            f"{PLATFORMS[account.platform]} account {account.account_id}, "
            f"connection {account.connection_id}; UTC requested window "
            f"[{window[0].isoformat()}, {window[1].isoformat()}): {reason}. "
        )
        if reason == "catalog_unavailable":
            prefix += "Catalog collection was unavailable when this plan was prepared; "
            prefix += "current provider availability is not assessed. "
        values = groups[key]
        if values == [None]:
            rendered.append(bounded_text(prefix + "Catalog scope."))
            expanded.add((key, None))
            continue
        if None in values or len(values) != len(set(values)):
            raise PlanCompositionUnavailable("ambiguous gap grouping")
        chunk: list[str] = []
        for ident in sorted(v for v in values if v is not None):
            candidate = prefix + "Campaign IDs: " + ", ".join(chunk + [ident]) + "."
            if len(candidate) > 2000:
                if not chunk:
                    raise PlanCompositionUnavailable("gap identity exceeds text capacity")
                rendered.append(bounded_text(prefix + "Campaign IDs: " + ", ".join(chunk) + "."))
                expanded.update((key, value) for value in chunk)
                chunk = []
            chunk.append(ident)
        if chunk:
            rendered.append(bounded_text(prefix + "Campaign IDs: " + ", ".join(chunk) + "."))
            expanded.update((key, value) for value in chunk)
    if expanded != original or sum(len(values) for values in groups.values()) != len(original):
        raise PlanCompositionUnavailable("gap grouping lost an exact identity")
    return tuple(rendered)


def observation_text(
    label: str,
    item: SelectedWindowEvidenceV1,
    traffic: TrafficWindowEvidenceV1 | None,
    choice: CustomerEventSelectionV1,
) -> str:
    doc, summary = item.document, item.document.summary
    scope = doc.pin.aggregate.scope
    selected = summary.conversions
    count = "unavailable" if selected.value is None else format(selected.value, "f")
    text = (
        f"{label} {summary.starts_on.isoformat()} through "
        f"{summary.ends_on.isoformat()} ({scope.time_zone}, {scope.currency}): "
        f"selected event resource {choice.native_event_id}; "
        f"metric family {choice.metric_family}; "
        f"selected count {count} ({selected.coverage}; "
        f"{selected.present_days}/{summary.requested_days} days present); "
        f"{summary.missing_calendar_days} selected calendar days absent. "
    )
    if traffic is None:
        text += "Clicks and spend unavailable: no qualified raw traffic provenance. "
    else:
        raw = traffic.document
        clicks = "unavailable" if raw.clicks.value is None else str(raw.clicks.value)
        spend = (
            "unavailable"
            if raw.spend_micros.value is None
            else format(Decimal(raw.spend_micros.value) / Decimal(1_000_000), "f")
        )
        text += (
            f"{clicks} observed clicks ({raw.clicks.coverage}); "
            f"{spend} {scope.currency} observed spend ({raw.spend_micros.coverage}). "
        )
        if raw.spend_micros.coverage == "partial":
            text += "Spend is an observed subtotal, not the full requested-window total. "
        text += f"{raw.missing_calendar_days} traffic calendar days absent. "
    if summary.zero_for_requested_window:
        text += "Observed zero selected conversions across this complete requested window. "
        if (
            traffic is not None
            and traffic.document.spend_micros.value is not None
            and traffic.document.spend_micros.value > 0
        ):
            text += (
                "Positive reported spend was observed in the same window; "
                "investigate the selected event and reporting settings. "
            )
    elif selected.value is None or selected.coverage != "observed_requested_days":
        text += "Missing or partial selected observations are not full-window zero. "
    return text


def requested_summary(
    target: TargetRef | AccountTarget,
    paired: SelectedPairedEvidenceV1,
    inputs: PlanInputRevision,
) -> tuple[Literal["investigate", "retain"], str, tuple[str, ...]]:
    evidence = paired.selected
    if not isinstance(target, TargetRef):
        return "investigate", "No included native campaign is available for campaign planning.", ()
    parts = []
    keys = []
    kind: Literal["investigate", "retain"] = "investigate"
    for label, window in (
        ("Primary", inputs.reporting_window),
        ("Comparison", inputs.comparison_window),
    ):
        if window is None:
            continue
        performance = next(
            (
                p
                for p in evidence.performance
                if p.target == target and instants(p.document.requested_window) == instants(window)
            ),
            None,
        )
        if performance is not None:
            traffic = next(
                (
                    p
                    for p in paired.traffic
                    if p.target == target
                    and instants(p.document.requested_window) == instants(window)
                ),
                None,
            )
            choice = next(
                g.capture.request.selection
                for g in evidence.selected_captures
                if g.source_fence.account == target.account
            )
            parts.append(observation_text(label, performance, traffic, choice))
            if traffic is not None:
                keys.append(traffic.reference.key)
            keys.append(performance.reference.key)
            value = performance.document.summary.conversions.value
            if label == "Primary" and value is not None:
                with localcontext(Context(prec=50)):
                    if Decimal(value) > 0:
                        kind = "retain"
        else:
            gap = next(
                (
                    g
                    for g in evidence.window_gaps
                    if g.target == target and instants(g.requested_window) == instants(window)
                ),
                None,
            )
            if gap is None:
                raise PlanCompositionUnavailable("campaign window slot missing")
            start, end = instants(window)
            parts.append(
                f"{label} UTC requested window [{start.isoformat()}, {end.isoformat()}): "
                f"observations unavailable ({gap.reason}). "
            )
    parts.append(
        "Provider-reported observations only; periods may differ in length. "
        "Attribution and causal sales effects are unavailable; no normalized improvement "
        "or budget transfer is assessed."
    )
    return kind, bounded_text("".join(parts)), tuple(keys)


class SelectedPlanComposer:
    def compose(
        self,
        *,
        ticket: GenerationTicket,
        evidence: SelectedPairedEvidenceV1,
        policy: PlanningCompositionPolicy,
        generated_at: datetime,
    ) -> PlanVersion:
        ticket = GenerationTicket.model_validate(ticket)
        evidence = SelectedPairedEvidenceV1.model_validate(evidence)
        policy = PlanningCompositionPolicy.model_validate(policy)
        try:
            validate_creative_policy(
                ticket.inputs.creative, policy.version, policy.generator_version
            )
        except ValueError as error:
            raise PlanCompositionUnavailable(str(error)) from error
        canonical = PlanningCompositionPolicy(
            version=SELECTED_POLICY_VERSION, generator_version=SELECTED_GENERATOR_VERSION
        )
        if policy != canonical or (policy.version, policy.digest()) != (
            ticket.policy_version,
            ticket.policy_digest,
        ):
            raise PlanCompositionUnavailable("exact selected policy and genuine ticket required")
        evidence.assert_ticket(ticket)
        if generated_at.tzinfo is None or generated_at.utcoffset() is None:
            raise PlanCompositionUnavailable("aware generation time required")
        try:
            with localcontext(Context(prec=50)):
                return self._compose(ticket, evidence, policy, generated_at.astimezone(UTC))
        except ValidationError as error:
            raise PlanCompositionUnavailable(
                "complete plan violates document bounds or invariants"
            ) from error

    def _compose(
        self,
        ticket: GenerationTicket,
        paired: SelectedPairedEvidenceV1,
        policy: PlanningCompositionPolicy,
        generated_at: datetime,
        *,
        creative: CollectedCreativeBasisV1 | None = None,
    ) -> PlanVersion:
        if creative is not None:
            creative = CollectedCreativeBasisV1.model_validate(creative)
            contract = assert_selected_composition_policy(
                policy,
                ticket_policy_version=ticket.policy_version,
                ticket_policy_digest=ticket.policy_digest,
            )
            if not contract.requires_creative:
                raise PlanCompositionUnavailable("creative collection requires canonical v5")
            paired.assert_ticket(ticket)
            assert_creative_collection_time(creative, ticket, generated_at)
        evidence = paired.selected
        inputs = ticket.inputs
        version, parent_digest = ticket.expected_version + 1, ticket.expected_parent_digest
        generated_by = ticket.actor_id
        if (
            evidence.input_digest != inputs.digest()
            or evidence.collected_at.astimezone(UTC) > generated_at
        ):
            raise PlanCompositionUnavailable("composition input/time mismatch")
        contexts = {entry.reference.kind: entry for entry in evidence.context}
        if (
            set(contexts) != {"customer_context", "planning_policy"}
            or contexts["customer_context"].document != inputs
            or contexts["planning_policy"].document != policy
        ):
            raise PlanCompositionUnavailable("exact customer and policy context required")
        customer_key = contexts["customer_context"].reference.key
        policy_key = contexts["planning_policy"].reference.key
        references = [entry.reference for entry in evidence.catalogs]
        references += [entry.reference for entry in evidence.performance]
        references += [entry.reference for entry in paired.traffic]
        references += [entry.reference for entry in evidence.context]
        if evidence.commerce is not None:
            references.append(evidence.commerce.reference)
        if not evidence.catalogs or not references:
            raise PlanCompositionUnavailable("a current owned catalog is required")
        if len(references) > MAX_EVIDENCE:
            raise PlanCompositionUnavailable("complete evidence set exceeds document capacity")
        valid_until = min(ref.expires_at.astimezone(UTC) for ref in references)
        creative_proof = None
        creative_composition = None
        if creative is not None:
            creative_proof = creative_proof_from_collection(creative, ticket)
            references.append(creative_basis_reference(creative_proof, inputs, valid_until))
            if len(references) > MAX_EVIDENCE:
                raise PlanCompositionUnavailable("complete evidence set exceeds document capacity")
        if generated_at >= valid_until:
            raise PlanCompositionUnavailable("evidence expired before composition")
        if any(
            ref.workspace_id != inputs.workspace_id
            or ref.privacy_revision != evidence.privacy_revision
            or (ref.account is not None and ref.account not in inputs.accounts)
            for ref in references
        ):
            raise PlanCompositionUnavailable("foreign composition evidence")

        all_targets = {
            target.canonical_entity_key: target
            for catalog in evidence.catalogs
            for target in targets(catalog)
        }
        for fixed in inputs.fixed_allocations:
            if all_targets.get(fixed.target.canonical_entity_key) != fixed.target:
                raise PlanCompositionUnavailable("fixed allocation target changed")
        for intent in inputs.scenario_intents:
            for allocation in intent.allocations:
                if all_targets.get(allocation.target.canonical_entity_key) != allocation.target:
                    raise PlanCompositionUnavailable("customer scenario target changed")
        for perf in evidence.performance:
            if all_targets.get(perf.target.canonical_entity_key) != perf.target:
                raise PlanCompositionUnavailable("performance target changed")

        actions: list[ManualAction] = []
        briefs: list[CreativeBrief] = []
        limitations = [
            "Provider reports do not establish causal lift, unique customers or future sales.",
            "No native budget change or forecast is qualified by this descriptive policy.",
            "Planning allocations are alternatives, not provider caps or verified remaining spend.",
        ]
        section_limits = [
            bounded_text(
                f"Catalog collection-time outcome for account "
                f"{gap.account.account_id if gap.account else 'unavailable'} "
                f"({gap.reason}): {gap.explanation}"
            )
            if gap.section == "catalog"
            else gap.explanation
            for gap in evidence.gaps
        ]
        section_limits.extend(grouped_window_gaps(evidence))
        section_limits.extend(inputs.constraints)
        if inputs.constraints:
            section_limits.append(
                "Freeform constraints need customer clarification before substantive proposals."
            )
        if inputs.maximum_creative_assets is None:
            section_limits.append(
                "Production capacity is unconfirmed; creative tasks are proposals."
            )
        capacity = (
            MAX_BRIEFS if inputs.maximum_creative_assets is None else inputs.maximum_creative_assets
        )
        for account in sorted(inputs.accounts, key=lambda value: value.account_id):
            catalog = next(
                (entry for entry in evidence.catalogs if entry.reference.account == account), None
            )
            if catalog is None:
                section_limits.append(
                    f"{PLATFORMS[account.platform]} account {account.account_id}: "
                    "native catalog collection was unavailable when this plan was prepared."
                )
                continue
            campaign_targets = sorted(
                (
                    value
                    for value in targets(catalog)
                    if value.kind == "campaign"
                    and value.canonical_entity_key not in inputs.excluded_entity_keys
                ),
                key=lambda value: value.canonical_entity_key,
            )
            scopes: list[TargetRef | AccountTarget] = list(campaign_targets)
            if not scopes:
                scopes = [AccountTarget(account=account)]
            for target in scopes:
                key = (
                    f"review:{target.canonical_entity_key}"
                    if isinstance(target, TargetRef)
                    else f"review:account_{account.account_id}"
                )
                kind, rationale, metric_keys = requested_summary(target, paired, inputs)
                if inputs.constraints or inputs.total_ceiling_micros == 0:
                    kind = "investigate"
                    rationale += " Confirm the customer constraints and spending ceiling first."
                if isinstance(target, AccountTarget):
                    kind, rationale = (
                        "investigate",
                        ("No included native campaign is available for campaign planning."),
                    )
                evidence_keys = [catalog.reference.key, policy_key]
                evidence_keys.extend(metric_keys)
                actions.append(
                    ManualAction(
                        key=key,
                        priority=len(actions) + 1,
                        kind=kind,
                        target=target,
                        proposed_fields=(),
                        conflicts=(),
                        measurement_criterion=(
                            "Confirm the event, requested dates, currency and available rows; "
                            "record unresolved gaps before comparing cost per event."
                        ),
                        title="Review Measurement"
                        if kind == "investigate"
                        else "Review Reported Results",
                        rationale=bounded_text(rationale),
                        evidence_keys=tuple(evidence_keys),
                        assumption_keys=(),
                        prerequisites=(),
                        manual_steps=(
                            f"Locate {location(target)} in your advertising account.",
                            "Check the selected event and attribution/reporting settings.",
                            "Compare the requested closed dates with the imported report; "
                            "do not replace absent events with zero.",
                            "Compare current settings with the confirmed planning ceiling and "
                            "customer constraints; continued delivery is not assumed affordable.",
                            "Clarify the constraints shown in this plan before making changes; "
                            "record any change you choose to make outside Inlet.",
                        )
                        + observed_child_steps(
                            target, targets(catalog), inputs.excluded_entity_keys
                        ),
                        expected_effect="Improve decision evidence; sales effect is unknown.",
                        limitations=tuple(limitations[:2]),
                        native_budget=None,
                    )
                )
            if catalog.reference.coverage != "complete_in_declared_scope":
                section_limits.append(f"Account {account.account_id}: catalog coverage is partial.")
            if creative is not None:
                continue
            if inputs.constraints:
                continue
            if not inputs.product_offer or len(briefs) >= capacity:
                section_limits.append(
                    f"Account {account.account_id}: creative production deferred pending product "
                    "facts or available customer capacity."
                )
                continue
            target = scopes[0]
            creative_key = f"creative:account_{account.account_id}"
            platform = PLATFORMS[account.platform]
            format_name, asset, visual = {
                "google_ads": (
                    "Text Concept; Confirm Supported Campaign Format",
                    "One reviewed text concept",
                    "Plan headline and description variants around one substantiated product fact.",
                ),
                "meta_ads": (
                    "Image Concept; Confirm Placement",
                    "One reviewed product image concept",
                    "Show the product clearly and draft one alternate explanatory caption.",
                ),
                "tiktok_ads": (
                    "Video Storyboard; Confirm Placement",
                    "One reviewed product demonstration video concept",
                    "Storyboard a product introduction, demonstration and factual call to action.",
                ),
            }[account.platform]
            creative_evidence = (customer_key, catalog.reference.key, policy_key)
            actions.append(
                ManualAction(
                    key=creative_key,
                    priority=len(actions) + 1,
                    kind="creative_review",
                    target=target,
                    proposed_fields=(),
                    conflicts=(),
                    measurement_criterion=(
                        "Choose one available reported event and keep its definition and window "
                        "consistent when reviewing the concept; no performance promise."
                    ),
                    title=f"Prepare A {platform} Creative Concept",
                    rationale="Use supplied product facts to explore a message hypothesis.",
                    evidence_keys=creative_evidence,
                    assumption_keys=(),
                    prerequisites=(),
                    manual_steps=(
                        f"Confirm the intended account and scope: {location(target)}.",
                        "Review the brief, substantiate each product claim and confirm capacity.",
                        "Create the asset outside Inlet; check current placement requirements.",
                        "Review the finished creative and campaign changes before publication.",
                    ),
                    expected_effect="Test a message hypothesis; effect and eligibility unknown.",
                    limitations=("No owned media or provider approval is inferred.",),
                    native_budget=None,
                )
            )
            briefs.append(
                CreativeBrief(
                    key=f"brief:account_{account.account_id}",
                    action_key=creative_key,
                    target=target,
                    product_facts=(inputs.product_offer,),
                    hypotheses=(
                        "A clearer explanation of the product may improve relevant engagement.",
                    ),
                    placement="Customer must confirm the actual supported placement.",
                    format=format_name,
                    asset_gaps=(asset,),
                    landing_page_constraints=(
                        "Confirm a relevant, working product destination and claims.",
                    ),
                    objective="Explore one message hypothesis within the existing customer plan.",
                    audience="Customer to confirm product audience; no sensitive traits inferred.",
                    offer=inputs.product_offer,
                    claim_evidence_keys=(customer_key,),
                    assumption_keys=(),
                    hooks=("Introduce the product and explain one substantiated use or feature.",),
                    copy_directions=(
                        "Use substantiated supplied facts; do not invent discounts or reviews.",
                    ),
                    visual_directions=(visual,),
                    required_assets=(asset,),
                    customer_review_checklist=(
                        "Confirm claims, destination, asset rights, placement and capacity.",
                        "Customer reviews creative and settings before publishing externally.",
                    ),
                    measurement_plan=(
                        "Record the event/window and review reports separately from Shopify sales; "
                        "do not infer causal lift."
                    ),
                )
            )
        if creative is not None:
            creative_composition = compose_creative_proposals(
                inputs,
                evidence.catalogs,
                creative.basis,
                CreativeCompositionReferencesV1(
                    basis_key="creative:basis",
                    basis_digest=creative.basis.digest(),
                    customer_key=customer_key,
                    customer_input_digest=inputs.digest(),
                    policy_key=policy_key,
                    policy_digest=policy.digest(),
                    policy=policy,
                ),
                first_priority=len(actions) + 1,
                account_prerequisites=tuple(actions),
            )
            actions.extend(proposal.action for proposal in creative_composition.proposals)
            briefs.extend(proposal.brief for proposal in creative_composition.proposals)
            section_limits.extend(creative_composition.limitations)
        if len(actions) > MAX_ACTIONS or len(briefs) > MAX_BRIEFS or len(section_limits) > 30:
            raise PlanCompositionUnavailable("complete plan exceeds current document capacity")

        scenarios = []
        for index, intent in enumerate(inputs.scenario_intents):
            scenarios.append(
                BudgetScenario(
                    key=f"customer_{index + 1}",
                    title=intent.title,
                    period=inputs.budget_period,
                    ceiling_micros=inputs.total_ceiling_micros,
                    allocations=tuple(
                        Allocation(
                            key=f"allocation_{i + 1}",
                            target=item.target,
                            amount_micros=item.amount_micros,
                            rationale="Customer hypothesis; no optimum claimed.",
                            evidence_keys=(customer_key, item.target.catalog_evidence_key),
                        )
                        for i, item in enumerate(intent.allocations)
                    ),
                    unallocated_micros=intent.unallocated_micros,
                    assumptions=(
                        "Customer supplied this alternative; native conversion is unassessed.",
                    ),
                    provenance="customer_supplied_hypothesis",
                    customer_intent_key=intent.key,
                )
            )
        if len(scenarios) < MAX_SCENARIOS:
            scenarios.insert(
                0,
                BudgetScenario(
                    key="fixed_and_unallocated",
                    title="Fixed Allocations And Unallocated Budget",
                    period=inputs.budget_period,
                    ceiling_micros=inputs.total_ceiling_micros,
                    allocations=tuple(
                        Allocation(
                            key=f"fixed_{i + 1}",
                            target=item.target,
                            amount_micros=item.amount_micros,
                            rationale="Preserve the customer's fixed planning allocation.",
                            evidence_keys=(customer_key, item.target.catalog_evidence_key),
                        )
                        for i, item in enumerate(inputs.fixed_allocations)
                    ),
                    unallocated_micros=inputs.total_ceiling_micros
                    - sum(item.amount_micros for item in inputs.fixed_allocations),
                    assumptions=(
                        "Unallocated budget is a planning remainder, not verified available spend.",
                    ),
                ),
            )
        return PlanVersion(
            creative_proof=creative_proof,
            creative_composition=creative_composition,
            selected_reporting_proof=evidence.reporting_proof,
            inputs=inputs,
            version=version,
            parent_digest=parent_digest,
            generator_version=policy.generator_version,
            policy_version=policy.version,
            readiness="needs_input",
            section_limitations=tuple(section_limits),
            generated_by=generated_by,
            generated_at=generated_at,
            valid_until=valid_until,
            evidence=tuple(references),
            actions=tuple(actions),
            scenarios=tuple(scenarios),
            briefs=tuple(briefs),
            summary=(
                "Review your campaign evidence, customer-supplied allocation alternatives and "
                "creative hypotheses. Native changes and forecast benefits remain unqualified."
            ),
            limitations=tuple(limitations),
        )
