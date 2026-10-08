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

## Database Checkpoint

Actual0088 frozen SQLite DDL and PostgreSQL Alembic upgrade now tested. Receipt
inserts bind original actor/session/authentication epoch and owner membership;
canonical payload_bytes equals actual UTF-8 octets. Input links bind scoped input
actor/digest, receipt composite and creation deadline. Every UPDATE is denied on
all three tables; unused deletion and FK-safe semantic erasure remain possible.
Linked receipt deletion is RESTRICT; deleting sessions does not delete history.
Populated downgrade refuses; empty downgrade/re-upgrade succeeds.

`pytest -q -o addopts='' tests/test_catalog_receipt_storage.py tests/test_model_registry.py -x`
with existing disposable PostgreSQL environment:6passed5.52s, one existing Alembic
path_separator warning. First test setup run failed because the synthetic account
omitted existing required currency/time_zone; fixture corrected before final pass.
No product default/schema requirement was weakened.

Model registry and lifecycle ownership inventory include all tables; semantic privacy
bump deletes input links before inputs, selections before headers. Receipt export is
INTENTIONALLY fail-closed at this intermediate checkpoint until the helper lane's
historical validators can check canonical payload plus complete associated rows.
Planning-specific row cap applies; global archive caps stay unchanged. This checkpoint
does not claim receipt archive/export completion. Helper database qualification may
consume this exact DDL/trigger snapshot; storage lane continues export integration.
