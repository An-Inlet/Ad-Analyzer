"""Deterministic descriptive plans, with explicit gaps instead of invented optimization."""

from datetime import datetime
from decimal import Decimal
from typing import Literal

from app.planning_documents.actions import Allocation, BudgetScenario, CreativeBrief, ManualAction
from app.planning_documents.common import MAX_ACTIONS, MAX_BRIEFS, MAX_SCENARIOS
from app.planning_documents.context import AccountTarget, PlanInputRevision, TargetRef
from app.planning_documents.documents import PlanVersion
from app.planning_documents.ports import (
    CatalogEvidence,
    EvidenceBundle,
    PerformanceEvidence,
    PlanningCompositionPolicy,
)

GENERATOR_VERSION = "inlet.descriptive-planning.v1"
POLICY_VERSION = "inlet.descriptive-review.v1"
PLATFORMS = {"google_ads": "Google Ads", "meta_ads": "Meta Ads", "tiktok_ads": "TikTok Ads"}


class PlanCompositionUnavailable(ValueError):
    """Explicit clarification or a smaller scope is needed; no partial save is implied."""


def targets(catalog: CatalogEvidence) -> tuple[TargetRef, ...]:
    account = catalog.reference.account
    if account is None:
        raise PlanCompositionUnavailable("owned catalog account required")
    return tuple(
        TargetRef(
            account=account,
            provider_reference=row.entity.reference,
            canonical_entity_key=row.canonical_entity_key,
            selection_key=row.selection_key,
            catalog_evidence_key=catalog.reference.key,
            kind=row.entity.kind,
            display_name=row.entity.name,
            budget_owner_key=row.budget_owner_key,
        )
        for row in catalog.catalog.targets
    )


def location(target: TargetRef | AccountTarget) -> str:
    platform = PLATFORMS[target.account.platform]
    if isinstance(target, AccountTarget):
        return f"{platform} connected account {target.account.account_id}"
    ref = target.provider_reference
    name = target.display_name or "Name unavailable"
    parent = f", parent campaign {ref.parent_campaign_id}" if ref.parent_campaign_id else ""
    return (
        f"{platform} advertiser {ref.advertiser_id}, {target.kind} {ref.entity_id}{parent} ({name})"
    )


def reported_summary(
    performance: PerformanceEvidence | None,
) -> tuple[Literal["investigate", "retain"], str]:
    if performance is None:
        return "investigate", "No matching campaign performance document is available."
    doc = performance.document
    facts = []
    if doc.clicks is not None:
        facts.append(f"{doc.clicks} reported clicks")
    if doc.spend_micros is not None:
        amount = Decimal(doc.spend_micros) / Decimal(1_000_000)
        facts.append(f"{amount:f} {doc.currency} reported spend")
    if doc.conversions is not None and Decimal(doc.conversions) > 0:
        facts.append(f"{doc.conversions} provider-reported conversions")
    else:
        facts.append("selected conversion presence is unqualified; missing is not zero")
    period = f"{doc.starts_on.isoformat()} through {doc.ends_on.isoformat()}"
    summary = f"For {period}: {'; '.join(facts)}."
    if performance.conversion_qualification != "reported_only":
        return "investigate", summary + " Verify the selected event and reporting basis."
    return "retain", summary + " These observations do not establish an improved allocation."


class DescriptivePlanComposer:
    """Implements the pure port; final source/authority proof remains service-owned."""

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
        inputs = PlanInputRevision.model_validate(inputs)
        evidence = EvidenceBundle.model_validate(evidence)
        policy = PlanningCompositionPolicy.model_validate(policy)
        if (policy.version, policy.generator_version) != (POLICY_VERSION, GENERATOR_VERSION):
            raise PlanCompositionUnavailable("unsupported explicit composition policy")
        if evidence.input_digest != inputs.digest() or evidence.collected_at > generated_at:
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
        references += [entry.reference for entry in evidence.context]
        if evidence.commerce is not None:
            references.append(evidence.commerce.reference)
        if not evidence.catalogs or not references:
            raise PlanCompositionUnavailable("a current owned catalog is required")
        valid_until = min(ref.expires_at for ref in references)
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
        section_limits = [gap.explanation for gap in evidence.gaps]
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
                    "native read unavailable."
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
                performance = next(
                    (
                        item
                        for item in evidence.performance
                        if item.target == target
                        and item.reference.reporting_window == inputs.reporting_window
                    ),
                    None,
                )
                kind, rationale = reported_summary(performance)
                if inputs.constraints or inputs.total_ceiling_micros == 0:
                    kind = "investigate"
                    rationale += " Confirm the customer constraints and spending ceiling first."
                if isinstance(target, AccountTarget):
                    kind, rationale = (
                        "investigate",
                        ("No included native campaign is available for campaign planning."),
                    )
                evidence_keys = [catalog.reference.key, policy_key]
                if performance is not None:
                    evidence_keys.append(performance.reference.key)
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
                        rationale=rationale,
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
                        ),
                        expected_effect="Improve decision evidence; sales effect is unknown.",
                        limitations=tuple(limitations[:2]),
                        native_budget=None,
                    )
                )
            if catalog.reference.coverage != "complete_in_declared_scope":
                section_limits.append(f"Account {account.account_id}: catalog coverage is partial.")
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
        if len(actions) > MAX_ACTIONS or len(section_limits) > 30:
            raise PlanCompositionUnavailable("reduce selected scope for a bounded reviewable plan")

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
