# Explicit Model And Guard Registration — 2026-10-07

Isolated from frozen integration `bb836c2` on
`codex/inlet-model-registry-repair`. A bounded reproduction of
`tests/test_model_registry.py::test_registry_covers_every_model_module` failed:
`app.commerce.acquisition_guards` appeared in the declared-model list despite
having no ORM model class. This is independent reproduction; the active frozen
Full run has not yet emitted its terminal failure report.

Keep required acquisition guard installation in the central registration path,
now in explicit `GUARD_MODULES`, after declared `MODEL_MODULES`. Retain exact model
inventory coverage. A new fresh-process regression verifies registration imports
and installs the acquisition metadata listener without the test installing it
first. No schema, ownership guard or source-retraction behavior is removed.

Checks actually run:

- Before repair: isolated model-inventory regression **1 failed in 1.17s**.
- After repair: `python -m pytest -ra tests/test_model_registry.py`:
  **4 passed in 2.34s**.
- `python -m pytest -ra tests/test_commerce_acquisition_storage.py::test_actual_owned_job_immutable_private_export_and_nonempty_downgrade`:
  **2 passed in 5.32s**, SQLite/PostgreSQL on a disposable local database.
- Whole `ruff check .`, prescribed `mypy` (**923 files**), `git diff --check`:
  passed. An initial Ruff import-order finding was corrected before final checks.

No edits to frozen Full checkout/database, no hosted retry, no provider IO.
