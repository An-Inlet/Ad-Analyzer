# Proposed Customer Export And Closure Contract v1

Status: proposal for parent interface review; no schema, routes, worker, deletion,
provider calls, or retention policy implemented by this package. Baseline PR112
`3a3cca8`; isolated branch `codex/inlet-customer-closure-proposal`.

## Scope And Existing Gaps

Customer identity is global (`customer_users`, `customer_sessions`); ownership is
per workspace (`customer_memberships`). Closing a workspace must not close another
member's identity or the requester's other workspaces. Shopify data requests and
redaction cover only Shopify/commerce facts. They do not export or close the Inlet
account, billing, advertising jobs, publication accounting, or object storage.

Recommend workspace export/closure first, then separate identity closure. Do not
make a destructive catch-all account endpoint whose tenant scope is implicit.
Existing workspace status checks are useful, but insufficient: workers must fence
already claimed work, callbacks must not recreate connections, and the billing
dispatcher currently excludes non-active workspaces. Simply setting status inactive
would hide the very billing reconciliation needed to finish closure.

## Shared Versioned Interfaces To Freeze Before Implementation

`LifecycleScopeV1 = {schema_version: "inlet.lifecycle.scope.v1", kind: "workspace",
workspace_id: positive_int}`. Customer/actor IDs come only from authentication.
Future identity scope is a different discriminator; it is not silently expanded to
all owned workspaces. Each adapter receives the complete server-resolved scope.

`LifecycleRequestV1 = {id, scope, operation: export|close, requested_by,
request_digest, state, revision, fence, created_at, updated_at, policy_version,
blockers[], completed_steps[], summary_counts}`. A required bounded Idempotency-Key
is namespaced by scope + actor + operation, and binds normalized input. Reuse with
changed input is 409. Scope/authority is checked before receipt lookup. Store only
safe classified error codes, never tokens or arbitrary provider payloads.

`LifecycleBlockerV1 = {code, subsystem, resource_ref, resolution_kind,
customer_summary}`. Initial codes: `publication_unresolved`, `billing_unresolved`,
`provider_revocation_unverified`, `worker_not_quiescent`, `retention_policy_unset`,
`media_generation_unavailable`, `legacy_scope_unclassified`, `export_incomplete`.
Resolution kind is `implementation`, `customer_action`, `operator_evidence`, or
`owner_policy`. No client-supplied flag can mark an external action verified.

`ClosureStepV1 = {request_id, step_key, scope, expected_revision, fence,
state: pending|running|blocked|complete, attempts, safe_result, evidence_digest}`.
Workers claim under lock; every commit rechecks request revision/fence and scope.
Replay is idempotent; stale workers cannot mark a newer request complete. An adapter
provides `inventory(scope)`, `quiesce(scope, fence)`, `purge_local(scope, policy,
fence)`, `verify(scope, fence)`; it does not own commits. External actions are
separate typed work items and remain blocked in the offline implementation.

Proposed customer routes: POST workspace `/exports`, GET `/exports/{id}`, GET
`/exports/{id}/download`, POST workspace `/closure-preview`, POST `/closures`, GET
`/closures/{id}`. Closure POST requires exact preview revision/digest + explicit
workspace confirmation. Only current owners can close/export; no admin role
escalation. CSRF, recent session checks and mutation-boundary reauthorization apply.
A dedicated receipt-reader authorizes the recorded requester/current owner against
the tombstone, without reopening normal product access after closure begins.

## Export Semantics

Manifest `inlet.customer-export.v1`: workspace scope, snapshot time, export ID,
section schema versions, counts, per-section SHA-256, included/excluded fields,
media inventory with digest/size/MIME, and an explicit completeness result. Use
allowlisted serializers, never ORM dumps. Include customer-visible configuration,
goals/revisions, mandates/actions/accounting, campaigns/metrics/findings, connection
status/account names, billing status, and owned commerce/measurement/legacy CRM data.
Exclude ciphertext, grants, session/CSRF/token digests, secret-manager references,
provider cursors, internal transport payloads and unrelated members' personal data.
Actor references may use stable scoped IDs; do not export global identity profiles.

First package recommendation: synchronous bounded streaming export from a consistent
PostgreSQL REPEATABLE READ snapshot (SQLite equivalent tested), using server-side
bounded batches and explicit byte/row limits. No persisted export artifact or emailed
URL, so no invented export-retention policy. A disconnected/incomplete stream never
marks the request complete; the manifest/footer verifies completeness. Retry creates
a new snapshot revision of the same request, explicitly labeled, not silently mixed
pages. A full export that exceeds bounds reports incomplete and a typed blocker;
large durable exports remain a declared implementation gap, not a false success.
Media bytes are separate authenticated exact-content downloads until an export
archive store with generation-bound cleanup is implemented; manifest-only media
must be labeled as such and cannot be called a complete portable media archive.

## Closure State Machine And Safety Conditions

`requested -> quiescing -> blocked | ready_to_purge -> purging -> verifying -> closed`.
Retryable step errors retain the last durable stage and safe error; `blocked` keeps
resume_stage. No automatic reopening/cancellation after quiescing: credentials may
already be gone. Reconnection is a separately authorized workflow, not receipt replay.

1. Preview inventories exact scope, external liabilities and uncertainty. Confirmed
   request locks workspace, then users/sessions/memberships in canonical order before
   product locks. Avoid cross-workspace locking in one transaction. Increment a
   lifecycle fence and mark workspace closing, pause mandates/automation, revoke
   workspace-specific pending authorization nonces, and disable new product work.
2. Fence imports, CRM leases/checkpoints, callbacks, campaign changes and dispatch.
   Cancel only provably undispatched work; preserve dispatch fences and all uncertain
   outcomes. Clear locally stored grants and pending encrypted grants, increment
   connection generations, suspend integrations. This is local credential removal,
   not provider-side revocation. External revocation is a separate unresolved item.
3. Drain/reconcile in-flight work. Late import commits must fail the lifecycle fence;
   late billing/publication receipts may enter an append-only reconciliation lane,
   but cannot reenable entitlements, connections, jobs or mandates. Reconciliation
   for closing workspaces needs explicit new code, not reuse of active-only guards.
4. Block purge of connected accounting graphs when mandate actions are dispatching
   or outcome_unknown, publication steps are dispatching/unknown/conflict, a worker
   retains an active lease, or billing checkout/subscription state is unresolved.
   Preserve reservations, request/fence IDs, receipts, audits, referenced immutable
   creative and plan definitions. A timeout, cancel_requested, disconnected grant,
   or paused_verified campaign is NOT proof of no effect or settled exposure.
5. Under an approved disposition policy, purge eligible local data in dependency
   order with restartable receipts. Keep the workspace tombstone and minimal required
   accounting/evidence until disposition permits removal. Never hard-delete Workspace
   and rely on cascades: mixed CASCADE/RESTRICT and JSON references make that unsafe.
6. Verify zero active grants/nonces/jobs/membership access, no normal product writes,
   no unclassified rows, complete eligible media deletion receipts, settled external
   obligations and known retained-data disposition. Only then mark closed. If any
   external or retention item is unresolved, show closure pending with exact blockers;
   do not claim all data erased, billing stopped or external ads paused.

Workspace closure invalidates workspace access/authorizations, not every global user
session. Identity closure is a later explicit request: revoke all that user's sessions,
resolve owned workspaces by closure or owner transfer, remove remaining memberships,
then minimize identity under approved policy. Do not globally delete other members.
`customer_token_exchanges` has no user linkage: retain its bounded expiry protection
until normal expiry rather than delete all customers' replay receipts.

## Table And Resource Disposition Inventory

| Family / ownership route | Export / closure treatment |
| --- | --- |
| workspaces, workspace_configurations, workspace_findings; workspace_memberships (operator), customer_memberships, customer_workspace_signups | Explicit workspace filters. Export customer-visible config/findings. Suspend both access planes for closing scope; retain ownership/idempotency tombstone. Operator membership is not interchangeable with customer identity. |
| customer_users, customer_sessions, customer_token_exchanges | Identity-global: workspace export redacts secrets/other users; workspace closure does not erase global identities. Separate identity-close workflow and bounded token replay expiry. |
| workspace_integrations; google_customer_authorizations/connections/import_completions; customer_source_authorizations/connections | Remove local grants/staged payloads/nonces; retire generation and import work. Secret-manager references describe external resources; never destroy cloud secrets merely by deleting a DB reference. Google completion ownership joins through job_runs. |
| meta_connections/oauth_states/pending_grants/staged_metrics/audits/detail_checkpoints/detail_staged_pages | Scope by workspace and compound connection/account ownership. Invalidate native grants/generations and staged continuation; no remote revocation calls. Audit disposition is policy-controlled. |
| shopify_connections/oauth_states/orders/tombstones/privacy_requests/audits/privacy_identities | Reuse proven local disconnect/privacy helpers inside the lifecycle transaction, after refactoring internal commits if needed. Preserve erasure suppression until reconnection is impossible/closure tombstone established. Shopify erase alone is insufficient. |
| commerce_stores/orders/entries/daily_revisions/snapshots/source_links/suppressions/shop_aliases | Store-to-workspace joins; purge derived snapshots and legacy bridges as well as raw facts. Preserve anti-resurrection fences until inputs are permanently blocked. Existing 13-month measurement retention is not authority for other tables. |
| crm_connections/events, lead_attribution, crm_sync_runs; customer_context_quotas/checkpoints | Export only owned persisted records. Transient CRM previews are not stored profiles. Checkpoints join through source connection; opaque quota hashes lack direct workspace FK and require explicit derivation/attribution before deleting. Never blanket-delete shared rate state. |
| advertising_accounts/campaigns/ad_groups/ad_sets/ads/keywords/search_terms/daily_metrics/conversion_events | Compound workspace/integration/account joins, including entities without direct workspace column. Partition purge only after publication/accounting dependencies are resolved. Remote ads keep existing provider state. |
| job_runs, import_rejections, analysis_runs; recommendations/recommendation_audits/execution_audits | Quiesce claims and fence completion first. Some legacy rows/rejections need explicit ownership classification; unknown scope blocks deletion/export inclusion. Preserve execution evidence for uncertain effects. |
| customer_goals/goal_creations/goal_revisions/goal_previews/goal_confirmations, goal_usage_policies, goal_interpretation_usage | Goal/workspace joins; export confirmed and editable history. Purge only once mandate/publication references are classified; retain minimal replay/tombstone requirements per policy. |
| spending_mandates/revisions, mandate_actions/audits; publication_plans/steps/receipts | Protected accounting graph. Never delete unknown outcomes or release reserved exposure to make closure appear complete. Settled record retention requires policy. |
| customer_media_objects, customer_campaign_drafts/revisions; local/GCS bytes | SQL deletion does not delete bytes. Current MediaStore has no generation receipt/delete API; typed lifecycle metadata + conditional delete/outbox is separate implementation. JSON artifact references require explicit reachability, including publication plans and uncertain receipts. |
| customer_workspace_billing, customer_billing_events | Events join by canonical billing customer ID, not a workspace FK. Retain uncertain checkout keys/subscriptions and receipts. No cancellation/refund/revocation call is authorized by this offline assignment; late events use a closure reconciliation lane. |
| measurement_contracts/stage_definitions/event_mappings/web_analytics_events; intelligence_records/revisions | Workspace/contract/parent joins; versioned customer-visible export serializers and explicit derived-data purge. Do not silently omit legacy product data. |
| workspace_automation_controls, automation_control_audits; platform_automation_controls | Disable scoped automation; retain scoped audit per policy. Never alter global platform controls when closing one customer. |
| logs, backups, caches, provider-side data, queue deliveries, object versions/soft-delete | Not represented completely in SQL. Inventory deploy/runtime resources before completion claims; restore must replay closure tombstones before workers start. No automatic backup deletion or provider mutation. |

## Decisions Versus Implementable Work

Implementable now without new commercial decisions: scope/owner/CSRF and idempotency
contracts, inventory/export serializers, lifecycle receipts/fences, quiescing and
no-resurrection tests, local grant invalidation, closure status UI, explicit external
blockers, mocked external evidence adapters, and safe protected-accounting detection.
None needs a chosen paid price or an invented retention duration.

Owner decisions still required: immediate vs period-end paid cancellation/refund
behavior; disposition/retention of settled financial/security/audit records and creative;
backup/object soft-delete recovery windows and region; identity tombstone/re-signup
policy; export artifact retention/delivery if durable archives are introduced. Recommend
fail-closed pending status, no automatic charge/refund, no arbitrary retention numbers,
and explicit visible retained-data categories until those decisions are recorded.

No legal conclusion is proposed here. Unknown accounting is an engineering safety
invariant, not a discretionary retention choice. External provider cancellation,
revocation or deletion requires separate live authority and verified evidence.

## Dependency-Ordered Packages And Acceptance

1. Freeze interfaces; add schema migrations for lifecycle request/step/fence, typed
   inventory and all scoped export serializers. Tests enumerate metadata tables so
   future tables cannot escape classification. Foreign-tenant sentinels in every family.
2. Add preview/confirm/status, atomic local quiescing and worker/receipt fencing. Test
   in-flight import/OAuth refresh/CRM acknowledgment/paused publication and late billing
   events against two tenants, SQLite and PostgreSQL. No provider side effects.
3. Add bounded consistent export + explicit media manifest/download limitations. Test
   stream interruption, revoked session, concurrent mutation, scope replay and secret
   exclusion. No incomplete stream is labeled complete.
4. Add policy-gated purge and generation-bound media delete receipts after interface
   approval. Test crash/retry between object and SQL operations, missing/replaced object,
   shared references, unknown publication preservation and restore anti-resurrection.
5. Add independent identity-close flow and, only under approved live authority,
   external billing/grant resolution. Synthetic full closure can use fixture evidence;
   it must not be reported as production closure or provider verification.

No implementation tests were run for this documentation-only investigation. Baseline
source review covered models, current guards, publication/mandate accounting, billing
active-only dispatcher, scoped disconnect and Shopify/commerce privacy paths.

## Parent Approval And Package 1 Implementation

On 2026-10-06 the parent approved the workspace-only v1 interfaces and package 1:
inventory, durable receipts/fences, and allowlisted export serializers. Migration
`20261006_0044` is reserved on `20261006_0042`; scheduler branch `0043` is independent.
Disposition remains explicitly unset. No purge or remote billing/grant action is
approved. Atomic local quiescing is a separate subsequent package.

Implemented internal foundation in `app/lifecycle`: owner-only intent receipts with
scope/actor/operation-bound replay, workspace-serialized creation, composite-scoped
inventory steps, expiring worker leases and stale-fence rejection. The caller owns
transaction commit. Completing an inventory step does not complete an export or
close a workspace. Models are registered along with otherwise unloaded publication
models, so publication accounting cannot disappear from inventory by import order.

Static table policies classify the entire baseline SQL model graph, including global
and unclassified state that must not be queried as tenant-owned. Scoped counts and
allowlisted scalar projections use direct or explicit ancestor ownership predicates.
All omitted fields are reported; unbounded text and nested JSON require further
schema-specific serializers. Internal section projection is capped at 1,000 rows,
64 KiB per serialized row and 4 MiB per section; truncated results are explicit.
Unknown publication/mandate outcomes are typed blockers and their accounting graph
is protected. No delete function, external transport, or complete-export transition
exists in this package.

This is not a customer-download or full-export implementation. Snapshot/streaming
routes, nested historical JSON serializers, portable media bytes and the customer UI
remain work. Every section says `complete_export=false` and
`media_archive_complete=false`. No durable export file or retention duration is
invented. Workspace memberships, other tenants, global sessions and unknown financial
reservations remain unchanged by package 1. Registry mismatch fails closed until a
new package's tables are explicitly classified.

Package 1 validation (2026-10-06): combined lifecycle/migration/prior-migration/
authorization-race/customer-identity run **65 passed, 3 SQLite lock skips**; then the
final lifecycle file, including the added unknown-accounting preservation case,
**18 passed, 1 SQLite lock skip**. PostgreSQL counterparts ran. Ruff passed; mypy
passed for 325 source files; `git diff --check` passed. Migration roundtrip tests
preserved existing tenants and rejected cross-scope steps and invented disposition
policy. Full/hosted CI remains pending; no live environment was used.

The prior reviewed migration test now checks its fixed merge ancestry, rather than
assuming 0042 remains the latest head forever. Removed the obsolete GCS test typing
suppression already removed by root PR113; no GCS behavior changed.
