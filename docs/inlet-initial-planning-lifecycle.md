# Initial Planning Retention And Export

Local successor of `85e52eb`, frozen contracts `3c835fb`, models `1f1e71b`,
backend/migration `7428640`, and effective-clock repair `2175a5b`. This package
implements derived-data lifecycle handling, not empirical learning qualification,
spending authority, live configuration or an owner-selected retention duration.

Capture configuration remains absent by default. Cleanup nevertheless processes
persisted explicit deadlines, including closing workspaces. One bounded housekeeping
pass selects at most20 workspaces (hard limit100), takes the workspace lock first,
and rechecks actual database expiry before deleting anything. No provider IO or paid
entitlement is required. A future injected application clock cannot prove DB expiry.

Observation expiry conservatively erases that workspace's initial-planning graph via
the shared semantic privacy bump. Short-lived preview/calibration expiry deletes only
the expired derived rows, retaining eligible historical observations. The approved
0075 triggers advance the export counter on before-expiry deletion, but not on actual
DB-expired deletion; their workspace NOWAIT guard remains unconditional. This avoids
requiring a new provider import every time a preview's short lifetime ends.

That exception is safe only alongside archive deadlines: the builder captures the
minimum expiry of included observations/reports/previews. Every fresh authorization
checkpoint compares it against both application UTC and fresh database wallclock
(PostgreSQL `clock_timestamp()`, not transaction-start time). A lagging application
clock cannot extend delivery beyond DB expiry. Expiry is enforced without waiting
for the cleanup worker, and interrupted streams close their temporary file/slot.

True privacy invalidation, native disconnect/reconnect/generation loss and workspace
closure delete capsules and derived numerics transactionally. Hooks cover Meta,
Google, TikTok/generic-source transitions and closure's separate bulk-revocation path.
The same existing export/privacy revision fences concurrent snapshots. Correction-only
derived deletion retains labelled historical observations and advances the same
counter before the next terminal completion stamps it; it never invokes recursive
semantic erasure. Historical capsule eligibility relies on surviving owned rows and
current source generation/ownership, not promotion of captured privacy metadata into
current reporting facts. Current-report readers retain their existing strict checks.

No protected execution review, original attempt/receipt or exposure reservation is
deleted by these hooks. Existing closure remains blocked by unresolved external or
retention obligations; this package does not claim full erasure or physical worker
termination. Lifecycle classifications are explicit for all four new tables. The
serializer validates typed aggregate/report/preview/objective/intent documents against
owned scalar fields/digests/times, rejects unknown JSON, and excludes the actual
`original_session_digest` authentication lookup hash.

A broader actual-API regression also exposed a pre-existing omission:
`campaign_performance_completions` was missing from the local-work registry, causing
closure `reconcile-local` to raise on both databases. It is now explicitly classified
as retained source completion metadata, preserving the fail-closed registry check.

Validation records:

- Initial lifecycle suite:16 passed on SQLite/PostgreSQL after correcting fixture-only
  disabled SQLite foreign keys and a test clock name shadow (initial8 failures were
  not product defects).
- Broader export/privacy/closure/Meta/TikTok suite:122 passed,2 expected skips;2 closure
  API failures identified the registry omission above. Corrected final run below.
- Actual populated0075 Alembic graph/FK/immutable/cascade/rollback/downgrade/upgrade plus
  Google connection and customer runtime tests:50 passed,1 SQLite migration skip.
- Final focused successor tests (`test_initial_planning_lifecycle`, `test_customer_quiescing`,
  `test_initial_observations`, `test_initial_calibration`, `test_initial_planning_migration`):
  71 passed,2 expected SQLite-only skips in56.45s.
- Final populated migration recheck plus actual housekeeping dispatcher cleanup:
  3 passed,1 SQLite migration skip in4.33s. A prior static type correction changed the
  insert expression to SQLAlchemy's typed `insert(ObservationRow)`; behavior rechecked.
- `ruff check .`: passed. Configured `mypy`: passed,647 source files. `git diff --check`: passed.

Tests use fresh disposable database `inlet_performance_restore_test_20261006`, each PG
fixture in an isolated schema; no shared/candidate database reset. PostgreSQL purge
contention and independent archive-snapshot erasure are exercised; clock tests need
no sleep. No Full, live service, push, PR, CI dispatch, deployment or credentials.
