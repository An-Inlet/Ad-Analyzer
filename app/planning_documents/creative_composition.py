"""Pure manual creative proposals. No registered v5 policy or runtime authority."""

from pydantic import model_validator

from app.planning_documents.actions import CreativeBrief, ManualAction
from app.planning_documents.common import MAX_ACTIONS, Digest, Key, NoAuthority, unique
from app.planning_documents.composer import PlanCompositionUnavailable, location, targets
from app.planning_documents.context import PlanInputRevision, TargetRef
from app.planning_documents.creative_basis import CreativeBasisV1, CustomerProductV1
from app.planning_documents.creative_production_contracts import (
    CreativeCompositionV1,
    CreativeProductionV1,
    CreativeProposalV1,
    CreativeShotV1,
)
from app.planning_documents.ports import CatalogEvidence, PlanningCompositionPolicy


def canonical_creative_policy() -> PlanningCompositionPolicy:
    """Fresh canonical value for standalone validation, deliberately unregistered."""
    return PlanningCompositionPolicy(
        version="inlet.descriptive-review.v5", generator_version="inlet.descriptive-planning.v5"
    )


class CreativeCompositionReferencesV1(NoAuthority):
    basis_key: Key
    basis_digest: Digest
    customer_key: Key
    customer_input_digest: Digest
    policy_key: Key
    policy_digest: Digest
    policy: PlanningCompositionPolicy

    @model_validator(mode="after")
    def exact(self) -> "CreativeCompositionReferencesV1":
        unique((self.basis_key, self.customer_key, self.policy_key), "creative evidence key")
        canonical = canonical_creative_policy()
        if self.policy != canonical or self.policy_digest != canonical.digest():
            raise ValueError("exact standalone canonical v5 policy required")
        return self


def _offer(product: CustomerProductV1) -> str:
    if product.list_price is None:
        return product.name + "; customer supplied; offer verification required."
    whole, fraction = divmod(product.list_price.micros, 1_000_000)
    amount = str(whole) + ("." + f"{fraction:06d}".rstrip("0") if fraction else "")
    return (
        f"{product.name}; customer-supplied list price {amount} "
        f"{product.list_price.currency}; verify the current offer."
    )


def _proposal(
    target: TargetRef,
    basis: CreativeBasisV1,
    refs: CreativeCompositionReferencesV1,
    product: CustomerProductV1,
    priority: int,
) -> CreativeProposalV1:
    meta = target.account.platform == "meta_ads"
    offer = _offer(product)
    restrictions = (
        "Customer restrictions (verbatim):\n" + "\n".join(product.restrictions)
        if product.restrictions
        else "Ask the customer to confirm any further product restrictions."
    )
    image = basis.images[0] if basis.images else None
    image_text = (
        (
            f"Selected source image {image.media_id}: owned bytes observed at "
            f"{image.observed_at.isoformat()}. Inspect product depiction; "
            f"visual suitability and rights are not assessed."
        )
        if image
        else (
            "No image witness supplied. Obtain an owned product image before "
            "preparing the image creative."
            if meta
            else "No image witness supplied. Film the actual product; do not represent "
            "an image or video asset as already available."
        )
    )
    demonstration = (
        (
            "Substantiate this customer-supplied fact before filming, then "
            "demonstrate it without adding features: "
        )
        + product.customer_asserted_facts[0]
        if product.customer_asserted_facts
        else (
            "Ask the customer for one substantiated product use or feature "
            "before filming a demonstration; invent none."
        )
    )
    shots = (
        ()
        if meta
        else (
            CreativeShotV1(
                purpose="introduction",
                capture_instruction=(
                    f"Film the actual {product.name} clearly. Inspect framing and "
                    f"confirm product identity before editing."
                ),
                proposed_caption=f"Meet {product.name}.",
            ),
            CreativeShotV1(
                purpose="demonstration",
                capture_instruction=demonstration,
                proposed_caption=(
                    "Draft a factual demonstration caption only after the customer "
                    "substantiates the demonstrated use or feature."
                ),
            ),
            CreativeShotV1(
                purpose="cta",
                capture_instruction=(
                    f"Return to a clear view of {product.name}; verify the destination "
                    f"and any displayed price before adding a call to action."
                ),
                proposed_caption=f"View the details of {product.name}.",
            ),
        )
    )
    steps = (
        (
            f"Confirm review scope: {location(target)}. Administrative "
            f"selection is not a performance ranking."
        ),
        image_text,
        f"Review the declared product and offer: {offer}",
        *(
            (
                (
                    f"Prepare one image creative introducing {product.name}. Inspect "
                    f"the selected image, choose a clear crop and keep text legible "
                    f"without assuming placement dimensions."
                ),
                (
                    f"Draft caption: Meet {product.name}. View product details. "
                    f"Include the supplied price only after verifying the current "
                    f"offer."
                ),
            )
            if meta
            else (
                (
                    "No video witness supplied; video production required. An image "
                    "does not establish that no video exists elsewhere in the library."
                ),
                *(shot.capture_instruction for shot in shots),
                (
                    "Edit the three shots into one deliverable; add readable factual "
                    "captions, review audio rights, and inspect continuity. No timing "
                    "or publication eligibility is prescribed."
                ),
            )
        ),
        restrictions,
        (
            "Review product claims, rights, destination, legibility and "
            "current placement requirements; customer approval is required "
            "before any external publication."
        ),
    )
    key = f"creative:account_{target.account.account_id}"
    limitation = (
        "No qualified performance, causal lift, visual suitability, "
        "rights or placement approval is established."
    )
    action = ManualAction(
        key=key,
        priority=priority,
        kind="creative_review",
        target=target,
        proposed_fields=(),
        conflicts=(),
        measurement_criterion=(
            "Choose a reported event and closed window only when supported; "
            "review descriptive results without attributing Shopify sales "
            "causally."
        ),
        title="Prepare One Image Creative" if meta else "Produce One Product Video",
        rationale=(
            f"Use declared facts about {product.name} for a customer-reviewed "
            f"production proposal; performance is unknown."
        ),
        evidence_keys=(
            refs.customer_key,
            refs.basis_key,
            target.catalog_evidence_key,
            refs.policy_key,
        ),
        assumption_keys=(),
        prerequisites=(),
        manual_steps=steps,
        expected_effect=(
            "A product-specific message proposal; sales and delivery effects are unknown."
        ),
        limitations=(limitation,),
        native_budget=None,
    )
    brief = CreativeBrief(
        key=f"brief:account_{target.account.account_id}",
        action_key=key,
        target=target,
        product_facts=product.customer_asserted_facts
        or (f"Customer-declared product: {product.name}",),
        hypotheses=(
            (
                f"Explore whether a clear introduction to {product.name} is useful "
                f"to the intended audience; no improvement is predicted."
            ),
        ),
        placement="Customer must verify the actual placement and current requirements.",
        format="Image creative proposal" if meta else "Three-shot product video proposal",
        asset_gaps=(
            "Finished image creative requires production and review."
            if meta
            else "No video witness supplied; finished video production and review required.",
        ),
        landing_page_constraints=(
            "Verify a working product destination and exact current offer.",
            restrictions,
        ),
        objective=f"Prepare one factual introduction to {product.name}.",
        audience="Customer must confirm audience; no sensitive traits are inferred.",
        offer=offer,
        claim_evidence_keys=(refs.customer_key,),
        assumption_keys=(),
        hooks=(f"Meet {product.name}.",),
        copy_directions=(
            "Use only customer-declared substantiated facts and verify the offer.",
            restrictions,
        ),
        visual_directions=(image_text,)
        if meta
        else tuple(shot.capture_instruction for shot in shots),
        required_assets=(
            "One reviewed image creative."
            if meta
            else "One reviewed video composed from three filmed shots.",
        ),
        customer_review_checklist=(
            restrictions,
            (
                "Inspect the finished asset and confirm claims, rights, "
                "destination, captions and placement before publication."
            ),
        ),
        measurement_plan=(
            "Reported metrics remain separate from causal effects; select an "
            "event/window only when supported. No spend or native change is "
            "authorized."
        ),
    )
    return CreativeProposalV1(
        action=action,
        brief=brief,
        production=CreativeProductionV1(
            source_images=basis.requested.media_selections,
            selected_image_id=image.media_id if image else None,
            source_image_status="owned_bytes_observed" if image else "not_supplied",
            deliverable="image_creative" if meta else "video",
            basis_evidence_key=refs.basis_key,
            storyboard=shots,
        ),
    )


def compose_creative_proposals(
    inputs: PlanInputRevision,
    catalogs: tuple[CatalogEvidence, ...],
    basis: CreativeBasisV1,
    references: CreativeCompositionReferencesV1,
    *,
    first_priority: int,
) -> CreativeCompositionV1:
    inputs = PlanInputRevision.model_validate(inputs)
    basis = CreativeBasisV1.model_validate(basis)
    refs = CreativeCompositionReferencesV1.model_validate(references)
    if type(first_priority) is not int or not 1 <= first_priority <= MAX_ACTIONS:
        raise ValueError("bounded strict positive first priority required")
    if type(catalogs) is not tuple:
        raise ValueError("explicit catalog tuple required")
    catalogs = tuple(CatalogEvidence.model_validate(c) for c in catalogs)
    unique(tuple(c.reference.account for c in catalogs), "catalog account")
    unique(tuple(c.reference.key for c in catalogs), "catalog key")
    if (
        refs.basis_digest != basis.digest()
        or refs.customer_input_digest != inputs.digest()
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
        raise ValueError("exact creative basis/input/catalog references required")
    limitations = [
        "Standalone manual production only; no qualified performance or publication authority."
    ]
    if not catalogs:
        limitations.append(
            "No owned catalogs supplied; creative composition deferred. "
            "Current privacy qualification remains the caller's "
            "responsibility."
        )
    product = basis.requested.product
    capacity = inputs.maximum_creative_assets
    proposals: list[CreativeProposalV1] = []
    for account in sorted(inputs.accounts, key=lambda a: a.account_id):
        prefix = f"Account {account.account_id}: "
        catalog = next((c for c in catalogs if c.reference.account == account), None)
        if catalog is None:
            limitations.append(prefix + "owned catalog unavailable; deferred.")
            continue
        if catalog.reference.coverage != "complete_in_declared_scope":
            limitations.append(prefix + "catalog coverage is partial; no complete-account claim.")
        if account.platform not in {"meta_ads", "tiktok_ads"}:
            limitations.append(prefix + "unsupported creative policy; deferred.")
            continue
        included = sorted(
            (
                t
                for t in targets(catalog)
                if t.kind == "campaign"
                and t.canonical_entity_key not in inputs.excluded_entity_keys
            ),
            key=lambda t: t.canonical_entity_key,
        )
        if not included:
            limitations.append(prefix + "no included campaign; deferred without account fallback.")
        elif inputs.constraints:
            limitations.append(
                prefix + "unresolved customer constraints; creative production deferred."
            )
            limitations.extend(inputs.constraints)
        elif product is None:
            limitations.append(prefix + "typed product information missing; deferred.")
        elif capacity is None:
            limitations.append(prefix + "production capacity unconfirmed; deferred.")
        elif len(proposals) >= capacity:
            limitations.append(prefix + "global confirmed production capacity exhausted; deferred.")
        else:
            priority = first_priority + len(proposals)
            if priority > MAX_ACTIONS:
                raise PlanCompositionUnavailable(
                    "creative priorities exceed complete document capacity"
                )
            proposals.append(_proposal(included[0], basis, refs, product, priority))
    result = CreativeCompositionV1(
        basis_digest=basis.digest(), proposals=tuple(proposals), limitations=tuple(limitations)
    )
    result.assert_basis(basis)
    return result
