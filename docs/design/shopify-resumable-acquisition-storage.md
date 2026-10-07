# Resumable Shopify Acquisition: Storage And Callable Proposal

For review before implementation. Builds on `ec7c281` and existing
`IndependentAcquirer`, `OwnedAcquisition` and immutable commerce publication v2.
Migration **0082 is prospective, not allocated or implemented**. No new assurance,
directional producer, maturity registry or advertising authority is proposed.

## Three Owned Storage Roles

Three new tables suffice; daily accumulators live in bounded typed checkpoint JSON.
Names and field groups below are proposed implementation contracts.

### CommerceAcquisitionJob / commerce_acquisition_jobs

- `id` (32-hex PK) is the ScanRequest.acquisition_id; unique `(id, workspace_id)`.
- `workspace_id`, `store_id`, `native_connection_id`, `integration_id`, `goal_id`,
  `goal_revision`; immutable `request` canonical ScanRequest JSON and request_digest.
- Original `actor_id`, `session_digest`, `authenticated_at`, and a digest committing
  the captured issuer/subject. No token, raw subject, email or refresh credential.
- Explicit environment and immutable limits document/digest. `created_at`,
  `deadline_at`, optional `started_at` set once at first authority HTTP claim.
  The deadline is fixed at enqueue plus configured lifetime, not extended on start.
- State: pending/running/completed/unavailable/cancelled/expired. `due_at`,
  `lease_token`, `lease_until`, `step_sequence`, bounded error_code, request-attempt
  counter, completed-request counter and conservatively charged response bytes.
- Nullable `publication_id`, valid only in completed state; terminal_at/cleanup_at.
  No numeric result in the job. Status reads resolve the owned publication normally.

Composite FKs, all with CASCADE because this is erasable operational work:
`(store_id,workspace_id)` → commerce_stores;
`(native_connection_id,workspace_id)` → shopify_connections;
`(integration_id,workspace_id)` → workspace_integrations;
`(goal_id,workspace_id)` → goals;
`(publication_id,workspace_id)` → commerce_measurement_publications.
The existing `(goal_id,revision)` GoalRevision PK is an additional FK; the owned
Goal FK establishes workspace scope without rebuilding that parent. Actor/session
FKs refer to existing customer records; insert validation must bind session.user_id
to actor_id. Source insertion also checks native/store/integration relationships,
request scalar equality and captured generation/version/privacy. FK existence alone
is not admission. Portable guards freeze all identity/request/limit/time fields;
operational fields alone may change, with started_at NULL→value once.

A PostgreSQL/SQLite partial unique index on `(workspace_id,store_id)` where state
is pending or running admits at most one active scan per store. A replay of the
same original-session/goal/window active request returns that job; a different
active request returns a fixed conflict, never steals another session's job.
Deletion of a publication cascades its completed job; deleting a job does not
delete its publication. Existing source invalidation still removes publications.

### CommerceAcquisitionCheckpoint / commerce_acquisition_checkpoints

PK `job_id`, workspace_id; composite FK to job ON DELETE CASCADE. Columns:
phase, sequence, state_document, state_digest, encrypted_handles, updated_at.

Strict typed state_document (maximum 128 KiB) holds only:

- request/limits digest and expected phase/sequence;
- pending order metadata for at most 50 items: HMAC order/customer identities,
  original created/updated timestamps and test flag, not raw customer IDs;
- current agreement HMAC/type/reason and metric timestamp; supported semantic
  status, not historical sale payloads;
- tentative current-order daily sums/counts and committed scan daily sums/counts,
  each at most 400 requested local days; counters and bounded continuation flags.

encrypted_handles (maximum 16 KiB) contains only native order/parent IDs needed for
the next request, order/agreement/sale cursors and the last numeric order ID used
for ID-order validation. It contains **no customer ID, token, HTTP body or old
financial payload**. Authenticated encryption is domain-bound to workspace/store/
job/request/phase/sequence so blobs cannot be moved between jobs. Use existing
server vault primitives through a dedicated payload purpose; no new customer key.
If existing primitives cannot bind those fields, freeze that small helper before use.

Each sale page is normalized and reduced immediately using shared existing metric
semantics; no whole-history agreement/sale list is persisted. Only after the exact
order-check response matches does its tentative aggregate enter committed totals.
Unsupported or malformed data anywhere fails the scan, including out-of-window
agreements, preserving current conservative behavior. A test order contributes no
values but still receives complete traversal and parent checks.

### CommerceAcquisitionSeen / commerce_acquisition_seen

PK `(job_id,kind,identity_digest)`; workspace_id and composite job FK CASCADE.
Kinds order/agreement/sale/cursor. Workspace/store/job-keyed HMACs only. Cursor
digests also commit connection kind and exact parent, so one parent's cursor cannot
masquerade as another. This gives durable duplicate/cycle rejection across ticks.
Explicit server capacity: default 100,000 keys, hard maximum 250,000, in addition
to existing request/order/byte caps. Hitting a cap aborts without a publication.
These are engineering limits, not maturity policy or Shopify guarantees.

## State Machine And One-Request Claim Protocol

Phases: authority_before → order_page → agreement_page ↔ sale_page → order_check →
next order/page → authority_after → publish. Empty enumeration still executes both
authority HTTP checks. Nested phase changes derive only from validated pageInfo.
`publish` is local and emits no HTTP. There are no parallel pages within a scan.

1. Bounded due selection takes at most one job per workspace, with an explicit
   batch limit. Workspace-first lock; reconstruct the exact original principal;
   reuse OwnedAcquisition's source/goal/retention/privacy checks; then lock the job
   and checkpoint. Verify due time, fixed deadline, phase/sequence and lease.
2. Charge one request attempt before committing the claim. Reserve one maximum
   response-byte allowance before IO, conservatively retaining that charge if a
   worker disappears. A validated completion may refund unused bytes. Completed
   requests are counted separately, so failed attempts are not claimed as reads.
3. Close the owned transaction. Obtain only a fresh permit through a separate
   short session. Emit at most one fixed GraphQL HTTP request with the existing
   bounded timeout/stream/deadline checks. No customer session or source row lock
   spans HTTP, and no code commits/rolls back a caller-owned transaction.
4. Reacquire canonical authority and fresh clock, then exact job/checkpoint locks.
   Accept output only for the original lease token and sequence, unexpired deadline
   and unchanged full ScanRequest. Atomically update bounded staging and clear lease.
5. A expired lease permits a new GET attempt only; elapsed time is not proof the
   former worker terminated. Its later response cannot commit after token change.
   Duplicate reads never double-add values because all changes use sequence+lease.

Retryable transport/throttle errors preserve the exact acquisition ID, initial
start/deadline, checkpoint and charged budgets, with bounded due_at/backoff. They
cannot renew authority or omit an incomplete child page. Unsupported semantics,
changed order, lost cursor, duplicate identity, partial GraphQL errors, privacy,
source/generation/goal/session changes, capacity and deadline failures become
terminal unavailable/expired. Do not restart from zero invisibly under the same ID.
Configuration unavailable receives bounded scheduling deferral without touching
authority; revoked original identity is terminal. Both paths avoid tenant starvation.

The existing `_publish` opens its own transaction. Extract a narrow internal
`publish_owned_in_transaction(db, completion, original_guard, clock)` primitive
shared by synchronous and resumable callers, preserving old behavior. The worker's
publication insertion, completed job/result pointer and staging deletion must be
one transaction. Lost response returns that stored result; it never reconstructs an
erased publication. No change to existing v1/v2 serialization or completion hashes.

## Privacy, Retention And Export

Active checkpoint/seen rows expire at the fixed job deadline (maximum existing
30-minute lifetime). Purge immediately on every terminal state, cancellation,
disconnect/rebind, source invalidation, customer erasure, workspace closure or
original-session deletion. Revocation detected before the next step denies IO and
purges staging; active source/privacy hooks purge immediately under the same fence.
Every delivery still rechecks authority. A bounded sweeper handles abandoned jobs
even while acquisition is disabled. Never infer missing rows as successful zero.

Retain terminal job status at most 24 hours for recovery, without staging/native
handles; expose that engineering retention in settings/docs. Cleanup deletes only
the job, leaving the immutable publication subject to its existing source-wide
privacy and 13-calendar-month metric retention. The 13 months never limits the age
of orders searched and does not authorize retaining their historical payloads.

Classify all three tables in the canonical lifecycle/worker registry. Checkpoint
and seen tables are private erasable staging and excluded from customer exports.
Job export uses a strict allowlist: job/goal/window/state/times/error/publication ID;
omit actor/session/issuer commitments, native handles, request JSON, limits internals
and lease data. Existing strict v2 publication export handles aggregate results.
Any concurrent privacy/source invalidation must invalidate an in-flight export via
the existing export fence. Protected advertising receipts/holds are untouched.

Migration proposal: create only these tables, indexes and portable guards; no
populated parent rebuild. BothDB ownership/guard tests, exact populated upgrade and
nonempty downgrade refusal required. Delete/expire jobs explicitly before downgrade;
never silently discard retained publication or hidden staging. Allocation awaits review.

## Actual Entry Points And Default-Off Assembly

- Setting `customer_independent_acquisition_enabled=false` gates new requests and
  worker IO; missing private source configuration is unavailable before IO.
- POST `/api/customer/v1/workspaces/{wid}/commerce/acquisitions`: owner+original
  session+CSRF; body goal_id, expected_goal_revision, start, end only. Returns job ID
  and explicit unresolved/unqualified interpretation. Source resolved from goal.
- GET `/commerce/acquisitions/{id}`: same original-session owner, current scope,
  no-store; pending/phase/fixed error or existing owned publication projection.
- POST `/commerce/acquisitions/{id}/cancel`: same authority/CSRF; atomically cancel
  and erase staging. Cancellation never deletes unrelated rolling imports.
- `run_independent_acquisition_tick(engine, settings, identity, clock)` joins the
  existing customer tick as a separate opt-in read stage, with master data-sync and
  existing paid-work/workspace gates. No reuse of a global principal or credential.

Required server configuration supplies technical capacity/backoff/tick budgets;
customers do not set those. Actual tests inject only the low-level HTTP transport,
identity/test settings; they must use ordinary configured API and shipped worker.
No runtime getter override or seeded job/checkpoint/publication.

## Acceptance Boundary

Prove enqueue→multiple one-HTTP ticks→old-order recent refund→owned v2 publication
on both DBs; resume every phase; two concurrent claims; loser response; throttle and
crash budgets; original-session revocation during HTTP; source/privacy changes;
fair next-tenant/next-tick scheduling; fixed deadline; same-ID response recovery;
zero/negative/DST and all nested pagination; strict export and timed cleanup.
Assert v1 rolling cadence unchanged, v2 correction unresolved/snapshot unavailable,
no qualified evidence/direction/automatic registration and no advertising writes.

This is a concrete operational acquisition package. Store-wide snapshot assurance,
settlement, calibrated recommendation qualification and authoritative action timing
remain separate, unproved facts. No implementation or tests run for this proposal.
