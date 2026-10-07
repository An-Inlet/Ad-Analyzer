# Populated Planning Restore Evidence

This test-only successor to `2d3b9b1` adds native PostgreSQL custom-archive restore
coverage for the real offline Meta journeys in migrations 0076 and 0077.
`tests/test_populated_planning_restore.py` uses actual Alembic migrations in a
unique disposable schema and the existing guarded native `pg_dump` / `pg_restore`
transport. It compares the complete schema/data/privilege fingerprint before and
after dropping and restoring only that schema. The two journeys use separate
archives, avoiding artificial cross-platform provenance.

The 0076 journey prepares an actual Meta preview-derived execution review. After
restore it verifies protected lineage, strict session-hash exclusion, foreign
workspace exclusion, immutable evidence, privacy erasure of the preview pointer,
and denial of replay while retaining the original protected review.

The 0077 journey uses actual mocked Meta HTTP acquisition and original execution,
real calibrated baseline, comparison and changed preview (46 to 47 million budget
micros). After restore it validates the preview's dependencies, denies expired,
changed-generation and revoked-original-session reads, verifies immutable numeric
evidence and strict session-hash/foreign-workspace exclusion, then erases the
numeric graph through the real privacy helper while preserving original financial
receipts and reservations. The only advertising POST is the fixture's separately
approved original offline action; archive and verification do not publish.

This proves these populated graphs survive a native local archive, not live
provider qualification, a production recovery-time objective, physical media
object restoration, or an aggregate Full pass. Existing financial/social restore
coverage remains unchanged in `test_inlet_restore_drill.py`.

## Reproduction

Use a dedicated disposable database, never an active validation database:

```sh
AD_ANALYZER_TEST_POSTGRES_URL=postgresql+psycopg://postgres@127.0.0.1:55432/inlet_initial_restore_test_20261006 \
AD_ANALYZER_CI_DISPOSABLE_POSTGRES=true \
INLET_RESTORE_POSTGRES_CONTAINER=inlet-b01-postgres \
/workspace/inlet-venv/bin/pytest -o addopts='' -q tests/test_populated_planning_restore.py
```

SQLite cases explicitly skip because this package verifies native PostgreSQL
archives. Provider responses and financial qualification are controlled offline
fixtures. No live configuration, remote activity or production policy changes.

Final focused result: **2 passed, 2 expected SQLite skips**, two existing Alembic
warnings, 61.79 seconds. Log: `/tmp/inlet-populated-planning-restore-final-pass.log`.
Whole-repository `ruff check .`, configured `mypy` (702 source files) and
`git diff --check` passed. No aggregate suite was run.
