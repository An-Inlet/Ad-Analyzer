# B18 Bounded Customer Export

This package implements export for the integrated PR130 and commerce-publication schema. It does
not close accounts, delete records, cancel billing, call advertising providers,
or fetch remote customer data. Existing identity revocation checks still apply.
The parent approved these interfaces before implementation, including strict `{}`
input and mandatory media inclusion, on 2026-10-06.

## Customer Interface

All routes use `/api/customer/v1/workspaces/{workspace_id}/exports`:

- POST with `{}`, customer CSRF and `Idempotency-Key` creates/replays a request.
- GET `/{request_id}` returns the requester-bound owner receipt.
- GET `/{request_id}/download` builds an ephemeral TAR in a synchronous worker
  thread and streams it. A retry builds a new snapshot revision; it does not
  resume or mix data from the previous snapshot.

Active and locally closing workspaces can export. The requester must still be an
active owner, with an active customer identity, membership and unexpired session.
Other owners cannot adopt an existing request. Global identity sessions and other
workspace memberships are untouched. No public download link or stored artifact
is created. The existing closure APIs are unchanged.

## Snapshot And Completeness Contract

The TAR contains `manifest.json`, explicit versioned per-table JSONL sections,
and media named using validated server IDs and MIME extensions. Every section and
media member has a SHA256 and byte count. Structured fields use explicit
allowlists and existing typed product contracts where available; ORM objects,
provider grants, encrypted fields, session credentials and raw internal staging
are not dumped. Invalid historical structured data is omitted and reported as
unsupported, not silently counted as complete. New unclassified ORM tables stop
export entirely until their ownership is reviewed.

One PostgreSQL REPEATABLE READ or SQLite read transaction supplies all data.
The manifest records the established snapshot's as-of time and request revision.
The receipt persists that timestamp, revision, completeness summary and manifest
digest after building. An export attempt has its own lease and fence. Concurrent
PostgreSQL claims have one winner; stale attempts cannot overwrite a newer result.

The manifest distinguishes:

- `supported_customer_data_complete`: every supported scoped field serialized;
- `media_archive_complete`: all owned media was read and verified;
- `all_stored_workspace_data_complete`: also requires no unclassified ownership.

The last flag remains false for baseline legacy `import_rejections` and
`customer_context_quotas`, which lack proven workspace predicates. Their contents
and global counts are never read. Identity-global and platform-global tables and
security/internal columns are explicit intentional exclusions. Missing/corrupt
media fails the build rather than returning a purportedly complete archive.

`archive_built` describes generation only. `delivery` is always `unconfirmed`,
including after the iterator exhausts. A browser/network failure cannot prove
customer receipt. No export request is marked delivered or globally complete.

## Resource And Revocation Bounds

Limits: 100,000 rows, conservative 1 MiB stored/serialized row, 32 MiB JSON data,
128 MiB total media, existing 64 MiB individual-media bound, 192 MiB TAR,
120-second cooperative build deadline, 300-second stream deadline, two simultaneous
build/streams per process. PostgreSQL statements have a 15-second local timeout.
Underlying storage/identity calls retain their own timeout behavior; the build
deadline is checked before and after calls, not a promise to interrupt a blocked SDK.
SQL CASE prevents oversized selected values being materialized by the driver.
Anonymous temporary files are closed on build exceptions, normal completion,
iterator cancellation, unstarted response cleanup and ASGI send errors. No durable
artifact retention policy is needed or implied. Capacity is per process, not a
cross-replica quota.

Authorization uses separate fresh transactions during generation and before each
64 KiB output chunk. It checks local admission again after provider IO. Revoked
access aborts the stream; bytes already delivered cannot be recalled. The original
snapshot is not reused as an authorization cache. Session expiry and superseded
request fences are also checked.

## Integration And Remaining Work

This branch began from PR122 plus canonical model registry commit `8fb35bc`,
then integrated frozen candidate `0cf6706` and commerce publication `e9708ec`.
The provider-review and commerce publication schemas are explicitly classified.
Parallel production-execution/outcome models require additional lifecycle and
structured export classification before integration; do not weaken the guard.
The shared workspace privacy revision and commerce stamp are described below.
No retained-export policy, purge policy, final closure state or live provider
verification is claimed. Export UI and cross-replica resource admission are not
part of this backend package.

Validation results and exact branch/head are recorded below once checks finish.

## Backend Validation

On the package candidate before UI/privacy-generation integration:

- `pytest tests/test_customer_exports.py tests/test_customer_lifecycle.py tests/test_customer_quiescing.py tests/test_model_registry.py tests/test_lifecycle_migration.py -o addopts='' -q`: **77 passed, 2 skipped** (SQLite row-lock-only cases), 58.68 seconds. Uses disposable PostgreSQL plus file SQLite/WAL.
- `ruff check app tests/test_customer_exports.py`: passed.
- `mypy app tests`: passed, 334 source files.
- `git diff --check`: passed.

Log: `/tmp/inlet-exports-final-focused.log`. Coverage includes real HTTP session/CSRF,
create replay, TAR download/status, separate owner denial, logout, both-database
snapshot consistency under concurrent committed changes, corrupt/missing/path-unsafe
media, nested secret omission with incomplete flag, row/data/archive/deadline
bounds, build revocation, stream expiry/revocation, ASGI send failure cleanup,
closing workspace access, admin denial, and PostgreSQL concurrent claim contention.
This is backend evidence, not a live environment or full-suite pass.

## Customer Export Page

`/app/workspace-export` adds an owner workspace selector, request creation, native
browser TAR download and generation-status refresh. Native download avoids loading
a 192 MiB archive into JavaScript memory. It displays supported-data/media/all-data
completeness separately and never claims successful delivery. Receipt links also
work for locally closing workspaces after authorization. Request keys survive an
ambiguous network retry in the current page/workspace; they are not persisted
across reloads. Account changes clear rendered data, request links and pending keys.

Focused page checks: **2 passed**, including actual Chromium DOM with mocked HTTP
responses (lost response keeps key, receipt/status, unconfirmed delivery, account
switch and empty workspace), plus shell security headers. Backend HTTP/database
coverage above uses real APIs and SQL. These are complementary tests, not a claim
that this Chromium fixture exercises the real API. Ruff passed; mypy **335 files**
passed. Logs `/tmp/inlet-export-ui-focused2.log`, `/tmp/inlet-export-mypy2.log`.

## Integrated Checkpoint

Merged frozen candidate `0cf6706` into this isolated branch (`c75fb7a`), preserving
newer billing and closure navigation. Added typed provider-review/plan projections;
qualification evidence remains an intentional internal exclusion. Meta OAuth
phase is exported; nonce digests remain excluded.

Actual HTTPS Chromium → production session/workspace/export APIs → file SQLite and
PostgreSQL: **2 passed**. Browser created an owned workspace/request, fetched the
real TAR, verified stored workspace content and DOM receipt, revoked its cookie
through logout, and received 401 on another archive request. Only identity is an
offline provider fixture; browser fetch is not replaced. The test consumes the
real archive with browser fetch, rather than claiming an operating-system Save
File dialog was verified.

Integrated export/backend/UI/closure UI/model-registry focused checks: **53 passed,
1 SQLite row-lock skip**, 63.47 seconds. Ruff and mypy **365 files** passed. Logs
`/tmp/inlet-export-real-browser.log` and `/tmp/inlet-export-browser-combined.log`.
Full remains parent-coordinated. Shared workspace privacy revision work is approved
and underway; this checkpoint is not final acceptance for concurrent erasure.

## Privacy Generation Contract

The parent approved one shared `Workspace.export_privacy_revision` (BIGINT,
initially zero) and reserved migration `0053` down `0047`. It is not a retention
policy. `app.lifecycle.privacy.bump_workspace_export_revision` locks the workspace
without an active-only admission predicate and increments inside the caller's
transaction. It never commits. Closing and retained inactive workspaces still
receive erasure/retention maintenance; rollback reverses both deletion and revision.
Call before native/store locks, or only after the same workspace is already locked.
Multiple workspaces are locked in increasing ID order.

The archive captures both this revision and `workspace_privacy_stamp` inside its
single data snapshot. Every fresh build/stream authorization checkpoint compares
both against independent current reads. A change aborts generation or further
streaming; previously delivered bytes cannot be recalled. The commerce stamp also
includes the store set, source generation and privacy epoch. The workspace revision
covers legacy-only stores that never had a CommerceStore.

Wired destructive source paths:

| Stored Data | Existing Destructive Writer | Transactional Fence |
| --- | --- | --- |
| Legacy Shopify facts and privacy identities | Authenticated orders/delete, customer redact, shop redact and uninstall handling | Ordered owning workspace locks, then shared revision before native/store work |
| Legacy Shopify imported orders | Sync page suppressed/test-order removal and retained-history cleanup | Already-held workspace lock, increment inside page savepoint |
| Native Shopify connection and cascading facts | Explicit local disconnect | Shared revision before native connection locks |
| Expired legacy orders, tombstones, privacy requests, audit records | Existing retention sweep | One owner transaction, workspace first, shared revision before cleanup |
| Commerce facts, snapshots and aggregate publications | Commerce invalidation for erase, disconnect, rebind and retention | Existing workspace-first invalidation advances shared revision and source epoch |
| Native Meta connection and cascading/staged data | Explicit local disconnect | Shared revision before native locks |

CRM and customer Google/source disconnect currently retain imported facts; no
existing customer-data erase/retention writer was found for those domains. Their
normal data updates are represented by the as-of snapshot. Credentials and raw
transport staging are intentionally excluded. Future destructive writers and
media-deletion APIs must adopt this same revision contract before being enabled.
Unknown model ownership remains fail-closed, and intentionally unattributable
legacy data remains omitted with `all_stored_workspace_data_complete=false`.

No separate privacy counter was introduced in parallel. Commerce change
`a3e1e39` is integrated. Migration `0051` and `0053` remain separate heads for the
parent's final schema integration; this package does not invent a merge revision.
Export UI now exposes expired build leases as interrupted so an owner can explicitly
retry after a stopped worker; it never auto-restarts or declares delivery complete.

## Privacy-Integrated Acceptance Checkpoint

The final focused command included export APIs/serializers/browser UI, real HTTPS
browser/API/database journeys, shared privacy revision races/migration, commerce
publication/migration, existing Shopify and Meta connections, registry, lifecycle,
quiescing and lifecycle migration: **162 passed, 3 SQLite row-lock-only skips**,
107.87 seconds. No test failure remains in that run. Logs:
`/tmp/inlet-export-final-acceptance.log` and `/tmp/inlet-export-final-mypy3.log`.
Ruff passed; `mypy app tests` passed **371 files**; `git diff --check` passed.

Actual legacy-only erasure tests keep an export snapshot open while a separate
connection commits `orders/delete`, and also erase after the first stream chunk.
Both SQLite/WAL (foreign keys enabled) and PostgreSQL abort further export access.
PostgreSQL statement capture verifies the first destructive lock is the workspace.
Tests separately cover closing-workspace disconnect, uninstall, retention, Meta
cleanup, privacy revision rollback, expired build recovery, and populated 0053
upgrade/downgrade. No live identity/provider/storage call, merge or deployment was
performed. Full and hosted CI are not represented by these focused results.

Parallel production coordinator and outcome-assessment schemas were still being
integrated by the parent after this checkpoint. Their owned JSON must receive
explicit versioned serializers (or remain visibly unsupported); the prior scalar
allowlists alone do not establish complete customer data export.

## Deployment Gate: No Mixed Destructive Writers

`INLET_CUSTOMER_EXPORT_ENABLED` defaults to `false`. Creation and archive download
return 503 while disabled; every generation/stream checkpoint also aborts when it
is disabled. Owner receipt status remains readable. Offline tests explicitly enable
the setting only against fixture identity/storage and disposable databases.

A schema migration alone does **not** qualify privacy-safe exports: an old writer
can delete data without incrementing the new column. There is no supported mixed
old/new writer rolling-deployment qualification. Before a release owner enables
exports, keep the flag off on every API instance, stop or drain old API/operator,
importer, scheduler and privacy-worker processes and their transactions, migrate,
then start only the same verified hook-enabled revision. Account for manual and
scheduled processes that share the database. Verify source erasure/retention hook
coverage and uniform running versions; uncertainty leaves exports disabled.
Disabling the flag also interrupts existing streams at their next checkpoint.
No live rollout, credentials, migrations or flag enablement are authorized by this
implementation package.

The coordinator followup merges rootnext `caff2a3` (including 0056 schema join).
Its twelve production execution tables now use explicit scalar projections plus
strict versioned policy, exact creation review, exposure, bound request, response,
receipt and normalized projection serializers. Unknown/future JSON remains
unsupported and sets supported-data completeness false. Internal control fields
remain excluded even if a newly reviewed table's inventory scalar list contains
them. Further outcome-assessment models still require separate classification.

## Coordinator And Disabled-Runtime Followup

Isolated `codex/inlet-export-coordinator` preserves PR140 at `4317cfe` and merges
rootnext `caff2a3` at `5702597`. Actual coordinator creates an owned production
review, bound attempt, response and verified receipt using the existing Google
HTTP MockTransport. Both SQL engines then export the resulting policy/document/
request/response/receipt/projection/exposure JSON through strict versioned schemas.
Malformed/future payloads are omitted and explicitly marked unsupported.

Focused export/coordinator/privacy/browser/registry/lifecycle tests: **81 passed,
1 SQLite row-lock skip**, 97.86 seconds; log
`/tmp/inlet-export-coordinator-focused.log`. Includes default-disabled config,
creation/download rejection while disabled, interruption when disabled mid-stream,
and existing real HTTPS browser/API/database journeys. Separate strict-domain
suite: **10 passed**, both databases. Ruff passed; `mypy app tests` **387 files**
passed; diff check passed. No new local Full, live provider call or rollout occurred.
