# W1 SQLite Migration Fixture Repair

Base `d85db66`; approved interface `13fed34`. This test-only successor addresses
one frozen W1 failure, not the aggregate result or the five PostgreSQL producer
mismatches. Frozen aggregate XML and traceback mapping remain unchanged.

The current 0090 trigger references `meta_connections` while the older 0077
SQLite batch migration temporarily rebuilds that table. The fixture now proves
0090 context/payload data empty, calls actual 0090 downgrade before the original
0077 roundtrip, and reinstalls actual 0090 afterward. Every original staged
metric, checkpoint and page survives; original legacy columns are compared during
the older schema and the complete initial snapshot after reinstall. Restored
0090 trigger names are checked. PostgreSQL follows its original DDL sequence;
the existing phase guard/refusal test is unchanged. No production migration,
privacy hook, authority guard or schema metadata is patched.

Qualification: `pytest -q tests/test_reported_feedback_migration.py` with the
explicit disposable PostgreSQL environment: **3 passed, 1 expected SQLite skip,
0 failures/errors, 6.008 seconds** (JUnit). The skipped case requires PostgreSQL
DDL; both staging-roundtrip variants passed. Four existing Alembic configuration
warnings. Whole `ruff check .`, bare `mypy` (**1127 source files**) and
`git diff --check` passed. No aggregate run or aggregate database access.

Durable evidence: `/workspace/inlet-evidence/20261009/w1-migration-sqlite/`
`focused.log` and `focused.xml`. Remaining work: separately frozen single-phase
commerce producer feasibility at real 0053; social two-phase remains deferred.
