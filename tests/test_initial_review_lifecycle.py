"""Actual reviewed Meta preview provenance survives derived erasure, both databases."""

import importlib
from dataclasses import replace
from typing import Any

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from app.initial_planning.contracts import PreviewIntentV1
from app.initial_planning.models import PreviewRow
from app.initial_planning.review_bridge import prepare_preview_review
from app.initial_planning.review_models import InitialPreviewReviewLink
from app.lifecycle.contracts import LifecycleScopeV1
from app.lifecycle.export_serializers import fields, serialize
from app.lifecycle.inventory import export_section, inventory
from app.lifecycle.privacy import bump_workspace_export_revision
from app.publication import customer_optimization, forward_provenance
from app.publication.customer_optimization_contracts import BudgetIntent, InitialOptimizationIntent
from app.publication.execution_models import ProviderExecutionReview
from app.settings import Settings
from fastapi import HTTPException
from sqlalchemy import Engine, delete, func, select, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_initial_preview_review import ready
from tests.test_shopify_sales import configuration as configuration


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
    configuration: Settings,
    monkeypatch: pytest.MonkeyPatch,
    replicas: Any,
    actual_migration: bool,
) -> None:
    migration = importlib.import_module("migrations.versions.20261006_0076_initial_preview_review")
    if actual_migration:
        with customer_engine.begin() as conn, Operations.context(MigrationContext.configure(conn)):
            migration.downgrade()
            migration.upgrade()
    wid, preview, principal, provider, runtime, server, _ = ready(
        customer_engine, configuration, monkeypatch, replicas
    )
    prepared = prepare_preview_review(
        runtime, principal, provider, wid, preview.id, preview.digest()
    )
    with Session(customer_engine) as db:
        value = exported(db, prepared.review_id)
        assert value["preview_id"] == preview.id
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
                principal.user.id,
                replace(runtime.optimization.execution, initial_preview_review_guard=None),
                runtime.planning.clock,
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
        assert row and row.initial_preview_origin_id == preview.id
        bound = customer_optimization.bind(runtime.optimization, principal, provider)
        with pytest.raises(HTTPException, match="retracted"):
            forward_provenance.check(
                db, row, principal.user.id, bound.execution, runtime.planning.clock
            )
        db.rollback()
        # A retracted pointer cannot reattach, even to the previous origin.
        with pytest.raises(DBAPIError), db.begin_nested():
            db.execute(
                update(InitialPreviewReviewLink)
                .where(InitialPreviewReviewLink.review_id == prepared.review_id)
                .values(
                    preview_id=preview.id,
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
    with pytest.raises(HTTPException):
        prepare_preview_review(runtime, principal, provider, wid, preview.id, preview.digest())
    if actual_migration:
        with (
            customer_engine.begin() as conn,
            Operations.context(MigrationContext.configure(conn)),
            pytest.raises(RuntimeError, match="provenance"),
        ):
            migration.downgrade()
    assert not server.posts


def test_cached_ordinary_marker_cannot_bypass_new_protected_origin(
    customer_engine: Engine,
    configuration: Settings,
    monkeypatch: pytest.MonkeyPatch,
    replicas: Any,
) -> None:
    wid, preview, principal, provider, runtime, _, _ = ready(
        customer_engine, configuration, monkeypatch, replicas
    )
    with Session(customer_engine) as db:
        saved = db.get(PreviewRow, preview.id)
        assert saved
        intent = PreviewIntentV1.model_validate(saved.intent)
        assert (
            intent.choice
            and intent.mandate_id
            and intent.mandate_revision
            and preview.after_budget_micros
        )
        bound = customer_optimization.bind(runtime.optimization, principal, provider)
        ordinary = customer_optimization.prepare(
            db,
            wid,
            InitialOptimizationIntent(
                choice=intent.choice,
                mandate_id=intent.mandate_id,
                mandate_revision=intent.mandate_revision,
                action=BudgetIntent(kind="set_budget", amount_micros=preview.after_budget_micros),
            ),
            principal.user.id,
            bound,
        )
        review_id = ordinary.id
        db.commit()
    with Session(customer_engine, expire_on_commit=False) as cached:
        row = cached.get(ProviderExecutionReview, review_id)
        assert row and row.initial_preview_provenance_required is False
        assert row.initial_preview_origin_id is None
        cached.commit()
        with Session(customer_engine) as writer:
            writer.execute(
                update(ProviderExecutionReview)
                .where(ProviderExecutionReview.id == review_id)
                .values(
                    initial_preview_provenance_required=True, initial_preview_origin_id=preview.id
                )
            )
            writer.commit()
        assert row.initial_preview_provenance_required is False
        with pytest.raises(HTTPException, match="authority unavailable"):
            forward_provenance.check(
                cached,
                row,
                principal.user.id,
                replace(bound.execution, initial_preview_review_guard=None),
                runtime.planning.clock,
            )
