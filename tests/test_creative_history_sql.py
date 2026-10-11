"""Standalone v5 history over real reporting/media; direct storage, no v5 runtime."""

import io
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from app.billing.models import WorkspaceBilling
from app.campaign_performance.range_receipt_models import RangeReceiptRow
from app.campaign_performance.selected_models import SelectedFactRow
from app.campaign_review.models import MediaObject
from app.campaign_review.service import upload
from app.campaign_review.storage import LocalMediaStore
from app.lifecycle.privacy import bump_workspace_export_revision
from app.planning_documents import selected_plan_history as history
from app.planning_documents.creative_basis import CreativeInputV1, PlanningMediaSelectionV1
from app.planning_documents.creative_basis_reader import OwnedPlanningImageReader
from app.planning_documents.creative_composition import canonical_creative_policy
from app.planning_documents.creative_plan_bundle import CreativePairedEvidenceV1
from app.planning_documents.creative_plan_composer import CreativePlanComposer
from app.planning_documents.models import PlanDependencyRow, PlanInputRow, PlanRow, PlanVersionRow
from app.planning_documents.ports import GenerationTicket
from app.planning_documents.retained_sources import commerce_witness
from app.planning_documents.selected_paired_reader import OwnedSelectedPairedReader
from app.planning_documents.storage import canonical
from app.settings import Settings
from PIL import Image
from sqlalchemy import Engine, delete, func, select, update
from sqlalchemy.orm import Session

from tests.selected_range_plan_fixture import prepared_range_plan
from tests.test_campaign_review import png
from tests.test_creative_history import rows
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_shopify_sales import configuration as configuration


def stored(
    engine: Engine,
    config: Settings,
    replicas: Any,
    patch: pytest.MonkeyPatch,
    path: Path,
    request: pytest.FixtureRequest,
    *,
    image_count: int = 1,
) -> Any:
    old, ticket, f, _, _ = prepared_range_plan(engine, config, replicas, patch)
    request.addfinalizer(f.alice.close)
    request.addfinalizer(f.bob.close)
    store = LocalMediaStore(path)
    selections = []
    for index in range(image_count):
        data = png()
        if index:
            stream = io.BytesIO()
            Image.new("RGB", (4, 4), (index, 100, 0)).save(stream, "PNG")
            data = stream.getvalue()
        with Session(engine) as db:
            media = upload(
                db, ticket.inputs.workspace_id, ticket.actor_id, data, store, datetime.now(UTC)
            )
            selections.append(
                PlanningMediaSelectionV1(media_id=media.id, expected_sha256=media.sha256)
            )
    policy = canonical_creative_policy()
    ticket = GenerationTicket.model_validate(
        ticket.model_copy(
            update={
                "inputs": ticket.inputs.model_copy(
                    update={"creative": CreativeInputV1(media_selections=tuple(selections))}
                ),
                "policy_version": policy.version,
                "policy_digest": policy.digest(),
            }
        )
    )
    paired = OwnedSelectedPairedReader(
        old.sessions, principal=old.principal, provider=old.provider, policy=policy, clock=old.clock
    ).collect(ticket)
    assert ticket.inputs.creative is not None
    collection = OwnedPlanningImageReader(
        old.sessions, principal=old.principal, provider=old.provider, store=store, clock=old.clock
    ).collect_pinned(ticket, ticket.inputs.creative)
    document = CreativePlanComposer().compose(
        ticket=ticket,
        evidence=CreativePairedEvidenceV1(reporting=paired, creative=collection),
        policy=policy,
        generated_at=datetime.now(UTC),
    )
    inputs = document.inputs
    dependencies = rows(document)
    with Session(engine) as db, db.begin():
        # Genuine commerce commitment; reporting commitments are the actual collected proof.
        common = dict(
            workspace_id=inputs.workspace_id,
            plan_id=inputs.plan_id,
            version=document.version,
            observed_at=document.generated_at,
            expires_at=document.valid_until,
            privacy_revision=ticket.privacy_revision,
        )
        witness = commerce_witness(
            db, principal=old.principal, document=document, common=common, now=datetime.now(UTC)
        )
        dependencies[-2] = PlanDependencyRow(**witness.model_dump())
        db.add(
            PlanRow(
                workspace_id=inputs.workspace_id,
                id=inputs.plan_id,
                input_head=1,
                version_head=1,
                event_sequence=0,
                created_by=inputs.created_by,
                created_at=inputs.created_at,
            )
        )
        db.flush()
        db.add(
            PlanInputRow(
                workspace_id=inputs.workspace_id,
                plan_id=inputs.plan_id,
                revision=1,
                goal_id=inputs.goal.goal_id,
                goal_revision=inputs.goal.revision,
                confirmed_preview_id=inputs.goal.confirmation_reference,
                definition_digest=inputs.goal.definition_digest,
                canonical_json=canonical(inputs),
                digest=inputs.digest(),
                actor_id=inputs.created_by,
                created_at=inputs.created_at,
            )
        )
        db.flush()
        db.add(
            PlanVersionRow(
                workspace_id=inputs.workspace_id,
                plan_id=inputs.plan_id,
                version=1,
                input_revision=1,
                parent_digest=None,
                canonical_json=canonical(document),
                digest=document.digest(),
                generator_version=document.generator_version,
                policy_version=document.policy_version,
                actor_id=document.generated_by,
                generated_at=document.generated_at,
                valid_until=document.valid_until,
                privacy_revision=ticket.privacy_revision,
            )
        )
        db.flush()
        db.add_all(dependencies)
    return document, store, old, f


@pytest.mark.parametrize("change", ["metadata_and_bytes", "capture", "traffic"])
def test_real_historical_graph_and_independent_media_loss(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    change: str,
    request: pytest.FixtureRequest,
) -> None:
    document, store, reader, f = stored(
        customer_engine, configuration, replicas, monkeypatch, tmp_path, request
    )
    before = document.model_dump_json(), document.digest()
    with Session(customer_engine) as db, db.begin():
        history.validate_selected_plan_history(db, document)

    def forbidden(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError(
            "historical validation must not inspect bytes/provider/paid entitlement"
        )

    monkeypatch.setattr(store, "read_exact", forbidden)
    monkeypatch.setattr(reader.provider, "check_active", forbidden)
    # Cancel entitlement without semantic erasure; historical validation is still allowed.
    with Session(customer_engine) as db, db.begin():
        db.execute(
            update(WorkspaceBilling)
            .where(WorkspaceBilling.workspace_id == f.wid)
            .values(status="canceled")
        )
        if change == "metadata_and_bytes":
            db.execute(delete(MediaObject).where(MediaObject.workspace_id == f.wid))
            for path in tmp_path.rglob("*"):
                if path.is_file():
                    path.unlink()
        elif change == "capture":
            db.execute(delete(SelectedFactRow).where(SelectedFactRow.workspace_id == f.wid))
        else:
            db.execute(delete(RangeReceiptRow).where(RangeReceiptRow.workspace_id == f.wid))
    with Session(customer_engine) as db, db.begin():
        if change == "metadata_and_bytes":
            history.validate_selected_plan_history(db, document)
            assert before == (document.model_dump_json(), document.digest())
        else:
            with pytest.raises(ValueError):
                history.validate_selected_plan_history(db, document)
    if change == "metadata_and_bytes":
        with Session(customer_engine) as db, db.begin():
            bump_workspace_export_revision(db, f.wid)
        with Session(customer_engine) as db, db.begin():
            assert (
                db.scalar(
                    select(func.count())
                    .select_from(PlanDependencyRow)
                    .where(PlanDependencyRow.workspace_id == f.wid)
                )
                == 0
            )
            with pytest.raises(ValueError):
                history.validate_selected_plan_history(db, document)
    f.alice.close()
    f.bob.close()


@pytest.mark.parametrize("version", [4, 5])
def test_sql_fetch_preserves_overflow_sentinel(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    version: int,
    request: pytest.FixtureRequest,
) -> None:
    if version == 5:
        document, _, _, f = stored(
            customer_engine, configuration, replicas, monkeypatch, tmp_path, request
        )
    else:
        from tests.test_selected_plan_history_read_export import stored_fixture

        document, _ = stored_fixture(customer_engine, configuration, replicas, monkeypatch)
        f = None
    scope = (
        PlanDependencyRow.workspace_id == document.inputs.workspace_id,
        PlanDependencyRow.plan_id == document.inputs.plan_id,
    )
    with Session(customer_engine) as db, db.begin():
        count = db.scalar(select(func.count()).select_from(PlanDependencyRow).where(*scope))
        assert isinstance(count, int)
        # Move only engineering constants down to the actual fixture cardinality.
        # The exact allowed count passes; one SQL overflow row must still be fetched.
        monkeypatch.setattr(history, "MAX_ACCOUNTS", 0)
        monkeypatch.setattr(history, "MAX_EVIDENCE", count - 1 - int(version == 5))
        history.validate_selected_plan_history(db, document)
        row = db.scalar(select(PlanDependencyRow).where(*scope))
        assert row is not None
        extra = {c.name: getattr(row, c.name) for c in row.__table__.columns}
        extra["evidence_key"] = "zz:overflow"
        db.add(PlanDependencyRow(**extra))
    with (
        Session(customer_engine) as db,
        db.begin(),
        pytest.raises(ValueError, match="selected historical proof required"),
    ):
        history.validate_selected_plan_history(db, document)
    if f:
        f.alice.close()
        f.bob.close()
