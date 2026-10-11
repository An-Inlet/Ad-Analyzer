"""Complete v5 history, never runtime activation or current image authorization."""

from datetime import timedelta
from typing import Any

import pytest
from app.planning_documents.creative_history import (
    creative_local_witness,
    validate_creative_local_dependency,
)
from app.planning_documents.documents import PlanVersion
from app.planning_documents.models import PlanDependencyRow
from app.planning_documents.retained_sources import RetainedSourceWitness
from app.planning_documents.selected_plan_history import validate_selected_historical_dependencies

from tests.test_creative_plan_composer import compose, ready
from tests.test_selected_plan_history import dependencies as old_dependencies
from tests.test_selected_plan_proof import none_document


def rows(document: PlanVersion) -> list[PlanDependencyRow]:
    common = dict(
        workspace_id=document.inputs.workspace_id,
        plan_id=document.inputs.plan_id,
        version=document.version,
    )
    result = [
        PlanDependencyRow(
            **common,
            evidence_key=ref.key,
            account_id=ref.account.account_id if ref.account else None,
            connection_id=ref.account.connection_id if ref.account else None,
            store_id=document.inputs.goal.definition.store_id
            if ref.kind == "shopify_measurement"
            else None,
            kind=ref.kind,
            source_binding_digest=ref.source_binding_digest,
            document_digest=ref.document_digest,
            source_revision=ref.source_revision,
            observed_at=ref.observed_at,
            expires_at=ref.expires_at,
            privacy_revision=ref.privacy_revision,
        )
        for ref in document.evidence
    ]
    proof = document.selected_reporting_proof
    assert proof is not None
    for account in proof.accounts:
        fence = account.source_fence
        result.append(
            PlanDependencyRow(
                **common,
                evidence_key=f"local:reporting:{fence.account.account_id}",
                account_id=fence.account.account_id,
                connection_id=fence.account.connection_id,
                store_id=None,
                kind="local_reporting_v3",
                source_binding_digest=fence.source_binding_digest,
                document_digest=account.state_digest(),
                source_revision=fence.source_revision,
                observed_at=document.generated_at,
                expires_at=document.valid_until,
                privacy_revision=fence.privacy_revision,
            )
        )
    result.append(
        PlanDependencyRow(
            **common,
            evidence_key=f"local:commerce:{document.inputs.goal.definition.store_id}",
            account_id=None,
            connection_id=None,
            store_id=document.inputs.goal.definition.store_id,
            kind="local_commerce_v1",
            source_binding_digest="1" * 64,
            document_digest="2" * 64,
            source_revision="1",
            observed_at=document.generated_at,
            expires_at=document.valid_until,
            privacy_revision=document.evidence[0].privacy_revision,
        )
    )
    result.append(PlanDependencyRow(**creative_local_witness(document).model_dump()))
    return result


@pytest.mark.parametrize("images", [0, 1, 2])
def test_complete_document_and_empty_basis(images: int) -> None:
    document = compose(ready(images=images))
    dependencies = rows(document)
    witness = creative_local_witness(document)
    assert document.creative_proof is not None
    assert witness.document_digest == document.creative_proof.digest()
    assert witness.observed_at == document.generated_at
    validate_creative_local_dependency(document, dependencies)
    assert validate_selected_historical_dependencies(document, dependencies) == ()
    assert RetainedSourceWitness.model_validate_json(witness.model_dump_json()) == witness
    with pytest.raises(ValueError):
        validate_selected_historical_dependencies(document, dependencies[:-1])


@pytest.mark.parametrize(
    "field,value",
    [
        ("workspace_id", 999),
        ("plan_id", "f" * 32),
        ("version", 9),
        ("privacy_revision", 999),
        ("account_id", 999),
        ("connection_id", 999),
        ("store_id", "f" * 32),
        ("evidence_key", "local:creative:other"),
        ("kind", "local_commerce_v1"),
        ("source_binding_digest", "f" * 64),
        ("document_digest", "f" * 64),
        ("source_revision", "wrong"),
        ("observed_at", None),
        ("expires_at", None),
    ],
)
def test_complete_creative_row_exact(field: str, value: Any) -> None:
    document = compose(ready(images=2))
    dependencies = rows(document)
    if field in {"observed_at", "expires_at"}:
        value = getattr(dependencies[-1], field) + timedelta(seconds=1)
    setattr(dependencies[-1], field, value)
    with pytest.raises(ValueError):
        validate_selected_historical_dependencies(document, dependencies)


@pytest.mark.parametrize(
    "attack", ["extra", "duplicate", "extra_kind", "reordered", "creator", "created"]
)
def test_complete_set_and_image_commitments(attack: str) -> None:
    values = ready(images=2)
    document = compose(values)
    dependencies = rows(document)
    if attack in {"extra", "duplicate", "extra_kind"}:
        extra = rows(document)[-1]
        if attack == "extra":
            extra.evidence_key, extra.kind = "unrecognized", "unrecognized"
        elif attack == "extra_kind":
            extra.evidence_key = "local:creative:extra"
        dependencies.append(extra)
    else:
        ticket, evidence, policy, now = values
        pins = evidence.creative.rows
        if attack == "reordered":
            # Exact reordered input changes full document and must reject old dependencies.
            requested = ticket.inputs.creative.model_copy(
                update={
                    "media_selections": tuple(reversed(ticket.inputs.creative.media_selections))
                }
            )
            ticket = ticket.model_copy(
                update={"inputs": ticket.inputs.model_copy(update={"creative": requested})}
            )
            # Reordering the retained row hash alone already violates basis/image order.
            proof = document.creative_proof
            assert proof is not None
            with pytest.raises(ValueError):
                type(proof).model_validate(
                    proof.model_copy(update={"images": tuple(reversed(proof.images))})
                )
            return
        pin = pins[0]
        if attack == "creator":
            pin = pin.model_copy(update={"created_by": "f" * 32})
        else:
            pin = pin.model_copy(
                update={
                    "witness": pin.witness.model_copy(
                        update={"created_at": pin.witness.created_at - timedelta(seconds=1)}
                    )
                }
            )
        creative = evidence.creative.model_copy(
            update={
                "rows": (pin, *pins[1:]),
                "basis": evidence.creative.basis.model_copy(
                    update={"images": (pin.witness, *evidence.creative.basis.images[1:])}
                ),
            }
        )
        document = compose(
            (ticket, evidence.model_copy(update={"creative": creative}), policy, now)
        )
    with pytest.raises(ValueError):
        validate_selected_historical_dependencies(document, dependencies)


def test_v4_bytes_and_complete_dependencies_unchanged() -> None:
    doc = none_document()
    before = doc.model_dump_json(), doc.digest()
    assert validate_selected_historical_dependencies(doc, old_dependencies()) == ()
    assert before == (doc.model_dump_json(), doc.digest())
    with pytest.raises(ValueError):
        creative_local_witness(doc)
    with pytest.raises(ValueError):
        validate_selected_historical_dependencies(
            doc, old_dependencies() + [rows(compose(ready()))[-1]]
        )


@pytest.mark.parametrize(
    "field,value",
    [("account_id", 1), ("connection_id", 1), ("store_id", "f" * 32), ("evidence_key", "wrong")],
)
def test_creative_witness_scope_never_adopts_source_fields(field: str, value: Any) -> None:
    witness = creative_local_witness(compose(ready(images=0)))
    with pytest.raises(ValueError):
        RetainedSourceWitness.model_validate(witness.model_copy(update={field: value}))


def test_standalone_import_cycle_safe() -> None:
    import subprocess
    import sys

    subprocess.run(
        [
            sys.executable,
            "-c",
            "import app.planning_documents.creative_history; "
            "import app.planning_documents.selected_plan_history",
        ],
        check=True,
    )
