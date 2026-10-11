"""Pure location-only v4 projection; no native metrics or action authority."""

import hashlib
from typing import Any

import pytest
from app.planning_documents.composer import PlanCompositionUnavailable, location, targets
from app.planning_documents.context import AccountTarget, TargetRef
from app.planning_documents.selected_composer import observed_child_steps

from tests.test_selected_paired_composer import compose, ready


def refs() -> tuple[TargetRef, TargetRef]:
    _, paired, _ = ready()
    values = targets(paired.selected.catalogs[0])
    return next(v for v in values if v.kind == "campaign"), next(
        v for v in values if v.kind == "adgroup"
    )


def child_copy(child: TargetRef, number: int, **changes: Any) -> TargetRef:
    return TargetRef.model_validate(
        child.model_copy(
            update={
                "canonical_entity_key": f"{number:064x}",
                "selection_key": f"{number + 100:064x}",
                "provider_reference": child.provider_reference.model_copy(
                    update={"entity_id": str(number)}
                ),
                **changes,
            }
        )
    )


def test_exact_observed_locations_deterministic_duplicate_names_and_exclusions() -> None:
    parent, child = refs()
    children = tuple(child_copy(child, number) for number in (3, 1, 2))
    steps = observed_child_steps(parent, (parent, *children), ())
    assert steps == observed_child_steps(parent, tuple(reversed(children)), ())
    assert len(steps) == 3  # Same observed name is not a join or a deduplication key.
    for step, value in zip(
        steps, sorted(children, key=lambda c: c.canonical_entity_key), strict=True
    ):
        assert location(value) in step
        assert step.startswith("Observed catalog location only:")
        assert "Campaign metrics are not child metrics; no child change is proposed." in step
        assert "clicks" not in step and "conversions" not in step and "budget" not in step
    assert observed_child_steps(parent, children, (children[0].canonical_entity_key,)) == steps[:2]
    assert observed_child_steps(AccountTarget(account=parent.account), children, ()) == ()
    assert observed_child_steps(parent, (parent,), ()) == ()


@pytest.mark.parametrize(
    "mismatch",
    ["workspace", "account", "connection", "generation", "advertiser", "parent", "catalog"],
)
def test_child_join_requires_full_owned_account_advertiser_and_parent(mismatch: str) -> None:
    parent, child = refs()
    if mismatch in {"workspace", "account", "connection", "generation"}:
        field = {
            "workspace": "workspace_id",
            "account": "account_id",
            "connection": "connection_id",
            "generation": "connection_version",
        }[mismatch]
        account = child.account.model_copy(
            update={field: "next" if mismatch == "generation" else 999}
        )
        child = child_copy(child, 2, account=account)
    elif mismatch == "catalog":
        child = child_copy(child, 2, catalog_evidence_key="catalog:other")
    else:
        field = "advertiser_id" if mismatch == "advertiser" else "parent_campaign_id"
        child = child_copy(
            child,
            2,
            provider_reference=child.provider_reference.model_copy(update={field: "9999999999"}),
        )
    # A matching display name cannot attach foreign or unknown-parent metadata.
    assert child.display_name == parent.display_name
    assert observed_child_steps(parent, (child,), ()) == ()


def test_capacity_is_complete_or_explicitly_unavailable() -> None:
    parent, child = refs()
    children = tuple(child_copy(child, n) for n in range(1, 17))
    assert len(observed_child_steps(parent, children[:15], ())) == 15
    with pytest.raises(PlanCompositionUnavailable, match="capacity"):
        observed_child_steps(parent, children, ())
    assert len(observed_child_steps(parent, children, (children[-1].canonical_entity_key,))) == 15
    with pytest.raises(PlanCompositionUnavailable, match="capacity"):
        observed_child_steps(parent, (child, child), ())
    # Defense at the formatter boundary even for an unsafe copied long-name value.
    oversized = child.model_copy(update={"display_name": "x" * 2000})
    with pytest.raises(PlanCompositionUnavailable, match="capacity"):
        observed_child_steps(parent, (oversized,), ())


def test_actual_v4_composition_adds_only_location_step_and_preserves_catalog_citation() -> None:
    ticket, paired, policy = ready()
    plan = compose(ticket, paired, policy)
    parent, child = refs()
    action = next(a for a in plan.actions if a.target == parent)
    assert len(action.manual_steps) == 6
    assert action.manual_steps[-1] == observed_child_steps(parent, (child,), ())[0]
    assert child.catalog_evidence_key in action.evidence_keys
    assert not action.proposed_fields and action.native_budget is None
    # Captured from the unchanged composer at32fb055. Apart from the explicitly
    # added child steps, the complete canonical fixture output is byte-identical.
    previous = plan.model_copy(
        update={
            "actions": tuple(
                a.model_copy(update={"manual_steps": a.manual_steps[:5]}) for a in plan.actions
            )
        }
    )
    assert (
        hashlib.sha256(previous.model_dump_json().encode()).hexdigest()
        == "0d2ded776c017815d1c91633b059a883060dc41e29505e983f65729e19d3d7dd"
    )


@pytest.mark.parametrize("platform,kind", [("meta_ads", "adset"), ("tiktok_ads", "adgroup")])
def test_other_observed_child_kinds_remain_location_only(platform: str, kind: str) -> None:
    parent, child = refs()
    account = parent.account.model_copy(update={"platform": platform})
    parent = TargetRef.model_validate(
        parent.model_copy(
            update={
                "account": account,
                "provider_reference": parent.provider_reference.model_copy(
                    update={"platform": platform}
                ),
            }
        )
    )
    child = TargetRef.model_validate(
        child.model_copy(
            update={
                "account": account,
                "kind": kind,
                "provider_reference": child.provider_reference.model_copy(
                    update={"platform": platform}
                ),
            }
        )
    )
    steps = observed_child_steps(parent, (child,), ())
    assert len(steps) == 1 and f", {kind} 7, parent campaign 1" in steps[0]
    assert "no child change is proposed" in steps[0]
