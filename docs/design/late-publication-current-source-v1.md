# Current Closure And Late Publication Receipt From Original Source

Proposal from `eb96dcc`, exactly the SQLite/PostgreSQL cases of
`tests/test_customer_quiescing.py::test_late_publication_receipt_is_strict_evidence_only`.
No other quiescing test moves to historical execution. No shared publication seed,
transport, claim, receipt or lifecycle implementation changes.

## Fixed Original Preclosure Source

New helper `tests/late_publication_retained_fixture.py` and child
`tests/fixtures/retired_execution/late_publication_seed_driver.py`. Fixed verified
PIN `2155ff3e3ab00cd62057dd86cb49d45359d4f49f` and existing exact app/tests/scripts
trees. No selector besides owned target/output; no arbitrary callback, source PIN,
provider, mode or authority crosses the process boundary.

The child invokes untouched original `test_publication_core.approved` using actual
original configuration and evidence-local media path, then reproduces the exact
original preclosure sequence:

1. `publication.claim_next` with key `publication-one`; assert non-None.
2. Original typed `PublishReceipt` with the first bound scope/plan/step/fence/digest,
   outcome `verified_no_effect`, at original publication_now; actual record_receipt.
3. Actual second claim with same key; assert non-None. It retries the same first
   step with a new fence, not a later dependent step. Require the two original
   requests have distinct fences/digests and the actual current step attempt is 2.
4. Create the unchanged `FixturePublicationTransport`, call apply_once on the
   second bound request, require measured `transport.calls == 1`, and serialize
   the actual resulting verified_effect/PAUSED receipt. Do not record it yet.

This transport is the original deterministic local fixture, with no sockets or
provider HTTP; its measured fixture call is not a live or current advertising
write count. Original approval/preclosure claims stay historical. Do not create
original customer session/closure records in the child; those stay current.
Commit and close the source Session before output/parent readback. Keep media,
scalar/output JSON and logs outside the source extraction.

## Owned Storage And Lifetime

Reuse the established closed helper architecture, not a generic callback runner.
Parent creates current DDL only. New SQLite file is absolute exact regular
`current.sqlite`, exclusively created, nonsymlink including every ancestor, plain
sqlite URL with no query/credentials/host/port; validation precedes factory/DDL.
Child independently checks the unresolved exact file. PostgreSQL is explicit
loopback disposable URL, no query, parent engine equality and actual
`inlet_test_<32hex>` schema. Both sides reject all non-Alembic nonempty tables
before original source creation; parent checks schema fingerprint unchanged.
No migration, schema reset/stamp or nonempty bootstrap exception.

Add one SourceLifetime profile `late_publication` with the exact helper/driver,
leaf `source`, existing archive name. No generic utility or historical batch
changes. Cleanup occurs only after reap and immutable source verification.

## Data-Only Boundary

Strict exact-key output JSON <=16384 bytes:

- `workspace_id`: strict positive integer.
- `actor_id`, `plan_id`, `mandate_id`, `action_id`, `first_receipt_id`, `fence`:
  exact32hex scalar IDs.
- `mandate_revision`: strict positive integer.
- `step_id`: exact literal `budget` for this fixed original fixture.
- `plan_digest`, `request_digest`, `late_receipt_digest`: exact64hex.
- `fixture_calls`: strict integer exactly1, measured on the original transport.
- `late_receipt`: actual `PublishReceipt` JSON, revalidated with the current model
  and canonical `inlet.publication-receipt.v1` digest. Nested scope is part of that
  typed evidence, not an independent customer-selected scope or authority.

Do not serialize original ORM, Session, customer session material, callable,
DatabaseFixtureAuthority or transport objects. Parent reconstructs current
BoundRequest from the actual second `PublicationStepRecord.request` and verifies
its plan/step/fence/digest/scope/time against current PublishPlan and the typed
late receipt. Parent checks current owned actor/membership, approved plan/revision,
actual mandate/action, one existing original verified_no_effect receipt, exact
first request/fence relationship and second attempt dispatching state. The first
and second source non-None assertions remain in the child; current parent readback
also asserts the retained typed requests exist and bind the exact stored rows.

Parent may construct a *new current* DatabaseFixtureAuthority with the retained
local media store for the original final claim call signature. It never receives
or reuses the historical authority object. No validation callback is patched.

## Current Consumer And Exact Permitted Delta

Only replace preclosure setup/claims/fixture emission. Current consumer reloads
actual user, constructs its original current CustomerSession and principal, then
runs unchanged current `confirmed`, `quiesce`, grant-cleared assertion, duplicate
late record_receipt, strict fence/conflict rejection, step-state and lifecycle
blocker assertions. Keep the original late receipt test body from `confirmed`
onward (except a precise extra denial assertion described below). No API seed or
historical execution of those current privacy/lifecycle checks.

Before yielding, snapshot all provider_* tables (expected empty), original
spending mandate/revisions/audits/actions, publication plan/steps/receipts. After
the current Session closes, compare exact graph with only:

- Original owned spending_mandates.paused becomes true.
- Original owned mandate_actions.cancel_requested becomes true.
- Exactly one new publication_receipts row appended: same workspace/plan/step,
  exact current retained second request bytes, exact actual late receipt bytes,
  validated late digest and recorded_at publication_now. The new row ID must be
  fresh32hex. Original first receipt remains byte-identical. Duplicate submission
  must produce no third row; malformed/conflicting submissions produce no delta.

No publication plan/step transition, resource rebinding, counter, opening/observed/
reserved micros or other original financial field may change. The existing step
stays dispatching and the one original horizon reservation stays held as the
unchanged legacy reserved_micros/action state, not falsely represented as a newer
ProviderExposureReservation. Provider rows remain empty. Customer/workspace/grant/
lifecycle updates are actual current closure behavior outside this financial graph,
with the original explicit assertions retained. Any unexpected financial delta is
investigated, not exempted wholesale.

Current `claim_next` has an unconditional AdvertisingWritesDisabled guard before
its workspace/authority checks. Preserve the original final HTTPException assertion
and additionally require that exact planning-only409 detail/type. Report this as
**current artifact write prohibition**, not as proof that the deeper historical
closure authority path ran. Current grant removal, immutable receipt checks and
blocked closure inventory independently remain tested without a bypass.

## Bounded Qualification

Initial actual SQLite/PostgreSQL cases, then the entire unchanged current
quiescing module plus86 default execution/transport boundary cases and16 source
lifetime pure cases. Add pure URL/path/data negatives as needed. Preserve all
existing current assertions; document the two preclosure non-None assertions
retained in the fixed original producer. Whole Ruff, bare mypy using own /tmp
cache and diff checks with separately recorded exits. Keep original W1 failure
identities, all probe failures, source provenance and exact logs/XML. No aggregate,
historical batch expansion, live transport or production feature work.
