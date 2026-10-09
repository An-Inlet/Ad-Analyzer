# Current Meta Review Lifecycle Locks — Exact Two PostgreSQL Cases

Proposal only on8acd74e. Original function test_meta_review_locks::
test_review_native_meta_lock_order[postgres-disconnect|reauthorize] remains current.
Its actual threads, DB lock barriers, timeout bounds, current ConnectionService and
review.binding calls/assertions must not be marked retained or replaced by old code.
The two existing SQLite skips remain unchanged and are not failure-closure credit.

Only setup review_fixture is obsolete: it calls legacy simulation mandate approval
through setup, then actual offline Meta authorization/account selection, changes the
mandate account scope, approves it, builds RevisionInput and obtains a second pending
grant. It emits no advertising writes. Replacing its approval with a current fabricated
row or disabling the guard would weaken evidence, so preserve that exact original
setup in one closed pinned producer, following existing SourceLifetime conventions.

## Closed Source Interface

New meta_review_lock_seed_driver invokes untouched PIN2155 test_meta_review_locks.
review_fixture with original configuration/meta_configuration.__wrapped__ fixtures,
on the explicitly named fresh current UUID PostgreSQL schema. No SQLite path needed:
consumer skips before source invocation, matching current PostgreSQL-only contract.
Verify localhost disposable URL/flag, exact UUID schema/search_path, all tables empty,
PIN/app source root and fixed app/tests/scripts trees before source setup. Close all
Sessions/engine before returning. No runtime, session cookie, grant or credential
leaves the child. Same fixed 180sec bound and conservative new SourceLifetime profile.

JSON <=8192bytes, exact fields only: workspace_id, mandate_id, mandate_revision,
account_id, integration_id, native_id. All positive IDs/revision strictly integers;
mandate UUID exact32hex. No caller-provided source selector or callbacks. Derive
RevisionInput again in parent from the original known test constants after validating
all IDs against actual current rows, policy/account/platform/connection ownership,
active approved revision, original60micros reviewed budget and Meta external101.
The source original body is reconstructed as the same strict RevisionInput rather
than importing a ready current object. Source actor remains the original literal
owner; no identity or current runtime is created by this test.

Read and structurally validate that original pending grant exists for original
owner-session, workspace and original expiry. Never expose its encrypted payload.
Current meta_configuration fixture uses the same existing synthetic key and actual
FakeMeta instance, preserving genuine decrypt/select/disconnect behavior.

## Current Consumer And Graph Invariants

Use a current fixture dependent on original customer_engine/configuration/
meta_configuration and tmp_path. Invoke source only after the existing PostgreSQL
skip. Parent load_source returns wid/body; no current ConnectionService operation
runs in setup. Keep review_fixture unchanged for any other callers. Change only
selected test setup to load the source; entire code from Event construction onward
and all decorators/assertions remain AST-identical.

Before yielding snapshot physical schema, all provider_* financial rows, mandate*
rows/revisions/actions/audits, goals/goal revisions/confirmations, advertising account
identity/ownership, integration workspace/provider identity, and customer/workspace
ownership rows. Require zero provider attempts/responses/receipts/reservations and
no MandateAction (this original setup has only a simulation approval).
After actual current lifecycle operation require exact schema/financial/goal/customer
invariants. For account/integration snapshots preserve ownership and immutable fields;
current lifecycle status/timestamps may change only if the actual service definition
proves it, with explicit per-operation fields frozen before implementation. Never
exclude whole account/integration tables. Meta grant/native/audit/staging mutations
are the behavior under test and are checked against exact original assertions plus
explicit owned rows/operation invariants. No foreign row/timestamp exemption.

Current disconnect must remove only owned native/grant/staging records, preserve
account/workspace/financial ownership, and retain original binding rejection. Current
reauthorize must keep exact owned native ID/account/integration, increment generation
1→2 through real service, preserve original successful binding suffix2 and consume
the actual pending grant. Read service source first to freeze exact lifecycle deltas;
if it differs, revise this interface with evidence before qualification.

## Qualification

First current two PostgreSQL cases (actual concurrent lock barriers, no fake success),
then exact module2pass/2existing SQLite skips plus unchanged86 current write boundaries
and16 SourceLifetime. Strict source schema/ID negatives before any IO, exact original
node intersection and whole post-setup AST proof. Whole Ruff/bare mypy/diff separately.
All runs use explicit unique/tmp basetemps with durable logs/XML. No aggregate, live
Meta calls, artifact write override or original source mutation. Independent interface
review and explicit lifecycle-delta freeze precede implementation.

## Lifecycle Delta Freeze From Current Service Source

Read app/meta/service.py select_account/disconnect, app/imports/native.py/scope.py,
and app/lifecycle/privacy.py. Both operations increment the owned workspace's
export_privacy_revision exactly1; its ORM updated_at may advance only within actual
parent begin/end wall-clock bounds. Every other workspace/customer/goal/mandate field
stays exact. Assert derived observation/plan/candidate/presence tables are empty at
source entry so their normal privacy erasure cannot hide an unrelated mutation.

Disconnect deletes the one owned MetaConnection, its one pending grant and any owned
OAuth state (exact baseline set), changes only its original WorkspaceIntegration
status active→revoked (plus bounded updated_at), appends exactly one MetaAudit with
action disconnected/actor_role owner/record_count0 and bounded created_at. Account
identity and fields remain exact. Original derived staging is empty and stays empty.

Reauthorize consumes the one original pending grant and leaves OAuth-state set as
implemented; it updates the same native row generation1→2 and reencrypts the exact
original pending-grant bundle with the normal Vault. Validate decrypt equality locally
without printing/serializing fake token material. No arbitrary credential allowance.
All connection identity/ownership/external ID fields stay exact. Actual fixed NOW
connected_at, connected/purchase, campaigns phase and original null cursor/windows/
coverage/retry/error fields are required. Original integration stays active with
all other fields exact. Upserted account retains actual FakeMeta metadata and all
ownership fields; only its ORM updated_at, if changed, must be within observed bounds.
Append exactly one owned connected audit with owner/0/bounded creation time.

All audit/grant/native allowances are exact row dictionaries or explicit validated
field transitions; all metadata tables otherwise compare exactly. Original metadata
may have nondeterministic creation timestamps, retained byte-for-byte rather than
recomputed. New audit integer ID must be positive, unique and additional to original
IDs. If current framework onupdate semantics produce another actual field delta,
retain failure and review the documented exception before continuing.
