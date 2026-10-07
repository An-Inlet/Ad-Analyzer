# Shopify Independent Full-Window Acquisition Proposal

Design only, 2026-10-06. Inspected root c0e10dce4cb85191d324142d019d069ca90f6c4f.
No implementation, migration, provider request, credential access, live registration,
or operational maturity policy is introduced by this document.

## Finding And Recommended First Package

Implement a fresh, bounded enumeration of accessible Shopify order history and its
complete agreement/sale connections, independently accumulated from zero. Filter
normalized merchandise events by their actual metric timestamp into the requested
local-day window. Do not reuse CommerceEntry totals or the incremental cursor as
inputs. Exhaustion must be proved; capacity/error/permission/privacy uncertainty
must return an incomplete acquisition, never zero-filled complete days.

This is technically implementable for stores whose entire accessible order history
fits the explicit acquisition limits. It is not a universal historical completeness
promise. A bounded collector cannot promise to finish every size of store, and
Shopify does not document a transactional snapshot or authoritative finality for
these reads. Keep the production maturity policy/producer registry disabled until
the concrete acquisition assurance and retained-artifact integration are reviewed.
The first code package can exercise actual HTTP request/response parsing with
injected synthetic transport without live registration.

## Existing Contract And Exact Semantic Boundary

- app/shopify/security.py pins API_VERSION to 2026-07.
- CommerceSyncService.page uses updated_at ranges and a seven-day overlap after
  initial acquisition. Terminal CommerceMeasurementPublication v1 carries
  source_range_semantics=updated_at_inclusive. Repeated publications do not prove
  independent re-enumeration.
- ReconciliationObservations explicitly reports terminal_updated_at_import,
  independent_reconciliation=unqualified, maturity=unqualified.
- IndependentReconciliationEvidence requires environment, exact MaturityScope,
  start/end, at most 16 observations, completion digests, fresh_through,
  correction_state and complete/missing/suppressed daily values/counts.
- Scope contains workspace/store/generation/privacy epoch, goal/revision/digest,
  metric digest, currency and time zone. It is server constructed, not HTTP proof.
- owned_v3 evaluates outside locks then revalidates owned lineage. Its operational
  association also requires authoritative action timing; a commerce scan cannot
  supply that advertising evidence.
- policy_for and producer_for return None. Preserve both defaults. Operational
  maturity thresholds, finality and causal attribution are not decided here.

Use the existing normalized_entries metric exactly: supported OrderAgreement and
OrderEditAgreement use happenedAt; RefundAgreement uses refund.processedAt.
PRODUCT net amounts exclude tax; shipping/duty/fees/tips/gift cards remain excluded.
Unsupported agreement/action semantics mark coverage unresolved. Do not replace
these with payment totals or order.processedAt, and do not reinterpret returns as
processed refunds. Cross-currency data fails the measurement basis check.

## Official API Evidence And External Limits

1. Orders default to only the last 60 days. Historical access requires approved
   read_all_orders access alongside read_orders; a local settings string is not
   evidence the token was granted that access. Existing measurement requirements
   additionally include read_products/read_customers; do not silently drop them.
   [Order](https://shopify.dev/docs/api/admin-graphql/2026-07/objects/Order),
   [Scopes](https://shopify.dev/docs/api/usage/access-scopes).
2. orders.processed_at filters the ORDER processedAt. The documented orders search
   filters do not supply a refund-processed-date enumeration. updated_at describes
   an order's latest update, not an immutable refund journal or historical snapshot.
   [Orders](https://shopify.dev/docs/api/admin-graphql/2026-07/queries/orders).
3. Refund.processedAt is the refund-processing timestamp; Refund.updatedAt is a
   different field. The standalone refund query requires an already-known ID.
   [Refund](https://shopify.dev/docs/api/admin-graphql/2026-07/objects/Refund).
4. API pagination caps at 25,000 objects; count queries share that cap. Input arrays
   cap at 250. Costs/throttling are app/store/plan-dependent and may be reduced;
   respect actual returned cost metadata and throttling, not a guessed fixed QPS.
   [API Limits](https://shopify.dev/docs/api/usage/limits).
5. Bulk query operations support up to five concurrent operations per app/shop
   in 2026-01 onward and must finish within ten days. They are a separate async
   lifecycle, not a free assertion of an atomic snapshot. Bulk URLs, partial
   outputs, cancellation, access, private download bounds and privacy cleanup
   would need explicit implementation. They are not the first synchronous package.
   [Bulk Queries](https://shopify.dev/docs/apps/build/apis/graphql-admin/bulk-operations/queries).

Therefore a refund processed yesterday may belong to an order created years ago.
A 13-month ORDER creation cutoff is unsound even for a one-day refund window.
All accessible historical orders can be enumerated with approved history access,
subject to platform limits and resource availability. Erased/deleted/inaccessible
orders cannot be recovered or declared absent merely because enumeration returns
nothing. There is no documented maximum order age after which a refund cannot
contribute; do not invent one.

## Proposed Shared Acquisition Port

New server-only module app/commerce/independent_contracts.py; exact names proposed:

- IndependentScanRequest: version; acquisition UUID; exact MaturityScope;
  local start/end; current server capture time; API/metric versions; selected
  source connection identity/version; privacy/export revision; limits version.
  Bound window to 400 days AND the current existing 13-calendar-month retention
  floor. No customer-submitted query, scopes, credentials, proof, clock or cursor.
- IndependentScanPage: request digest; monotonically increasing page sequence;
  owned source binding; encrypted continuation handled by adapter; minimal
  normalized entries; completeness diagnostics; measured acquisition timestamps.
- IndependentScanCompletion: unique scan ID and digest; request digest; actual
  scan start/end; exact local window; source/account proof digest; fresh scope;
  enumerated order/agreement/sale counts; terminal cursor proof; daily aggregate
  values/counts; suppression/unsupported/mutation flags; assurance version.
- IndependentScanFailure: fixed reason code; retryable flag; bounded retry-after;
  no raw provider message, order IDs, cursor or token.
- acquire(request, server_source, transport, clock, cancellation) returns a
  completion or typed failure. No DB session held during transport calls.
- publish_owned_completion(db, completion, original_authorizer, clock) rechecks
  source/shop binding, generation/privacy/export fences, goal/revision, active
  workspace and fresh retention time before one atomic publication. It never
  populates a completion from the incremental ledger.
- load_owned_independent_evidence(context, start, end) reads only retained, typed,
  same-scope independent completions. It is the eventual EvidenceProducer adapter;
  no network work during feedback loading and no arbitrary digest resolution.

## Enumeration, Bounds And Consistency

Suggested initial engineering limits (not Shopify guarantees or maturity policy):
50 orders/page, 2,000 total orders, 50 nested requests/order, 10,000 total requests,
2 MiB/response, 128 MiB total decoded response budget, 15-second request timeout,
30-minute total acquisition lifetime, at most one in-flight scan per owned store.
Every cap yields acquisition_limit_exceeded, not a partial complete result.
The initial implementation can use smaller injected bounds in deterministic tests.
A durable resumable variant requires a reserved migration; no unbounded sleep loop.

Enumerate all orders with a stable supported ID sort from a fresh empty cursor,
without lower created/processed/updated date filtering and without exclusions for
closed/cancelled orders. Traverse every agreement and sale page, retaining only
in-window normalized facts. Enforce unique order/agreement/sale identities, strict
cursor advancement and cross-order agreement binding. Observe test-order exclusion
consistently. Verify each order's update identity before/after its nested reads;
changes cause restart/failure, not a mixed order. Independently repeat enumeration
from zero for a comparison observation; never continue the incremental checkpoint.

Global concurrent mutation and deleted history remain real limitations: equal
passes are observations, not transactional proof. Keep actual scan interval and
conservative acquisition-start freshness separately from publication time. Never
assign scan end as historical completeness merely because it is recent. Changes,
unknown deletion coverage, suppression or unresolved nested data must produce
correction_state=unresolved. Do not automatically set settled_as_of from HTTP200,
terminal cursor or matching totals. The reviewed mapping from acquisition evidence
to that existing field is a prerequisite for registering operational maturity.
An independent scan can be fully acquired while operational maturity is unavailable.

## Privacy, Closure And Retained Artifact Coordination

Outside-window historic order/customer IDs are transient selectors needed to locate
recent refunds; no old personal payload, address/email/name or sale history is
persisted. Normalize with existing workspace/store HMAC identity and suppression
logic before accumulation. Never resurrect suppressed data. If privacy coverage
cannot be proved, conservatively suppress/fail the scan. A source erasure/rebind,
disconnect, retention boundary crossing or workspace closure invalidates in-flight
work. Read current clocks after all blocking I/O/locks, not only at task entry.
Privacy processing still works on closing workspaces; new scans/publications do not.

Customer_signin's approved 0064 feedback package currently requires every supporting
completion to resolve through an owned CommerceMeasurementPublication FK. Existing
v1 manifests cannot honestly represent this new scan. Recommended storage contract:
versioned independent manifest within the same publication identity/table, with a
strict discriminated v1/v2 parser and source_kind/assurance specific validation.
V1 remains immutable incremental history. V2 contains only the typed aggregate
completion, same direct store ownership/generation/privacy and existing deletion
cascade. A separate typed scan checkpoint table, if used, is operational staging,
not retained assessment evidence. Never forge a v1 updated_at completion digest.

This recommendation needs the feedback/export owner to approve the v2 publication
variant before implementation. Alternative is a new independent-artifact table and
explicit second composite dependency FK with exactly-one-kind checks; never use a
free-form source_type/source_id pair with no FK. No schema number is allocated here.
Either choice requires canonical lifecycle classification, strict typed export,
source-wide atomic invalidation, feedback/slot/candidate cascading and 13-month
retention. No private artifact may survive merely to preserve a maturity claim.

## Focused Acceptance Cases

- Refund in requested day from an order older than 13 months is counted on refund
  processedAt; original old sale is not retained or counted.
- Missing actual historical scope never becomes a zero-sales day.
- Fresh scan starts empty despite a populated or deliberately wrong incremental
  ledger; independent digest identifies acquisition, not only matching totals.
- All nested pages required; limits, repeated cursors, mismatched agreement parent,
  deleted/null order, unsupported return semantics and currency errors fail closed.
- Changed order during nested read, privacy erase/rebind/close during I/O, expired
  session/owner and crossed retention floor cannot publish numeric evidence.
- DST local boundaries, genuine zero, negative refund day and excluded taxes/fees.
- Publication version/FK compatibility; deletion of ANY supporting completion
  erases derived feedback; strict export does not expose transient identities.
- Existing incremental observations remain unqualified under every policy.

## Research/Validation Status

Read the Shopify Admin skill and official pinned/current docs. Its bundled shell
search/validation helpers were not present on this executor (bounded filesystem
search); no GraphQL code is generated or represented as schema-validated here.
No merchant API calls, tests, code edits, model registration or schema writes ran.
This proposal identifies implementable acquisition separately from unresolved
provider snapshot assurance and explicitly unconfigured operational maturity policy.
