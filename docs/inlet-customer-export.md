# B18 Bounded Customer Export

This package implements export for the frozen PR122 stored-data schema. It does
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

This branch is based on PR122 plus canonical model registry commit `8fb35bc`.
New provider-review/production-execution models added in parallel need explicit
lifecycle classification and structured export allowlists before integration;
the completeness guard must not be weakened. Source-privacy epoch work proposed
for B17 is separate; this package does not introduce a shared privacy epoch.
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
