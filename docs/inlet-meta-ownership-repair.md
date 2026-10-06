# Retained Meta Account Ownership Repair

Isolated child of frozen PR125 (`512cadc`). No live provider access or advertising changes.

The existing globally unique `MetaConnection.external_account_id` already prevented two
active Meta connections for one external account. It did not cover retained historical
`AdvertisingAccount` rows after disconnect. Customer selection releases locks for
provider account metadata IO: another workspace could create the same account and then
disconnect in that interval. The stale pre-IO ownership check permitted a second retained
account because its existing unique key was workspace/platform/external ID.

Selection now repeats the foreign-workspace ownership check after provider IO. Migration
**0049 down0045** adds a Meta-only partial unique index on the retained account's external
ID. The database index serializes all concurrent writers, including writers that do not
create a MetaConnection. Existing workspace-first locking and sanitized IntegrityError
rollback remain unchanged. Other advertising platforms keep their current scoped keys.

The migration preflights existing duplicate Meta IDs and stops with a fixed reconciliation
message. It does not pick an owner, move data, or delete historical records. An actual
legacy conflict requires explicit reconciliation before migration; no conflict was observed
against real customer data because none was accessed.

## Verification

- Focused ownership/customer Meta/operator/first-connection tests: **49 passed, 1 skipped**.
- Ownership plus import-ingress/import-ownership/workspace regression suite:
  **48 passed, 1 skipped**. Each skip is the PostgreSQL-only two-writer race on SQLite.
- Controlled provider-IO regression actually connects then disconnects workspace B
  while workspace A waits; A is rejected and B retains the sole historical account.
- Two PostgreSQL writers rendezvous after prechecks. A raw historical-account insert
  wins; the customer connection loses on the named `uq_meta_external_account_owner`
  index, rolls back, and returns the sanitized ownership error. No duplicate account,
  connection or consumed losing grant remains.
- Populated SQLite and PostgreSQL migration tests cover upgrade/downgrade/upgrade,
  unchanged stored rows, explicit duplicate refusal and unchanged Google account scope.
- Ruff, mypy (**326 files**) and `git diff --check` pass. Full/hosted CI pending.

No new advisory lock or application-only serialization assumption is used. Parent owns
integration of migration branches and Full at the next unfrozen candidate.
