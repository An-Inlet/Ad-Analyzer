# Q12: Private V6 Customer Input Concurrency

Source-only inspection of root `ce25c17`, October 11, 2026. No implementation,
tests, provider calls or production changes performed for this proposal.

## Missing Join Versus Existing Coverage

Frozen Q12 in `docs/design/comprehensive-planning-quality-cases.md` requires two
edits against the same current revision/version, exact request replay, changed
key-payload conflict and obsolete/changed-action refusal without partial state or
advertising authority.

`tests/test_planning_document_repository.py:162` already races independent
PostgreSQL sessions through `repository.save_input`: same-key create is replayed;
different-key edits produce one saved revision and one CAS conflict. Its generation
race at line713 calls the actual service under a legacy Meta fixture, not customer
HTTP with the full private V6 owner graph. These are valuable existing tests and
should not be rerun merely to increase counts.

`tests/test_planning_documents_api.py:48` already exercises generic actual HTTP
create/generate/replay, manual decision, successor, comparison, obsolete decision
and history/export. It does not race actual V6 customer input requests carrying
resolved selected reporting, product/media and original shared-budget ownership.

Smallest missing join: two original-session authenticated HTTP edits to one genuine
V6 plan, with its complete retained owner graph intact, followed by exact replay,
changed-key-payload refusal and a generated successor's obsolete-decision check.
No additional shared-owner discovery scenarios, native money policy, Q09 analysis,
new schema or V7 are needed.

## Fixture And Ownership

New test-only module, provisionally `tests/test_owner_review_customer_cas.py`.
Reuse unchanged `tests.owner_review_runtime_fixture.configured_owner_review`:
its `ready_inputs` obtains real local customer upload, aggregate/selected capture,
catalog and owner-discovery receipts. It explicitly installs canonical private
V6 and leaves the default V3 untouched. Use its complete, nonempty owner option;
never replace it with `google_daily_budget_intents=[]` to simplify concurrency.
No fabricated proof, document, receipt or manual source-generation mutation.

Use two independent TestClient instances against the same configured ASGI app,
with copies of the original authenticated browser cookies and matching CSRF
headers. Do not concurrently share a TestClient or mint a new login/session to
make the race pass. API database dependencies already yield a distinct Session
per request (`tests/test_customer_identity.py:92–109`). Test-only identity/provider
and MockTransport dependencies remain the existing fixture's; no live access.

## Exact Proposed Selection

One new function using the existing `customer_engine` fixture gives two nodes:

- `[sqlite]`: sequential HTTP parity for the same two stale edits and all follow-on
  assertions. Explicitly **not** PostgreSQL concurrency evidence.
- `[postgres]`: both edit HTTP requests overlap via a deterministic barrier.

Avoid SQLite concurrent writes against its shared StaticPool connection; do not
claim a skipped SQLite race as a passing concurrency case. These are two new API
composition cases, not repetitions of old repository tests.

## Deterministic Race Boundary

Wrap the existing `PlanningDocumentService.revise` method test-locally only for
these two known request keys. At method entry, before delegating unchanged to the
original method, record each arrival and wait at `threading.Barrier(2)` with a
bounded failure timeout. Run each HTTP request from its own client/thread. This
boundary is before input resolution and workspace/session locks: never place the
barrier after a workspace lock, which would deadlock the contender.

Assert both arrivals and both requests terminate. The wrapper must not replace
resolution, catalogs, currentness, receipt checks, transaction writes or commit.
No sleeps, artificial TTL extension, forced lock failures or predetermined winner.
This qualifies overlapping admitted customer requests and real serialized CAS;
it does not claim that both transactions simultaneously own the workspace lock.
Restore the wrapper after the race so replay/successor calls do not enter it.

## Journey And Exact Acceptance

1. Customer creates/generates genuine V6 V1 and accepts one exact action. Capture
   immutable V1 document/digest/export/event plus an owned graph snapshot.
2. Build two otherwise identical input revisions changing only milestone text;
   distinct request keys, each expected input1/version1. Keep original owner intent,
   scenario, catalog selection, selected capture, uploaded image and goal unchanged.
3. PostgreSQL overlap (SQLite sequential parity) must yield exactly one200 input2
   and one409 `plan input or version changed`. Never assert a particular winner.
4. Replay the winning HTTP request exactly: identical InputResult, no new revision,
   no extra request receipt, no changed links. Reuse that winning key with altered
   milestone and unchanged expected fields: exact409
   `request key is bound to different input`, not merely any409. Failed loser/key
   attempts leave the entire owned graph unchanged relative to the winner.
5. Generate V2 through HTTP using the winning input2/version1. Assert canonical
   V6, exact parent digest, winning milestone, unchanged explicit owner intents,
   full owner member identities/observed amount and customer creative/media input.
   Current observations may have new timestamps; immutable V1 remains unchanged.
6. Submit the obsolete V1 decision using a new request key and the current event
   sequence, isolating obsolete version/digest refusal from a sequence conflict.
   Separately forge the current action digest with current version/document/sequence
   to isolate changed-action refusal. Both return the exact service-defined409
   reason and add no events/receipts; do not accept arbitrary authorization errors.
7. Comparison identifies only the intended customer change plus legitimate refreshed
   evidence metadata; `decisions_carried_over=false`. V1's singleton accepted event
   is still exactly bound to V1. V2 has no automatically accepted decision. Read,
   export and request-result recovery remain original-owner scoped.

## Full Graph And Zero Effects

Read-only SQL snapshots are permitted for assertions, not fixture authority. Bind
rows by workspace/plan: PlanRow heads, PlanInputRow canonical payload/digest,
PlanVersionRow canonical payload/digest, PlanDependencyRow witnesses,
PlanEventRow chain, PlanRequestRow operation/key/result bindings,
InputCatalogReceiptRow and its referenced CatalogReceiptRow/selection links.
Include original owner discovery receipt references from the actual resolved
input/retained V6 proof; do not count unrelated fixture catalog rows globally.
Check no orphan revision2/catalog links on loser rollback and no third input or
extra version after replay/key conflict. Preserve exact V1 snapshot before and
after successor; compare rejection snapshots before further intended mutations.

Assert zero ProviderExecutionRun, ProviderExecutionAttempt and
ProviderExposureReservation, plus no new production mandate/consent/obligation
relative to setup. MockHTTP must remain the actual bounded read-only fixture;
no mutation endpoint is allowed. Store synthetic customer document/comparison/
event/export and per-stage scoped graph evidence for review, without raw provider
payloads, cookies or tokens.

## Execution And Remaining Limits

Source and precise node/runner manifest require independent review before bodies.
Run SQLite first then PostgreSQL only after exact success, using existing per-node
resource/source/fresh-path checks. Preserve first failure and unrun cases; do not
retry unchanged source. No existing cohorts need rerunning for this additive test.

This does not newly qualify generation-vs-generation concurrency, same-key
concurrent creation, expiry/revocation races, a browser tab race, reconnect privacy
or human usefulness. Existing coverage retains its own evidence; this package
claims only the actual V6 customer input/receipt/decision composition described.
