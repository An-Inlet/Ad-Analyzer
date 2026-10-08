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

## Historical Archive Completion

Integrated frozen helper `7fe1453` as `e45fd71`; retained its approved historical
validator addendum when resolving the append-only design-document conflict.
The database-aware export adapter validates the actual scoped scalar row, canonical
receipt payload, complete selection index, and complete input-revision receipt links.
Both snapshot archives and bounded internal sections use this adapter. Serialization
without the scoped database remains fail-closed. Original session removal and elapsed
receipt authority do not authorize new work or remove otherwise retained history.
Session digests and authentication timestamps remain excluded from exports.

Receipt payloads retain the exact 1 MiB canonical bound; the existing planning row
bound accommodates the decoded document and scalar/JSON overhead. Global archive,
row-count, deadline, privacy checkpoints, and non-planning row limits are unchanged.
A missing selection row aborts archive construction rather than claiming completeness.

Validation:

- `AD_ANALYZER_TEST_POSTGRES_URL=<disposable-local-test-database> AD_ANALYZER_CI_DISPOSABLE_POSTGRES=true /workspace/inlet-venv/bin/pytest -q -o addopts='' tests/test_catalog_receipt_exports.py`: **6 passed in 21.84s**, SQLite and PostgreSQL. Covers actual archive completeness, corrupted selection refusal, delivery privacy fence, original-session deletion, scalar mismatch, exact 1 MiB synthetic capacity fixture and one-byte-overbound refusal without partial receipt insertion.
- Initial run: 4 passed / 2 fixture failures (SQLite authentication replicas used a different database; lifecycle request key below its existing minimum). Corrected fixture wiring/key only; no product guard changes.
- `/workspace/inlet-venv/bin/ruff check .`: passed.
- `/workspace/inlet-venv/bin/mypy`: **1061 source files passed**. An initial `mypy .` invocation hit the repository's duplicate script-module discovery; the configured command above is authoritative.
- `git diff --check`: passed.

No live provider calls, deployment, full-suite qualification, or receipt route/service
integration is claimed. Source helpers own quotas and cleanup; this package validates
retained export and schema/privacy behavior. Root owns customer-flow integration.

- Compatibility command: `AD_ANALYZER_TEST_POSTGRES_URL=<disposable-local-test-database> AD_ANALYZER_CI_DISPOSABLE_POSTGRES=true /workspace/inlet-venv/bin/pytest -q -o addopts='' tests/test_catalog_receipt_model_contracts.py tests/test_catalog_receipt_storage.py tests/test_model_registry.py tests/test_planning_document_storage.py::test_actual_archive_includes_planning_graph_and_privacy_fences_delivery`: **10 passed, 1 existing Alembic path-separator warning in 16.54s**.

Final completeness refinement validates receipt bindings on **every input revision**,
including a zero-row retained link set. This detects total link deletion before any
archive can claim completeness. Focused history/archive rerun (same DB environment,
`tests/test_catalog_receipt_exports.py -k 'not maximum' tests/test_planning_document_storage.py::test_actual_archive_includes_planning_graph_and_privacy_fences_delivery`):
**6 passed, 2 deselected in 34.86s**.

Integrated helper capacity repair `a1cfd96` as `ac6cb06`; the final maximum test now
requires `CatalogReceiptUnavailable("capacity_exceeded")`, not an arbitrary exception.
`tests/test_catalog_receipt_exports.py -k maximum`: **2 passed, 4 deselected in 10.68s**.
The helper repair was applied during the tail of the history compatibility run; it
changes only write-time oversize normalization, and the dedicated size rerun ran
against the repaired source. Final Ruff, configured mypy, and diff checks passed.
