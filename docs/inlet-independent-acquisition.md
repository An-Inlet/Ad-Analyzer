# Bounded Independent Shopify Acquisition

The server-only `IndependentAcquirer.acquire(ScanRequest)` performs actual fixed
GraphQL HTTP parsing through an injected transport. No customer API, scheduler,
default runtime, persistence, credentials or operational-maturity registration is
added. The first interface was frozen at `084c119` before the adapter implementation.

The collector starts from an empty cursor, enumerates accessible order history in
ID order without a time lower bound, traverses agreement/sale connections completely,
and uses the existing merchandise normalizer. Thus a recent refund on an ancient
order contributes on `Refund.processedAt`, while the ancient original sale does not
enter the requested daily totals. No incremental ledger values are inputs.

Actual `currentAppInstallation.accessScopes` plus shop identity/currency/time zone
are checked before enumeration and again at completion. Local scope configuration
is insufficient. Every nested response includes the order ID and verifies its
parent; continued sale pages verify agreement identity. A second order read must
match the initial order/customer/test/update identity. Limits, unsupported metric
semantics, missing permissions, errors and invalid pagination return fixed errors,
never partial complete days. Returned objects contain only request lineage and
in-window aggregates, not external order/customer IDs or out-of-window facts.

The injected `ScanAuthority` is mandatory and called before/after requests and
stream chunks, and before returning a completion. A production authority adapter
must freshly verify the original session/owner, workspace active state, native
connection identity/version, store generation/privacy epoch, goal revision and
workspace export privacy revision against the request digest. `privacy_resolved`
must mean no unresolved or applicable suppression state across the full enumeration;
a cached true value is not a production implementation. This package tests changing
server authority but does not implement or claim a DB-backed adapter. No DB locks
are held by the HTTP collector. Current retention and closed local-day boundaries
are rechecked with fresh clocks, and a monotonic deadline bounds acquisition.

Default engineering limits: 2,000 orders, 10,000 total requests, 50 nested requests
per order, 2 MiB per response, 128 MiB total response bytes, 15-second I/O timeout
bounded by a 30-minute acquisition deadline. Response compression and redirects
are rejected. Throttling returns a bounded retry hint and never loops/sleeps/retries.
These are capacity bounds, not Shopify guarantees or maturity policy thresholds.

A complete acquisition always reports correction_state=`unresolved`, snapshot
consistency/finality unavailable and maturity unqualified. Equal totals or terminal
pagination do not establish a globally consistent snapshot. There is deliberately
no conversion to `IndependentReconciliationEvidence` and no `fresh_through` invented
from acquisition completion. Both production policy/producer registries stay None.

The Shopify Admin skill's local scripts were unavailable. Connected documentation
search and schema validation were used instead: all five generated/adapted GraphQL
operations validated. That validator does not expose a version selector; it is not
claimed as pinned-2026-07 validation. Fields/semantics were also inspected in the
pinned official docs listed in the proposal. No operation was executed on a store.

## Owned Publication Contract — Implemented Offline

Feedback storage owner confirmed existing publication identities/FKs can support
an explicit v2 manifest. The owned adapter and strict parser now implement these rules:

- Discriminated parser: current v1 stays incremental; new
  `inlet.commerce-independent-publication.v2` contains the exact typed
  `ScanCompletion` in `acquisition`, plus scalar workspace/store/generation/privacy,
  source/publication revisions, publication timestamp, definition/digest, source,
  unit, grain and currency/time-zone fields matching the owned row.
- Acquisition request/window/digest and the same owned scope must match scalar
  metadata; days must equal the requested local window. v2 uses acquisition start/
  end for row source_window_start/end as an acquisition interval only, explicitly
  `source_range_semantics=full_accessible_order_history`, no factual source
  watermark/fresh-through. Do not reuse v1's updated_at watermark interpretation.
- Completion commitment is domain-separated:
  digest of `["inlet.commerce-independent-completion.v2", acquisition.model_dump(mode="json")]`.
  Manifest commitment remains the canonical entire typed manifest digest. No
  relabeling, rewriting or rehashing existing v1 documents.
- Existing `(workspace_id, publication_id)` composite dependencies still reference
  the same publication row. Feedback resolves exact manifest/completion digests;
  publication/store privacy deletion cascades through every feedback dependency.
- The independent evidence loader accepts only v2, never v1 imports. Since this
  completion's correction state is unresolved, loading it cannot produce an
  eligible operational assessment. Maturity registries remain disabled.
- Existing v1 observations/reconciliations must explicitly reject unsupported v2,
  and their latest-publication selection must filter supported versions so adding
  v2 does not break currently working v1 customer measurements.
- Strict export must parse the versioned union and serialize allowlisted aggregate
  fields only; lifecycle ownership and source-wide invalidation remain unchanged.
- Source publication requires a DB-backed authority adapter and a final atomic
  workspace-first scope/privacy/session/retention recheck. No migration is reserved.

Any future settled-as-of mapping needs reviewed assurance, not a type cast.


`OwnedAcquisition` now captures the original session identity, reauthorizes in
short independent transactions before/after HTTP, and atomically publishes after
fresh source/privacy/retention checks. No locks span provider HTTP. Existing opaque
shop identity is proved by its keyed digest; no raw shop identity is persisted.
The v2 manifest union is strict in explicit reads, archive exports and feedback
dependencies. Unresolved v2 acquisitions cannot satisfy maturity supporting
completion requirements. Deleting any retained v2 dependency cascades its owned
assessment. Latest v1 readers and candidate fences select supported versions before
limiting results; adding v2 alone does not displace working v1 evidence.

There is no customer route, worker registration, credential refresh, installed
maturity policy or production producer. A future HTTP caller must enforce origin
and CSRF before invoking the server-only adapter. Full-history capacity, granted
historical access, privacy suppression resolution and intended-environment operation
remain qualification limits; independent acquisition does not establish finality.
