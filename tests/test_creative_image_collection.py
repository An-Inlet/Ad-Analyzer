"""Private pin binding and actual original-session image collection; no finalization."""

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from app.campaign_review.models import MediaObject
from app.customers.models import CustomerSession
from app.planning_documents.creative_basis import CreativeInputV1
from app.planning_documents.creative_basis_reader import PlanningImageUnavailable
from app.planning_documents.creative_image_collection import (
    CollectedCreativeBasisV1,
    PlanningImageRowPinV1,
)
from app.planning_documents.ports import GenerationTicket
from app.settings import Settings
from fastapi import HTTPException
from sqlalchemy import Engine, update
from sqlalchemy.orm import Session

from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_owned_planning_images import prepared
from tests.test_planning_creative_basis import basis as pure_basis
from tests.test_planning_document_ports import ready_bundle
from tests.test_shopify_sales import configuration as configuration


def saved(ticket: Any, requested: CreativeInputV1) -> GenerationTicket:
    return GenerationTicket.model_validate(
        ticket.model_copy(
            update={"inputs": ticket.inputs.model_copy(update={"creative": requested})}
        )
    )


def envelope() -> tuple[CollectedCreativeBasisV1, GenerationTicket]:
    ticket, _ = ready_bundle()
    raw = pure_basis(2).model_dump(mode="python")
    raw["workspace_id"] = ticket.inputs.workspace_id
    raw["privacy_revision"] = ticket.privacy_revision
    for image in raw["images"]:
        image["workspace_id"] = ticket.inputs.workspace_id
        image["privacy_revision"] = ticket.privacy_revision
    basis = type(pure_basis()).model_validate(raw)
    ticket = saved(ticket, basis.requested)
    value = CollectedCreativeBasisV1(
        basis=basis,
        rows=tuple(
            PlanningImageRowPinV1(witness=x, created_by=ticket.actor_id) for x in basis.images
        ),
        ticket_digest=ticket.digest(),
    )
    return value, ticket


def test_exact_order_witness_time_and_complete_identity() -> None:
    value, ticket = envelope()
    value.assert_ticket(ticket)
    assert CollectedCreativeBasisV1.model_validate_json(value.model_dump_json()) == value
    pin = value.rows[0]
    later = pin.model_copy(
        update={
            "witness": pin.witness.model_copy(
                update={"observed_at": pin.witness.observed_at + timedelta(seconds=1)}
            )
        }
    )
    assert later.identity() == pin.identity()
    with pytest.raises(ValueError):
        CollectedCreativeBasisV1.model_validate(
            value.model_copy(update={"rows": (later, value.rows[1])})
        )
    assert pin.model_copy(update={"created_by": "f" * 32}).identity() != pin.identity()
    changed = pin.model_copy(
        update={
            "witness": pin.witness.model_copy(
                update={"created_at": pin.witness.created_at - timedelta(seconds=1)}
            )
        }
    )
    assert changed.identity() != pin.identity()
    with pytest.raises(ValueError):
        pin.model_copy(update={"created_by": 123}).identity()


@pytest.mark.parametrize(
    "attack", ["missing", "extra", "reverse", "digest", "ticket", "requested", "empty_rows"]
)
def test_copied_envelope_or_ticket_rejects(attack: str) -> None:
    value, ticket = envelope()
    if attack == "missing":
        value = value.model_copy(update={"rows": value.rows[:1]})
    elif attack == "extra":
        value = value.model_copy(update={"rows": (*value.rows, value.rows[0])})
    elif attack == "reverse":
        value = value.model_copy(update={"rows": tuple(reversed(value.rows))})
    elif attack == "digest":
        value = value.model_copy(update={"ticket_digest": "f" * 64})
    elif attack == "ticket":
        ticket = ticket.model_copy(update={"operation_id": "f" * 32})
    elif attack == "requested":
        ticket = saved(ticket, CreativeInputV1())
    else:
        value = value.model_copy(update={"rows": ()})
    with pytest.raises(ValueError):
        value.assert_ticket(ticket)


@pytest.mark.parametrize("empty", [False, True])
def test_actual_pinned_collection_one_inspection_and_compatibility(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    empty: bool,
) -> None:
    reader, ticket, requested, mid, calls = prepared(
        customer_engine, configuration, replicas, monkeypatch, tmp_path
    )
    requested = CreativeInputV1() if empty else requested
    ticket = saved(ticket, requested)
    identity_checks = []
    original_check = reader.provider.check_active
    tracked = []
    original_sessions = reader.sessions

    def session() -> Session:
        db = original_sessions()
        assert isinstance(db, Session)
        tracked.append(db)
        return db

    reader.sessions = session

    def check(*args: Any) -> Any:
        assert all(not db.in_transaction() for db in tracked)
        identity_checks.append(1)
        return original_check(*args)

    monkeypatch.setattr(reader.provider, "check_active", check)
    value = reader.collect_pinned(ticket, requested)
    value.assert_ticket(ticket)
    assert len(calls) == (0 if empty else 1)
    assert len(identity_checks) == 2
    if not empty:
        with Session(customer_engine) as db:
            row = db.get(MediaObject, mid)
            assert row
            assert value.rows[0].created_by == row.created_by
            assert value.rows[0].witness.created_at.replace(tzinfo=None) == row.created_at.replace(
                tzinfo=None
            )
        assert value.rows[0].witness == value.basis.images[0]
    else:
        assert value.rows == () and value.basis.images == ()
    legacy = reader.collect(ticket, requested)
    assert legacy.requested == value.basis.requested
    assert tuple(x.model_dump(exclude={"observed_at"}) for x in legacy.images) == tuple(
        x.model_dump(exclude={"observed_at"}) for x in value.basis.images
    )
    assert len(calls) == (0 if empty else 2)


@pytest.mark.parametrize("change", ["missing_saved", "wrong_requested"])
def test_pinned_saved_input_rejects_before_any_io(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    change: str,
) -> None:
    reader, ticket, requested, _, calls = prepared(
        customer_engine, configuration, replicas, monkeypatch, tmp_path
    )
    if change == "wrong_requested":
        ticket = saved(ticket, CreativeInputV1())

    def forbidden(*args: Any) -> None:
        raise AssertionError("identity IO before exact saved-input binding")

    monkeypatch.setattr(reader.provider, "check_active", forbidden)
    with pytest.raises(PlanningImageUnavailable):
        reader.collect_pinned(ticket, requested)
    assert not calls


@pytest.mark.parametrize("change", ["creator", "created_at", "session"])
def test_pinned_final_rows_and_session_changes_reject(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    change: str,
) -> None:
    reader, ticket, requested, mid, calls = prepared(
        customer_engine, configuration, replicas, monkeypatch, tmp_path
    )
    ticket = saved(ticket, requested)
    original = reader.store.read_exact

    def read(*args: Any) -> bytes:
        data = original(*args)
        assert isinstance(data, bytes)
        with Session(customer_engine) as db, db.begin():
            if change == "session":
                db.execute(
                    update(CustomerSession)
                    .where(CustomerSession.digest == ticket.session_digest)
                    .values(revoked_at=1)
                )
            else:
                db.execute(
                    update(MediaObject)
                    .where(MediaObject.id == mid)
                    .values(
                        **(
                            {"created_by": "f" * 32}
                            if change == "creator"
                            else {"created_at": datetime.now(UTC) - timedelta(days=1)}
                        )
                    )
                )
        return data

    monkeypatch.setattr(reader.store, "read_exact", read)
    if change == "session":
        with pytest.raises(HTTPException) as err:
            reader.collect_pinned(ticket, requested)
        assert err.value.status_code == 401
    else:
        with pytest.raises(PlanningImageUnavailable):
            reader.collect_pinned(ticket, requested)
    assert len(calls) == 1


def test_actual_multiple_pins_preserve_order_and_inspect_once(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    import io

    from app.campaign_review.service import upload
    from app.planning_documents.creative_basis import PlanningMediaSelectionV1
    from PIL import Image

    reader, ticket, requested, _, calls = prepared(
        customer_engine, configuration, replicas, monkeypatch, tmp_path
    )
    data = io.BytesIO()
    Image.new("RGB", (2, 2), "blue").save(data, "PNG")
    with Session(customer_engine) as db:
        row = upload(
            db,
            ticket.inputs.workspace_id,
            ticket.actor_id,
            data.getvalue(),
            reader.store,
            datetime.now(UTC),
        )
        second = PlanningMediaSelectionV1(media_id=row.id, expected_sha256=row.sha256)
    requested = CreativeInputV1(media_selections=(second, *requested.media_selections))
    ticket = saved(ticket, requested)
    value = reader.collect_pinned(ticket, requested)
    value.assert_ticket(ticket)
    assert tuple(row.witness.media_id for row in value.rows) == tuple(
        x.media_id for x in requested.media_selections
    )
    assert tuple(row.witness for row in value.rows) == value.basis.images
    assert len(calls) == 2


@pytest.mark.parametrize("field", ["workspace_id", "privacy_revision", "goal_currency"])
def test_envelope_scope_must_match_original_ticket(field: str) -> None:
    value, ticket = envelope()
    raw = value.model_dump(mode="python")
    raw["basis"][field] = "EUR" if field == "goal_currency" else 999
    if field == "goal_currency":
        raw["basis"]["requested"]["product"]["list_price"]["currency"] = "EUR"
    else:
        for row, image in zip(raw["rows"], raw["basis"]["images"], strict=True):
            row["witness"][field] = image[field] = 999
    changed = CollectedCreativeBasisV1.model_validate(raw)
    with pytest.raises(ValueError, match="original ticket"):
        changed.assert_ticket(ticket)


def test_dependency_light_import() -> None:
    import subprocess
    import sys

    subprocess.run(
        [
            sys.executable,
            "-c",
            "import app.planning_documents.creative_image_collection; import sys; "
            "assert 'app.planning_documents.ports' not in sys.modules",
        ],
        check=True,
        capture_output=True,
    )
