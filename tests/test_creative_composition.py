"""Standalone synthetic pure composition, not authenticated media or API qualification."""

from decimal import localcontext
from typing import Any

import pytest
from app.planning_documents.common import MAX_ACTIONS
from app.planning_documents.composer import targets
from app.planning_documents.context import PlanInputRevision
from app.planning_documents.creative_basis import CreativeBasisV1, CustomerListPriceV1
from app.planning_documents.creative_composition import (
    CreativeCompositionReferencesV1,
    canonical_creative_policy,
    compose_creative_proposals,
)
from app.planning_documents.creative_production_contracts import CreativeCompositionV1
from pydantic import ValidationError

from tests.test_planning_composer import fixture
from tests.test_planning_creative_basis import basis as image_basis


def ready(platform: str = "meta", *, images: int = 1, **changes: Any) -> Any:
    inputs, bundle, _ = fixture(platform, maximum_creative_assets=1, **changes)
    raw = image_basis(images).model_dump(mode="python")
    raw["workspace_id"] = inputs.workspace_id
    raw["privacy_revision"] = bundle.catalogs[0].reference.privacy_revision
    for image in raw["images"]:
        image["workspace_id"] = raw["workspace_id"]
        image["privacy_revision"] = raw["privacy_revision"]
    basis = CreativeBasisV1.model_validate(raw)
    return inputs, bundle.catalogs, basis


def references(inputs: Any, basis: Any) -> CreativeCompositionReferencesV1:
    policy = canonical_creative_policy()
    return CreativeCompositionReferencesV1(
        basis_key="creative:basis",
        basis_digest=basis.digest(),
        customer_key="context:inputs",
        customer_input_digest=inputs.digest(),
        policy_key="context:policy",
        policy_digest=policy.digest(),
        policy=policy,
    )


def compose(inputs: Any, catalogs: Any, basis: Any, *, priority: Any = 1) -> CreativeCompositionV1:
    return compose_creative_proposals(
        inputs, catalogs, basis, references(inputs, basis), first_priority=priority
    )


@pytest.mark.parametrize("platform", ["meta", "tiktok"])
def test_product_specific_complete_image_basis_and_no_authority(platform: str) -> None:
    inputs, catalogs, basis = ready(platform, images=2)
    result = compose(inputs, catalogs, basis)
    assert len(result.proposals) == 1
    p = result.proposals[0]
    assert p.production.source_images == basis.requested.media_selections
    assert p.production.selected_image_id == basis.images[0].media_id
    assert p.production.visual_assessment == "not_assessed"
    assert p.production.deliverable_status == "production_required"
    assert "Reusable travel mug" in p.brief.offer and "25 USD" in p.brief.offer
    assert p.brief.claim_evidence_keys == ("context:inputs",)
    assert p.action.evidence_keys == (
        "context:inputs",
        "creative:basis",
        catalogs[0].reference.key,
        "context:policy",
    )
    assert p.action.native_budget is None and not p.action.proposed_fields
    assert p.action.target in targets(catalogs[0])
    assert any("partial" in text for text in result.limitations)
    for restriction in basis.requested.product.restrictions:
        assert any(restriction in text for text in p.action.manual_steps)
        assert any(restriction in text for text in p.brief.copy_directions)
        assert any(restriction in text for text in p.brief.customer_review_checklist)
    if platform == "meta":
        assert p.production.storyboard == ()
        assert "Inspect product depiction" in " ".join(p.action.manual_steps)
    else:
        assert tuple(s.purpose for s in p.production.storyboard) == (
            "introduction",
            "demonstration",
            "cta",
        )
        assert "Substantiate" in p.production.storyboard[1].capture_instruction
        assert "No video witness supplied" in " ".join(p.action.manual_steps)
        assert "no video exists elsewhere" in " ".join(p.action.manual_steps)
    assert CreativeCompositionV1.model_validate_json(result.model_dump_json()) == result
    assert result.digest() == compose(inputs, catalogs, basis).digest()
    assert not result.advertising_writes_enabled and result.spending_authority == "none"
    result.assert_basis(basis)


@pytest.mark.parametrize(
    "case", ["zero", "unknown", "constraints", "product", "excluded", "catalog", "google"]
)
def test_deferrals_never_invent_fallback(case: str) -> None:
    inputs, catalogs, basis = ready("google" if case == "google" else "meta")
    if case in {"zero", "unknown", "constraints", "excluded"}:
        update = {
            "zero": dict(maximum_creative_assets=0),
            "unknown": dict(maximum_creative_assets=None),
            "constraints": dict(constraints=("Do not create anything until reviewed",)),
            "excluded": dict(
                excluded_entity_keys=tuple(
                    t.canonical_entity_key for t in targets(catalogs[0]) if t.kind == "campaign"
                )
            ),
        }[case]
        inputs = PlanInputRevision.model_validate(inputs.model_copy(update=update))
    if case == "product":
        basis = CreativeBasisV1.model_validate(
            basis.model_copy(
                update={"requested": basis.requested.model_copy(update={"product": None})}
            )
        )
    if case == "catalog":
        catalogs = ()
    result = compose(inputs, catalogs, basis)
    assert not result.proposals and any("deferred" in x for x in result.limitations)


def test_absent_image_fact_and_precision_independent_price() -> None:
    inputs, catalogs, basis = ready("tiktok", images=0)
    product = basis.requested.product.model_copy(
        update={
            "customer_asserted_facts": (),
            "list_price": CustomerListPriceV1(micros=999_999_999_999_999, currency="USD"),
        }
    )
    basis = CreativeBasisV1.model_validate(
        basis.model_copy(
            update={"requested": basis.requested.model_copy(update={"product": product})}
        )
    )
    with localcontext() as ctx:
        ctx.prec = 2
        p = compose(inputs, catalogs, basis).proposals[0]
    assert "999999999.999999 USD" in p.brief.offer
    assert (
        p.production.source_image_status == "not_supplied"
        and p.production.selected_image_id is None
    )
    assert "Ask the customer" in p.production.storyboard[1].capture_instruction


@pytest.mark.parametrize("priority", [True, False, 0, -1, 1.0, "1", MAX_ACTIONS + 1])
def test_strict_priority(priority: Any) -> None:
    with pytest.raises(ValueError):
        compose(*ready(), priority=priority)


@pytest.mark.parametrize(
    "attack",
    [
        "basis_digest",
        "customer_input_digest",
        "policy_digest",
        "basis_key",
        "policy",
        "basis_scope",
        "privacy",
        "catalog_duplicate",
        "catalog_key",
        "unsafe_product",
    ],
)
def test_exact_references_and_nested_tamper(attack: str) -> None:
    inputs, catalogs, basis = ready()
    refs = references(inputs, basis)
    if attack.endswith("digest"):
        refs = refs.model_copy(update={attack: "f" * 64})
    elif attack == "basis_key":
        refs = refs.model_copy(update={"basis_key": refs.customer_key})
    elif attack == "policy":
        refs = refs.model_copy(
            update={
                "policy": refs.policy.model_copy(update={"version": "inlet.descriptive-review.v4"})
            }
        )
    elif attack == "basis_scope":
        basis = basis.model_copy(update={"workspace_id": 999})
    elif attack == "privacy":
        basis = basis.model_copy(update={"privacy_revision": 999})
    elif attack == "catalog_duplicate":
        catalogs = (*catalogs, *catalogs)
    elif attack == "catalog_key":
        refs = refs.model_copy(update={"basis_key": catalogs[0].reference.key})
    else:
        basis = basis.model_copy(
            update={
                "requested": basis.requested.model_copy(
                    update={"product": basis.requested.product.model_copy(update={"name": 123})}
                )
            }
        )
    with pytest.raises(ValueError):
        compose_creative_proposals(inputs, catalogs, basis, refs, first_priority=1)


@pytest.mark.parametrize(
    "attack", ["images", "first", "storyboard", "priority", "target", "basis_key", "budget"]
)
def test_output_unsafe_copy_revalidation(attack: str) -> None:
    inputs, catalogs, basis = ready("tiktok", images=2)
    result = compose(inputs, catalogs, basis)
    p = result.proposals[0]
    if attack == "images":
        p = p.model_copy(
            update={
                "production": p.production.model_copy(
                    update={"source_images": tuple(reversed(p.production.source_images))}
                )
            }
        )
    elif attack == "first":
        p = p.model_copy(
            update={
                "production": p.production.model_copy(
                    update={"selected_image_id": basis.images[1].media_id}
                )
            }
        )
    elif attack == "storyboard":
        p = p.model_copy(
            update={
                "production": p.production.model_copy(
                    update={"storyboard": tuple(reversed(p.production.storyboard))}
                )
            }
        )
    elif attack == "priority":
        p = p.model_copy(update={"action": p.action.model_copy(update={"priority": 101})})
    elif attack == "target":
        p = p.model_copy(
            update={
                "brief": p.brief.model_copy(
                    update={
                        "target": p.brief.target.model_copy(update={"display_name": "Different"})
                    }
                )
            }
        )
    elif attack == "basis_key":
        p = p.model_copy(
            update={"production": p.production.model_copy(update={"basis_evidence_key": "wrong"})}
        )
    else:
        p = p.model_copy(
            update={
                "action": p.action.model_copy(update={"native_budget": {"reason": "unsupported"}})
            }
        )
    with pytest.raises(ValueError):
        result.model_copy(update={"proposals": (p,)}).assert_basis(basis)


def test_text_overflow_rejects_without_truncation() -> None:
    inputs, catalogs, basis = ready()
    product = basis.requested.product.model_copy(update={"restrictions": ("x" * 2000, "y" * 2000)})
    basis = CreativeBasisV1.model_validate(
        basis.model_copy(
            update={"requested": basis.requested.model_copy(update={"product": product})}
        )
    )
    with pytest.raises(ValidationError):
        compose(inputs, catalogs, basis)


def two_accounts() -> Any:
    from app.planning_catalog.metadata_contracts import PlanningMetadataV1
    from app.planning_catalog.projection_v2 import project_v2
    from app.planning_documents.ports import CatalogEvidence
    from app.publication.contracts import fingerprint

    from tests.test_planning_metadata_binding import bundle

    inputs, catalogs, basis = ready()
    inventory, metadata = bundle("tiktok")
    raw = inventory.model_dump(mode="python")
    raw["request"]["account"]["account"]["account_id"] = 99
    inventory = type(inventory).model_validate(raw)
    source = inventory.request.account
    metadata = PlanningMetadataV1.model_validate(
        metadata.model_copy(
            update={
                "account_id": 99,
                "source_binding_digest": fingerprint(
                    "inlet.planning-source.v1", source.model_dump(mode="json")
                ),
                "native_inventory_digest": inventory.digest(),
                "request_digest": inventory.request.digest(),
            }
        )
    )
    cat = project_v2(inventory, metadata)
    ref = catalogs[0].reference.model_dump(mode="python")
    account = dict(
        workspace_id=metadata.workspace_id,
        account_id=99,
        connection_id=metadata.connection_id,
        platform=metadata.platform,
        connection_version=metadata.connection_version,
    )
    ref.update(
        key="catalog:99",
        account=account,
        document_digest=cat.composite_digest,
        source_binding_digest=metadata.source_binding_digest,
        expires_at=cat.expires_at,
        observation_started_at=metadata.observation_started_at,
        observed_at=metadata.observed_at,
        reporting_window=dict(
            starts_at=metadata.reporting_starts_at, ends_at_exclusive=metadata.reporting_ends_at
        ),
    )
    second = CatalogEvidence(reference=ref, catalog=cat)
    inputs = PlanInputRevision.model_validate(
        inputs.model_copy(update={"accounts": (*inputs.accounts, second.reference.account)})
    )
    return inputs, (*catalogs, second), basis


def test_global_capacity_and_complete_priority_overflow() -> None:
    inputs, catalogs, basis = two_accounts()
    result = compose(inputs, tuple(reversed(catalogs)), basis)
    assert (
        len(result.proposals) == 1
        and result.proposals[0].action.target.account == inputs.accounts[0]
    )
    assert any("capacity exhausted" in x for x in result.limitations)
    assert result == compose(inputs, catalogs, basis)
    inputs = PlanInputRevision.model_validate(
        inputs.model_copy(update={"maximum_creative_assets": 2})
    )
    result = compose(inputs, catalogs, basis, priority=99)
    assert tuple(p.action.priority for p in result.proposals) == (99, 100)
    with pytest.raises(ValueError):
        compose(inputs, catalogs, basis, priority=100)


def test_full_output_byte_bound_and_no_silent_truncation() -> None:
    import copy
    import json

    from app.planning_documents.common import MAX_DOCUMENT_BYTES

    result = compose(*ready())
    raw = result.model_dump(mode="python")
    original = raw["proposals"][0]
    proposals = []
    for n in range(30):
        p = copy.deepcopy(original)
        p["action"].update(
            key=f"creative:account_{n + 1}", priority=n + 1, manual_steps=["x" * 2000] * 20
        )
        p["brief"].update(
            key=f"brief:account_{n + 1}",
            action_key=f"creative:account_{n + 1}",
            copy_directions=["y" * 2000] * 10,
        )
        for holder in (p["action"], p["brief"]):
            holder["target"]["account"]["account_id"] = n + 1
        proposals.append(p)
    raw["proposals"] = proposals
    assert len(json.dumps(raw, default=str).encode()) > MAX_DOCUMENT_BYTES
    with pytest.raises(ValueError, match="byte limit"):
        CreativeCompositionV1.model_validate(raw)


def test_ordered_sources_and_exact_basis_not_only_output_shape() -> None:
    inputs, catalogs, basis = ready(images=2)
    result = compose(inputs, catalogs, basis)
    p = result.proposals[0]
    with pytest.raises(ValueError):
        p.production.model_validate(
            p.production.model_copy(update={"source_images": set(p.production.source_images)})
        )
    reverse = p.production.model_copy(
        update={
            "source_images": tuple(reversed(p.production.source_images)),
            "selected_image_id": basis.images[1].media_id,
        }
    )
    valid_shape = result.model_copy(
        update={"proposals": (p.model_copy(update={"production": reverse}),)}
    )
    with pytest.raises(ValueError, match="exact basis"):
        valid_shape.assert_basis(basis)


@pytest.mark.parametrize(
    "change",
    [
        {"purpose": "hook"},
        {"purpose": 1},
        {"advertising_writes_enabled": 0},
        {"spending_authority": "approved"},
        {"extra": True},
    ],
)
def test_shot_strict_closed_identifiers(change: dict[str, Any]) -> None:
    shot = compose(*ready("tiktok")).proposals[0].production.storyboard[0]
    with pytest.raises(ValueError):
        type(shot).model_validate(shot.model_copy(update=change))


def test_no_policy_registration_and_dependency_light_contract_import() -> None:
    import subprocess
    import sys

    subprocess.run(
        [
            sys.executable,
            "-c",
            "import app.planning_documents.creative_production_contracts; import sys; "
            "assert 'app.planning_documents.ports' not in sys.modules",
        ],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        [sys.executable, "-c", "import app.planning_documents.creative_composition"],
        check=True,
        capture_output=True,
    )


def test_valid_basis_foreign_currency_or_privacy_still_rejected() -> None:
    inputs, catalogs, basis = ready()
    currency = basis.model_dump(mode="python")
    currency["goal_currency"] = "EUR"
    currency["requested"]["product"]["list_price"]["currency"] = "EUR"
    with pytest.raises(ValueError, match="references"):
        compose(inputs, catalogs, CreativeBasisV1.model_validate(currency))
    privacy = basis.model_dump(mode="python")
    privacy["privacy_revision"] += 1
    for image in privacy["images"]:
        image["privacy_revision"] = privacy["privacy_revision"]
    with pytest.raises(ValueError, match="references"):
        compose(inputs, catalogs, CreativeBasisV1.model_validate(privacy))


def test_canonical_v5_value_does_not_register_capability() -> None:
    from app.planning_documents.policy_capabilities import reporting_capability

    policy = canonical_creative_policy()
    with pytest.raises(ValueError, match="unknown"):
        reporting_capability(policy.version, policy.generator_version)
