"""Historical receipt archives validate exact retained graph, not live native authority."""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from app.campaign_review.storage import LocalMediaStore
from app.customers.models import CustomerSession
from app.lifecycle.contracts import LifecycleInputV1, LifecycleScopeV1
from app.lifecycle.export_serializers import fields, serialize
from app.lifecycle.exports import Authority
from app.lifecycle.inventory import export_section
from app.lifecycle.privacy import bump_workspace_export_revision
from app.lifecycle.service import begin
from app.planning_documents.catalog_receipt_models import (
    CatalogReceiptRow,
    CatalogReceiptSelectionRow,
    InputCatalogReceiptRow,
)
from app.planning_documents.catalog_receipts import CatalogReceiptUnavailable
from fastapi import HTTPException
from sqlalchemy import Engine, delete, select
from sqlalchemy.orm import Session

from tests.test_catalog_receipt_helpers import intent_for, observe, save
from tests.test_customer_exports import build, unpack
from tests.test_customer_exports import export_engine as export_engine
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_planning_evidence_adapter import setup_evidence
from tests.test_shopify_sales import configuration as configuration

pytestmark = pytest.mark.planning_boundary


def test_historical_receipt_sections_validate_complete_graph(
    customer_engine: Engine, configuration: Any, replicas: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    reader, ticket, principal, _ = setup_evidence(
        customer_engine, configuration, replicas, monkeypatch, "google_ads"
    )
    _, _, catalog = observe(customer_engine, reader, ticket, principal)
    ticket, _ = save(customer_engine, ticket, principal, intent_for(ticket, catalog))
    wid = ticket.inputs.workspace_id
    with Session(customer_engine) as db:
        # Retained history survives removal of its original authentication session.
        db.execute(
            delete(CustomerSession).where(CustomerSession.digest == principal.session.digest)
        )
        db.commit()
        scope = LifecycleScopeV1(workspace_id=wid)
        for model in (CatalogReceiptRow, CatalogReceiptSelectionRow, InputCatalogReceiptRow):
            result = export_section(db, scope, model.__tablename__)
            assert result["rows"]
            stored = db.scalars(select(model)).first()
            assert stored is not None
            row = {key: getattr(stored, key) for key in fields(model.__tablename__)}
            output, omitted = serialize(model.__tablename__, row, db=db)
            assert (
                not omitted and "session_digest" not in output and "authenticated_at" not in output
            )
            with pytest.raises(ValueError, match="scoped database"):
                serialize(model.__tablename__, row)
        header = db.scalars(select(CatalogReceiptRow)).one()
        row = {key: getattr(header, key) for key in fields(header.__tablename__)}
        with pytest.raises(ValueError, match="row changed"):
            serialize(header.__tablename__, {**row, "target_count": 0}, db=db)
        with db.begin_nested() as nested:
            db.execute(delete(InputCatalogReceiptRow))
            with pytest.raises(CatalogReceiptUnavailable):
                export_section(db, scope, "planning_input_revisions")
            nested.rollback()
        db.execute(delete(CatalogReceiptSelectionRow))
        db.commit()
        with pytest.raises((ValueError, HTTPException, CatalogReceiptUnavailable)):
            serialize(header.__tablename__, row, db=db)


def test_actual_receipt_archive_and_privacy_delivery_fence(
    export_engine: Engine,
    configuration: Any,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from collections.abc import Generator

    from app.database.session import get_db

    def export_database() -> Generator[Session, None, None]:
        with Session(export_engine) as db:
            yield db

    for client in replicas[:2]:
        client.app.dependency_overrides[get_db] = export_database
    reader, ticket, principal, _ = setup_evidence(
        export_engine, configuration, replicas, monkeypatch, "google_ads"
    )
    _, _, catalog = observe(export_engine, reader, ticket, principal)
    ticket, _ = save(export_engine, ticket, principal, intent_for(ticket, catalog))
    wid = ticket.inputs.workspace_id
    with Session(export_engine) as db:
        request = begin(
            db,
            principal,
            reader.provider,
            LifecycleInputV1(scope=LifecycleScopeV1(workspace_id=wid), operation="export"),
            "receipt-export-request",
            datetime.now(UTC),
        )
        db.commit()
        authority = Authority(export_engine, principal, reader.provider, wid, request.id)
    authority.claim()
    file, manifest = build(export_engine, authority, LocalMediaStore(tmp_path / "media"))
    try:
        _, entries = unpack(file)
        for model in (CatalogReceiptRow, CatalogReceiptSelectionRow, InputCatalogReceiptRow):
            rows = [
                json.loads(line)
                for line in entries[f"data/{model.__tablename__}.jsonl"].splitlines()
            ]
            assert rows and all(row["workspace_id"] == wid for row in rows)
        assert manifest["supported_customer_data_complete"] is True
        with Session(export_engine) as db:
            db.execute(delete(CatalogReceiptSelectionRow))
            db.commit()
        with pytest.raises(CatalogReceiptUnavailable):
            build(export_engine, authority, LocalMediaStore(tmp_path / "media"))
        with Session(export_engine) as db:
            bump_workspace_export_revision(db, wid)
            db.commit()
        with pytest.raises(HTTPException):
            authority.check()
    finally:
        file.close()


def test_maximum_receipt_payload_export_and_overbound_refusal(
    customer_engine: Engine, configuration: Any, replicas: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.planning_documents import catalog_receipts as receipts
    from app.planning_documents.storage import canonical

    reader, ticket, principal, _ = setup_evidence(
        customer_engine, configuration, replicas, monkeypatch, "google_ads"
    )
    inventory, metadata, _ = observe(customer_engine, reader, ticket, principal)

    def payload(padding: int) -> Any:
        # Synthetic size fixture only; no claim that a provider returned this padding.
        native = inventory.model_copy(update={"reasons": ["x" * padding]})
        bound = metadata.model_copy(update={"native_inventory_digest": native.digest()})
        return receipts.ReceiptPayloadV1(inventory=native, metadata=bound)

    limit = 1024 * 1024
    base = len(canonical(payload(0)).encode())
    maximum = payload(limit - base)
    assert len(canonical(maximum).encode()) == limit
    with Session(customer_engine) as db:
        receipts.write_catalog_receipt(
            db,
            principal=principal,
            source=ticket.sources[0],
            inventory=maximum.inventory,
            metadata=maximum.metadata,
            now=reader.clock(),
        )
        db.commit()
        header = db.scalars(
            select(CatalogReceiptRow).where(CatalogReceiptRow.payload_bytes == limit)
        ).one()
        row = {key: getattr(header, key) for key in fields(header.__tablename__)}
        exported, omitted = serialize(header.__tablename__, row, db=db)
        assert not omitted
        assert (
            len(canonical(receipts.ReceiptPayloadV1.model_validate(exported["document"])).encode())
            == limit
        )
        overbound = payload(limit - base + 1)
        with pytest.raises(CatalogReceiptUnavailable, match="capacity_exceeded"):
            receipts.write_catalog_receipt(
                db,
                principal=principal,
                source=ticket.sources[0],
                inventory=overbound.inventory,
                metadata=overbound.metadata,
                now=reader.clock(),
            )
        db.rollback()
        assert len(db.scalars(select(CatalogReceiptRow)).all()) == 2
