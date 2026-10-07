
## Local Backend Checkpoint

The capture/calibration services flush within the caller's transaction and never commit
or release its workspace locks. Actual Meta terminal publication invalidates account
calibration reports before stamping the replacement completion's export revision.
Historical observations remain labelled, retained prospective captures until explicit
expiry or semantic source/privacy deletion. Google/TikTok terminal writes also retract
account-derived reports, including unqualified legacy-descriptor completions.

Migration 0075 installs the same immutable-document and dependency-deletion triggers
used by metadata-created test databases. Deleting any dependency erases the entire
calibration report (and its previews). Raw deletes take an unconditional PostgreSQL
workspace NOWAIT fence. Expired rows do not advance the export counter when the
DB UTC wallclock has reached their expiry; archive delivery independently enforces its
earliest included expiry. Pre-expiry deletions still advance the counter. This avoids
invalidating unchanged current performance merely because a short-lived report expires.

Local checkpoint: 35 focused tests passed (SQLite and PostgreSQL capture/ownership,
immutability/dependency deletion, DB-time expiry fence, required contracts and pure
chronological sensitivity); Ruff and mypy (641 source files) passed. Actual composed
confirmed-goal/API/browser calibration and retention/export composition remain separate
consumer/lifecycle validation, not claimed by this checkpoint. App/DB clock-skew delivery
hardening is coordinated before final integration. No remote or live operations occurred.

### Delivery Clock And Acquisition Age Successor

`initial_planning.clock.effective_now(db, runtime)` uses the later of the application
UTC clock and a fresh database UTC wallclock, including after lock waits. It delegates
to the shared lifecycle helper; PostgreSQL uses `clock_timestamp()`, not transaction
start time. A lagging application clock therefore cannot serve a DB-expired capsule.
The pure replay function remains deterministic for its explicit evaluation cutoff.

Minimum closed-window age is measured at the actual provider completion time, not at
capture time. Delaying capture cannot qualify a report acquired before its window
closed. Reported day counts are retained exactly; sparse rows never imply observed
zero on missing dates. Rule outputs remain heuristic sensitivity, not empirical success.

Successor validation: 37 tests passed and one SQLite-only migration test skipped before
the final clock regression; the added lagging-clock regression passed on both databases
(2 passed). A first combined attempt found a missing test-only NOW import; it was fixed
and that exact regression reran successfully. Actual PostgreSQL0075 downgrade/re-upgrade
passed. Full Ruff and mypy (643 source files) passed. No Full or remote run was started.

Final frozen-backend combined rerun after that fixture fix: **39 passed, 1 skipped**
in18.43s; skip is the intentionally PostgreSQL-only actual Alembic roundtrip case on
SQLite. The PostgreSQL migration case passed. Three pre-existing Alembic
`path_separator` deprecation warnings were emitted. Working tree was clean at2175a5b.

### Historical 0074 Fixture Compatibility

Reproduced the historical test's direct DROP failure under PostgreSQL:
`DependentObjectsStillExist`, from the new observation completion/account/workspace FK.
Before:1 passed/1 failed. The fixture now downgrades0075 before0074 historical DDL and
restores0075 before current importer execution; final roundtrip uses the same dependency
order. Application code and constraints are unchanged. After:2 passed; Ruff/mypy643 pass.

The two existing performance modules ran to completion:60 passed,2 failed at
`verify_registry()` because this isolated backend branch intentionally does not yet
contain the separately owned lifecycle table registration. Both failures are the same
registry composition gap, not migration/importer failures. Lifecycle integration must
rerun those cases; no application missing-table fallback was added.

### Derived Storage Bound

Separate engineering safety limits cap retained calibration runs and previews at128
per owned campaign and environment. Expired rows still count until physical cleanup.
The calibration insert checks this under the existing workspace fence and rejects
`initial_calibration_capacity_reached`; policy parameters and business recommendations
are unchanged. Preview consumer applies its matching bound independently. Actual SQLite
and PostgreSQL cap tests passed (2 passed), including expired-row accounting and scope/
environment separation. Ruff and mypy644 passed. The optional identical-basis reuse is
not relied upon for bounded storage; cutoff-specific analytical reproducibility remains.
