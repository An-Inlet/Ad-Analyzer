"""Raw erasure contention and real export snapshots fail closed on both DBs."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import pytest
from app.commerce.evidence import lock_workspace
from app.customers.access import CustomerPrincipal
from app.customers.models import CustomerMembership, CustomerSession, CustomerUser
from app.lifecycle import archive
from app.lifecycle.contracts import LifecycleInputV1, LifecycleScopeV1
from app.lifecycle.exports import Authority
from app.lifecycle.privacy import workspace_export_revision
from app.lifecycle.service import begin
from app.outcome_feedback.models import V3Assessment, V3EvidenceDependency
from app.outcomes.owned_v3 import OwnedV3Assessment
from app.settings import Settings
from fastapi import HTTPException
from sqlalchemy import Engine, delete, select
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from tests.test_commerce_measurement import NOW
from tests.test_customer_exports import export_engine as export_engine
from tests.test_customer_identity import FakeProvider
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_execution_session_authorizer import guard
from tests.test_feedback_policy import assessment as assessment
from tests.test_feedback_policy import make_assessment
from tests.test_feedback_storage import seed_graph
from tests.test_shopify_sales import configuration as configuration


def test_raw_delete_nowait_preserves_graph_and_counter_until_explicit_retry(
    customer_engine: Engine,
    configuration: Settings,
    assessment: OwnedV3Assessment,
) -> None:
    if customer_engine.dialect.name != "postgresql":
        pytest.skip("SQLite serializes writers; PostgreSQL row-lock boundary")
    with Session(customer_engine) as db:
        identifier, _, _, _ = seed_graph(db, assessment, configuration)
        wid = assessment.context.scope.workspace_id
        revision = workspace_export_revision(db, wid)

    def erase() -> str:
        try:
            with Session(customer_engine) as db:
                db.execute(
                    delete(V3EvidenceDependency).where(
                        V3EvidenceDependency.assessment_id == identifier,
                        V3EvidenceDependency.ordinal == 0,
                    )
                )
                db.commit()
            return "committed"
        except DBAPIError as error:
            return str(getattr(error.orig, "sqlstate", "unexpected_database_error"))

    with ThreadPoolExecutor(max_workers=1) as pool, Session(customer_engine) as holder:
        lock_workspace(holder, wid, active=True)
        assert pool.submit(erase).result(timeout=5) == "55P03"
        assert holder.get(V3Assessment, identifier) is not None
        assert workspace_export_revision(holder, wid) == revision
    assert erase() == "committed"  # Separate explicit attempt after the fence is released.
    with Session(customer_engine) as db:
        assert db.get(V3Assessment, identifier) is None
        assert workspace_export_revision(db, wid) > revision


def test_real_export_repeatable_snapshot_cannot_return_erased_feedback(
    export_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
) -> None:
    value = make_assessment(export_engine, configuration, tmp_path)
    with Session(export_engine) as db:
        identifier, _, _, _ = seed_graph(db, value, configuration)
        wid = value.context.scope.workspace_id
        actor = db.scalar(
            select(CustomerMembership.user_id).where(CustomerMembership.workspace_id == wid)
        )
        assert actor
        _, token = guard(db, actor)
        user, session = db.get(CustomerUser, actor), db.get(CustomerSession, token)
        assert user and session
        user.issuer = FakeProvider().issuer
        db.commit()
        principal = CustomerPrincipal(user=user, session=session)
        request = begin(
            db,
            principal,
            FakeProvider(),
            LifecycleInputV1(scope=LifecycleScopeV1(workspace_id=wid), operation="export"),
            "feedback-export-snapshot-race",
            NOW,
        )
        db.commit()
        authority = Authority(export_engine, principal, FakeProvider(), wid, request.id)
    authority.claim()
    retained: list[bool] = []

    def capture(snapshot: Session) -> dict[str, Any]:
        captured = authority.capture_privacy(snapshot)
        first = snapshot.scalar(select(V3Assessment.document).where(V3Assessment.id == identifier))
        assert first and first["absolute_difference_micros"] is not None
        with Session(export_engine) as writer:
            writer.execute(
                delete(V3EvidenceDependency).where(
                    V3EvidenceDependency.assessment_id == identifier,
                    V3EvidenceDependency.ordinal == 0,
                )
            )
            writer.commit()
        # Real PostgreSQL REPEATABLE READ / SQLite WAL snapshot still contains numeric data.
        assert (
            snapshot.scalar(select(V3Assessment.document).where(V3Assessment.id == identifier))
            == first
        )
        retained.append(True)
        return captured

    def unused_store():  # type: ignore[no-untyped-def]
        raise AssertionError("privacy guard must reject before media access")

    assert authority.revision is not None
    with pytest.raises(HTTPException) as error:
        archive.build(
            export_engine,
            wid,
            authority.request_id,
            authority.revision,
            unused_store,
            authority.check,
            capture,
        )
    assert error.value.status_code == 409 and retained == [True]
    with Session(export_engine) as db:
        assert db.get(V3Assessment, identifier) is None
