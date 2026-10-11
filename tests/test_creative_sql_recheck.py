"""Real owned inspection followed by SQL-only recheck, with no runtime activation."""

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from app.billing.models import WorkspaceBilling
from app.campaign_review.models import MediaObject
from app.customers.models import CustomerMembership, CustomerSession
from app.goals.models import Goal
from app.lifecycle.privacy import bump_workspace_export_revision
from app.planning_documents.creative_basis import CreativeInputV1
from app.planning_documents.creative_finalization import recheck_collected_creative
from app.planning_documents.creative_retained_proof import (
    creative_image_row_identity_digest,
    creative_proof_from_collection,
)
from app.planning_documents.read_context import PlanningReadContexts
from app.settings import Settings
from fastapi import HTTPException
from sqlalchemy import Engine, delete, update
from sqlalchemy.orm import Session

from tests.test_creative_image_collection import envelope, saved
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_owned_planning_images import prepared
from tests.test_shopify_sales import configuration as configuration


def ready(
    engine: Engine,
    config: Settings,
    replicas: Any,
    patch: pytest.MonkeyPatch,
    path: Path,
    *,
    empty: bool = False,
) -> Any:
    reader, ticket, requested, mid, calls = prepared(engine, config, replicas, patch, path)
    if empty:
        requested = CreativeInputV1()
    ticket = saved(ticket, requested)
    collection = reader.collect_pinned(ticket, requested)
    reads = PlanningReadContexts(
        reader.sessions,
        reader.principal,
        reader.provider,
        ticket.inputs.workspace_id,
        ticket.actor_id,
    )
    return reader, ticket, collection, mid, calls, reads


def test_row_digest_preserves_original_factory_bytes() -> None:
    from app.planning_documents.common import fingerprint

    collection, ticket = envelope()
    proof = creative_proof_from_collection(collection, ticket)
    for pin, commitment in zip(collection.rows, proof.images, strict=True):
        expected = fingerprint(
            "creative-image-row-identity.v1",
            {
                key: value.isoformat() if isinstance(value, datetime) else value
                for key, value in pin.identity().items()
            },
        )
        assert creative_image_row_identity_digest(pin) == commitment.row_identity_digest == expected
        with pytest.raises(ValueError):
            creative_image_row_identity_digest(pin.model_copy(update={"created_by": 42}))


@pytest.mark.parametrize("empty", [False, True])
def test_actual_collection_recheck_no_io_preserves_time(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    empty: bool,
) -> None:
    reader, ticket, collection, _, calls, reads = ready(
        customer_engine, configuration, replicas, monkeypatch, tmp_path, empty=empty
    )
    original = reader.provider.check_active

    def active(*args: Any) -> None:
        assert not any(db.in_transaction() for db in sessions)
        original(*args)

    sessions: list[Session] = []
    monkeypatch.setattr(reader.provider, "check_active", active)
    with reads.open() as db:
        sessions.append(db)
        root, connection = db.get_transaction(), db.connection()
        transaction = connection.get_transaction()
        result = recheck_collected_creative(
            db,
            principal=reader.principal,
            ticket=ticket,
            collection=collection,
            now=datetime.now(UTC),
            authorize=reads.authorize,
        )
        assert result == creative_proof_from_collection(collection, ticket)
        assert result.basis.images == collection.basis.images
        assert db.get_transaction() is root and connection.get_transaction() is transaction
        assert not db.new and not db.dirty and not db.deleted
    assert len(calls) == (0 if empty else 1)


@pytest.mark.parametrize(
    "change",
    [
        "created_by",
        "created_at",
        "sha256",
        "size",
        "mime",
        "width",
        "height",
        "missing",
        "session",
        "membership",
        "paid",
        "goal",
        "privacy",
        "foreign",
    ],
)
def test_mutated_actual_source_rejected(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    change: str,
) -> None:
    reader, ticket, collection, mid, calls, reads = ready(
        customer_engine, configuration, replicas, monkeypatch, tmp_path
    )
    with Session(customer_engine) as db, db.begin():
        values = dict(
            created_by="f" * 32,
            created_at=datetime.now(UTC) - timedelta(days=1),
            sha256="f" * 64,
            size=11,
            mime="image/jpeg",
            width=3,
            height=3,
        )
        if change in values:
            db.execute(
                update(MediaObject).where(MediaObject.id == mid).values(**{change: values[change]})
            )
        elif change == "missing":
            db.execute(delete(MediaObject).where(MediaObject.id == mid))
        elif change == "foreign":
            from app.workspaces.models import Workspace

            other = Workspace(
                slug="foreign-recheck", name="Other", client_name="Other", status="active"
            )
            db.add(other)
            db.flush()
            db.execute(
                update(MediaObject).where(MediaObject.id == mid).values(workspace_id=other.id)
            )
        elif change == "session":
            db.execute(
                update(CustomerSession)
                .where(CustomerSession.digest == ticket.session_digest)
                .values(revoked_at=1)
            )
        elif change == "membership":
            db.execute(
                update(CustomerMembership)
                .where(CustomerMembership.user_id == ticket.actor_id)
                .values(role="viewer")
            )
        elif change == "paid":
            db.execute(
                update(WorkspaceBilling)
                .where(WorkspaceBilling.workspace_id == ticket.inputs.workspace_id)
                .values(status="canceled")
            )
        elif change == "goal":
            db.execute(
                update(Goal)
                .where(Goal.id == ticket.inputs.goal.goal_id)
                .values(confirmed_preview_id=None)
            )
        else:
            bump_workspace_export_revision(db, ticket.inputs.workspace_id)
    with pytest.raises(HTTPException) as error, reads.open() as db:
        recheck_collected_creative(
            db,
            principal=reader.principal,
            ticket=ticket,
            collection=collection,
            now=datetime.now(UTC),
            authorize=reads.authorize,
        )
    assert error.value.status_code == {"session": 401, "membership": 403, "paid": 402}.get(
        change, 409
    )
    assert len(calls) == 1


@pytest.mark.parametrize(
    "attack",
    [
        "dirty",
        "no_root",
        "nested",
        "rollback",
        "connection",
        "callback",
        "final_callback",
        "future",
        "naive",
        "unsafe",
        "actor",
    ],
)
def test_transaction_and_final_boundaries(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    attack: str,
) -> None:
    reader, ticket, collection, mid, calls, reads = ready(
        customer_engine, configuration, replicas, monkeypatch, tmp_path, empty=True
    )
    # Use an independently refreshed original authority; don't mask rejection on context exit.
    from app.planning_documents import authority

    fact = authority.refresh(reader.principal, reader.provider)
    count = 0

    def authorize(db: Session, wid: int, actor: str) -> None:
        nonlocal count
        count += 1
        if attack == "rollback" and count == 1:
            db.rollback()
            db.begin()
        elif attack == "connection" and count == 1:
            connection = db.connection()
            connection.rollback()
            connection.begin()
        elif attack == "callback" or (attack == "final_callback" and count == 5):
            raise RuntimeError("callback failure")
        else:
            authority.lock(db, reader.principal, wid, fact)

    with Session(customer_engine) as db:
        if attack != "no_root":
            db.begin()
        if attack == "dirty":
            row = db.get(MediaObject, mid)
            assert row is not None
            row.width = 2
        elif attack == "nested":
            db.begin_nested()
        elif attack == "future":
            ticket = ticket.model_copy(
                update={"prepared_at": datetime.now(UTC) + timedelta(days=1)}
            )
            collection = collection.model_copy(update={"ticket_digest": ticket.digest()})
        elif attack == "unsafe":
            collection = collection.model_copy(update={"ticket_digest": "x"})
        elif attack == "actor":
            ticket = ticket.model_copy(update={"session_digest": "f" * 64})
            collection = collection.model_copy(update={"ticket_digest": ticket.digest()})
        error_type = RuntimeError if attack in {"callback", "final_callback"} else HTTPException
        with pytest.raises(error_type):
            recheck_collected_creative(
                db,
                principal=reader.principal,
                ticket=ticket,
                collection=collection,
                now=datetime.now() if attack == "naive" else datetime.now(UTC),
                authorize=authorize,
            )
        db.rollback()
        row = db.get(MediaObject, mid)
        assert row is not None and row.width == 4
    assert not calls


@pytest.mark.parametrize("clock_case", ["ticket_fold", "image_fold", "equivalent_offset"])
def test_utc_instant_checks(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    clock_case: str,
) -> None:
    from datetime import timezone
    from zoneinfo import ZoneInfo

    from app.planning_documents import creative_finalization as module

    reader, ticket, collection, _, _, reads = ready(
        customer_engine, configuration, replicas, monkeypatch, tmp_path
    )
    now = datetime.now(UTC).astimezone(timezone(timedelta(hours=5)))
    if clock_case != "equivalent_offset":
        zone = ZoneInfo("America/New_York")
        now = datetime(2100, 11, 7, 1, 30, tzinfo=zone, fold=0)
        later = now.replace(fold=1)
        assert now == later and later.astimezone(UTC) > now.astimezone(UTC)
        monkeypatch.setattr(module, "database_utc_now", lambda db: now)
        if clock_case == "ticket_fold":
            ticket = ticket.model_copy(update={"prepared_at": later})
            collection = collection.model_copy(update={"ticket_digest": ticket.digest()})
        else:
            pin = collection.rows[0]
            witness = pin.witness.model_copy(update={"observed_at": later})
            collection = collection.model_copy(
                update={
                    "rows": (pin.model_copy(update={"witness": witness}),),
                    "basis": collection.basis.model_copy(update={"images": (witness,)}),
                }
            )
    with reads.open() as db:
        if clock_case == "equivalent_offset":
            proof = module.recheck_collected_creative(
                db,
                principal=reader.principal,
                ticket=ticket,
                collection=collection,
                now=now,
                authorize=reads.authorize,
            )
            assert proof == creative_proof_from_collection(collection, ticket)
        else:
            with pytest.raises(HTTPException) as error:
                module.recheck_collected_creative(
                    db,
                    principal=reader.principal,
                    ticket=ticket,
                    collection=collection,
                    now=now,
                    authorize=reads.authorize,
                )
            assert error.value.status_code == 409


def test_multiple_images_exact_order(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from io import BytesIO

    from app.campaign_review.service import upload
    from app.planning_documents.creative_basis import PlanningMediaSelectionV1
    from PIL import Image

    reader, ticket, request, _, calls = prepared(
        customer_engine, configuration, replicas, monkeypatch, tmp_path
    )
    data = BytesIO()
    Image.new("RGB", (2, 2), "blue").save(data, format="PNG")
    with Session(customer_engine) as db:
        media = upload(
            db,
            ticket.inputs.workspace_id,
            ticket.actor_id,
            data.getvalue(),
            reader.store,
            datetime.now(UTC),
        )
        selection = PlanningMediaSelectionV1(media_id=media.id, expected_sha256=media.sha256)
    request = request.model_copy(
        update={"media_selections": (selection, *request.media_selections)}
    )
    ticket = saved(ticket, request)
    collection = reader.collect_pinned(ticket, request)
    reads = PlanningReadContexts(
        reader.sessions,
        reader.principal,
        reader.provider,
        ticket.inputs.workspace_id,
        ticket.actor_id,
    )
    with reads.open() as db:
        proof = recheck_collected_creative(
            db,
            principal=reader.principal,
            ticket=ticket,
            collection=collection,
            now=datetime.now(UTC),
            authorize=reads.authorize,
        )
        assert proof == creative_proof_from_collection(collection, ticket)
        assert tuple(x.media_id for x in proof.images) == tuple(
            x.media_id for x in request.media_selections
        )
    assert len(calls) == 2


@pytest.mark.parametrize("change", ["session", "goal", "paid", "privacy", "dirty"])
def test_changes_at_final_authority_boundary(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    change: str,
) -> None:
    from app.planning_documents import authority

    reader, ticket, collection, mid, _, _ = ready(
        customer_engine, configuration, replicas, monkeypatch, tmp_path, empty=True
    )
    fact = authority.refresh(reader.principal, reader.provider)
    count = 0

    def authorize(db: Session, wid: int, actor: str) -> None:
        nonlocal count
        count += 1
        authority.lock(db, reader.principal, wid, fact)
        if count != 3:
            return
        # SQL-only fault injection AFTER callback's ordinary authority check.
        # Independent port checks must reject, even for an empty inspection.
        if change == "session":
            db.execute(
                update(CustomerSession)
                .where(CustomerSession.digest == ticket.session_digest)
                .values(revoked_at=1)
            )
        elif change == "goal":
            db.execute(
                update(Goal)
                .where(Goal.id == ticket.inputs.goal.goal_id)
                .values(confirmed_preview_id=None)
            )
        elif change == "paid":
            db.execute(
                update(WorkspaceBilling)
                .where(WorkspaceBilling.workspace_id == wid)
                .values(status="canceled")
            )
        elif change == "privacy":
            bump_workspace_export_revision(db, wid)
        else:
            media = db.get(MediaObject, mid)
            assert media is not None
            media.width = 2

    with Session(customer_engine) as db, db.begin():
        with pytest.raises(HTTPException) as error:
            recheck_collected_creative(
                db,
                principal=reader.principal,
                ticket=ticket,
                collection=collection,
                now=datetime.now(UTC),
                authorize=authorize,
            )
        assert error.value.status_code == {"session": 401, "paid": 402}.get(change, 409)
        db.rollback()
    with Session(customer_engine) as db:
        media = db.get(MediaObject, mid)
        session = db.get(CustomerSession, ticket.session_digest)
        assert media is not None and media.width == 4
        assert session is not None and session.revoked_at is None
