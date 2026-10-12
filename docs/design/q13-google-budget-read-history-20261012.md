# Q13 Injected Google Budget Read And History Contract

Continues ab3e5f44. This contract covers only the retained V6 Google daily shared-budget
hypothesis. Defaults, release holds and INLET-REL-20261012-01 remain unchanged.

## Acquisition Boundary

Pin Google Ads API v22 and an exact extraction profile. Inject an explicit search-only
port; provide no network default or production factory. Its ticket binds a fresh server
nonce, original version/action, the complete owned ExecutionAccount, current privacy
revision, original reporting window and a server interval of at most five minutes.
The reporting window binds the catalog schema; these queries collect settings, not metrics.
The service resolves ownership locally before issuing a ticket and rechecks it after IO.
The reader never accepts a customer-provided URL, query, version, account or evidence.

Use three fixed GAQL queries, with no page-size override: customer resource/currency/
time-zone/status/manager; all ENABLED/PAUSED/REMOVED campaigns' resource/budget/status;
all ENABLED/REMOVED budgets' resource/amount/total/sharing/count/period/status/type.
Retain only bounded selected response objects and request/response cursor linkage.
Reject duplicate JSON keys, unknown response/row fields, invalid JSON scalars, over-bound
pages, duplicate resource identities, foreign customer prefixes and broken joins.
Require explicit amount/count/sharing/currency/status fields. Do not default missing
zero/false. DAILY total_amount must be absent; a present value (including null or zero)
is not silently discarded. Accept int64 as canonical unsigned decimal strings only.
One million micros is one account currency unit; never round or convert currency.

Read every page, preserving identical query/version/account, exact token progression,
no token loop, terminal cursor, monotonic request/receipt timestamps and complete query
order. Bound ten pages and 200 rows per query, with conservative refusal on overflow.
Use the union of campaign rows, including removed rows, to join budget resources.
Count nonremoved owner members and require exact reference_count. This is a conservative
consistency check, not a simultaneous snapshot. Recheck time before/after each injected
search and never extend the original ticket deadline.

Derive a fresh minimal catalog from these exact retained fields. Mark unqueried campaign
names/channel/bidding/date settings unavailable; never copy old values into fresh facts.
Revalidate proof and deterministic derivation before comparing. Preserve full selected
page bytes (no headers/tokens/credentials), extraction version, ticket, timestamps and
normalized catalog. Cursor strings are bounded provider pagination state and retained
under the same ownership/erasure policy, never logged. A fixture-backed injected port
qualifies structure/extraction only: the evidence explicitly says injected_fixture.
It must never be labeled authenticated/live-provider evidence.

Primary references: [v22 budget fields](https://developers.google.com/google-ads/api/reference/rpc/v22/CampaignBudget),
[v22 campaign link](https://developers.google.com/google-ads/api/reference/rpc/v22/Campaign),
[pagination](https://developers.google.com/google-ads/api/docs/reporting/paging), and
[ProtoJSON mapping](https://protobuf.dev/programming-guides/json/). No provider access.

## Append-Only Interpretation Before Persistence

Introduce exact discriminants inlet.google-budget-observation.v1 and
inlet.google-budget-invalidation.v1. They are distinct from ReadObservedStatus and
customer reports. Existing physical observation kind may store these only after
storage/API/history/browser/archive readers explicitly dispatch these schemas and
preserve legacy bytes/digests. Unknown schemas fail closed. This is the reader floor;
there is no mixed-version writer activation or production writer factory.

An observation retains comparison and read proof, exact binding, event ID, original
requesting actor (not an implementer), recorded time and fixture provenance. Its only
finding is matches_hypothesis or differs_from_hypothesis. Acquisition failure appends
nothing; it cannot create a false unavailable/zero observation.

An invalidation is a distinct server-authored integrity event, not a replacement read or
a customer report. It names the exact observation event ID, digest and sequence; binds
the same action/version and current server-resolved privacy/source generation, records
a bounded reason code, and never rewrites the observation. No public customer invalidation
route. It removes that observation from current reliance while preserving the original
historical result. A new read cannot reverse an invalidation; it creates a separate event.

## Service, Atomicity And Replay

Prepare inside a short owner/paid/session-scoped transaction: validate exact current
plan/input/action, resolve complete current account and privacy, check same-key receipt,
capture expected event sequence. Release all SQL transactions before injected reads.
Refresh the original identity outside locks after IO, then atomically recheck original
session, owner/paid role, plan/input/version, account/connection/source/privacy and deadline.
Append immutable event/proof and exact request receipt with a PlanRow sequence CAS in
one transaction. No partial proof/event/receipt/head survives conflict or failure.

Same actor/workspace/operation/key with identical intent returns the original result
without reacquisition after current authorization. Changed intent conflicts. Revoked
sessions/erasure override replay. Invalidation has its own operation and replay key,
requires an existing exact observation and expected sequence, and rejects an already
invalidated observation except exact receipt replay. Customer correction chains are
unchanged. Late reads after source/privacy/session change cannot commit.

History and export retain both variants and explicit fixture/not-implementation labels.
Erasure removes events, proofs and receipts atomically with existing planning data.
Tests cover actual injected service-to-history, replay/changed-key, revoked/foreign
access, source/expiry races, privacy erasure, CAS and rollback on SQLite then PostgreSQL.
Fixture qualification never closes live provenance, deployment, execution or release gates.

## Review Refinements

All observations and invalidations explicitly declare current_reliance not_assessed.
The comparison packet's clear integrity is historical admission context only. Neither
replay nor a partial/paginated history claims that evidence remains usable now; expiry
and later invalidations never rewrite the original result. No current-reliance view.

Initially admit only source_generation_changed invalidation. The server resolves the
currently owned, active account again and proves its complete source binding differs
from the recorded acquisition. Caller-supplied reason/source/privacy is not accepted.
Unavailable/deleted source resolution refuses; erasure deletes retained evidence instead.

Pin the exact query text plus profile digest. Limit aggregate proof to 384 KiB and the
entire event to the existing one-MiB canonical storage limit. Overflow refuses before
publication. Stable receipt intent includes version/action/document, profile digest,
expected sequence and, for invalidation, original observation ID/digest/sequence. It
excludes acquisition nonce, local clock readings and result bytes.

## Qualified Retained-Read Preparation Boundary

Retained-proof decoding can exceed a short authority fact window. Exact replay copies
all immutable receipt/event columns under current authorization, closes SQL, performs
all original strict decoding and result validation, then refreshes the original identity
and compares every copied column/byte under fresh authorization before returning.
Invalidation prepares its exact prior observation similarly and rechecks the complete
row in both later transactions. A receipt found during final publication unwinds all
SQL scopes and enters this same recovery path; authority errors are never retried.

Event history uses a dedicated prepared-read context with the existing READ_ROLES,
physical SQLite BEGIN, exact ordered page/limit/cursor and lookahead. Full strict page
construction occurs outside SQL, followed by fresh authorization and complete requery
comparison plus owned-plan existence. Budget receipt GETs similarly preserve actor scope
and compare the complete receipt/event pair. Unrelated read contexts and other receipt
operations are unchanged. Prepared results are invocation-private; no global cache,
trusted-data flag, skipped validation or larger authority deadline is introduced.

Revocation, erasure or row/page mismatch after decoding refuses before result delivery.
These readers make only historical statements; neither complete nor partial pages
establish current reliance. No general reliability or incident closure is implied.
