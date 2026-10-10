# Exact Archive Financial/Social Source And Privacy Contract

Addendum to [the accepted split proposal](archive-closure-financial-social-current-v1.md),
read against `d878264936c8aad5af96f191617412692aecc307`. Documentation only.
This replaces the proposal's provisional output shape and deferred privacy-delta
enumeration. No producer, consumer, test or current write capability is implemented.

## Empty Target, Not A Bootstrap Exception

`tests/test_customer_exports.py::export_engine` delegates PostgreSQL to
`tests/test_customer_identity.py::customer_engine`; both install `Base.metadata.create_all`,
not Alembic migration seeds. SQLite export uses a file, WAL and foreign keys.
The closed replacement uses that same current metadata/DDL on its independently owned
file/schema. Before source invocation **every registered table has zero rows**;
`alembic_version` is absent. Reject a migration-seeded target rather than allowing
Denticode/default-workspace/control rows. Schema fingerprints include the actual
current constraints/indexes/triggers and remain identical after production and consumption.

`goal_usage_policies(scope='global',call_limit=1000,cost_limit_micros=0,version=1)`
is created once by the original `test_customer_goals.seed`, not target bootstrap.
Its exact row is retained unchanged. No nonempty target exception is needed.
The source creates two workspaces, two users and two owner memberships itself.
Its unchanged original assignments produce issuer `ISSUER`, subjects `brand-a`/`brand-b`,
email `mock@example.invalid`, workspace names matching subjects, final workspace slugs
`brand-b-{id}` for both, and Shopify domains `brand-{connection.id}.myshopify.com`.
No additional/current identity, domain, slug or email rewrite is permitted.

## Closed Scalar DTO

One UTF-8 JSON object, at most 16 KiB, maximum nesting depth eight. Reject duplicate
object keys, unknown/missing fields, NaN/infinity, non-JSON values and coercions.
All fields below are required; only explicitly marked null unions permit JSON null.
No credentials, URLs, filesystem paths, identity claims, clocks, database selectors,
source code, arbitrary table names or raw documents are output. Two brands are named
fields, not a caller-sized list. Generated references must be independently reloaded;
the envelope never grants ownership or defines the expected privacy delta.

Primitive definitions:

| Alias | Exact accepted value |
| --- | --- |
| `Id` | ASCII string matching `^[a-f0-9]{32}$` |
| `Digest` | ASCII string matching `^[a-f0-9]{64}$` |
| `IntId` | JSON integer, not bool, `1 <= n <= 2147483647` |
| `Rev` | JSON integer, not bool, `1 <= n <= 2147483647` |
| `One` | JSON integer exactly 1, not bool |

Envelope fields:

| Field | Type/value |
| --- | --- |
| `schema_version` | literal `inlet.test.archive-financial-social-source.v1` |
| `source_commit` | literal `2155ff3e3ab00cd62057dd86cb49d45359d4f49f` |
| `source_file_sha256` | literal `15049bf103f6f9178c41622cad79c2c3d2ef75ef574191daa07c801eec2ed4b3` |
| `source_function_ast_sha256` | literal `36ba3f74cb7f08b5e9db750ee83d270b73d9b1ef5cbb8fed53911779a8f60199` |
| `source_prefix_ast_sha256` | literal `f58209c8b6a20b1fffbe0fa202feec8fe466e0889f5475426aadc893e7e07cf2` |
| `brand_a` | `Brand`, provider exactly `meta_ads`, social nonnull |
| `brand_b` | `Brand`, provider exactly `google_ads`, social null |

`Brand` has exactly these fields:

| Field(s) | Type |
| --- | --- |
| `provider` | literal `meta_ads` or `google_ads`, constrained by envelope position |
| `workspace_id` | `IntId` |
| `actor_id` | `Id` |
| `goal_id`, `simulation_mandate_id` | `Id` each |
| `google_connection_id` | `Id` (both brands retain their original Google setup) |
| `google_account_id`, `google_integration_id` | `IntId` each |
| `meta_connection_id`, `meta_account_id`, `meta_integration_id` | `IntId` each for A, null each for B |
| `shopify_connection_id`, `shopify_integration_id`, `crm_connection_id`, `crm_integration_id` | `IntId` each |
| `commerce_store_id` | `Id` |
| `provider_mandate_id`, `consent_id`, `ledger_id` | `Id` each |
| `provider_mandate_revision` | `One` |
| `original_review_id`, `original_run_id`, `original_attempt_id`, `original_fence` | `Id` each |
| `original_request_digest`, `original_response_digest`, `original_receipt_digest` | `Digest` each |
| `original_receipt_id` | `Id` |
| `predecessor_reservation_id`, `repeat_review_id`, `successor_run_id`, `successor_reservation_id`, `replacement_id` | `Id` each |
| `repeat_review_digest`, `replacement_digest` | `Digest` each |
| `google_source` | `SourceRevision` (present in both brands) |
| `social` | `Social` for A, null for B |
| `source_mutation_count` | `One`, original mock server effect count only |

`SourceRevision`: exactly `draft_id: Id`, `revision: One`, `digest: Digest`.
`Social`: exactly `source: SourceRevision`, `media_id: Id`, `media_sha256: Digest`,
`review_id: Id`, `review_digest: Digest`, `approval_digest: Digest`.
No nullable scalar can substitute an empty string. References with different semantic
roles must differ except the explicitly shared graph keys (workspace, owner, ledger,
mandate, account/integration and response's attempt key). Meta and Google workspaces,
owners and every generated record identity must remain distinct. Revision-one claims
refer to campaign revisions and the separate provider mandate, not the simulation
mandate, which the original prefix legitimately edits/approves several times.

No response ID is invented: `provider_execution_responses` has composite key
`(attempt_id,digest)`. Approval keys are their review IDs. No successor attempt/fence/
receipt field exists because those rows must not exist. Parent discovers and validates
any retained Google original-completion row by the original attempt FK and its typed
`GoogleCompletionDocument`, not by trusting a new child assertion of terminality.

## Required Graph Before Current Requests

Read all registered tables including empty tables, ordered by complete primary keys,
with exact JSON/scalar values and canonical UTC datetime comparison. The parent derives
owned edges from actual foreign keys/documents, not solely returned IDs. Require:

- Exactly two workspaces/users/customer owner memberships, no sessions/token exchanges,
  lifecycle requests or lifecycle steps. No customer signup or operator membership row.
- Each brand has one CRM connection/integration (`crm-source`, HubSpot), one Shopify
  connection/integration/store, one Google account/integration (`fixture-ads`)/connection,
  one fixture Google campaign, goal and simulation mandate. A additionally has exactly
  one Meta account/integration (`optimization-test`)/connection. Thus A has four owned
  integration rows and B three. No `customer_source_connections` or CRM OAuth rows.
- Each has exactly one provider ledger/mandate/revision/consent, two execution reviews,
  two execution approvals, two runs and two steps (`step_id='optimize',ordinal=0`);
  one original attempt, one response, one original receipt (`sequence=1`,
  `supersedes_id=null`); two holds and one replacement audit. Original run is canceled
  with the source cancellation time; successor is reserved, its step pending, with
  no attempt/response/receipt and `canceled_at=null`. Original step retains
  `verified_target_state`. Original receipt and normalized projection validate exactly.
- Predecessor hold is superseded; successor hold is held40,000,000 micros; predecessor amount is also40,000,000.
  The repeat action setting44,000,000 is distinct from its mock exposure upper bound. Preserve
  both full evidence documents and any settlement nulls; bind replacement old/new
  amounts to actual holds and strict `ReplacementAuditDocument`, not a fabricated
  release. Review types are `OptimizationExecutionReview` and `RepeatOptimizationReview`;
  requests/responses/receipts use the exact optimization types selected by provider.
  Canonical hashes, ownership, plan/intent, fences, environment, ancestry and full
  normalized receipt projection must all match. Ledger action_count is2, spent_high_water_micros is0 and last_dispatch_at is the
  original fixed source NOW. These and source charging evidence are independently
  recomputed from the two admitted operations; neither
  consumer nor DTO may choose an expected counter or financial document.
- Both have their original approved Google campaign revision. A has one additional
  approved Meta revision, one private image, exactly one social configuration review
  and confirmation. Parse `SocialConfigurationDocument`, bind owned image bytes/hash/
  size, source artifact/digest, selected no-DSA profile and exact confirmation digest.
  B has no social rows/media. Original goal, commerce and measurement records remain
  their full authentic source graph, not substituted minimum records.

These exact counts are source-reading expectations, **not yet executed qualification**.
If the pinned prefix or its independently parsed graph contradicts them, stop and
return a contract correction for review; do not widen a range or exempt a table.
All later source-absent tables stay empty unless explicitly listed below. Existing
source rows stay field-for-field equal unless a particular owned row/field is listed.

## Login Delta: Two Existing Actors, No Identity Mutation

Use separate fresh cookie jars for A and B; no old cookie is supplied to login.
Current offline identity provider verifies the persisted issuer/subject and returns
that same persisted email (rather than FakeProvider's default different email).
Original historical2 continues its unchanged original provider behavior separately.
Use unique fixed test tokens `brand-a:1` and `brand-b:1` only inside the test process;
never log tokens, cookies or CSRF values. Provider verifies authenticated/expiry times
against bounded actual call intervals, without patching clocks or extending TTL.

Per login, exactly one new `customer_sessions` row:
`digest=SHA256(actual issued session cookie)`, `csrf_digest=SHA256(actual csrf cookie)`,
`user_id=original actor`, `created_at=int(real issue time)`,
`expires_at=created_at+28800`, `authenticated_at=verified identity authenticated_at`,
`revoked_at=null`. Exactly one new `customer_token_exchanges` row:
`digest=SHA256(actual supplied token)`, `expires_at=verified identity expires_at`.
Both integer times fall in the captured request/verification intervals; the offline
provider uses expiry authenticated time+3600, not a source-era fixed timestamp.
No prior token rows exist to prune and no old session exists to rotate. No other
append/delete/update is allowed; user email, identities and memberships remain exact.
Subsequent GET/session, failed foreign requests and both denied advances have zero
persisted delta. Test setup must not use login itself to repair source identity.

## Export Delta: One Request And One Build Step Only

Current `customer_export_enabled=true` is the existing offline export fixture seam,
not advertising authority or deployment qualification. A's exact key is
`archive-replacement-social`. `LifecycleInputV1` is operation export with exact A scope.
Hash this known typed input using `service.begin`'s sorted compact JSON algorithm;
key digest is SHA256 of the known key, independently of the returned row.

POST creates exactly one `customer_lifecycle_requests` row: UUID hex ID/fence,
A workspace/actor, schema `inlet.lifecycle.request.v1`, operation export,
known key/request digests, state requested, revision1, disposition null, blockers[],
created_at=updated_at in POST interval. No step yet. Foreign Bob download is zero delta.

Owned download updates this same request: revision2, new hex fence,
state archive_built, updated_at exactly parsed manifest `snapshot_as_of` within build
interval; created_at and all identity/request fields unchanged. Blockers exactly one
`export_snapshot` object with the manifest's snapshot_revision, snapshot_as_of,
supported_customer_data_complete, media_archive_complete,
all_stored_workspace_data_complete (no other fields). Require customer completeness
true and actual private image archived. Do not assert all stored/internal data complete.
Exactly one new `customer_lifecycle_steps` row with key `(export_id,'export_build')`,
A workspace, request_revision2, request's new fence, attempts1, state complete,
lease_until null, evidence_digest SHA256 of canonical `archive.encoded(manifest)`.
The in-flight lease is180seconds, not a persisted post-completion exception.

`Authority.capture_privacy` writes no database row: it reads workspace export revision,
commerce/reporting stamps and retention deadline into memory/manifest. Download
completion does not create a delivered receipt, bump privacy revision, or retain an
archive blob. No other table/row/field change is permitted. Check manifest/download
bytes and original foreign-data assertions independently of these database deltas.

## Closure Preview And Confirmation Delta

Preview key is exactly `closure-replacement-social`; typed input operation close/A scope.
Exactly one additional lifecycle request: A actor/workspace, known input/key digests,
schema as above, state requested, revision1, disposition null, created_at=updated_at
within preview interval, final inventory-claim hex fence. Blockers initially exactly
`retention_policy_unset/lifecycle/owner_policy` (typed `LifecycleBlockerV1`).
Exactly one step `(closure_id,'inventory')`: A workspace, request_revision1,
same fence, attempts1, complete, lease null, evidence_digest exact SHA256 of the
sorted compact preview inventory. Independently recompute inventory for the exact
pre-confirm graph, including this request/step and the existing archive bookkeeping;
require equality with the returned digest. No other preview mutation.

Confirm uses that exact revision1/digest/A workspace. Only A's following existing
rows can change; row identities and **all fields not named remain equal**:

| Exact source rows | Permitted final values |
| --- | --- |
| A `workspaces` (one) | status closing; export_privacy_revision old+1; updated_at within confirm interval |
| A `workspace_integrations` (four) | status revoked; secret_manager_reference null; updated_at within confirm interval |
| A `crm_connections` (one) | status closed; secret_manager_reference empty string; updated_at within confirm interval |
| A `google_customer_connections` (one) | status disconnected; encrypted_grant null; cursor null; staged{}; next_attempt_at null; generation old+1 |
| A `meta_connections` (one) | status reconnect_required; encrypted_credentials empty; cursor null; next_attempt_at null; generation old+1 |
| A `shopify_connections` (one) | status reconnect_required; encrypted_credentials empty; cursor null; next_attempt_at null; no generation or connected_at change |
| A `spending_mandates` (one) | paused true only; state/revision/counters/documents unchanged |
| A `provider_execution_mandates` (one) | state revoked only; revision/ledger unchanged |
| A successor `provider_execution_runs` (one) | state canceled; canceled_at exact confirmation `now` within interval |

The already-canceled original run is completely unchanged. `updated_at` allowances
above are only the declared SQLAlchemy onupdate columns in workspaces/CRM models;
no blanket timestamp allowance applies elsewhere. No run step state is changed by
quiesce, and no action/hold/ledger is released. The precise existing row counts matter:
there are no session automation runs, workspace automation controls, mandate actions,
customer source connections or context checkpoints to stop/update, and no OAuth states/
pending grants to delete. Require those tables empty both before and after.

The privacy erasure functions visit source-absent presence/staging/planning/candidate/
initial-observation/reported-feedback/automatic-origin families. For this exact source
there are no such rows to delete and no deletion-trigger counter increments: privacy
revision increases **once** by `advance_workspace_export_revision`. The original
commerce orders/entries/snapshots/goals/source media/financial/social documents are
not erased by this closure. Any observed deletion or additional revision increment
is a contract failure, not a broad privacy exemption.

Closure request becomes blocked, revision2, fresh hex fence, updated_at exact confirm
now; its original created_at/digests/actor/scope/disposition stay fixed. Inventory step
remains unchanged at revision1/old fence. Exactly one new step
`(closure_id,'analysis_queue_cancel')`: A workspace, request_revision2, new closure
fence, attempts1, state complete, lease null. Its evidence digest is SHA256(sorted
compact JSON) of exactly `{schema_version:'inlet.lifecycle.queue_cancellation.v1',
workspace_id:A,request_id:closure_id,revision:2,rows_canceled:0}`.
`google_customer_import_completions` remains empty. No local-quiescence/reconcile step
is created; the test calls status, not reconcile-local.

Final blockers are exactly this ordered list, using `LifecycleBlockerV1` keys
`code`, `subsystem`, `resolution_kind`:

1. retention_policy_unset / lifecycle / owner_policy
2. legacy_scope_unclassified / inventory / implementation
3. publication_unresolved / provider_exposure_reservations / operator_evidence
4. provider_revocation_unverified / connections / operator_evidence
5. billing_unresolved / billing / operator_evidence
6. worker_not_quiescent / jobs / implementation

`inventory.blockers` supplies the first three (held successor); quiesce deduplicates
its repeated retention blocker then adds the last three. No unresolved execution
step exists in this successful-original/unclaimed-successor source. Current status
observes local work without persisting it. Both session rows remain valid/unrevoked;
Bob's entire source graph is unchanged; Alice is blocked, not closed/erased.

## Protected And Zero-Effect Assertions

All provider revisions/consents/reviews/approvals, attempts, responses, receipts,
Google original completion, replacement audit, both holds and ledger scalars are exact
pre-request values after privacy, as are full social review/confirmation documents,
approved source revisions, image metadata and bytes. Permit only mandate/run status
changes listed above, not mutations inside their approved documents. Verify the full
snapshot, not only immutable-table row counts or digests returned by the producer.

Finally snapshot every registered row/schema before and after EACH A/B advance.
Both must be409 with exact detail `advertising_writes_disabled_in_planning_mvp` and
zero database/media delta. No historical runtime crosses into this phase and no guard
or transport factory is patched to enable writes. Original Bob200/second mutation is
covered only by the separately unchanged historical2 execution.

Review gate: exact contract approval before implementation or source execution.
No new owner decision is needed for preserving the authentic historical assignments.

## Approved Access-Order Refinement (2026-10-10)

The first current SQLite privacy gate passed source typing, both real logins, the
complete archive and exact closure graph, then established Alice's post-closure
advance returns404. `app/api/planning_boundary.py::deny_advertising_mutation` calls
`bind_authority` before the planning write guard. Thus the precise revised contract
is both ACTIVE brands409 before closure, then closing Alice404 (`workspace not found`)
and still-active Bob409 afterward. Every advance has a full zero-delta snapshot.
This supersedes earlier wording requiring both post-closure responses409; no production
authority or guard is changed. Parent approved the refinement before continuing.
Original failure XML and exact source DB/media/DTO/lifetime/producer log are preserved
in `/workspace/inlet-evidence/archive-current-contract-01/`.
