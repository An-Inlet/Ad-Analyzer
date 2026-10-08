# Campaign Performance 0074 Fixture Repair

Base: `3d87ed4`. Only `tests/test_campaign_performance.py` and this ledger change.

The untouched named SQLite case reproduced `no such table:
main.initial_plan_previews` during 0075's `DROP initial_calibration_runs`. Its fixture
started with the current model-created schema and applied selected old downgrades,
leaving newer dependent tables referencing parents already dropped. This is a
mixed-schema test setup failure, not evidence that 0074 or new presence storage
introduced a production defect.

A function-scoped fixture now stages the isolated customer engine's initial
`create_all` call. It creates the recursively identified compatible prerequisite
ancestors from current model metadata, executes the real 0074 migration's
upgrade, empty downgrade, and upgrade, then creates only the remaining missing
current tables. This is **not** a complete historical 0073 migration replay.
The target tables retain the actual 0074 DDL and immutable trigger. No unrelated
historical downgrade runs against current descendants, and no foreign key is
disabled. SQLite foreign-key enforcement is explicitly enabled and asserted.

The existing actual Meta MockHTTP import and owned reader assertions are unchanged:
completion metadata UPDATE is rejected, a foreign-workspace current reference is
rejected, deleting the retained completion cascades its current pointer, and the
subsequent current read is unavailable. Current importer/invalidation hooks see the
complete current schema. No source hooks, consent, authority, migration, or
production behavior were patched. The schema staging patch is local to this test;
the shared customer-engine fixture still owns disposable schema creation/cleanup.

## Checks Actually Run

Approved disposable PostgreSQL configuration, isolated fixture schemas:

```text
pytest -q tests/test_campaign_performance.py -k actual_0074 --maxfail=1 --junitxml=/tmp/performance-fixture-repaired.xml
pytest -q tests/test_campaign_performance.py --junitxml=/tmp/performance-fixture-module.xml
```

Named repaired case: **2 passed, zero skipped, 3.084 seconds** (SQLite/PostgreSQL).
Complete focused module: **22 passed, zero skipped, 18.381 seconds**. Times are
JUnit elapsed. Whole `ruff check .`, prescribed `mypy` (**1071 source files**) and
`git diff --check` passed. Baseline failure log and repaired logs/JUnit are preserved
at `/workspace/inlet-evidence/20261008/performance-migration-fixture/`.

These new results qualify this fixture repair separately. They do not retroactively
change the earlier presence-storage cohort's exclusion or constitute the eventual
aggregate, historical-chain migration certification, or production qualification.
No Full, live provider, remote, hosted CI, merge, or deployment action occurred.
