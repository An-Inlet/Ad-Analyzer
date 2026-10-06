
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
