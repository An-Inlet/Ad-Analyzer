# Directional Adapter6 Current Server V1

Proposal only, base `460d70a`. Exactly three functions/six original failed database
variants in `tests/test_directional_candidate_adapter.py`: real queue/epoch policy
refresh, committed retraction after native I/O, original-session/installed-producer
requirements. No newer-held-action case, production or historical runtime change.

## The Original 50m/45m Distinction

`test_google_optimization_http.Server` starts campaign5, Google budget resource7,
USD/UTC, with amountMicros=50000000. `test_optimization_candidates.fixture` reads
this state BEFORE its optional receipt branch; the immutable CandidateObservation
and runtime.reader closure retain that50m state. The with_receipt=True branch
then approves/claims/applies45m through the actual original Google transport.
Server.__call__ updates the mutable budget dict to45000000 on its one MockHTTP
mutation. The already-captured native server reference sees45m, but the earlier
observation remains50m. The original adapter helper later obtains its template
from the frozen observation and makes fresh read_current calls against that45m
server. Replacing both states with50m or both with45m would change this contract.

The reviewed current `load_receipt_candidate` deliberately creates a NEW current
Google mock server. Its inherited `load_candidate_read_fixture` makes real
GoogleOptimizationTransport reads at50m and builds the corresponding original
observation; then the receipt loader binds the actual persisted original45m
receipt. This is correct for frozen source reconstruction, but its server has not
performed the child process's original mutation and therefore still contains50m.
The old adapter's capture of `candidate_fixtures.ready` cannot work here: that
function runs only in the pinned child, and no runtime/server object crosses it.

## Concrete Local Interface And Wiring

Reuse unchanged `snapshot_receipt_source` on the three adapter test functions:
add its explicit Engine argument/local engine assignment and planning_boundary
marker, as in reviewed snapshot/directional cases. No new source producer or
shared fixture change.

Inside this module's `prepared` helper only, replace the old ready-capture block
with a scoped capture of `tests.test_feedback_snapshot.fixture`, whose current
outer alias is the reviewed retained-source loader. `assembly` already wraps that
alias, so it will receive the EXACT original six-element current tuple, never a
fabricated old eight-element ready result. The capture returns that tuple unchanged
and records its actual current Google Server for the remainder of prepared.
Use the following explicit checks before setting its mock read state:

1. `result` is the actual six-element loader tuple. Its server is an instance of
   `tests.test_google_optimization_http.Server`; it has zero current writes.
2. The captured CandidateObservation budget_owner.budget_amount_micros is50m,
   and the server budget amount is the string50000000. Preserve that immutable
   observation and all scope/evidence/timestamp/policy fields unchanged.
3. Use its exact work.scope.source.attempt_id and owned workspace to read the
   persisted original optimization request/receipt via current owned evidence
   functions, not caller-provided amounts. Require original request's action
   GoogleBudgetSetV1(amount_micros=45_000_000), exact campaign5/budget resource and
   matching owned account; receipt sequence1 and verified_target_state remain
   required by the unchanged receipt loader. Cross-check returned source attempt/
   receipt against these current rows. This is read validation, not reconstructed
   approval/execution runtime or a new claim.
4. Set ONLY the current mock server budget amount to the validated original45m
   target, reproducing the already-observed historical effect for subsequent
   reads. No mutate endpoint, fabricated response/capture or added server.writes
   record. Verify template remains50m and server now45m, zero current writes.

Keep capture scoped around assembly and restore the source alias afterward.
Require exactly one captured tuple. After assembly obtains the unchanged template,
select the recorded actual server explicitly rather than indexing an old-ready
shape. This local setup change is the only modification to `prepared` before its
existing GoogleOptimizationTransport construction. Its transport, numeric policy
adaptation, `read` function, candidate evidence, adapter construction and returned
tuple stay unchanged. The source fixture's original counter still observes one
loader call and its original server object, so its zero-write and exact24-table
history finalizer covers this path without changes.

If the persisted request's target budget resource cannot be validated through the
existing request/receipt shape, stop and report the concrete shape rather than
inventing an authority proof. A SQL row read must remain scoped to this owned
source; no foreign ID/name match or manual replacement action is permitted.

## Preserved Actual Read And Counterfactual Coverage

All original test bodies, assertions, parameters and run helper remain unchanged
except their explicit engine setup. Preserve actual queued reads through
GoogleOptimizationTransport.read_current and its real MockTransport handler.
The new server's writes counter starts0 (the historical one lived in the child);
original before/after equality still proves zero CURRENT writes. Never prepopulate
a fake write count to match the child.

The first case retains actual candidate processing/result reads, two-observation
qualification, current authorized epoch, same opportunity across clock and policy/
calibration/profile changes, and changed candidate audit digest. The second still
commits contribution deletion from a separate real Session AFTER actual native
read and requires candidate job/result erasure with blocked processing. The third
still creates a different actual session and rejects epoch reuse, absent policy
producer and double wrapping. Original template/evidence expiry and clock logic
stay unchanged; do not claim extra expiry cases that the original bodies lack.

## Qualification And Scope

After interface review, one current queue positive on both databases first; then
all six +86 default boundary cases, plus six directional/snapshot8 compatibility
if needed to verify alias scoping (no new closure credit). Capture evidence that
fresh native reads see45m while original template remains50m; no current mutations.
Include exact original failure identity and AST proof: all test/run bodies
identical after fixture setup normalization; prepared identical after replacing
only the documented source-capture/server-selection block. Shared assembly,
producer, loader and runtime remain untouched.

Whole Ruff, bare mypy, diff and raw log/JUnit before freeze/review. No aggregate,
external provider, source-policy relaxation, default write enablement or second
held-original action. No implementation under this proposal before review.
