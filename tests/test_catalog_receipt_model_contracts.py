"""Frozen model seam only; actual migration/trigger qualification follows separately."""

import pytest
from app.database.models import register_models
from app.planning_documents.catalog_receipt_models import (
    CatalogReceiptRow,
    CatalogReceiptSelectionRow,
    InputCatalogReceiptRow,
)
from sqlalchemy import CheckConstraint, ForeignKeyConstraint, create_engine
from sqlalchemy.schema import CreateTable


@pytest.mark.parametrize("dialect_name", ["sqlite", "postgresql+psycopg"])
def test_receipt_ddl_preserves_exact_scoped_keys_and_bounds(dialect_name: str) -> None:
    dialect = create_engine(dialect_name + "://").dialect
    metadata = register_models()
    header = metadata.tables[CatalogReceiptRow.__tablename__]
    selections = metadata.tables[CatalogReceiptSelectionRow.__tablename__]
    links = metadata.tables[InputCatalogReceiptRow.__tablename__]
    assert tuple(header.primary_key.columns.keys()) == ("workspace_id", "id")
    assert tuple(selections.primary_key.columns.keys()) == (
        "workspace_id",
        "account_id",
        "selection_key",
    )
    assert tuple(links.primary_key.columns.keys()) == (
        "workspace_id",
        "plan_id",
        "input_revision",
        "account_id",
    )
    for table in (header, selections, links):
        ddl = str(CreateTable(table).compile(dialect=dialect))
        assert "FOREIGN KEY" in ddl
        assert all(
            not column.nullable and column.server_default is None for column in table.columns
        )
    assert "1048576" in str(CreateTable(header).compile(dialect=dialect))
    assert "400" in str(CreateTable(links).compile(dialect=dialect))
    assert not any(fk.target_fullname.startswith("customer_") for fk in header.foreign_keys)
    link_fks = [
        constraint
        for constraint in links.constraints
        if isinstance(constraint, ForeignKeyConstraint)
    ]
    assert {(tuple(fk.column_keys), fk.ondelete) for fk in link_fks} == {
        (("workspace_id", "plan_id", "input_revision"), "CASCADE"),
        (("workspace_id", "receipt_id", "account_id", "connection_id"), "RESTRICT"),
    }
    assert len([c for c in header.constraints if isinstance(c, CheckConstraint)]) == 5
