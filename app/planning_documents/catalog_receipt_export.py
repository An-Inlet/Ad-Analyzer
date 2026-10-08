"""Scoped historical receipt export; validation never depends on live session or TTL."""

import json
from collections.abc import Mapping
from typing import Any

from sqlalchemy.orm import Session

from app.planning_documents.catalog_receipt_models import (
    CatalogReceiptRow,
    CatalogReceiptSelectionRow,
    InputCatalogReceiptRow,
)
from app.planning_documents.models import PlanInputRow
from app.planning_documents.storage import MAX_PLANNING_ROW_BYTES, document_for_row


def export_receipt_row(db: Session, table: str, row: Mapping[str, Any]) -> dict[str, Any]:
    # Imported lazily: receipt helpers reuse the ordinary input resolver/storage.
    from app.lifecycle.export_serializers import fields
    from app.lifecycle.inventory import scalar
    from app.planning_documents.catalog_receipts import (
        validate_retained_input_receipts,
        validate_retained_receipt,
    )
    from app.planning_documents.context import PlanInputRevision

    stored: CatalogReceiptRow | CatalogReceiptSelectionRow | InputCatalogReceiptRow | None
    if table == CatalogReceiptRow.__tablename__:
        stored = db.get(CatalogReceiptRow, (row["workspace_id"], row["id"]), populate_existing=True)
    elif table == CatalogReceiptSelectionRow.__tablename__:
        stored = db.get(
            CatalogReceiptSelectionRow,
            (row["workspace_id"], row["account_id"], row["selection_key"]),
            populate_existing=True,
        )
    elif table == InputCatalogReceiptRow.__tablename__:
        stored = db.get(
            InputCatalogReceiptRow,
            (row["workspace_id"], row["plan_id"], row["input_revision"], row["account_id"]),
            populate_existing=True,
        )
    else:
        raise ValueError("unknown receipt export table")
    if stored is None or any(
        scalar(getattr(stored, key)) != scalar(row[key]) for key in fields(table)
    ):
        raise ValueError("receipt export row changed")
    receipt_id = stored.id if isinstance(stored, CatalogReceiptRow) else stored.receipt_id
    receipt = db.get(CatalogReceiptRow, (row["workspace_id"], receipt_id), populate_existing=True)
    if receipt is None:
        raise ValueError("retained receipt unavailable")
    payload, _ = validate_retained_receipt(db, receipt)
    if isinstance(stored, InputCatalogReceiptRow):
        source = db.get(
            PlanInputRow,
            (stored.workspace_id, stored.plan_id, stored.input_revision),
            populate_existing=True,
        )
        if source is None:
            raise ValueError("retained receipt input unavailable")
        inputs = document_for_row(
            source.__tablename__,
            {column.name: getattr(source, column.name) for column in source.__table__.columns},
        )
        assert isinstance(inputs, PlanInputRevision)
        validate_retained_input_receipts(db, inputs)
    output = {key: scalar(row[key]) for key in fields(table) if key != "canonical_json"}
    if isinstance(stored, CatalogReceiptRow):
        output["document"] = payload.model_dump(mode="json")
    if (
        len(json.dumps(output, ensure_ascii=False, allow_nan=False).encode())
        > MAX_PLANNING_ROW_BYTES
    ):
        raise ValueError("receipt export row exceeds bound")
    return output


def validate_input_receipt_export(db: Session, row: Mapping[str, Any]) -> None:
    """Check even zero retained links, so deleting an entire link set fails closed."""
    from app.planning_documents.catalog_receipts import validate_retained_input_receipts
    from app.planning_documents.context import PlanInputRevision

    inputs = document_for_row(PlanInputRow.__tablename__, row)
    assert isinstance(inputs, PlanInputRevision)
    validate_retained_input_receipts(db, inputs)
