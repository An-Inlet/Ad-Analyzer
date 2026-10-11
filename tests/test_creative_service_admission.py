"""SQL metadata admission is not image observation or generation authority."""

from datetime import UTC, datetime
from pathlib import Path

import pytest
from app.campaign_review.models import MediaObject
from app.campaign_review.storage import LocalMediaStore
from app.planning_documents.creative_basis import CreativeInputV1, PlanningMediaSelectionV1
from app.planning_documents.creative_composition import canonical_creative_policy
from app.planning_documents.policy_capabilities import ticket_reporting_capability
from app.planning_documents.repository import check_creative_media_references
from app.planning_documents.service import PlanningDocumentService
from app.workspaces.models import Workspace
from fastapi import HTTPException
from sqlalchemy import Engine, create_engine, select
from sqlalchemy.orm import Session

from tests.test_customer_identity import FakeProvider
from tests.test_customer_identity import customer_engine as customer_engine


def test_explicit_store_canonical_policy_and_unchanged_default(tmp_path: Path) -> None:
    engine = create_engine("sqlite://")
    policy = canonical_creative_policy()
    try:
        assert PlanningDocumentService(engine, FakeProvider()).policy.version.endswith(".v3")
        with pytest.raises(ValueError, match="explicit creative media store"):
            PlanningDocumentService(engine, FakeProvider(), policy=policy)
        service = PlanningDocumentService(
            engine, FakeProvider(), policy=policy, media_store=LocalMediaStore(tmp_path)
        )
        assert service.policy == policy
        assert (
            ticket_reporting_capability(policy.version, policy.digest()).mode
            == "creative_selected_requested_window"
        )
        with pytest.raises(ValueError):
            PlanningDocumentService(
                engine,
                FakeProvider(),
                policy=policy.model_copy(update={"max_actions": 1}),
                media_store=LocalMediaStore(tmp_path),
            )
    finally:
        engine.dispose()


@pytest.mark.parametrize("mode", ["owned", "empty", "missing", "foreign", "hash_changed"])
def test_owned_media_admission(customer_engine: Engine, mode: str) -> None:
    with Session(customer_engine) as db, db.begin():
        a = Workspace(slug="admission-a", name="A", client_name="A")
        b = Workspace(slug="admission-b", name="B", client_name="B")
        db.add_all([a, b])
        db.flush()
        row = MediaObject(
            id="a" * 32,
            workspace_id=b.id if mode == "foreign" else a.id,
            sha256="b" * 64,
            size=1,
            mime="image/png",
            width=1,
            height=1,
            created_by="c" * 32,
            created_at=datetime.now(UTC),
        )
        db.add(row)
        db.flush()
        wid = a.id
    creative = CreativeInputV1(
        media_selections=()
        if mode == "empty"
        else (
            PlanningMediaSelectionV1(
                media_id="d" * 32 if mode == "missing" else "a" * 32,
                expected_sha256="e" * 64 if mode == "hash_changed" else "b" * 64,
            ),
        )
    )
    with Session(customer_engine) as db, db.begin():
        # Actual caller lock order: workspace first, then selected media IDs.
        db.scalar(select(Workspace).where(Workspace.id == wid).with_for_update())
        if mode in ("owned", "empty"):
            check_creative_media_references(db, wid, creative)
        else:
            with pytest.raises(HTTPException) as error:
                check_creative_media_references(db, wid, creative)
            assert error.value.status_code == 409
            assert error.value.detail == "selected creative media unavailable"
        assert not db.new and not db.dirty and not db.deleted
