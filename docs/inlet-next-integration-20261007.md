# Inlet Customer Foundation Integration — October 7

This isolated branch combines reviewed local packages with the preserved validation
repairs. It is not the frozen `9450aa48` qualification tree, is not deployed, and
does not establish live provider qualification.

## Integrated Code

- `422bbe4`: configured planning/native observations, immutable reported-feedback
  revisions, conditional customer budget consent, Google/Meta execution and actual
  configured TLS customer journeys.
- `02b405cd`: goal progress, canonical workspace-before-goal locking, and original
  session/role/revision/source-context revalidation after interpretation and after
  its accounting commit. Denied delivery retains incurred usage without replay.
- `9450aa48`: prior historical migration fixture repairs and the diagnostic Meta
  connection race harness. The original failed run's worker cause remains unknown;
  the controlled delayed-start and removed-lock evidence remains in its ledger.

The two merges required only progress-ledger conflict resolution; both histories
were retained. No product or test behavior was changed to resolve a conflict.

## Checks Actually Run

On integration head `413922fa3f59bc4e72a812172c4ed1704dd9d45c`:

- Whole-repository Ruff passed; mypy passed for 770 source files; diff check passed.
- Nine-file interpretation/progress/budget/feedback/configured Google+Meta TLS
  cohort: **38 passed, 42 skipped, 83.31 seconds**. This invocation omitted the
  disposable-PostgreSQL flag: 40 PostgreSQL cases were not exercised, alongside
  two expected SQLite concurrency skips. Log: `inlet-next-integration-focused.log`.
- The same cohort restricted to PostgreSQL, with its explicit disposable flag:
  **40 passed, 40 deselected, 187.68 seconds**. Log:
  `inlet-next-integration-postgres.log`.
- Seven-file historical and new populated migration/revision cohort:
  **29 passed, 3 expected SQLite skips, 25 warnings, 108.83 seconds**.
  Log: `inlet-next-integration-migrations.log`.

All database checks used the separate `inlet_oct07_next_integration_ci` database.
The active frozen Full database and checkout were untouched. No additional Full,
hosted run, push, merge to main, deployment or live provider call was performed.

The contracts/catalog/provenance/TikTok packages being developed afterward are not
part of these results. They require their own integration and checks.
