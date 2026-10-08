# Current Lifecycle Tests With Genuine Retired Producers

Branch `codex/inlet-current-lifecycle-adaptation`, base `a3cea7e`. This package
changes tests only. Current application guards, database triggers, serializers,
privacy deletion and restore behavior remain unchanged.

The reviewed `fb40d8a` subprocess seam remains pinned to
`2155ff3e3ab00cd62057dd86cb49d45359d4f49f`. It imports the exact historical
application and fixture in its own interpreter against a current disposable
schema. No old runtime, callback, principal or authority object crosses back.
The parent uses fresh current SQLAlchemy sessions and immutable returned IDs.

## Coverage Mapping

- `test_initial_review_lifecycle.py`: current protected provenance export, foreign
  workspace isolation, inventory classification, immutable raw SQL, semantic
  erasure, non-reattachment, financial retention and populated 0076 downgrade
  refusal. Missing forward authority and retracted-current-guard denial remain.
  The cache regression now places an adversarial stale ordinary marker in the
  identity map of a genuinely protected row; current `populate_existing` must
  recover the stored protected origin. It does not recreate ordinary review
  generation in current code. The old forward re-prepare call is no longer used
  as a lifecycle assertion; the current provenance guard directly rejects the
  erased origin. Historical forward behavior belongs to the separate pin harness.
- `test_initial_execution_proof_storage.py`: the existing clearly labeled
  structural V2 document fixture is unchanged. Genuine historical financial and
  preview parents replace current execution setup. Exact binding, forged proof,
  serializer, immutable SQL, deletion and actual 0081 migration checks remain.
  Synthetic structural proof values grant no execution authority.
- `reported_feedback_lifecycle_fixture.py` and
  `test_reported_feedback_lifecycle.py`: the actual retained attempt/receipt is
  loaded by current code. Existing synthetic storage-only comparison/capsule/slot
  contracts remain unchanged; contributor erasure, strict export, persisted-clock
  retention, actual 0077 triggers, foreign parents and PostgreSQL workspace-fence
  checks remain current.
- `test_initial_rule_dependencies.py`: a genuine historical Start replaces the
  old synthetic pending candidate graph. Current code deletes selected or
  historical observations or one captured dependency, then verifies the entire
  candidate graph disappears, the mandate remains, and protected Start loses only
  its nullable candidate link.
- `test_retained_initial_rule_lifecycle.py::test_current_populated_0085_refuses_downgrade`:
  the current migration refuses a genuine retained Start. The original forward
  admission tests remain separately mapped by the historical compatibility lane.
- `test_populated_planning_restore.py::test_native_restore_real_protected_meta_review`:
  actual PostgreSQL dump/restore preserves protected export, foreign isolation,
  immutability and post-restore erasure while retaining the single genuine
  historical attempt. Only this fixture-owned schema is restored.

## Narrow Seam Extensions

`prepare_schema(engine)` runs only before seeding, allowing existing exact empty
migration downgrade/upgrade tests on the same engine that receives genuine rows.
SQLite uses the seam's file-backed current schema rather than accidentally testing
DDL on a different in-memory fixture. The closed child selector is `review` or
`initial_rule`: the former makes one MockHTTP effect; the latter invokes the
unchanged pinned `initial_start_case` and actual Start with zero provider effects.
Each mode returns a separate frozen ID type. No arbitrary callable/import selector
is accepted by the child.

PostgreSQL schema validation additionally accepts exactly
`inlet_migration_fixture_<32 lowercase hex>` for the existing restore fixture,
alongside `inlet_test_<32 lowercase hex>`. The disposable-database requirement and
exact `current_schema()` equality check remain. No shared database reset occurs.

## Qualification

Evidence directory: `/workspace/inlet-evidence/20261008/current-lifecycle/`.
The first partial run (`initial.log/xml`) was invalidated when the child command
shape changed while the parent had the earlier fixture loaded. Two argument-count
failures resulted. It is not final qualification and no product defect is claimed.
The fresh combined run uses the stable source and writes `qualified.log/xml`.

Combined run: **42 passed, 2 skipped, 2 warnings, 1 setup error in 607.60s**.
Both skips are explicit PostgreSQL-only behavior on SQLite (workspace row lock and
native PostgreSQL archive). Warnings are existing Alembic path-separator notices.

The setup error was the actual 0077 SQLite batch rebuild of `meta_connections`
while the newer empty 0090 presence trigger referenced it. The fixture now
removes/reinstalls 0090 around that historical migration exercise **on SQLite
only**. The first repair unnecessarily attempted 0090 downgrade against the
PostgreSQL metadata-created schema, where the migration-specific constraint name
is absent: `migration-repair.log/xml` records **1 passed, 1 setup error in 14.31s**.
PostgreSQL does not batch-rebuild this table and retains its original passing
migration sequence. No production schema/trigger/migration code was altered.

Final affected both-database rerun: **2 passed in 25.98s** in
`migration-final.log/xml`. Thus every selected current case passed across the
combined run plus targeted repair; there was no claim of a fresh single all-green
combined run. Whole Ruff passed (`ruff-final.log`); bare mypy passed **1109 source
files** (`mypy-final.log`); `git diff --check` passed.

No W1 aggregate, live provider, hosted or production qualification is claimed.

Commands (the PostgreSQL URL is the existing loopback disposable fixture target):

```sh
AD_ANALYZER_TEST_POSTGRES_URL=postgresql+psycopg://postgres@127.0.0.1:55432/inlet_oct07_next_integration_ci \
AD_ANALYZER_CI_DISPOSABLE_POSTGRES=true \
INLET_RESTORE_POSTGRES_CONTAINER=inlet-b01-postgres \
/workspace/inlet-venv/bin/pytest -q -o addopts='' \
  tests/test_initial_review_lifecycle.py \
  tests/test_initial_execution_proof_storage.py \
  tests/test_reported_feedback_lifecycle.py \
  tests/test_initial_rule_dependencies.py \
  tests/test_retained_initial_rule_lifecycle.py \
  tests/test_populated_planning_restore.py::test_native_restore_real_protected_meta_review \
  --maxfail=2 --junitxml=/workspace/inlet-evidence/20261008/current-lifecycle/qualified.xml
/workspace/inlet-venv/bin/ruff check .
/workspace/inlet-venv/bin/mypy
git diff --check
```
