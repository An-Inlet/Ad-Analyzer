# Reporting Presence Storage — 2026-10-08

Branch `codex/inlet-reporting-presence-storage`, base `66019e5`.

Implemented the reviewed finalized-presence storage interface in migration0089:
immutable, scoped header/fact tables; matching SQLite/PostgreSQL insert guards and
frozen migration DDL; complete canonical graph validation; idempotent identical
stores; historical reads; lifecycle registry, semantic erasure and archive support.
Legacy completion columns, manifests, collectors and Meta staging are unchanged.

`store_presence` checks the actual current completion/pointer, account ownership
and money context, current privacy, complete legacy manifest, campaign/native mapping
and every present numeric cell before inserting. The caller owns source/workspace
locks and final authority, must roll back failures, and commits the transaction.
Source coverage need not already advance: the future terminal publisher will insert
these records in the same transaction before advancing coverage. No helper commits
or performs network I/O.

Historical reads validate the retained completion and exact complete graph without
requiring a current pointer, active original session/source or unchanged live metrics.
Ordinary export revision advancement preserves history; semantic privacy bump erases
both tables. Export checks every header, including zero facts or all missing child
rows. An explicit snapshot-session `PresenceExportContext` caches only one graph,
checks each selected row, and rejects reuse after rollback/new transaction. It is
operation-local, with no global or Session.info cache. Existing archive quotas and
current delivery authorization/privacy fences remain. The 128 MiB pure graph bound
does not promise that every graph fits the smaller archive quota.

## Executed Checks

All commands used `/workspace/inlet-venv/bin/` executables in this worktree. DB tests
used `AD_ANALYZER_TEST_POSTGRES_URL=postgresql+psycopg://postgres@127.0.0.1:55432/inlet_oct07_next_integration_ci`
and `AD_ANALYZER_CI_DISPOSABLE_POSTGRES=true`, with isolated fixture schemas.

- Initial `pytest -q -o addopts='' tests/test_reporting_presence_storage.py`:
  **30 passed**, one existing Alembic configuration warning, **18.87s**.
- Expanded storage/archive/registry/legacy cohort initially stopped with
  **56 passed, 1 failed, 41.84s** at the existing SQLite0074 downgrade test below.
- Exact failing test on a separate untouched `66019e5` worktree:
  `pytest -q -o addopts='' 'tests/test_campaign_performance.py::test_actual_0074_immutable_metadata_and_owned_reference[sqlite]' --tb=short`:
  **1 failed, 4.14s**, same pre-existing error.
- Final `pytest -q -o addopts='' tests/test_reporting_presence_storage.py tests/test_model_registry.py tests/test_campaign_performance.py tests/test_provider_campaign_performance.py -k 'not test_actual_0074_immutable_metadata_and_owned_reference' --tb=short`:
  **98 passed, 2 deselected, 1 warning, 67.83s**. Both parameterizations of only that
  old migration test were deselected; no new0089 test was excluded.
- Whole configured `ruff check .`: passed.
- Whole configured `mypy`: passed, **1074 source files**.
- `git diff --check`: passed.

The pre-existing failure is `sqlite3.OperationalError: no such table:
main.initial_plan_previews` while0075 downgrade drops `initial_calibration_runs`.
No older migration was changed to conceal this failure. Actual0089 DDL, immutable
updates, scoped insert rejection, selected-event/actual-date binding, populated
refusal and empty downgrade/re-upgrade were tested on SQLite and PostgreSQL.

Additional acceptance covers transaction rollback, present-value/manifest/source
mismatch, corrupt/missing complete fact sets, raw byte/digest inconsistencies,
retained history after correction/disconnection, actual archive creation and
fail-closed corruption, delivery privacy recheck, and erasure preserving a foreign
workspace's graph. This is not a full-suite pass, live import qualification or a
claim that a terminal publisher exists. Next dependent package: reviewed Meta
window context/staging/publisher (0090), separately owned and not implemented here.
