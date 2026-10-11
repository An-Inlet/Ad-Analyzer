"""Synthetic pure v5 document values, not observed ownership or runtime qualification."""

from datetime import timedelta
from typing import Any, cast

import pytest
from app.planning_documents.actions import BudgetScenario
from app.planning_documents.context import EvidenceRef, PlanInputRevision
from app.planning_documents.creative_basis import CreativeBasisV1, CreativeInputV1
from app.planning_documents.creative_composition import canonical_creative_policy
from app.planning_documents.creative_plan_document import creative_basis_reference
from app.planning_documents.creative_retained_proof import CreativeRetainedProofV1
from app.planning_documents.documents import PlanVersion
from app.planning_documents.policy_capabilities import reporting_capability
from app.planning_documents.selected_plan_proof import SelectedRetainedProofV1

from tests.test_creative_composition import compose, ready


def document_values(platform: str = "meta", *, empty: bool = False) -> dict[str, Any]:
    inputs, catalogs, raw = ready(platform, images=0 if empty else 1)
    requested = CreativeInputV1() if empty else raw.requested
    inputs = PlanInputRevision.model_validate(
        {**inputs.model_dump(), "creative": requested, "selected_reporting": ()}
    )
    basis = CreativeBasisV1.model_validate(
        {
            **raw.model_dump(),
            "requested": requested,
            "images": tuple(
                image.model_copy(
                    update={"created_at": inputs.created_at, "observed_at": inputs.created_at}
                )
                for image in raw.images
            ),
        }
    )
    proof = CreativeRetainedProofV1(
        basis=basis,
        images=tuple(
            dict(media_id=image.media_id, row_identity_digest="d" * 64) for image in basis.images
        ),
    )
    composition = compose(inputs, catalogs, basis)
    policy = canonical_creative_policy()
    now = max(c.reference.observed_at for c in catalogs) + timedelta(seconds=1)
    until = min(c.reference.expires_at for c in catalogs)
    creative = creative_basis_reference(proof, inputs, until)
    contexts = tuple(
        EvidenceRef.model_validate(
            {
                **creative.model_dump(),
                "key": key,
                "kind": kind,
                "document_digest": doc.digest(),
                "source_binding_digest": doc.digest(),
            }
        )
        for key, kind, doc in (
            ("context:inputs", "customer_context", inputs),
            ("context:policy", "planning_policy", policy),
        )
    )
    reporting = SelectedRetainedProofV1(
        accounts=tuple(
            dict(
                source_fence=dict(
                    account=c.reference.account,
                    source_binding_digest=c.reference.source_binding_digest,
                    source_revision=c.reference.account.connection_version,
                    privacy_revision=c.reference.privacy_revision,
                ),
                legacy_reporting_digest="a" * 64,
                selection_head=None,
                capture_pin=None,
            )
            for c in catalogs
        )
    )
    return dict(
        inputs=inputs,
        version=1,
        parent_digest=None,
        generator_version=policy.generator_version,
        policy_version=policy.version,
        readiness="reviewable",
        section_limitations=(),
        generated_by="a" * 32,
        generated_at=now,
        valid_until=until,
        evidence=tuple(c.reference for c in catalogs) + contexts + (creative,),
        actions=tuple(p.action for p in composition.proposals),
        briefs=tuple(p.brief for p in composition.proposals),
        scenarios=(
            BudgetScenario(
                key="retain",
                title="Retain Budget",
                period=inputs.budget_period,
                ceiling_micros=inputs.total_ceiling_micros,
                allocations=(),
                unallocated_micros=inputs.total_ceiling_micros,
                assumptions=(),
            ),
        ),
        summary="Typed creative proposal; production and customer review required.",
        limitations=("No empirical or live qualification.",),
        selected_reporting_proof=reporting,
        creative_proof=proof,
        creative_composition=composition,
    )


@pytest.mark.parametrize("platform", ["meta", "tiktok"])
@pytest.mark.parametrize("empty", [False, True])
def test_full_genuine_document(platform: str, empty: bool) -> None:
    doc = PlanVersion(**document_values(platform, empty=empty))
    assert PlanVersion.model_validate_json(doc.model_dump_json()) == doc
    assert doc.creative_proof is not None and doc.creative_composition is not None
    assert len(doc.creative_composition.proposals) == (0 if empty else 1)
    assert not doc.advertising_writes_enabled
    assert (
        reporting_capability(doc.policy_version, doc.generator_version).mode
        == "creative_selected_requested_window"
    )


@pytest.mark.parametrize(
    "field", ["creative_proof", "creative_composition", "selected_reporting_proof"]
)
def test_missing_required_proof(field: str) -> None:
    values = document_values()
    values.pop(field)
    with pytest.raises(ValueError):
        PlanVersion(**values)


@pytest.mark.parametrize(
    "attack",
    [
        "missing_ref",
        "extra_ref",
        "ref_hash",
        "ref_scope",
        "ref_time",
        "proof_hash",
        "privacy",
        "action",
        "brief",
        "extra_action",
        "extra_brief",
        "basis_key",
        "capacity",
        "unknown_capacity",
        "mixed",
        "legacy",
        "excluded",
        "foreign",
        "dropped_action",
        "dropped_brief",
        "composition_digest",
    ],
)
def test_exact_document_bindings(attack: str) -> None:
    v = document_values()
    proof, comp = v["creative_proof"], v["creative_composition"]
    refs = list(v["evidence"])
    if attack == "missing_ref":
        v["evidence"] = tuple(refs[:-1])
    elif attack == "extra_ref":
        v["evidence"] += (refs[-1].model_copy(update={"key": "creative:extra"}),)
    elif attack.startswith("ref_"):
        changes = {
            "ref_hash": dict(document_digest="0" * 64),
            "ref_scope": dict(account=v["inputs"].accounts[0]),
            "ref_time": dict(observed_at=v["generated_at"] + timedelta(seconds=1)),
        }
        v["evidence"] = (*refs[:-1], refs[-1].model_copy(update=changes[attack]))
    elif attack == "proof_hash":
        v["creative_proof"] = proof.model_copy(
            update={
                "images": (proof.images[0].model_copy(update={"row_identity_digest": "0" * 64}),)
            }
        )
    elif attack == "privacy":
        v["creative_proof"] = proof.model_copy(
            update={"basis": proof.basis.model_copy(update={"privacy_revision": 1})}
        )
    elif attack in {"action", "brief"}:
        key = "actions" if attack == "action" else "briefs"
        field = "title" if attack == "action" else "objective"
        v[key] = (v[key][0].model_copy(update={field: "Changed"}),)
    elif attack in {"extra_action", "extra_brief"}:
        key = "actions" if attack == "extra_action" else "briefs"
        v[key] += (
            v[key][0].model_copy(
                update={"key": "extra:creative", **({"priority": 2} if key == "actions" else {})}
            ),
        )
    elif attack == "basis_key":
        proposal = comp.proposals[0]
        v["creative_composition"] = comp.model_copy(
            update={
                "proposals": (
                    proposal.model_copy(
                        update={
                            "production": proposal.production.model_copy(
                                update={"basis_evidence_key": "context:inputs"}
                            )
                        }
                    ),
                )
            }
        )
    elif attack in {"capacity", "unknown_capacity"}:
        v["inputs"] = v["inputs"].model_copy(
            update={"maximum_creative_assets": 0 if attack == "capacity" else None}
        )
    elif attack in {"mixed", "legacy"}:
        v["generator_version"] = "inlet.descriptive-planning.v4"
        if attack == "legacy":
            v["policy_version"] = "inlet.descriptive-review.v4"
            v["inputs"] = v["inputs"].model_copy(update={"creative": None})
    elif attack == "foreign":
        proposal = comp.proposals[0]
        account = proposal.action.target.account.model_copy(update={"account_id": 999})
        target = proposal.action.target.model_copy(update={"account": account})
        action = proposal.action.model_copy(
            update={"target": target, "key": "creative:account_999"}
        )
        brief = proposal.brief.model_copy(
            update={"target": target, "key": "brief:account_999", "action_key": action.key}
        )
        v["creative_composition"] = comp.model_copy(
            update={"proposals": (proposal.model_copy(update={"action": action, "brief": brief}),)}
        )
        v["actions"], v["briefs"] = (action,), (brief,)
    elif attack in {"dropped_action", "dropped_brief"}:
        v["actions" if attack == "dropped_action" else "briefs"] = ()
    elif attack == "composition_digest":
        v["creative_composition"] = comp.model_copy(update={"basis_digest": "0" * 64})
    else:
        assert attack == "excluded"
        v["inputs"] = v["inputs"].model_copy(
            update={"excluded_entity_keys": (v["actions"][0].target.canonical_entity_key,)}
        )
    with pytest.raises(ValueError):
        PlanVersion(**v)


def test_legacy_explicit_null_fields_omit_without_digest_change() -> None:
    from tests.test_selected_planning_inputs import models

    old, _, _ = models()
    before = old.model_dump_json(), old.digest()
    parsed = PlanVersion.model_validate(
        {**old.model_dump(), "creative_proof": None, "creative_composition": None}
    )
    assert (parsed.model_dump_json(), parsed.digest()) == before
    assert "creative_proof" not in parsed.model_dump()
    assert "creative_composition" not in parsed.model_dump()


def test_helper_revalidates_copied_values() -> None:
    v = document_values()
    with pytest.raises(ValueError):
        creative_basis_reference(
            v["creative_proof"].model_copy(update={"images": ()}), v["inputs"], v["valid_until"]
        )
    for invalid in (True, 1, "not-a-date"):
        with pytest.raises(ValueError):
            creative_basis_reference(v["creative_proof"], v["inputs"], cast(Any, invalid))


def fold_values() -> dict[str, Any]:
    from datetime import datetime
    from zoneinfo import ZoneInfo

    zone = ZoneInfo("America/New_York")
    v = document_values(empty=True)
    created = datetime(2026, 11, 1, 1, 0, tzinfo=zone, fold=0)
    observed = datetime(2026, 11, 1, 1, 5, tzinfo=zone, fold=0)
    v["inputs"] = PlanInputRevision.model_validate(
        v["inputs"].model_copy(update={"created_at": created})
    )
    v["generated_at"] = datetime(2026, 11, 1, 1, 50, tzinfo=zone, fold=0)
    v["valid_until"] = datetime(2026, 11, 1, 1, 20, tzinfo=zone, fold=1)
    refs = []
    for ref in v["evidence"][:-1]:
        update = dict(
            observation_started_at=created, observed_at=observed, expires_at=v["valid_until"]
        )
        if ref.kind == "customer_context":
            update.update(
                document_digest=v["inputs"].digest(), source_binding_digest=v["inputs"].digest()
            )
        refs.append(ref.model_copy(update=update))
    v["evidence"] = (
        *refs,
        creative_basis_reference(v["creative_proof"], v["inputs"], v["valid_until"]),
    )
    return v


def test_v5_valid_dst_fold_uses_real_instants() -> None:
    from datetime import UTC

    doc = PlanVersion(**fold_values())
    assert doc.generated_at < doc.valid_until
    assert doc.generated_at.tzinfo is UTC
    assert all(ref.expires_at.tzinfo is UTC for ref in doc.evidence)
    restored = PlanVersion.model_validate_json(doc.model_dump_json())
    # Saved inputs retain their original timezone representation. Python's
    # ambiguous ZoneInfo fold equality differs from a parsed fixed offset;
    # the serialized immutable document and digest must remain exact.
    assert restored.model_dump_json() == doc.model_dump_json()
    assert restored.digest() == doc.digest()


@pytest.mark.parametrize("attack", ["input", "observed", "start", "expiry", "validity"])
def test_dst_fold_instant_inversions_reject(attack: str) -> None:
    from datetime import datetime
    from zoneinfo import ZoneInfo

    zone = ZoneInfo("America/New_York")
    v = fold_values()
    later = datetime(2026, 11, 1, 1, 10, tzinfo=zone, fold=1)
    if attack == "input":
        v["inputs"] = v["inputs"].model_copy(update={"created_at": later})
        v["evidence"] = (
            *v["evidence"][:-1],
            creative_basis_reference(v["creative_proof"], v["inputs"], v["valid_until"]),
        )
    elif attack == "validity":
        v["generated_at"], v["valid_until"] = later, v["generated_at"]
    else:
        changes = {
            "observed": dict(observed_at=later),
            "start": dict(observation_started_at=later),
            "expiry": dict(expires_at=datetime(2026, 11, 1, 1, 30, tzinfo=zone, fold=0)),
        }
        v["evidence"] = (v["evidence"][0].model_copy(update=changes[attack]), *v["evidence"][1:])
    with pytest.raises(ValueError):
        PlanVersion(**v)


def test_pure_module_import_order() -> None:
    import subprocess
    import sys

    for first, second in (
        ("documents", "creative_plan_document"),
        ("creative_plan_document", "documents"),
    ):
        subprocess.run(
            [
                sys.executable,
                "-c",
                f"import app.planning_documents.{first}; import app.planning_documents.{second}",
            ],
            capture_output=True,
            check=True,
            timeout=30,
        )


def legacy_documents() -> tuple[PlanVersion, ...]:
    from app.planning_documents.ports import (
        ContextEvidence,
        PlanningCompositionPolicy,
        ReportingPresencePin,
    )

    from tests.test_planning_composer import compose as legacy_compose
    from tests.test_planning_composer import fixture
    from tests.test_selected_paired_composer import compose as selected_compose
    from tests.test_selected_paired_composer import ready as selected_ready
    from tests.test_window_composer import compose as window_compose
    from tests.test_window_evidence_contract import ready as window_ready

    inputs, bundle, policy = fixture()
    first = legacy_compose(inputs, bundle, policy)
    second_policy = PlanningCompositionPolicy(
        version="inlet.descriptive-review.v2", generator_version="inlet.descriptive-planning.v2"
    )
    contexts = tuple(
        ContextEvidence(
            reference=item.reference.model_copy(update={"document_digest": second_policy.digest()}),
            document=second_policy,
        )
        if item.reference.kind == "planning_policy"
        else item
        for item in bundle.context
    )
    qualified = type(bundle).model_validate(
        bundle.model_copy(
            update={
                "context": contexts,
                "performance": (),
                "reporting_pins": tuple(
                    ReportingPresencePin(account=a, document_digest="d" * 64)
                    for a in inputs.accounts
                ),
            }
        )
    )
    second = legacy_compose(inputs, qualified, second_policy)
    ticket, evidence = window_ready()
    third = window_compose(ticket, evidence)
    fourth = selected_compose(*selected_ready())
    return first, second, third, fourth


def test_all_canonical_legacy_null_fields_preserve_bytes() -> None:
    for version, old in enumerate(legacy_documents(), 1):
        assert old.policy_version == f"inlet.descriptive-review.v{version}"
        restored = PlanVersion.model_validate(
            {**old.model_dump(), "creative_proof": None, "creative_composition": None}
        )
        assert restored.model_dump_json() == old.model_dump_json()
        assert restored.digest() == old.digest()
