# Google Historical Creation Source And Current API Regression Split

Proposal from `cf00c3e`, based on actual current test bodies and routes. Recommend
one shared closed source seam with two separately qualified consumer packages:
completion12 first, total-envelope20 second. No implementation until review.

## Classification And Exact Coverage

1. `test_google_execution_completion::test_real_api_completion_historical_authority_and_unknown_hold`
   has six modes × two databases. Its receipt GET, closing/revoked/expired/viewer/
   late-expired privacy checks, completion/unavailable projection and hold checks
   are current behavior. Its unknown branch also advances an old execution run and
   expects historical successful idempotency. Preserve the *entire original twelve*
   untouched at the fixed PIN in one new explicit historical batch, with AST-equal
   local renamed function and map to twelve new current counterparts. Current
   unknown advance is **409 AdvertisingWritesDisabled**, not404: the route exists
   with an early mutation dependency (`customer_execution.py:537`). No original
   idempotency assertion is silently converted to a different product claim.
2. `test_google_total_envelope_api::test_actual_created_total_envelope_read` has
   ten modes × two databases. Everything after `created(...)` is current read-only
   semantics, except its explicit current unknown-receipt adversary. Keep this
   original test current, changing only source/engine/normal-login plumbing and
   historical server-counter assertion to explicit measured-source/no-current-
   mutation proof. Keep all observation/ownership/source-generation/session/CSRF/
   configuration/hold assertions and real current MockHTTP callback behavior.
   **No extra historical20 batch** merely because its source setup used old writes.

Existing historical seven/349 remains unchanged except completion12 becoming an
explicit eighth/361 only after verified disjoint collection/provenance/AST mapping.
Do not rename/archive total-envelope current tests or rerun existing349.

## Fixed Original Producer

New `tests/google_created_retained_fixture.py` plus fixed
`tests/fixtures/retired_execution/google_created_seed_driver.py`, literal verified
2155 app/tests/scripts trees. Closed mode enum only:

- `daily_completed`: invoke untouched pinned `first_attempt(..., timeout=False)`.
- `daily_unknown`: invoke that same helper with `timeout=True` (actual MockHTTP
  timeout after original dispatch); one original provider mutation, held exposure,
  one attempt, unavailable original completion.
- `total_created`: invoke untouched pinned `created(...)`; two genuine original
  advances create budget and campaign, two attempts/completions and held exposure.

These helpers already return their actual original Google Server. Read measured
`server.posts`, exact stored graph and bounded resource-name strings from it; do
not manufacture counter values or recreate provider responses. Require measured
posts1/1/2 respectively, transport ownership where returned, and only the expected
original artifacts. No child current reads, privacy mutation, customer closure,
new campaigns beyond the fixed historical fixture, extra arbitrary mode/callback,
caller PIN, or authenticated/live provider. Close original test clients/Sessions
before parent use. The original helper's identity setup remains untouched inside
its fixed historical code; **never call it in the current parent**, where it would
rewrite subject/session source rows and attempt forbidden preparation.

Use the established strict owned-storage seam: parent current DDL, fresh exclusive
absolute regular nonsymlink SQLite file/all ancestors/plain no-query no-credential
URL before factory; child repeats checks. Or exact current engine/disposable
loopback no-query PostgreSQL URL plus actual fresh inlet_test_UUID schema. All
non-Alembic tables empty before child; schema fingerprint unchanged after. No
DDL/stamp/reset or bootstrap exception in the child. Add one exact SourceLifetime
profile `google_created` (helper/driver/source leaf/archive), no utility changes.
Original logs/media/manifest files and scalar output stay outside extraction.

## Frozen Proposed Data Boundary

Strict JSON <=8192 bytes, no authority, Session, callable, transport/server object,
credentials, entire provider rows, or customer session digest crosses:

- `mode`: exact closed enum; `workspace_id`, `account_id`, `mandate_revision`:
  positive strict integers.
- `actor_id`, `run_id`, `review_id`, `mandate_id`, `consent_id`, `ledger_id`,
  `reservation_id`, `native_connection_id`: exact32hex.
- `policy_digest`, `review_digest`, `plan_digest`: exact64hex.
- `reservation_amount_micros`: strict positive integer, measured from actual hold.
- `provider_posts`: strict integer measured actual1/1/2.
- `attempts`: one or two entries in frozen budget/campaign order. Each exact-key
  entry contains step_id (budget/campaign literal), attempt_id/fence32hex,
  request_digest64hex, response_digest64hex, latest_receipt_id32hex,
  latest_receipt_digest64hex, latest_receipt_sequence positive integer,
  completion_digest64hex or null only daily_unknown, resource_name bounded128
  or null only daily_unknown.

Parent uses *current* owned joins/contracts to verify every ID/digest/fence,
run/review/mandate/consent/ledger/hold ownership, exact request/response/receipt and
completion linkage. It recomputes commitments rather than trusting child flags.
The total mode's campaign resource/budget dependency must match actual original
receipt and campaign request resource map; its original total30 and paused campaign
operation remain actual stored configuration, never inferred financial upper bound.
Only the resource names needed by the unchanged diagnostic wire cross, bound to
those receipts. If actual pinned data violates the proposed counts/null contract,
retain the probe and freeze the exact mismatch before expanding it.

## Current Session And Routes

Rebind normal current replica fixture to the yielded actual engine. Mount real
customer_execution and, for total, customer_account_diagnostics routers. Perform
actual login for `configured-google:<fresh-test-token>`, requiring returned actor
matches source actor, new session digest not in the source session set, and current
user issuer/subject unchanged. Never assign issuer/subject/authenticated_at or
reuse a child session token. Existing test-selected revocation/expiry/viewer/closing
adversaries run *after* that normal login, unchanged.

Receipt GET has no execution-runtime dependency. Do not register a financial
source or executor to make history readable. Unknown advance should hit the actual
current planning guard409 before runtime/provider use; a sentinel factory can
prove no external composition, without replacing the real mutation guard.

For total observations configure only the existing explicit offline OAuth client/
encryption fixture needed to decrypt the genuine original grant, native-diagnostic
enabled setting, original local transport callback and current customer/session
provider. Do not construct an execution runtime. The original wire's OAuth/native
read handling and late-expiry transport-close callback stay actual current code.
No provider session or global-time rewrites; retain existing scoped API test clock.

## Current Graph And Consumer Obligations

Snapshot complete provider_* plus original completion graph before current reads.
Completion modes allow **no financial/provider delta**, including after unknown
advance409: original attempt/receipt/completion/hold IDs and values stay exact.
Session/customer role/workspace test adversaries are outside this financial graph
and their original current HTTP assertions remain.

Total modes retain original ten triggers: None, lower, disabled, session,
generation, csrf, foreign, late_expiry, shared, unknown. All statuses, no-read
short-circuit assertions, exact total values, configuration drift/unavailable,
null financial upper bound, no spending authority and observation-expiry ordering
stay current. Current native reads must emit no mutation HTTP; validate recognized
read requests at the actual MockHTTP boundary. Historical measured posts remain2,
not a live mutable server counter fabricated in the parent.

The total unknown branch intentionally calls real current coordinator.record_receipt
with its original unknown(request, dispatched_at). Preserve that action; it is
not an API advertising advance. Verify exactly one same-original-attempt receipt
append, next sequence/previous pointer and exact unknown receipt/projection, plus
only the coordinator's actual known run/step state changes. Preserve every other
financial row/hold/completion. Do not infer allowed fields from a broad after-the-
fact table exclusion. Snapshot immediately after this verified intentional
adversary and prove the actual envelope POST produces **no further graph change**.
If capture invalidation reveals another current semantic delta, stop and propose
that exact delta before allowing it. Original callback-driven native generation
changes remain explicitly scoped source adversaries, not financial effects.

## Staging And Qualification

Prefer completion12 first because it needs no new native-observation collector
wiring or receipt-append allowance. Qualify both SQLite success/unknown probes,
then all current12 +86 unchanged default boundaries, strict source/data/path
guards and the new pinned historical12 separately. Update strict partition count,
manifest provenance and original AST mapping to eight/361; no349 rerun.

Then qualify total20 from the same reviewed source seam: initial None/unknown bothDB,
all20 current test instances plus bounded existing source/reader/default boundaries,
exact assertion preservation and native no-mutation proof. No historical total batch.
For each package run whole Ruff, bare mypy in own /tmp cache and diff separately;
retain exact original failure identities/probes/logs/XML. No Full, W1 database,
hosted CI, remote push or live provider qualification.
