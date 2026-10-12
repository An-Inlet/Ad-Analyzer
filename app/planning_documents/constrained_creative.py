"""Candidate finite-rule production; does not rewrite inputs or invoke the legacy guard."""

from app.planning_documents.actions import ManualAction
from app.planning_documents.common import MAX_ACTIONS, unique
from app.planning_documents.composer import targets
from app.planning_documents.constraint_interpretation import interpret_constraints
from app.planning_documents.constraint_policy import is_constraint_policy
from app.planning_documents.context import PlanInputRevision, TargetRef
from app.planning_documents.creative_basis import CreativeBasisV1, CustomerProductV1
from app.planning_documents.creative_composition import CreativeCompositionReferencesV1, _proposal
from app.planning_documents.creative_production_contracts import (
    CreativeCompositionV1,
    CreativeProposalV1,
)
from app.planning_documents.ports import CatalogEvidence


def constrained_proposal(
    target: TargetRef,
    basis: CreativeBasisV1,
    refs: CreativeCompositionReferencesV1,
    priority: int,
) -> CreativeProposalV1:
    # Explicit public-copy projection. Original product/name/price/facts remain in basis/inputs.
    # No customer strings enter the copy template, even if a product name is promotional.
    neutral = CustomerProductV1(name="the selected product")
    base = _proposal(target, basis, refs, neutral, priority).model_dump(mode="python")
    instructions = (
        "Prepare a neutral product introduction using only the customer's selected source assets.",
        "Suggested public caption: Explore the product. View product details.",
        "Do not add prices, savings, discounts, promotions, testimonials "
        "or unsubstantiated claims.",
        "Do not copy customer product names or asserted facts into public copy without review.",
        "Inspect selected image pixels, video, audio and the destination for restricted claims; "
        "their compliance, suitability and rights have not been assessed.",
        "Confirm destination, rights and placement, then obtain customer approval before any "
        "publication. No advertising spend or production cost is authorized by this proposal.",
    )
    base["action"].update(manual_steps=instructions)
    base["brief"].update(
        product_facts=(
            "Original customer product facts are retained in the input and creative "
            "basis as provenance, not proposed public copy.",
        ),
        offer="Product details only; no promotional offer or price is proposed.",
        objective="Prepare a neutral product introduction for customer review.",
        hooks=("Explore the product.",),
        copy_directions=instructions[1:4],
        landing_page_constraints=(instructions[4],),
        customer_review_checklist=instructions[3:],
    )
    for shot in base["production"]["storyboard"]:
        shot["capture_instruction"] = {
            "introduction": "Film the selected product; inspect the frame for restricted claims.",
            "demonstration": "Show the product without performance, health or promotional claims.",
            "cta": "End with a neutral product view; inspect the destination before review.",
        }[shot["purpose"]]
        shot["proposed_caption"] = {
            "introduction": "Explore the product.",
            "demonstration": "See the product details.",
            "cta": "View product details.",
        }[shot["purpose"]]
    base["brief"]["visual_directions"] = (
        (instructions[4],)
        if not base["production"]["storyboard"]
        else tuple(s["capture_instruction"] for s in base["production"]["storyboard"])
    )
    return CreativeProposalV1.model_validate(base)


def compose_constrained_creative(
    inputs: PlanInputRevision,
    catalogs: tuple[CatalogEvidence, ...],
    basis: CreativeBasisV1,
    refs: CreativeCompositionReferencesV1,
    *,
    first_priority: int,
    account_prerequisites: tuple[ManualAction, ...] = (),
) -> CreativeCompositionV1:
    if type(account_prerequisites) is not tuple:
        raise ValueError("explicit prerequisite tuple required")
    for action in account_prerequisites:
        ManualAction.model_validate(action)
    inputs = PlanInputRevision.model_validate(inputs)
    basis = CreativeBasisV1.model_validate(basis)
    refs = CreativeCompositionReferencesV1.model_validate(refs)
    if not is_constraint_policy(refs.policy.version, refs.policy.generator_version):
        raise ValueError("exact candidate constraint policy required")
    if type(first_priority) is not int or not 1 <= first_priority <= MAX_ACTIONS:
        raise ValueError("bounded positive priority required")
    if type(catalogs) is not tuple:
        raise ValueError("explicit catalog tuple required")
    catalogs = tuple(CatalogEvidence.model_validate(c) for c in catalogs)
    unique(tuple(c.reference.account for c in catalogs), "catalog account")
    unique(tuple(c.reference.key for c in catalogs), "catalog key")
    if (
        refs.basis_digest != basis.digest()
        or refs.customer_input_digest != inputs.digest()
        or basis.requested != inputs.creative
        or basis.workspace_id != inputs.workspace_id
        or basis.goal_currency != inputs.budget_period.currency
        or any(
            c.reference.account not in inputs.accounts
            or c.reference.privacy_revision != basis.privacy_revision
            for c in catalogs
        )
        or {refs.basis_key, refs.customer_key, refs.policy_key}
        & {c.reference.key for c in catalogs}
    ):
        raise ValueError("exact original creative input and owned catalog basis required")
    interpretation = interpret_constraints(inputs)
    limitations = [
        "Customer instructions only; asset compliance, rights, performance and publication "
        "remain unverified. The advertising ceiling does not authorize production costs."
    ]
    proposals: list[CreativeProposalV1] = []
    for account in sorted(inputs.accounts, key=lambda a: a.account_id):
        prefix = f"Account {account.account_id}: "
        catalog = next((c for c in catalogs if c.reference.account == account), None)
        included = (
            []
            if catalog is None
            else sorted(
                (
                    t
                    for t in targets(catalog)
                    if t.kind == "campaign"
                    and t.canonical_entity_key not in inputs.excluded_entity_keys
                ),
                key=lambda t: t.canonical_entity_key,
            )
        )
        reason = None
        if interpretation.disposition == "unresolved":
            reason = (
                "unresolved global or product restrictions. Clarify the listed original "
                "instructions before creative production; none were relaxed."
            )
        elif catalog is None:
            reason = "owned catalog unavailable. Reconnect or refresh the selected account."
        elif account.platform not in {"meta_ads", "tiktok_ads"}:
            reason = (
                "creative production is unsupported on this channel. Keep it excluded "
                "from creative work or explicitly select a supported channel."
            )
        elif not included:
            reason = (
                "no included campaign. Review exclusions or explicitly select an eligible "
                "campaign; excluded campaigns were not restored."
            )
        elif basis.requested.product is None:
            reason = "product information missing. Supply product context before production."
        elif inputs.maximum_creative_assets is None:
            reason = "creative capacity unknown. Confirm a capacity before production."
        elif len(proposals) >= inputs.maximum_creative_assets:
            reason = (
                "confirmed creative capacity exhausted. Keep this task deferred or "
                "explicitly revise capacity; no extra asset was proposed."
            )
        elif not basis.images:
            reason = (
                "no selected owned source image. Select an allowed image or leave "
                "creative deferred; unselected or excluded assets were not substituted."
            )
        if reason:
            limitations.append(prefix + "Deferred: " + reason)
            continue
        assert catalog is not None
        if catalog.reference.coverage != "complete_in_declared_scope":
            limitations.append(prefix + "catalog is partial; other scopes remain unknown.")
        priority = first_priority + len(proposals)
        if priority > MAX_ACTIONS:
            raise ValueError("complete creative priorities exceed capacity")
        # The neutral template applies even without restrictions; this is a distinct policy.
        proposals.append(constrained_proposal(included[0], basis, refs, priority))
    result = CreativeCompositionV1(
        basis_digest=basis.digest(), proposals=tuple(proposals), limitations=tuple(limitations)
    )
    result.assert_basis(basis)
    return result
