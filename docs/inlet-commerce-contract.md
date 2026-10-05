# B05 Commerce Measurement Contract

Approved 2026-10-05; implementation builds on PR64 head f1793d9. Shopify alone owns
canonical merchandise sales. Customer-data sources may link verified Shopify order
IDs, never contribute duplicate revenue or merge people by guessed identity.

Identity is workspace + verified stable Shopify shop ID + order/customer ID,
HMAC-pseudonymized with the existing managed identifier key. Canonical identity
survives OAuth reconnect and domain changes. Registry connections record provenance.
No raw order/customer IDs, emails, names or payment data are stored in this layer.

`shopify_merchandise_net_sales_v1` sums PRODUCT sales agreement amounts after
discounts minus their tax amounts, once per stable sale ID. Order/order-edit entries
use `happenedAt`; refund entries require `RefundAgreement.refund.processedAt`.
Return agreements can reverse sales before refund processing, so return/exchange
workflows not reconciled by this adapter mark the total unavailable. They never
become an early deduction or a second refund. Shipping, duties, fees, tips and gift
card issuance are excluded. Unknown/unallocatable adjustment lines make the order
unreconciled, never guessed into merchandise. Existing `net_collected` is unchanged.

Reports explicitly bind currency, IANA timezone, half-open window, calendar-month
versus cumulative basis, definition version, source watermark, revision and as-of.
A complete empty interval is zero; unavailable/partial/stale data is not zero.
Known distinct customers and orders are separate; missing customer IDs stay unknown.
B06 must persist these fields in its editable confirmed goal; B05 creates no goal UI.

Minimal canonical order/event facts, daily revisions and measurement snapshots
last 13 calendar months. Raw legacy order detail still lasts 59 days. Snapshots
retain their as-of assessment while corrections produce revisions. Privacy erasure
overrides historical snapshots and removes linked financial/identity facts. Minimal
suppression hashes remain until workspace closure to prevent resurrection across
reconnects; they contain no financial or customer attributes.

The optional measurement importer requires verified read_all_orders access to
observe late refunds on old orders. The feature defaults off; current integrations
retain their existing scope/report. No provider grants are provisioned. The importer
paginates sales agreements independently; incomplete/unsupported data blocks a
complete measurement. Live source reconciliation and access approval are release gates.

## Implemented Interfaces And Release Gates

Customer routes under `/api/customer/v1/workspaces/{id}/commerce` list store status,
preview an explicit `MeasurementWindow`, create a snapshot, and retrieve a scoped
snapshot. Snapshot writes require owner/admin/analyst membership and the existing
session/CSRF/origin checks. Viewers can preview; revoked membership is checked on
every request. CRM crosswalk creation is an internal adapter interface only; B12
must verify its source's Shopify order identifier before calling it. No CRM adapter
or fuzzy identity reconciliation is claimed complete by B05.

`AD_ANALYZER_SHOPIFY_MEASUREMENT_ENABLED=false` preserves existing OAuth scope and
59-day reporting. Enabling the collector requires reauthorization with verified
`read_orders`, `read_products`, `read_all_orders`, and `read_customers` access.
Existing native connections remain unbound to measurement after migration; no
historical completeness is fabricated. The collector reads orders by updated time,
including late refunds to old orders, freezes each paginated window, overlaps seven
days for corrections, and commits facts with its cursor/watermark. Each order is
bounded to 50 agreement/sales requests. Exceeding the bound or receiving malformed
or unsupported data leaves the measurement unavailable and retryable.

Ordinary corrections preserve earlier snapshots and add daily revisions. Privacy
requests delete the affected canonical facts, source links, daily history and
snapshots. Suppression prevents erased orders/customers returning after replay or
reconnect. A store with suppression keys reports `privacy_suppressed_source` and
cannot claim a complete total from its remaining facts. This conservative behavior
also applies to later windows because suppressed customers may have later orders.
UI/B06 must show this limitation rather than treating the observed subtotal as a
complete goal result. Disconnect purges measurement facts; authenticated later
erasure events still record suppression against the retained store identity.

All three GraphQL queries passed Shopify's schema validator (revision 4). The
standalone documentation/version helper was unavailable in this executor; the
connector validator does not prove compatibility with the application's pinned
2026-07 version on a real installation. Required release checks remain approved
history/customer access, pinned-version execution in an authorized test shop, and
reconciliation of sale/return/edit/adjustment fixtures against that shop's reports.
No live shop, advertising account, credentials, IAM, deployment or spending changed.

Verified merchant-domain aliases are retained with the canonical store identity.
This lets delayed authenticated privacy events reach the current connection after
a domain-changing reconnect, including legacy 59-day facts. Aliases contain merchant
domains and a store reference, no customer attributes. Old uninstall events still
respect the latest authorization timestamp. Migration 0024 backfills current domains;
future verified reconnects preserve both previous and new domains.

The legacy 59-day report carries the same canonical HMAC order identity when bound
to measurement. Customer-level export/erasure therefore also reaches matching legacy
facts even when the event's explicit order list is empty. Migration 0024 backfills
known links without retaining raw identifiers. Once a store has suppression keys,
the legacy importer returns `shopify_privacy_reconciliation_required` before reading
orders: its older query has no customer identity and cannot safely reconcile that
erasure independently. Remaining legacy data is marked incomplete. OAuth reconnect
retains known privacy identity even with measurement disabled and baseline scopes;
turning off the feature cannot authorize replay of erased facts.

### Review Repairs: Refund Timing And Legacy Privacy

Refund processing date is validated against Shopify's
[Refund schema](https://shopify.dev/docs/api/admin-graphql/2026-07/objects/Refund)
and [return lifecycle](https://shopify.dev/docs/apps/build/orders-fulfillment/returns-apps/build-return-management).
The metric is merchandise sales, not a cash settlement report. Unsupported types,
missing processing dates or unallocated adjustments cannot produce a complete goal
result. Pagination preserves the agreement type, reason and refund timestamp.

Migration 0025 preserves available pre-measurement tombstones as workspace/domain
HMAC erasure guards. New privacy events preserve order/customer guards even before
measurement is enabled; disconnect and reconnect cannot remove them. Verified shop
identity is retained on baseline-scope OAuth too. Old domains whose stable identity
cannot be established remain unresolved rather than being assigned by guesswork.
Previously expired tombstones or customer identities never retained by old code
cannot be reconstructed; existing open requests with unclassified retained facts
are marked pending by migration and require verified identity reconciliation.

A customer-level request with an empty order list cannot complete while retained
legacy/canonical facts have unknown customer identity. Export and delivery return
409 while pending. Canonical backfill identifies matching facts before applying
suppression, removes only confirmed matches and links customer exports. Unrelated
facts are retained; inability to classify remains visible as pending reconciliation.
The legacy query cannot perform that reconciliation and pauses after erasure.

Scheduler eligibility (active ownership, workspace controls, freshness and backoff)
is applied before the ten-store batch limit. Paused/revoked stores do not starve
eligible stores or receive fabricated attempt/freshness updates.
