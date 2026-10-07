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

## Subsequent Origin Integration And Historical Fixtures

Head `92c472e` adds origin schema `59a1235` and catalog `2cc0bd1`. This is separate
from the earlier green integration above. Its first targeted cohort produced
**4 failed, 53 passed, 4 skipped in 133.67 seconds**: four historical fixtures
queried new ORM origin columns in genuine pre0080 databases.

The test-only repair reflects the real historical revision table and exposes only
readonly legacy/null origin discriminators. Explicit fixtures replace exact class
references in application modules, restore aliases including later imports, and
dispose only their own mapper. Production models, financial checks and physical
constraints are unchanged. Installation asserts that the new table/columns do not
exist; older schemas without any execution revision table never install it.

Retained intermediate evidence:

- Initial reflection omitted foreign-key target metadata: 3 failed, 1 passed;
  full foreign-key reflection corrected that fixture defect: 4 passed.
- Broader migration cohort: **1 failed, 75 passed, 7 skipped, 2 errors** in
  147.70 seconds. The failure was an overly broad helper invocation before the
  revision table existed. Explicit fixture installation fixes it. The two SQLite
  errors exposed a separate ORM foreign-key DDL metadata defect under investigation.
- Cleanup implementation initially omitted one pytest fixture parameter:
  1 failed, 7 passed. The parameter is now explicit.
- Final historical/isolation cohort: **8 passed, 26 warnings, 20.57 seconds**.
  It includes a late-import alias restoration regression and populated historical
  migration behavior. Whole Ruff, mypy782 and diff check passed.

The ORM cross-dialect defect and a final combined cohort remain outstanding here;
these eight passes do not relabel either failed aggregate as successful. Evidence
logs use the `inlet-next-integration-historical-*` and
`inlet-next-integration-migration-final` prefixes.
