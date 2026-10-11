# Selected Plan Historical Integrity

The reserved v4 historical port validates the complete ordinary/local dependency
set, exact saved account proof digests, ownership/version/privacy/time bindings,
and every chosen retained capture against its saved selection, request, aggregate
and full capture commitments. Duplicate, missing and extra dependency rows fail.
Current aggregate pointers, acquiring sessions and observation expiry are not
historical authority. The caller still owes current viewer/lifecycle authorization.
Opaque original aggregate and campaign-map hashes are bound commitments, not a
claim to reconstruct old mutable SQL. No v4 registration or archive wiring yet.

Validation: `pytest -q tests/test_selected_plan_history.py` with the explicit
disposable PostgreSQL opt-in passed 36 tests, zero skips, in 20.615s. This includes
28 pure dependency cases and 8 SQLite/PostgreSQL cases using actual selected API
captures (the catalog fixture is synthetic). Retained reads survive aggregate
pointer removal and reject missing captures, changed campaign ownership mappings,
and capture hash changes. This does not yet qualify actual ordinary sync, full
historical archive delivery or semantic erasure of persisted v4 plans.

Whole-repository Ruff and configured `mypy` passed (1333 files); diff check passed.
Evidence: `/workspace/inlet-evidence/20261011/selected-plan-history/root-02.{log,xml}`
and `mypy-03.log`. First run is retained: 34 passed, 2 failed because the fixture
deleted the current selection head, correctly invoking semantic erasure. The
positive fixture now removes only the aggregate pointer. An initial `mypy .`
invocation failed with duplicate module discovery; the repository-configured
no-path invocation passed. No credentials, providers, hosted CI, push or release.
