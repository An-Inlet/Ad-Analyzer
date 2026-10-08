"""Actual reviewed Meta preview provenance survives derived erasure, both databases."""

import importlib
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from app.customers.access import CustomerPrincipal
from app.customers.models import CustomerSession, CustomerUser
from app.initial_planning.review_bridge import guard_for
from app.initial_planning.review_models import InitialPreviewReviewLink
from app.initial_planning.runtime import InitialPlanningRuntime
from app.lifecycle.contracts import LifecycleScopeV1
from app.lifecycle.export_serializers import fields, serialize
from app.lifecycle.inventory import export_section, inventory
from app.lifecycle.privacy import bump_workspace_export_revision
from app.publication import forward_provenance
from app.publication.execution_models import ProviderExecutionReview
from app.publication.optimization_execution_contracts import OptimizationRuntime
from fastapi import HTTPException
from sqlalchemy import Engine, delete, func, select, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import set_committed_value

from tests.retired_producer_fixture import RetainedReviewIds, retained_review_fixture
from tests.test_customer_identity import FakeProvider
from tests.test_customer_identity import customer_engine as customer_engine


def exported(db: Session, review_id: str) -> dict[str, Any]:
    table = InitialPreviewReviewLink.__table__
    row = (
        db.execute(
            select(*[table.c[key] for key in fields("initial_preview_reviews")]).where(
                table.c.review_id == review_id
            )
        )
        .mappings()
        .one()
    )
    value, missing = serialize("initial_preview_reviews", dict(row))
    assert not missing
    assert "session" not in repr(value)
    return value


@pytest.mark.parametrize("actual_migration", [False, True])
def test_actual_review_provenance_erasure_export_and_db_constraints(
    customer_engine: Engine,
    tmp_path: Path,
    actual_migration: bool,
) -> None:
    migration = importlib.import_module("migrations.versions.20261006_0076_initial_preview_review")

    def prepare_schema(engine: Engine) -> None:
        if actual_migration:
            proof_migration = importlib.import_module(
                "migrations.versions.20261007_0081_initial_execution_proof"
            )
            with engine.begin() as conn, Operations.context(MigrationContext.configure(conn)):
                proof_migration.downgrade()
                migration.downgrade()
                migration.upgrade()
                proof_migration.upgrade()

    with retained_review_fixture(
        customer_engine, tmp_path / "seed", prepare_schema=prepare_schema
    ) as (engine, prepared):
        _review_lifecycle(engine, prepared, actual_migration)


def deny_runtime() -> OptimizationRuntime:
    def forbidden(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("No provider/runtime lookup is permitted by this lifecycle test")

    return OptimizationRuntime("contract_test", forbidden, forbidden, forbidden)


def _review_lifecycle(
    customer_engine: Engine, prepared: RetainedReviewIds, actual_migration: bool
) -> None:
    migration = importlib.import_module("migrations.versions.20261006_0076_initial_preview_review")
    wid = prepared.workspace_id
    with Session(customer_engine) as db:
        value = exported(db, prepared.review_id)
        assert value["preview_id"] == prepared.preview_id
        section = export_section(db, LifecycleScopeV1(workspace_id=wid), "initial_preview_reviews")
        assert len(section["rows"]) == 1
        assert (
            export_section(db, LifecycleScopeV1(workspace_id=wid + 1), "initial_preview_reviews")[
                "rows"
            ]
            == []
        )
        classified = inventory(db, LifecycleScopeV1(workspace_id=wid))
        assert any(
            s["table"] == "initial_preview_reviews" and s["protected"]
            for s in classified["sections"]
        )
        row = db.get(ProviderExecutionReview, prepared.review_id)
        assert row
        with pytest.raises(HTTPException, match="authority unavailable"):
            forward_provenance.check(
                db,
                row,
                prepared.actor_id,
                deny_runtime(),
                lambda: datetime.now(UTC),
            )
        db.rollback()
        for statement in (
            update(ProviderExecutionReview)
            .where(ProviderExecutionReview.id == prepared.review_id)
            .values(initial_preview_provenance_required=False, initial_preview_origin_id=None),
            delete(ProviderExecutionReview).where(ProviderExecutionReview.id == prepared.review_id),
            update(InitialPreviewReviewLink)
            .where(InitialPreviewReviewLink.review_id == prepared.review_id)
            .values(evidence_digest="e" * 64),
        ):
            with pytest.raises(DBAPIError), db.begin_nested():
                db.execute(statement)
        bump_workspace_export_revision(db, wid)
        db.commit()
        retracted = exported(db, prepared.review_id)
        assert all(
            retracted[k] is None
            for k in (
                "preview_id",
                "preview_workspace_id",
                "preview_account_id",
                "preview_campaign_id",
            )
        )
        assert retracted["review_digest"] == value["review_digest"]
        row = db.get(ProviderExecutionReview, prepared.review_id, populate_existing=True)
        assert row and row.initial_preview_origin_id == prepared.preview_id
        link = db.get(InitialPreviewReviewLink, prepared.review_id)
        assert link
        user = db.get(CustomerUser, prepared.actor_id)
        session = db.get(CustomerSession, link.original_session_digest)
        assert user and session
        principal = CustomerPrincipal(user, session)
        guarded = replace(
            deny_runtime(),
            initial_preview_review_guard=guard_for(
                InitialPlanningRuntime(lambda: Session(customer_engine)), principal, FakeProvider()
            ),
        )
        with pytest.raises(HTTPException, match="retracted"):
            forward_provenance.check(db, row, prepared.actor_id, guarded, lambda: datetime.now(UTC))
        db.rollback()
        # A retracted pointer cannot reattach, even to the previous origin.
        with pytest.raises(DBAPIError), db.begin_nested():
            db.execute(
                update(InitialPreviewReviewLink)
                .where(InitialPreviewReviewLink.review_id == prepared.review_id)
                .values(
                    preview_id=prepared.preview_id,
                    preview_workspace_id=wid,
                    preview_account_id=1,
                    preview_campaign_id=1,
                )
            )
        db.execute(
            delete(InitialPreviewReviewLink).where(
                InitialPreviewReviewLink.review_id == prepared.review_id
            )
        )
        db.commit()
        assert db.scalar(select(func.count()).select_from(ProviderExecutionReview)) == 1
    if actual_migration:
        with (
            customer_engine.begin() as conn,
            Operations.context(MigrationContext.configure(conn)),
            pytest.raises(RuntimeError, match="provenance"),
        ):
            migration.downgrade()
    assert prepared.provider_posts == 1


def test_cached_ordinary_marker_cannot_bypass_new_protected_origin(
    customer_engine: Engine,
    tmp_path: Path,
) -> None:
    with (
        retained_review_fixture(customer_engine, tmp_path / "seed") as (engine, result),
        Session(engine, expire_on_commit=False) as cached,
    ):
        row = cached.get(ProviderExecutionReview, result.review_id)
        assert row and row.initial_preview_provenance_required
        cached.commit()
        # Adversarial stale identity-map state; the genuine protected origin was
        # produced in the pinned child, never downgraded in current storage.
        set_committed_value(row, "initial_preview_provenance_required", False)
        set_committed_value(row, "initial_preview_origin_id", None)
        with pytest.raises(HTTPException, match="authority unavailable"):
            forward_provenance.check(
                cached, row, result.actor_id, deny_runtime(), lambda: datetime.now(UTC)
            )
        assert row.initial_preview_provenance_required
        assert row.initial_preview_origin_id == result.preview_id
