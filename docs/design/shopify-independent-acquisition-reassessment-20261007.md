# Shopify Independent Acquisition: Verified Strategy And Next Slice

Research only, 2026-10-07, source base `9580eb9`. No provider-account requests,
implementation, schema allocation, production registration or qualification changes.

## Corrected Inventory

The proposed acquisition prerequisite already exists. Do not rebuild it:

- `app/commerce/independent.py::IndependentAcquirer.acquire(ScanRequest)` starts
  with empty state, enumerates **all accessible orders**, traverses every agreement
  and sale connection, and computes requested daily values without reading the
  incremental ledger. `order_binding` checks each order again after nested reads.
- `independent_owned.py::OwnedAcquisition.capture/authority/acquire_and_publish/load`
  supplies original-session authorization through private short transactions,
  validates source/goal/privacy ownership and atomically publishes an immutable
  `inlet.commerce-independent-publication.v2` into the existing publication table.
- Completion explicitly says `correction_state=unresolved`,
  `snapshot_consistency=unavailable`, `maturity=unqualified`. There is no default
  route, worker, credential-refresh factory or conversion to qualified maturity.
- `CommerceSyncService.page` separately uses updated-at ranges and seven-day
  overlap. Its v1 publications are incremental and cannot substitute for a scan.

This corrects my earlier recommendation to implement a new independent collector.
The next work is bounded operational reachability and stronger observation evidence,
not another collector or a claim that current observations qualify learning.

## Current Official Contract

Inlet pins **2026-07**. The [orders query](https://shopify.dev/docs/api/admin-graphql/2026-07/queries/orders)
supports ID sorting and cursor pagination. Its `processed_at` filter concerns the
order; `updated_at` concerns its last update. Neither is a refund-processing-date
journal. Do not restrict acquisition by order creation/processing date, financial
status, cancellation or closure. A recent refund can belong to an ancient order.

The [Order object](https://shopify.dev/docs/api/admin-graphql/2026-07/objects/Order)
documents only 60 days of access by default. Historical access requires approved
`read_all_orders` in addition to an order-reading scope. Its agreements connection
has a `happened_at` filter, but this is not documented as equivalent to refund
processing time. Keep all agreements until normalization. Existing granted-scope
checks also require `read_products` and `read_customers`; do not silently remove them.
[Access scopes](https://shopify.dev/docs/api/usage/access-scopes) distinguish requested
access from the grants actually available to the installation.

[Refund.processedAt](https://shopify.dev/docs/api/admin-graphql/2026-07/objects/Refund#field-Refund.fields.processedAt)
is the refund-processing timestamp. Preserve `normalized_entries`: order/edit
agreements use happenedAt, refund agreements use processedAt; PRODUCT merchandise
amount excludes tax, and shipping/duties/fees/tips/gift cards are excluded. A
ReturnAgreement is not automatically a processed refund. No change to this metric.

[Pagination](https://shopify.dev/docs/api/usage/pagination-graphql#pagination-limits)
is capped at 25,000 objects, and large count results do not prove exact cardinality.
The existing collector's maximum 24,000 orders remains below this boundary; its
default is 2,000. Reaching any configured capacity is unavailable, never complete.

[Bulk queries](https://shopify.dev/docs/apps/build/apis/graphql-admin/bulk-operations/queries)
offer asynchronous large-result extraction with JSONL parent references and
connection restrictions. The reviewed page provides no transactional snapshot
guarantee. Bulk completion alone cannot justify settlement or freshness. A bulk
alternative would need its own operation lifecycle, private download limits,
partial-output rejection and cleanup; it is not needed for the first bounded slice.

## Exact Query And Coverage Strategy

Reuse the five existing operations, all revalidated against the documentation tool:

1. `InletIndependentAuthority`: shop ID/currency/timezone and actual installation
   scopes before enumeration and again at completion.
2. `InletIndependentOrders($after)`: orders(first:50, after:$after, sortKey:ID),
   pageInfo and id/createdAt/updatedAt/test/customer.id; **no date filter**.
3. `InletAgreements($id,$after)`: one agreement per page, parent order ID,
   agreement type/reason/happenedAt and refund.processedAt, first 50 sales.
4. `InletAgreementSales`: continue the exact agreement and verify its parent ID.
5. `InletIndependentOrderCheck`: compare original order identity/update/customer/
   test fields after all children. Mismatch or missing order aborts acquisition.

Follow every terminal cursor at every level. Reject repeated cursors, duplicate or
out-of-order orders, duplicate agreement/sale IDs, wrong parents, malformed money,
unknown metric semantics, GraphQL partial errors and permission failures. Never
replace missing data with zero. Empty days are zero only within a successfully
enumerated observation, with the existing unqualified consistency interpretation.

The **13-calendar-month retention floor limits retained event days, not order age**.
`retention_floor`, `normalized_entries` and owned publication enforce that window.
Old orders must be read transiently to locate recent refunds; do not persist their
old sale payloads or raw customer/order IDs in retained evidence. The current owned
adapter refuses unresolved suppression/privacy state instead of resurrecting it.

## What This Still Cannot Prove

Per-order reread detects some concurrent changes, not a global snapshot. An order
can change after its final check; a later deletion or imported/backdated event can
change an already scanned day. A second identical pass proves repeated observed
values, not impossibility of missing/late data. No snapshot, refund-age limit or
complete mutation-to-parent-update guarantee was established by the reviewed docs.

Consequently keep correction unresolved, no factual source watermark, and no
conversion into `IndependentReconciliationEvidence.assurance=independent_full_window`
or `settled_as_of`. A separate operational policy could eventually define an honest
observed-stability estimand, but that requires an explicit versioned contract; it
cannot silently populate strict v3/directional facts. Advertising action timing,
calibration and financial exposure remain independent prerequisites.

## Proposed Bounded Implementation Slice For Review

Reuse the existing owned adapter and v2 publication. Make acquisition resumable
before putting its current 30-minute synchronous loop in a scheduler or request.
No new table is authorized by this document.

Proposed minimal server-only interfaces:

- `capture_scan(principal, goal_id, expected_goal_revision, start, end) -> ScanRequest`
  delegates existing `OwnedAcquisition.capture`; store/source are resolved from the
  confirmed goal. Clients supply no scope proof, query, clock, cursor or credential.
- `advance_scan(checkpoint, authority, transport, clock, request_budget) -> StepResult`
  performs at most one bounded HTTP operation; phases are authority-before,
  order-page, agreement-page, sale-page, order-check, authority-after, publish.
  Required checkpoint binds exact ScanRequest digest, initial start/deadline,
  phase/sequence, cumulative limits and original-session identity. Pending source
  handles/cursors must be private, short-lived and erased with the source/job.
- `finish_scan` emits existing ScanCompletion only after every phase has completed;
  existing atomic publication performs final fresh source/session/privacy checks.
- `read_scan_status` returns phase, fixed blocker and publication ID, never native
  handles. A separate comparison of exact retained v2 IDs can report same-window
  per-day changes without claiming maturity or a candidate direction.

Persistence proposal before migration: owned operational job/checkpoint with exact
composite source ownership; bounded ephemeral de-duplication/partial aggregate
staging; immutable publication remains existing v2. No raw HTTP, credentials or
out-of-window historic facts. Configure per-tick/request/bytes/deadline limits
server-side. Preserve the original total deadline across retries; cooldown must
not renew scope or turn a partially read order into a complete one. Privacy,
disconnect/rebind, original-session revocation and expiry erase staging and deny
publication. One store's throttled/failed scan cannot starve another.

First acceptance after approval: actual configured job entrypoint using injected
HTTP, empty independent state despite a wrong incremental ledger, old-order/new
refund, all three pagination levels, zero/negative days, DST, restart after each
phase, limits/throttle, duplicate child, changed order and final-lock revocation;
SQLite/PostgreSQL publication/export/deletion checks. Assert unresolved/unqualified
throughout, no automatic evidence registration or spending authority.

## Research Validation And Limits

Applied the Shopify Admin skill. Materialized its bundled public-document helpers
locally. `search_docs.mjs --version 2026-07` failed with fetch failure; the pinned
validator failed because its packaged `/tmp/assets` schema directory was absent.
Fallback connected documentation search returned 2026-10 snippets, so versioned
web pages above were used for the pinned contract. Connected GraphQL validation
passed all five **existing** operations; its tool has no version selector, so this
is not claimed as pinned-2026-07 validation. No store operation was executed.

No repository tests, Full, database operation, runtime edit or live qualification
was performed. Existing schema fields were inspected, not newly implemented.
