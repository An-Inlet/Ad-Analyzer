# Q07 private V5 arithmetic acceptance — proposed interface

Design only, based on reviewed Q05 `ff497d9`. No implementation or tests have run
for this proposal. Frozen Q07 remains unchanged; passing deterministic cases will
not constitute expert acceptance or resolve the original browser 409.

## Existing evidence and missing joins

`tests/test_planning_customer_alternatives.py` already rejects over-ceiling,
negative and contradictory fixed allocations through real create APIs (422 and
zero plan/dependency/event/request/execution rows), then generates genuine legacy
alternatives. It does not prove private V5 currency rejection, assertive unchanged
ceiling, or a higher ceiling requiring a new confirmed goal/input revision.
Q05 adds genuine V5 three-platform save/generate/replay/export and independent
integer alternatives but deliberately does not supply those Q07 negatives.

`requests.AllocationIntent` has target and integer micros, not per-allocation
currency. `input_resolution.prepare` derives currency, ceiling and aggressiveness
from the exact current confirmed GoalDefinition; clients cannot override them in
CustomerInputs. `resolve` joins exact real catalog selectors and validates the
complete PlanInputRevision. These production boundaries remain unchanged.

## Stable fixture and ownership

Reuse `prepare_creative_q05_basis(engine, config, replicas, patch, artifacts)` and
its frozen CreativeQ05Basis fields unchanged. New tests only in
`tests/test_creative_q07_common_basis.py`; no fixture defaults or production edits.
Every variant starts from a deep copy of the real Q05 body, with unique request
keys. Preserve the original authenticated session, same owned accounts, September/
August windows, product/image/private proof, Google-only selected capture and
social gaps. Never construct positive documents or edit persisted confirmations.

## Proposed bounded matrix

1. Arithmetic/schema negatives: exact 400/400/200/reserve100 fails against1000;
   negative integer allocation fails; explicit foreign currency on an allocation
   fails the strict request schema. Keep these distinct from actual account currency
   mismatch. Assert unchanged plan/input/version/dependency/event/request counts
   relative to their before-request baseline and zero financial effects. Do not
   claim existing catalog receipts disappear on failed input saves.
2. Actual mixed-currency target: requires an explicitly EUR owned social account
   and matching real MockHTTP account metadata, acquired before selection through
   normal native catalog APIs, with the confirmed USD goal unchanged. Obtain a real
   selector; saving a scenario that includes this target must fail. Do not mutate
   an existing account/canonical receipt, manufacture a selector or use a schema
   extra-field rejection as proof of this stronger owned-currency case.
3. Assertive alone: edit the actual goal definition to assertive with budget still
   USD1000, preview and confirm through existing goal APIs; update inputs to that
   exact revision through the ordinary input CAS route. Over1100 remains rejected;
   genuine V5 generation/export still shows1000, assertive and exact independent
   alternatives. A direct client ceiling/aggressiveness field remains invalid.
4. Higher ceiling: revise the real goal to USD1100. Before confirmation, old and
   new-revision planning attempts must not adopt it. After actual preview/confirm,
   save a new input revision with matching goal revision and 400/400/200/100,
   generate/export and assert exact1100. Preserve the previous immutable1000
   version/digest and verify old input CAS cannot silently update it. No rewriting
   goal rows, input rows, receipts or source scopes.

The currency case needs one reviewed test-only seam before implementation:
optional social account currency in the Q05 bootstrap/MockHTTP constructor, default
USD unchanged, or a separate local Q07 account factory. Prefer the local Q07
factory if it avoids broadening Q05. Actual catalog refusal before selector issuance
is a valid early boundary observation but cannot replace the proposed save-boundary
assertion without documenting the actual rejection stage for review.

## Qualification and artifacts

After interface approval, SQLite first, then corresponding bounded both-database
cases with -x and exact route/fixed error evidence. Pin expected statuses/reasons
from actual code, not guessed generic409. If goal changes invalidate catalog or
source receipts, reacquire through genuine APIs under the same session; do not
relax currentness or refresh clocks. Any unexpected gate is preserved and examined.
No broad preservation rerun unless a shared fixture changes.

Retain actual generated/exported1000-assertive and1100-confirmed versions separately
with hashes and original goal/input revision bindings. Assert integer allocation
and reserve arithmetic, unchanged native calls on replay/read/export, and zero
execution/approval/reservation counts. Initial catalog acquisition may make local
read-only mock calls. No native amount change, FX conversion, spending authority,
full Q07 quality or expert approval is implied.
