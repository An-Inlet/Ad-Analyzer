# Operational Reported Feedback Lifecycle

Migration0077 follows0076. This package implements owned storage, retraction,
retention and export boundaries for the separately implemented operational
reported-feedback services. It does not install a policy, enable Meta access,
authorize advertising changes, or qualify causal lift/report finality.

The five reported-feedback tables are explicitly registered customer-owned,
erasable data. Jobs are a derived read queue; observations, comparisons and slots
are not financial accounting. Slot documents include their exact environment,
cohort and explicit feedback policy. Original authentication-session digests in
jobs and slots are internal and never customer-export fields.

## Erasure And Correction

- Semantic workspace privacy/closure deletes jobs and cascades capsules,
  comparisons, dependencies and slots. Source erasure is account-scoped. Existing
  workspace-first locking applies even when a workspace is closing; no active
  customer admission is required for cleanup.
- Ordinary terminal publication retracts account comparisons before capturing the
  next completion's export counter. Historical capsules/jobs remain until their
  explicit retention deadline or semantic erasure. No recursive privacy bump is
  introduced.
- A persisted slot can aggregate several comparisons. Deleting **any** workspace
  comparison, dependency, capsule or job conservatively retracts every workspace
  slot, including slots whose direct FK points to another comparison. Dependency
  deletion erases the entire parent comparison. Other workspaces remain isolated.
- Numeric documents and dependencies are immutable. Job input, original authority,
  ownership, source and policy commitments are immutable while bounded progress
  checkpoints remain writable. PostgreSQL deletes take a fail-fast workspace lock.
- No trigger deletes protected attempts, receipts, reservations or spending ledgers.
  Losing a numerical graph does not release an unknown financial obligation.

## Retention And Exports

The real housekeeping dispatcher runs a bounded persisted-deadline sweep even
when the runtime factory returns `None`. Expired capsules retire their owning
request and its graph. Expired comparisons/slots retract their dependent numerical
outputs. Cleanup uses the earlier of fresh application and database wall time;
an artificially ahead application clock cannot authorize premature deletion.

A deletion before expiry advances the shared export revision. Database-expired
numerical deletion can omit that counter change because export delivery enforces
the earliest included expiry against **both** clocks. This preserves current
campaign reporting availability after routine derived expiry. Broad deletion of
other unexpired dependent slots still advances the fence conservatively.

All four JSON-bearing tables have strict versioned serializers and explicit
scalar ownership/digest/time bindings. Archive capture includes every reported
row's expiry. Fresh delivery checks use the shared core dependency validators
under a workspace fence after identity IO, rather than trusting the archive's
cached snapshot or authentication session. Unavailable or changed numeric evidence
fails closed; no raw JSON fallback or permanent retained archive is introduced.
Historical request/capsule exports remain labelled by their versioned acquisition
and capture times, not as current recommendations.

## Migration Safety

The Meta phase constraint adds only `rf_campaigns`, `rf_adsets`, `rf_insights` to
ordinary phases. Downgrade refuses any retained fixed-window phase. PostgreSQL
changes the constraint directly. SQLite's table rebuild would cascade-delete
native staging when foreign keys are enabled; this was reproduced before freeze.
The migration therefore preserves the exact staging/checkpoint/page descendants
in transaction-local work, restores them in parent order, verifies exact equality
and runs `foreign_key_check`. It never disables foreign keys. These temporary
copies exist only on the migration connection, not as customer-export artifacts.

Historical0074 DDL tests remove0077 before earlier dependent schemas and restore
it last, using real migration operations. They do not use CASCADE shortcuts.

## Evidence Boundaries

Structural lifecycle fixtures use an actual offline Meta execution receipt and
held financial lineage. Their synthetic insufficient comparison/slot documents
exercise persistence, erasure and serializer guards; they do not claim acquisition
or feedback qualification. Separate acquisition tests use injected Meta HTTP with
actual native checkpoints. Exact commands and terminal counts belong in the
progress ledger; no Full, hosted CI or live qualification is claimed here.
