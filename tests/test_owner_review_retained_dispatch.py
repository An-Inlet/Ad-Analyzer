"""Actual V6 retained SQL boundaries; no runtime registration or generation API."""

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from app.ads.models import DailyMetric
from app.billing.models import WorkspaceBilling
from app.campaign_review.models import MediaObject
from app.customers.models import CustomerMembership, CustomerSession
from app.planning_documents import creative_retained_sources as creative
from app.planning_documents import google_budget_owner_retained as owner
from app.planning_documents import retained_sources as retained
from app.planning_documents.catalog_receipt_models import CatalogReceiptRow, InputCatalogReceiptRow
from app.planning_documents.creative_history import (
    creative_local_witness,
    validate_creative_local_dependency,
)
from app.planning_documents.selected_plan_history import validate_selected_plan_history
from fastapi import HTTPException
from sqlalchemy import Engine, delete, update
from sqlalchemy.orm import Session

from tests.owner_review_retained_fixture import stored
from tests.test_creative_retained_dispatch import dependencies
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_shopify_sales import configuration as configuration


@pytest.fixture
def ready(
    customer_engine: Engine,
    configuration: Any,
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
        empty=getattr(request, "param", False),
    )


@pytest.mark.parametrize("ready", [False, True], indirect=True)
def test_actual_current_history_full_dependencies_and_old_wrappers(
    customer_engine: Engine, ready: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    doc, principal, fixture, calls = ready
    before = doc.model_dump_json(), len(calls)
    with Session(customer_engine) as db, db.begin():
        db.execute(
            update(CustomerMembership)
            .where(CustomerMembership.user_id == principal.user.id)
            .values(role="viewer")
        )
        db.execute(update(WorkspaceBilling).values(status="canceled"))

    def forbidden(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("retained reads must not inspect media bytes")

    monkeypatch.setattr(fixture.store, "read_exact", forbidden)
    with Session(customer_engine) as db, db.begin():
        saved = dependencies(db, doc)
        current = retained.capture_retained_sources(
            db, principal=principal, document=doc, now=datetime.now(UTC)
        )
        assert len(current) == len(doc.inputs.accounts) + 2
        assert [x.kind for x in current] == [
            "local_reporting_v3",
            "local_commerce_v1",
            "local_creative_basis_v1",
        ]
        retained.recheck_retained_sources(
            db, principal=principal, document=doc, dependencies=saved, now=datetime.now(UTC)
        )
        validate_selected_plan_history(db, doc)
        for subset in [saved[:-1], saved[1:], (*saved, saved[-1])]:
            with pytest.raises(retained.RetainedSourcesChanged):
                retained.recheck_retained_sources(
                    db,
                    principal=principal,
                    document=doc,
                    dependencies=subset,
                    now=datetime.now(UTC),
                )
        with pytest.raises(ValueError):
            creative_local_witness(doc)
        with pytest.raises(ValueError):
            validate_creative_local_dependency(doc, saved)
        with pytest.raises(retained.RetainedSourcesChanged):
            creative.capture_creative_retained_sources(
                db, principal=principal, document=doc, now=datetime.now(UTC)
            )
    assert before == (doc.model_dump_json(), len(calls))


@pytest.mark.parametrize("change", ["missing_link", "opaque", "media", "reporting", "session"])
def test_actual_mutation_current_and_historical_boundaries(
    customer_engine: Engine, ready: Any, change: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    doc, principal, _, _ = ready
    with Session(customer_engine) as db, db.begin():
        saved = dependencies(db, doc)
        db.expunge_all()
        if change == "missing_link":
            db.execute(delete(InputCatalogReceiptRow))
        elif change == "media":
            db.execute(delete(MediaObject))
        elif change == "reporting":
            db.execute(update(DailyMetric).values(clicks=DailyMetric.clicks + 1))
        elif change == "session":
            db.execute(update(CustomerSession).values(revoked_at=1))
    if change == "opaque":
        original_get = Session.get

        def changed(db: Session, entity: Any, *args: Any, **kwargs: Any) -> Any:
            row = original_get(db, entity, *args, **kwargs)
            if entity is CatalogReceiptRow and row is not None:
                db.expunge(row)
                row.authenticated_at += 1
            return row

        monkeypatch.setattr(Session, "get", changed)
    with Session(customer_engine) as db, db.begin():
        expected = HTTPException if change == "session" else retained.RetainedSourcesChanged
        for action in ("capture", "recheck"):
            with pytest.raises(expected):
                if action == "capture":
                    retained.capture_retained_sources(
                        db, principal=principal, document=doc, now=datetime.now(UTC)
                    )
                else:
                    retained.recheck_retained_sources(
                        db,
                        principal=principal,
                        document=doc,
                        dependencies=saved,
                        now=datetime.now(UTC),
                    )
        if change in {"missing_link", "opaque"}:
            with pytest.raises(ValueError, match="original owner input evidence unavailable"):
                validate_selected_plan_history(db, doc)
        else:
            validate_selected_plan_history(db, doc)


@pytest.mark.parametrize("attack", ["rollback", "connection", "late_owner", "expiry", "unexpected"])
def test_between_delegated_reads_stays_same_transaction(
    customer_engine: Engine, ready: Any, monkeypatch: pytest.MonkeyPatch, attack: str
) -> None:
    doc, principal, _, _ = ready
    original = creative._capture_creative_retained_sources

    def intercepted(db: Session, **kwargs: Any) -> Any:
        value = original(db, **kwargs)
        if attack == "rollback":
            db.rollback()
            db.begin()
        elif attack == "connection":
            connection = db.connection()
            connection.rollback()
            connection.begin()
        elif attack == "late_owner":
            db.execute(delete(InputCatalogReceiptRow))
        elif attack == "expiry":
            monkeypatch.setattr(creative, "database_utc_now", lambda db: doc.valid_until)
        else:
            raise RuntimeError("synthetic unexpected dependency fault")
        return value

    monkeypatch.setattr(creative, "_capture_creative_retained_sources", intercepted)
    with Session(customer_engine) as db:
        db.begin()
        with pytest.raises(
            RuntimeError if attack == "unexpected" else retained.RetainedSourcesChanged
        ):
            retained.capture_retained_sources(
                db, principal=principal, document=doc, now=datetime.now(UTC)
            )
        db.rollback()
    with Session(customer_engine) as db, db.begin():
        owner.validate_owner_review_plan_history(db, doc)
