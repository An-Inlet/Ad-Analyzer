# Local Closure Admission And Drain

This records the approved local reconciliation interface and its implementation,
alongside the earlier verified import-lock repair. It does not
change retention, release financial exposure, revoke remote grants or terminate
processes. The owner has not supplied a data-disposition policy.

## Verified Import Repair

Branch `codex/inlet-import-closure-fence` starts from PR147 head0741b24. Legacy
Google advertising scope and CRM scope previously used joined FOR UPDATE queries
that acquired integration locks before waiting for the workspace. Actual PostgreSQL
closure held workspace; both waiting imports held integration, so closure's NOWAIT
integration lock failed with SQLSTATE55P03. This establishes a lock-order cycle,
without deliberately waiting for the database deadlock detector to kill a transaction.

Both guards now use the shared refreshed workspace NO KEY UPDATE lock first,
reject inactive/missing workspaces, then lock only their product/integration rows.
All existing ownership/provider/account checks remain. Closure commits before waiting
imports resume; each import then rejects the closed scope. No raw provider calls.

- Baseline: two PostgreSQL failures, two SQLite row-lock skips,6.02s;
  `/tmp/inlet-import-closure-before.log`.
- Focused:84 passed,two SQLite row-lock skips,35.06s;
  import closure/ownership,CRM worker/gateway,Google sync,customer quiescing.
- Ruff app/tests passed; mypy405 source files passed.
- Parent runs integrated Full; this package did not run it.

## Actual Worker Boundaries

| Worker family | Existing admission/persistence fence | Remaining evidence limit |
| --- | --- | --- |
| Analysis | PR147 workspace lock at claim, after durable claim and direct success; held through local outputs | A legacy RUNNING row has no termination receipt; age is not cancellation |
| Legacy Google runner | Explicit workspace-first scope validation at durable JobRun creation and before collector; transaction holds authority through persistence | Advisory lock ownership is not a portable historical termination record; unknown commit outcomes remain protected |
| Legacy CRM event worker | Workspace-first CRM scope before event/attribution writes and commit | Previously recorded CrmSyncRun status alone does not establish process termination |
| Customer Google/TikTok imports | Fresh active workspace/connection/generation at tick; scope locks held through provider page and local publication | Queued identifiers selected before closure are harmless only because tick rechecks; selected queues still need honest pending/canceled accounting |
| Meta/Shopify scheduled pages | Workspace first, then native connection; closure changes local native/integration authority | Selection is not a claim; tests must distinguish skipped from completed work |
| CRM customer context | Owned active source/generation plus committed checkpoint fence; rechecks after unlocked HTTP and on acknowledgement | Closure invalidates continuation but cannot prove an already issued HTTP read physically stopped; shared quota rows are not tenant-owned |
| Analysis completion outbox | PR147 rejects downstream analysis for closing workspaces | Pending GoogleImportCompletion retries currently remain pending/back off; they must never be marked delivered merely because closure rejected execution |
| Billing dispatcher/inbox | Dedicated closing receipt lane preserves events and defers active billing transitions | External subscription cancellation/readback is a separate obligation, not local worker drain |
| Publication/production execution | Workspace admission, revoked mandate/canceled future run; exact original attempt late-evidence lane | Emitting/dispatching/unknown/conflict attempts and held exposure remain unresolved, irrespective of time |
| Privacy/retention/export maintenance | Dedicated closing-compatible workspace guards and privacy revisions | Must remain permitted during closure; cannot be counted as forbidden customer work |

## Approved Versioned Reconciliation Interface

`POST /api/customer/v1/workspaces/{wid}/closures/{request_id}/reconcile-local`
with strict body `{"expected_revision": N}`; current requester/owner, active session,
CSRF and provider identity revalidation. Scope remains exactly one workspace; no
identity/global-session deletion or other membership changes. Lock order is
workspace → user → session → membership → lifecycle request → scoped product rows.
No network/provider calls inside reconciliation.

Return an explicit `inlet.lifecycle.local_quiescence.v1` observation:

- `workspace_id`, `request_id`, `request_revision`, `observed_at`;
- `admission_fenced`: closure status and all known local connection/mandate controls
  match expected revoked/disabled state, with complete worker-family registry;
- `local_records_drained`: no scoped nonterminal JobRun/AnalysisRun/CrmSyncRun or
  live customer-context continuation, and no uncanceled deliverable local queue;
- bounded counts per worker family, with `unknown` classification for historical
  states whose meaning cannot prove termination;
- `physical_workers_stopped: null`, always, because no process-termination protocol
  exists; `external_obligations_resolved` is separate and never inferred here;
- `blocked_reasons` and evidence digest, excluding identifiers/credentials/payloads.

The implementation uses the existing LifecycleStep receipt `step_key=local_quiescence_v1`, bound to the
request revision/fence, with a monotonic request update. The currently available
step stores only a digest, so GET recomputes and labels a current-only observation.
The retained digest includes its recorded request revision; it is explicitly not
a retained historical observation payload. Do not fabricate durable details from a digest.
GET remains read-only. Replays with stale revisions cannot mutate receipts.

## Implemented Engineering And Remaining Acceptance

1. Added an explicit, tested worker-family registry and scoped status
   queries. Unknown families/state values fail closed. Share scope predicates with
   lifecycle inventory; never scan or mutate another tenant's global quota.
2. Introduced an explicit terminal *local queue cancellation* receipt/state for
   pending analysis outbox work, preserving its completed source import and original
   run evidence. Fence dispatcher selection and acknowledgement under workspace
   authority. This state means no future local delivery, not worker termination.
3. Added the reconciliation route/service and structured UI distinction between
   admission fenced, observed local records drained, and external/policy blockers.
   A no-work fixture can satisfy the local step; a RUNNING legacy row cannot be
   cleared by timeouts. Late failure/receipt evidence can make a later observation
   drained without changing or erasing the prior run history.
4. Tested actual PostgreSQL and SQLite closure-before-selection, selected-before-
   closure, in-flight commit, late acknowledgement, replay, revoked owner/session,
   foreign workspace and unknown-state paths. PostgreSQL verifies lock ordering;
   SQLite does not substitute for row-lock proof.
5. Require a quiescent uniform worker upgrade before claiming the new fence covers
   a deployed installation. Old binaries that lack guards cannot be repaired by
   schema migration or a new UI label; no live deployment is authorized here.

The remaining owner decision is disposition/retention and external commercial
obligations, not permission to fix routine local admission defects. Local completion
must be attainable once its evidence criteria are met while overall closure remains
blocked by independent external, unknown-publication and policy obligations.


## Reconciliation Delivery Evidence

Implemented on isolated `codex/inlet-closure-reconciliation`, after priority shared
analysis-session repair155a2609d1. No schema migration: the existing outbox uses an
unconstrained String state. `canceled` means no future local delivery; the original
successful JobRun and records are unchanged. An atomic `analysis_queue_cancel`
LifecycleStep records a digest. Dispatch selection and acknowledgment refresh
workspace authority, and neither a late success nor failure resurrects canceled work.

The API uses the existing current-session/owner/CSRF authority and request revision.
Its observation clock is sampled after authority and request locks. A PostgreSQL
regression expires the session while reconciliation waits on workspace and verifies
401 with no revision change. Reconciliation failure rolls back its queue state,
request revision and digest together. Current local observations are read-only on GET.
Unknown work-table families and unrecognized legacy run states fail closed. Meta
detail continuation is classified through its native generation; protected publication
steps/attempts remain distinct external/accounting obligations. Shared quota state is
not mutated. Privacy/retention and exact original evidence lanes remain permitted.

The actual production closure page offers Check Local Work. Chromium exercised the
HTTPS page → authenticated API → SQLite/PostgreSQL flow, revision update, current-only
observation, retained-digest wording, continued full-closure blockers and logout/role
loss. The UI does not report process termination or data erasure.

Verification: combined reconciliation, closure, actual browser, runtime scheduler and
Google customer connection suite: **77 passed,1 SQLite-only row-lock skip**,41.01s.
An additional late-failure regression is recorded separately in the package report.
Ruff app/tests and mypy408 source files passed; integrated Full remains parent-owned.
Baseline queue tests failed all4 cases (both databases),4.25s. Logs:
`/tmp/inlet-closure-queue-before.log`, `/tmp/inlet-closure-reconciliation-final.log`.

Deployment qualification remains blocked on a quiescent uniform worker upgrade;
old binaries are not fenced by this code merely because schema is current. No live
rollout is authorized. Overall closure remains blocked by disposition/retention,
external grant/billing verification, legacy data scope and any unresolved publication
accounting. The local step can now be satisfied honestly when its observed criteria
are met, instead of a permanent implementation-only blocker.
