# Q06 Receipt-Backed Owner Discovery And Input Port

Proposal at `bb449f1`; requires independent review before implementation. This is
an input/discovery slice only, with no generated action attachment or native edit.
It builds on the separately frozen standalone owner/intent contract.

## Reuse Exact Existing Receipt Provenance

Every native-setting hypothesis must name one customer-supplied scenario containing
exactly one allocation to that account/owner. Its ordinary TargetSelector already
locates the owned catalog receipt through CatalogReceiptSelectionRow. Resolve all
existing selectors and original-session/source/window/expiry checks first, using
existing resolve_input_catalogs/_load and final bind_input_receipts gates.

Resolve the owner hypothesis only inside that same loaded catalog. Do not create
an owner-only input, accept a client-chosen receipt ID, search historical receipts,
or add a new table. The scenario's allocation guarantees an ordinary selected
entity and selected_count >= 1. InputCatalogReceiptRow already retains the entire
original typed inventory/metadata, even when only one member is allocated. The
resolved intent digest is included in the immutable input digest linked to that
receipt. Reconstruct its original full owner witness from that retained payload
and compare both observation and facts digests on every retained validation path.
Missing proof never degrades into a primitive-only intent.

## Discovery Endpoint

Add a distinct read-only POST `/planning/google-budget-owners`, rather than change
TargetCatalogV2 serialization or the existing catalog endpoint's default response.
Request: strict account_id, catalog_composite_digest and ReportingWindow. Customer
must first obtain the ordinary target catalog through the existing owned API.

Resolve current authority/paid/privacy/source fences and query the one original
receipt using workspace, actor, original session, account and composite digest,
whose uniqueness is already enforced. Call the existing _load path with the exact
source and requested window; additionally compare all window instants in UTC.
Recheck current original session, source and unchanged expiry after the bounded
pure work. Do not obtain new provider evidence or extend receipt lifetime. Return
no session/authentication commitment fields.

For each eligible shared owner, return account_id, opaque owner_selection_id,
expected_observation_digest, expected_owner_facts_digest, representative and full
affected campaign references, current_amount_micros, currency, daily/micros literals,
original observation interval/expiry, and fixed unqualified-economic/review-only
labels. Maximum20 eligible entries; overflow rejects without truncation. Unavailable
coverage/profile returns bounded fixed reason codes plus an explicit refresh and
review recovery message, not a claim that the account has no shared budgets.
Malformed evidence aborts rather than being relabeled ordinary unavailability.

The selection uses domain `inlet.google-budget-owner-selection.v1` with the exact
workspace/account/connection/source revision and binding/privacy, actor/session/
authenticated time, original composite digest, full owner-witness digest, owner key,
and reporting-window UTC instants. This value is an opaque lookup commitment, not
spending authority. Its inputs are rebuilt server-side; no private session values
are serialized in the response or logged.

## Input Admission And Original Proof Binding

Add omitted-by-default google_daily_budget_intents to CustomerInputs and its resolved
counterpart to PlanInputRevision only after this port's review. None preserves all
old Python/JSON bytes; reject duplicate full-account/owner pairs and bounded overflow.
Multiple independently owned budgets in one account remain representable.
Capability is exact private V5. Older configured policies reject the new field
rather than silently ignore it. Explicit empty remains distinct from absent.

For each request, find the named supplied scenario and its candidate allocations
for the selected account, from that same resolved catalog. Compute candidate opaque
selection commitments with each candidate owner and the request's expected original
observation digest. Require exactly one match, then derive its full witness and
verify the actual observation/facts digests, representative, amount, currency and
source. The candidate comparison is only lookup; the caller's digest is never
trusted as evidence. No cross-receipt search or fabricated representative is used.

The resolved intent stores the reviewed primitive fields plus server-resolved owner,
representative/current amount and source binding. Its original witness remains in
the linked immutable raw receipt and is recomputed to validate these fields. Extend
receipt/input retained validation to require all new intents have this exact link.
Current generation retains the existing original-session/unexpired-receipt contract;
it does not introduce a later fresh acquisition or weaken full-catalog rechecks.
Historical export validates original proof without current session/TTL eligibility.

Enforce all these rules on create/edit and retained reconstruction:
- One intent per full account/owner across the whole input, even if amounts agree.
- The named alternative contains exactly one owner allocation; it remains independently
  reconciled to the same confirmed total ceiling. Never sum alternative scenarios.
- Requested amount is a strict nonnegative integer, not greater than the observed
  current amount. Exact account/confirmed-goal currency and daily/micros profile.
- Zero total ceiling rejects a positive request. Zero requests remain hypotheses,
  with provider validity unqualified, never an Apply or pause instruction.
- Every affected campaign remains explicit. Any excluded affected member or its
  observed child blocks the hypothesis; parent identity is advertiser/native scoped.
- No global freeform constraint may be silently declared compatible; defer admission
  when its compatibility is not implemented. Fixed allocations still bind unchanged.
- Existing ordinary scenario rules prevent duplicate owner allocations. A child of
  an affected campaign cannot add a second allocation to that same native pool within
  the named scenario; reject that new intent rather than reinterpret legacy inputs.
  Join children through full advertiser/native parent identity in the entire catalog,
  including represented owner campaign rows; a Google child budget_owner_key of
  None is not evidence of an independent pool.

Exact existing create/edit receipt replay precedes new lookup. Changed request-key
reuse, source/goal/privacy/session changes, expiry or revision/version CAS failures
reject atomically with no partial input graph or financial/execution effect.

## No Output Activation In This Slice

New inputs may be stored only after the configured V5 service explicitly supports
retaining and exposing them as customer hypotheses; generation must fail closed
while the later review-action/document consumer is unavailable. A shared fail-closed
guard must reject every non-null new intent field, including an explicit empty tuple,
at genuine generation preparation, direct pure composition and PlanVersion document
admission. None alone uses the unchanged legacy path. A service-only gate is
insufficient. Do not generate a plan which silently drops stored hypotheses. Existing inputs with
no new field and Q08 empty-account preparation keep their current path unchanged.

Before enabling generation, independently freeze the exact review attachment,
source-fence argument to document validation, one-action-per-owner invariant,
original-input/current-generation witness joins and final actual-catalog comparison.
Positive daily amounts remain economically unqualified. No prerequisite, retained
receipt or unchanged overall input ceiling certifies their period spending impact.

## Required Bounded Evidence

Pure byte-compatibility and duplicate/excluded/child/zero/currency/constraint tests;
actual SQLite/PostgreSQL discovery and create/edit original-session/CAS/replay,
expired/foreign/reconnected/mixed-receipt refusal, original proof tampering and missing
link, retained export and erasure; legacy owner allocation and Q08 regressions.
No browser enablement or extra browser rerun until a reviewed UI/output consumer
exists. No provider, model, spending, publishing or deployment operation is introduced.
