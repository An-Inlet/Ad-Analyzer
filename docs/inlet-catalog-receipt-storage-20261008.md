# Catalog Receipt Storage

Initial model-interface freeze from root5ec904c:
`app/planning_documents/catalog_receipt_models.py` exposes CatalogReceiptRow,
CatalogReceiptSelectionRow and InputCatalogReceiptRow with the exact reviewed
column names and SQL types. Composite ownership FKs, deletion behavior, uniqueness,
count/byte/time ordering checks are represented; no public DTO changes.

Interface-only checks: `pytest -q -o addopts='' tests/test_catalog_receipt_model_contracts.py`
2passed0.06s, compiling SQLite/PostgreSQL DDL and checking exact scoped keys,
nonnullable/no-default fields, history-preserving identity scalars and bounds.
Whole Ruff/mypy1049 and diff checks pass. This first freeze is not migration,
trigger, runtime registration or archive qualification. Those remain this storage
lane's next package; helper consumers may import the names but must wait for actual
DDL/triggers before claiming database acceptance.
