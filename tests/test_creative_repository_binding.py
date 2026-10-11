"""Private collection identity must match the candidate before any persistence."""

from types import SimpleNamespace
from typing import Any, cast

import pytest
from app.planning_documents import authority, repository
from app.planning_documents.creative_image_collection import CollectedCreativeBasisV1
from app.planning_documents.creative_plan_bundle import CreativePairedEvidenceV1
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from tests.test_creative_plan_composer import compose, ready


def test_candidate_cannot_substitute_private_media_row_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    values = ready()
    ticket, evidence, _, now = values
    candidate = compose(values)
    creative = CollectedCreativeBasisV1.model_validate(
        evidence.creative.model_copy(
            update={
                "rows": (evidence.creative.rows[0].model_copy(update={"created_by": "d" * 32}),)
            }
        )
    )
    bundle = CreativePairedEvidenceV1(reporting=evidence.reporting, creative=creative)
    bundle.assert_ticket(ticket)
    principal = SimpleNamespace(
        user=SimpleNamespace(id=ticket.actor_id),
        session=SimpleNamespace(digest=ticket.session_digest),
    )
    monkeypatch.setattr(authority, "lock", lambda *a: principal)
    monkeypatch.setattr(repository, "receipt", lambda *a: None)
    monkeypatch.setattr(
        repository,
        "owned",
        lambda *a: SimpleNamespace(
            input_head=ticket.inputs.revision, version_head=ticket.expected_version
        ),
    )
    monkeypatch.setattr(repository, "inputs", lambda *a: ticket.inputs)

    def forbidden(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("mismatched private proof must stop before retained capture or writes")

    monkeypatch.setattr(repository, "paid_work", forbidden)
    engine = create_engine("sqlite://")
    try:
        with Session(engine) as db, pytest.raises(HTTPException) as error:
            repository.save_generation(
                db,
                principal=cast(Any, principal),
                fact=cast(Any, None),
                ticket=ticket,
                bundle=bundle,
                candidate=candidate,
                request_key="private-binding",
                request_digest="a" * 64,
                now=now,
                recheck=forbidden,
            )
        assert error.value.status_code == 409
        assert error.value.detail == "candidate creative proof differs from actual read bundle"
    finally:
        engine.dispose()


@pytest.mark.parametrize("images", [0, 1])
def test_candidate_cannot_predate_original_collection(
    monkeypatch: pytest.MonkeyPatch, images: int
) -> None:
    from app.planning_documents.documents import PlanVersion

    values = ready(images=images)
    ticket, bundle, _, now = values
    candidate = PlanVersion.model_validate(
        compose(values).model_copy(update={"generated_at": ticket.prepared_at})
    )

    def forbidden(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("timestamp gate must reject before authority or writes")

    monkeypatch.setattr(authority, "lock", forbidden)
    engine = create_engine("sqlite://")
    try:
        with Session(engine) as db, pytest.raises(HTTPException) as error:
            repository.save_generation(
                db,
                principal=cast(Any, None),
                fact=cast(Any, None),
                ticket=ticket,
                bundle=bundle,
                candidate=candidate,
                request_key="timestamp-binding",
                request_digest="b" * 64,
                now=now,
                recheck=forbidden,
            )
        assert error.value.status_code == 409
        assert error.value.detail == "candidate generation predates original creative collection"
    finally:
        engine.dispose()
