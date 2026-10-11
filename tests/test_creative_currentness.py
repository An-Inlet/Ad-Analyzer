"""Current metadata uses viewer authority; immutable history remains independent."""

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast

import pytest
from app.billing.models import WorkspaceBilling
from app.campaign_review.models import MediaObject
from app.customers.access import CustomerPrincipal
from app.customers.models import CustomerMembership, CustomerSession, CustomerUser
from app.goals.models import Goal
from app.lifecycle.privacy import bump_workspace_export_revision, database_utc_now
from app.planning_documents import creative_currentness as current
from app.planning_documents.creative_history import creative_local_witness
from app.planning_documents.retained_sources import RetainedSourcesChanged, _guard
from app.planning_documents.selected_plan_history import validate_selected_plan_history
from app.settings import Settings
from fastapi import HTTPException
from sqlalchemy import Engine, delete, select, update
from sqlalchemy.orm import Session

from tests.test_creative_history_sql import stored
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_shopify_sales import configuration as configuration


@pytest.fixture
def ready(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    request: pytest.FixtureRequest,
) -> Any:
    return stored(
        customer_engine,
        configuration,
        replicas,
        monkeypatch,
        tmp_path,
        request,
        image_count=getattr(request, "param", 1),
    )


@pytest.mark.parametrize("ready", [0, 1, 2], indirect=True)
@pytest.mark.parametrize("viewer", [False, True])
def test_unchanged_unpaid_and_different_viewer(
    customer_engine: Engine,
    ready: Any,
    monkeypatch: pytest.MonkeyPatch,
    viewer: bool,
) -> None:
    document, store, reader, _ = ready
    principal = reader.principal
    if viewer:
        with Session(customer_engine) as db, db.begin():
            user = CustomerUser(
                id="c" * 32,
                issuer=principal.user.issuer,
                subject="permitted-viewer",
                email="viewer@example.test",
                status="active",
            )
            db.add(user)
            db.flush()
            source = principal.session
            session = CustomerSession(
                digest="d" * 64,
                user_id=user.id,
                csrf_digest="e" * 64,
                created_at=source.authenticated_at,
                expires_at=source.expires_at,
                authenticated_at=source.authenticated_at,
            )
            db.add(session)
            db.add(
                CustomerMembership(
                    user_id=user.id,
                    workspace_id=document.inputs.workspace_id,
                    role="viewer",
                    status="active",
                )
            )
            db.flush()
            db.expunge(user)
            db.expunge(session)
            principal = CustomerPrincipal(user, session)
        assert principal.user.id != document.generated_by
    with Session(customer_engine) as db, db.begin():
        db.execute(update(WorkspaceBilling).values(status="canceled"))

    def forbidden(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("SQL currentness cannot read bytes/provider or commit")

    monkeypatch.setattr(store, "read_exact", forbidden)
    monkeypatch.setattr(reader.provider, "check_active", forbidden)
    with Session(customer_engine) as db, db.begin():
        monkeypatch.setattr(db, "commit", forbidden)
        root, connection = db.get_transaction(), db.connection()
        transaction = connection.get_transaction()
        before = document.model_dump_json()
        witness = current.capture_creative_retained_source(
            db,
            principal=principal,
            document=document,
            now=datetime.now(UTC),
        )
        assert witness == creative_local_witness(document)
        assert document.model_dump_json() == before
        assert db.get_transaction() is root and connection.get_transaction() is transaction
        assert not db.new and not db.dirty and not db.deleted


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
        "foreign",
        "session",
        "membership",
        "goal",
        "privacy",
    ],
)
def test_changed_source_or_authority(
    customer_engine: Engine,
    ready: Any,
    change: str,
) -> None:
    document, _, reader, _ = ready
    assert document.creative_proof is not None
    mid = document.creative_proof.basis.images[0].media_id
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

            other = Workspace(slug="foreign-current", name="Other", client_name="Other")
            db.add(other)
            db.flush()
            db.execute(
                update(MediaObject).where(MediaObject.id == mid).values(workspace_id=other.id)
            )
        elif change == "session":
            db.execute(
                update(CustomerSession)
                .where(CustomerSession.digest == reader.principal.session.digest)
                .values(revoked_at=1)
            )
        elif change == "membership":
            db.execute(
                update(CustomerMembership)
                .where(CustomerMembership.user_id == reader.principal.user.id)
                .values(status="suspended")
            )
        elif change == "goal":
            db.execute(
                update(Goal)
                .where(Goal.id == document.inputs.goal.goal_id)
                .values(confirmed_preview_id=None)
            )
        else:
            bump_workspace_export_revision(db, document.inputs.workspace_id)
    with (
        Session(customer_engine) as db,
        db.begin(),
        pytest.raises(
            HTTPException if change in {"session", "membership"} else RetainedSourcesChanged
        ) as error,
    ):
        current.capture_creative_retained_source(
            db,
            principal=reader.principal,
            document=document,
            now=datetime.now(UTC),
        )
    if isinstance(error.value, HTTPException):
        assert error.value.status_code == {"session": 401, "membership": 404}[change]
    else:
        assert isinstance(error.value, RetainedSourcesChanged)
        assert error.value.reason == "source_changed"
    if change == "missing":
        with Session(customer_engine) as db, db.begin():
            validate_selected_plan_history(db, document)


@pytest.mark.parametrize("ready", [0], indirect=True)
@pytest.mark.parametrize(
    "attack",
    [
        "absent",
        "nested",
        "dirty",
        "rollback",
        "connection",
        "exception",
        "naive",
        "expired",
        "final_expiry",
        "unsafe_proof",
    ],
)
def test_transaction_and_time_boundaries(
    customer_engine: Engine,
    ready: Any,
    monkeypatch: pytest.MonkeyPatch,
    attack: str,
) -> None:
    document, _, reader, _ = ready
    original_guard = _guard
    original_clock = database_utc_now
    calls = 0

    def guard(db: Session, *args: Any) -> None:
        if attack == "rollback":
            db.rollback()
            db.begin()
        elif attack == "connection":
            db.connection().rollback()
            db.connection().begin()
        elif attack == "exception":
            raise RuntimeError("unexpected SQL callback")
        else:
            original_guard(db, *args)

    def clock(db: Session) -> datetime:
        nonlocal calls
        calls += 1
        if attack == "final_expiry" and calls == 5:
            return cast(datetime, document.valid_until)
        return original_clock(db)

    monkeypatch.setattr(current, "_guard", guard)
    monkeypatch.setattr(current, "database_utc_now", clock)
    if attack == "unsafe_proof":
        document = document.model_copy(update={"creative_proof": None})
    with Session(customer_engine) as db:
        if attack != "absent":
            db.begin()
        if attack == "nested":
            db.begin_nested()
        if attack == "dirty":
            row = db.scalar(select(CustomerUser).where(CustomerUser.id == reader.principal.user.id))
            assert row is not None
            row.email = "not-persisted@example.test"
        instant = datetime.now(UTC)
        if attack == "naive":
            instant = instant.replace(tzinfo=None)
        elif attack == "expired":
            instant = document.valid_until
        with pytest.raises(RuntimeError if attack == "exception" else RetainedSourcesChanged):
            current.capture_creative_retained_source(
                db,
                principal=reader.principal,
                document=document,
                now=instant,
            )
        db.rollback()
        row = db.get(CustomerUser, reader.principal.user.id)
        assert row is not None and row.email != "not-persisted@example.test"
