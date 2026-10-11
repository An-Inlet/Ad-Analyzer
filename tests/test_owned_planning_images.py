"""Actual owned upload and confirmed goal, no external storage or provider traffic."""

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from app.billing.models import WorkspaceBilling
from app.campaign_review.models import MediaObject
from app.campaign_review.service import upload
from app.campaign_review.storage import LocalMediaStore
from app.customers.models import CustomerMembership, CustomerSession
from app.goals.models import Goal
from app.lifecycle.privacy import bump_workspace_export_revision
from app.planning_documents import creative_basis_reader as module
from app.planning_documents.creative_basis import CreativeInputV1, PlanningMediaSelectionV1
from app.planning_documents.read_context import PlanningReadContexts
from app.settings import Settings
from fastapi import HTTPException
from sqlalchemy import Engine, delete, update
from sqlalchemy.orm import Session

from tests.q16_clock_feasibility_probe import paid
from tests.test_campaign_review import png
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_planning_evidence_adapter import setup_evidence
from tests.test_shopify_sales import configuration as configuration


def prepared(
    engine: Engine, config: Settings, replicas: Any, patch: pytest.MonkeyPatch, path: Path
) -> Any:
    _, ticket, principal, _ = setup_evidence(engine, config, replicas, patch, "google_ads")
    paid(engine, ticket.inputs.workspace_id, datetime.now(UTC), patch)
    store = LocalMediaStore(path)
    with Session(engine) as db:
        row = upload(
            db, ticket.inputs.workspace_id, principal.user.id, png(), store, datetime.now(UTC)
        )
        request = CreativeInputV1(
            media_selections=(
                PlanningMediaSelectionV1(media_id=row.id, expected_sha256=row.sha256),
            )
        )
        media_id = row.id
    sessions: list[Session] = []

    def session() -> Session:
        db = Session(engine)
        sessions.append(db)
        return db

    original = store.read_exact
    calls: list[int] = []

    def read(*args: Any) -> bytes:
        assert sessions and all(not db.in_transaction() for db in sessions)
        calls.append(1)
        return original(*args)

    patch.setattr(store, "read_exact", read)
    reader = module.OwnedPlanningImageReader(
        session,
        principal=principal,
        provider=replicas[2],
        store=store,
        clock=lambda: datetime.now(UTC),
    )
    return reader, ticket, request, media_id, calls


@pytest.mark.parametrize("empty", [False, True])
def test_actual_owned_bytes_and_empty_input_authority(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    empty: bool,
) -> None:
    reader, ticket, request, mid, calls = prepared(
        customer_engine, configuration, replicas, monkeypatch, tmp_path
    )
    value = reader.collect(ticket, CreativeInputV1() if empty else request)
    assert value.workspace_id == ticket.inputs.workspace_id
    assert value.goal_currency == ticket.inputs.goal.definition.target_window.currency
    assert value.privacy_revision == ticket.privacy_revision
    assert len(value.images) == len(calls) == (0 if empty else 1)
    if not empty:
        image = value.images[0]
        assert image.media_id == mid and (image.mime, image.width, image.height) == (
            "image/png",
            4,
            4,
        )
        assert image.sha256 == request.media_selections[0].expected_sha256
        assert image.visual_assessment == "not_assessed" and not image.advertising_writes_enabled
    assert type(value).model_validate_json(value.model_dump_json()).digest() == value.digest()


@pytest.mark.parametrize(
    "damage",
    ["missing", "foreign", "expected_hash", "session_ticket", "mime", "dimensions", "size"],
)
def test_invalid_initial_scope_or_metadata_reads_no_bytes(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    damage: str,
) -> None:
    reader, ticket, request, mid, calls = prepared(
        customer_engine, configuration, replicas, monkeypatch, tmp_path
    )
    if damage in {"missing", "expected_hash"}:
        field = "media_id" if damage == "missing" else "expected_sha256"
        request = request.model_copy(
            update={
                "media_selections": (
                    request.media_selections[0].model_copy(
                        update={field: "f" * (32 if damage == "missing" else 64)}
                    ),
                )
            }
        )
    elif damage == "session_ticket":
        ticket = ticket.model_copy(update={"session_digest": "f" * 64})
    else:
        with Session(customer_engine) as db, db.begin():
            if damage == "foreign":
                from app.workspaces.models import Workspace

                other = Workspace(
                    slug="foreign-image", name="Other", client_name="Other", status="active"
                )
                db.add(other)
                db.flush()
                values: dict[str, Any] = {"workspace_id": other.id}
            else:
                values = (
                    {"mime": "video/mp4"}
                    if damage == "mime"
                    else {"width": 0}
                    if damage == "dimensions"
                    else {"size": 8 * 1024 * 1024 + 1}
                )
            db.execute(update(MediaObject).where(MediaObject.id == mid).values(**values))
    if damage == "session_ticket":
        with pytest.raises(HTTPException) as error:
            reader.collect(ticket, request)
        assert error.value.status_code == 401
    else:
        with pytest.raises(
            module.PlanningImageUnavailable, match="^owned planning image evidence unavailable$"
        ):
            reader.collect(ticket, request)
    assert not calls


@pytest.mark.parametrize(
    "change",
    [
        "deleted",
        "actor",
        "created_at",
        "dimensions",
        "privacy",
        "goal",
        "session",
        "membership",
        "paid",
    ],
)
def test_original_rows_and_authority_rechecked_after_storage(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    change: str,
) -> None:
    reader, ticket, request, mid, calls = prepared(
        customer_engine, configuration, replicas, monkeypatch, tmp_path
    )
    original = reader.store.read_exact

    def read(*args: Any) -> bytes:
        data = original(*args)
        assert isinstance(data, bytes)
        with Session(customer_engine) as db, db.begin():
            if change == "deleted":
                db.execute(delete(MediaObject).where(MediaObject.id == mid))
            elif change in {"actor", "created_at", "dimensions"}:
                values = (
                    {"created_by": "f" * 32}
                    if change == "actor"
                    else {"created_at": datetime.now(UTC) - timedelta(days=1)}
                    if change == "created_at"
                    else {"width": 3}
                )
                db.execute(update(MediaObject).where(MediaObject.id == mid).values(**values))
            elif change == "privacy":
                bump_workspace_export_revision(db, ticket.inputs.workspace_id)
            elif change == "goal":
                db.execute(
                    update(Goal)
                    .where(Goal.id == ticket.inputs.goal.goal_id)
                    .values(confirmed_preview_id=None)
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
                    .where(CustomerMembership.workspace_id == ticket.inputs.workspace_id)
                    .values(role="viewer")
                )
            else:
                db.execute(
                    update(WorkspaceBilling)
                    .where(WorkspaceBilling.workspace_id == ticket.inputs.workspace_id)
                    .values(status="canceled")
                )
        return data

    monkeypatch.setattr(reader.store, "read_exact", read)
    if change in {"session", "membership", "paid"}:
        with pytest.raises(HTTPException) as error:
            reader.collect(ticket, request)
        assert error.value.status_code == {"session": 401, "membership": 403, "paid": 402}[change]
    else:
        with pytest.raises(module.PlanningImageUnavailable):
            reader.collect(ticket, request)
    assert len(calls) == 1


@pytest.mark.parametrize("damage", ["type", "size", "swap", "io", "corrupt", "mime", "dimensions"])
def test_bad_bytes_and_decoded_metadata_are_fixed_failures(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    damage: str,
) -> None:
    import hashlib

    reader, ticket, request, mid, calls = prepared(
        customer_engine, configuration, replicas, monkeypatch, tmp_path
    )
    original = reader.store.read_exact
    if damage in {"mime", "dimensions", "corrupt"}:
        with Session(customer_engine) as db, db.begin():
            values = (
                {"mime": "image/jpeg"}
                if damage == "mime"
                else {"width": 3}
                if damage == "dimensions"
                else {"sha256": hashlib.sha256(b"not image").hexdigest(), "size": 9}
            )
            db.execute(update(MediaObject).where(MediaObject.id == mid).values(**values))
        if damage == "corrupt":
            request = request.model_copy(
                update={
                    "media_selections": (
                        request.media_selections[0].model_copy(
                            update={"expected_sha256": values["sha256"]}
                        ),
                    )
                }
            )

    def read(*args: Any) -> Any:
        if damage == "io":
            raise OSError("private-storage-path")
        if damage == "corrupt":
            return b"not image"
        data = original(*args)
        return (
            bytearray(data)
            if damage == "type"
            else data[:-1]
            if damage == "size"
            else b"x" * len(data)
            if damage == "swap"
            else data
        )

    monkeypatch.setattr(reader.store, "read_exact", read)
    with pytest.raises(module.PlanningImageUnavailable) as error:
        reader.collect(ticket, request)
    assert str(error.value) == "owned planning image evidence unavailable"


@pytest.mark.parametrize("mode", ["elapsed", "monotonic_reverse", "wall_reverse", "empty_final"])
def test_cooperative_deadline_and_reverse_clocks(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    mode: str,
) -> None:
    reader, ticket, request, _, _ = prepared(
        customer_engine, configuration, replicas, monkeypatch, tmp_path
    )
    ticks = [100.0]
    now = [datetime.now(UTC)]
    monkeypatch.setattr(module, "monotonic", lambda: ticks[0])
    reader.clock = lambda: now[0]

    def advance() -> None:
        if mode == "wall_reverse":
            now[0] -= timedelta(seconds=1)
        else:
            ticks[0] = 99.0 if mode == "monotonic_reverse" else 160.0

    if mode == "empty_final":
        request = CreativeInputV1()
        original = reader.provider.check_active
        calls = [0]

        def check(*args: Any) -> Any:
            result = original(*args)
            calls[0] += 1
            if calls[0] == 2:
                advance()
            return result

        monkeypatch.setattr(reader.provider, "check_active", check)
    else:
        original_read = reader.store.read_exact

        def read(*args: Any) -> bytes:
            result = original_read(*args)
            assert isinstance(result, bytes)
            advance()
            return result

        monkeypatch.setattr(reader.store, "read_exact", read)
    with pytest.raises(module.PlanningImageUnavailable):
        reader.collect(ticket, request)


def test_empty_selection_rechecks_original_session_and_unexpected_failures_propagate(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    reader, ticket, request, _, calls = prepared(
        customer_engine, configuration, replicas, monkeypatch, tmp_path
    )

    def unexpected(*args: Any) -> bytes:
        raise RuntimeError("unexpected programmer failure")

    with monkeypatch.context() as patch:
        patch.setattr(reader.store, "read_exact", unexpected)
        with pytest.raises(RuntimeError, match="unexpected programmer failure"):
            reader.collect(ticket, request)
    original = reader.provider.check_active
    refreshes = [0]

    def check(*args: Any) -> Any:
        result = original(*args)
        refreshes[0] += 1
        if refreshes[0] == 2:
            with Session(customer_engine) as db, db.begin():
                db.execute(
                    update(CustomerSession)
                    .where(CustomerSession.digest == ticket.session_digest)
                    .values(revoked_at=1)
                )
        return result

    monkeypatch.setattr(reader.provider, "check_active", check)
    with pytest.raises(HTTPException) as error:
        reader.collect(ticket, CreativeInputV1())
    assert error.value.status_code == 401 and refreshes[0] == 2 and not calls


def test_multiple_owned_images_keep_customer_order_and_identity_io_outside_sql(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    import io

    from PIL import Image

    reader, ticket, request, _, calls = prepared(
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
    request = CreativeInputV1(media_selections=(second, *request.media_selections))
    tracked: list[Session] = []
    original_sessions = reader.sessions

    def session() -> Session:
        db = original_sessions()
        assert isinstance(db, Session)
        tracked.append(db)
        return db

    reader.sessions = session
    original_check = reader.provider.check_active

    def check(*args: Any) -> Any:
        assert all(not db.in_transaction() for db in tracked)
        return original_check(*args)

    monkeypatch.setattr(reader.provider, "check_active", check)
    result = reader.collect(ticket, request)
    assert tuple(image.media_id for image in result.images) == tuple(
        item.media_id for item in request.media_selections
    )
    assert [(image.width, image.height) for image in result.images] == [(2, 2), (4, 4)]
    assert len(calls) == 2


def test_elapsed_after_final_authority_context_is_rejected(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from collections.abc import Iterator
    from contextlib import contextmanager

    reader, ticket, _, _, calls = prepared(
        customer_engine, configuration, replicas, monkeypatch, tmp_path
    )
    ticks = [100.0]
    monkeypatch.setattr(module, "monotonic", lambda: ticks[0])
    original = PlanningReadContexts.open
    exits = [0]

    @contextmanager
    def opened(self: Any) -> Iterator[Session]:
        with original(self) as db:
            yield db
        exits[0] += 1
        if exits[0] == 2:
            ticks[0] = 160.0

    monkeypatch.setattr(PlanningReadContexts, "open", opened)
    with pytest.raises(module.PlanningImageUnavailable):
        reader.collect(ticket, CreativeInputV1())
    assert exits[0] == 2 and not calls
