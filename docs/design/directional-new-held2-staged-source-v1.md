# Directional New Held2 Staged Source V1

Proposal only, base `be86a9e`. Scope is exactly the SQLite/PostgreSQL variants of
`test_directional_feedback::test_newer_held_original_without_receipt_blocks_old_qualified_anchor`.
The two original current reads must remain temporally separated by an actual
second approved run/claim. Pre-seeding both actions and pretending the first read
occurred before them is not equivalent.

## Why A One-Shot Producer Is Insufficient

The original test first obtains an actual Google45m receipt, resolves the CURRENT
original opportunity, then uses its captured original native runtime/server to
prepare/approve/claim46m. It does not execute that claim. Current code finally
rejects the old work because the newer held original has no receipt. There is no
safe way to return the historical runtime or mutate current rows to manufacture
this transition. Rebuilding a second native execution runtime from guessed scalar
inputs would duplicate the original fixture and is not proposed.

Use one closed two-stage historical child, preserving its original native runtime
and post45m mock server solely inside that child. It commits/closes every DB session
before waiting for the parent; the parent runs real CURRENT reads between stages.
The parent sends only one literal continuation command, never a runtime, selector,
action amount, authority result or arbitrary callback.

## Concrete Private Interfaces

New `tests/directional_held_retained_fixture.py` and exact driver
`tests/fixtures/retired_execution/directional_held_seed_driver.py`; one closed
`directional_held` SourceLifetime profile at literalPIN2155. No changes to existing
receipt/snapshot fixtures, run_bounded semantics or current product guards.

```
@dataclass(frozen=True)
class RetainedHeldClaimIds:
    workspace_id: int
    first_attempt_id: str
    attempt_id: str
    run_id: str
    review_id: str
    predecessor_id: str
    successor_id: str
    replacement_id: str

class StagedHeldSource:
    engine: Engine
    original: CandidateReceiptIds
    def claim_successor(self) -> RetainedHeldClaimIds: ...

@contextmanager
staged_held_source(customer_engine: Engine, artifacts: Path)
    -> Iterator[StagedHeldSource]
```

`claim_successor` is single-use, requires first output fully validated and no
active parent Session/connection transaction retained by the consumer seam. It
sends exactly `claim\n`, waits for child terminal success, validates exact scalar
output against actual scoped rows, and returns IDs only. It is offline fixture
construction, not an application capability or client-supplied command.

The child first calls the untouched pinned candidate fixture with Google and
with_receipt=True, capturing its original ready runtime exactly as the original
test did. It commits/closes Session and atomically writes bounded stage1 JSON
(the existing exact CandidateReceiptIds shape). It then waits on stdin while
holding no Session/transaction. It must reject EOF/unknown/second commands without
creating a successor. No other mode/provider/action/source selector exists.

On `claim`, in a fresh Session it uses the retained immutable work/actor and native
runtime/server from phase1, original replacement reader and EXACT original
prepare_repeat_optimization→approve_optimization→create_run→claim_step block:
46m, rationale a*64, same mandate/account/target/held reservation, original NOW.
No execute_claim or reconciliation. Commit/close; write bounded phase2 scalar IDs
atomically, then exit. The child proves first server has exactly one original
write both before and after phase2. It does not substitute a new runtime/server
or patch approval/capability functions.

The original child objects never cross the process boundary. If any captured
fixture closure cannot work across the intentional Session close/reopen without
additional source rewriting, stop and report; do not silently rebuild authority.

## Bounded Process And Storage Ownership

Dedicated closed runner uses Popen stdin pipe and log file, start_new_session,
existing MAX_LOG_BYTES, one180-second total monotonic bound (including parent
first-read time), with an independent child command-wait bound. Stage1 file wait
checks child liveness/exit, file/log limits and deadline. Command handoff then
bounded wait uses the remaining total budget. Exceptions/abandonment close stdin,
terminate/kill/reap only this process group with existing bounded escalation.
SourceLifetime child_started/after_reaped ordering is preserved; never clean an
unreaped child's source. No generic interactive subprocess API or callback runner.

Fresh exact evidence-owned nonsymlink current.sqlite/no URL query/host/user/port,
or validated disposable loopback PostgreSQL URL/exact engine and UUID schema.
Parent AND child check all non-Alembic tables empty before stage1 and unchanged
physical DDL. Both JSON stages require size<=8KiB, exact dict keysets, strict scalar
types/hex lengths and current scoped-row validation before use. No arbitrary
artifact paths/symlinks, row copying, DDL change or database reset.

## Preserve The Current Before/After Sequence

Consumer uses the actual source engine and unchanged current
`load_receipt_candidate(db, original)` to obtain principal/work/runtime. This
already validates the first actual owned receipt, account/source/session and
original request lineage. Keep the ORIGINAL line:

`initial = resolve_original_opportunity(db, principal, work, runtime)`

Then commit/close that CURRENT read-only Session to release locks before the child
continues. Assert no pending new/dirty/deleted objects before this read-context
close and exact first provider-history equality across the current read. This
extra boundary is needed for cross-process DB isolation, not permission to move
or fake the initial assertion. No source correction or artificial row edit occurs.

After `claim_successor` returns, open a fresh current Session. Re-load the exact
original principal/session through existing current loader; require its work
scope/policy equal the saved original work and keep that saved original work as
the argument to the final reader. Do not remap to successor work/receipt. Preserve:

`assert claim and claim.attempt_id != initial.original_attempt_id`

`with pytest.raises(HTTPException, match="verified current original action"):`
`    resolve_original_opportunity(db, principal, work, runtime)`

Here `claim` is the strictly validated scalar claim result, not a fabricated old
OptimizationClaim or execution runtime. The current first successful read and
second exact-message rejection execute on opposite sides of the real successor
claim. The original historical transition block moves to the pinned child and
must be AST compared after only scalar/session binding adaptation. The first3
current directional functions/helpers remain untouched.

## Exact Graph Boundaries

Before/after each CURRENT read phase, require immutable equality of the full
reviewed provider/spending/draft/media graph, plus current write capability false
and zero current transport writes. Historical child phase2 is the only allowed
writer, with an explicitly checked typed transition, not blanket count allowances:

- First attempt/response/receipt rows are byte-identical and still sequence1.
  Exactly one response and one receipt globally; no successor receipt/response.
- Actual second46m request targets the exact same account/mandate/owner/target;
  its attempt/run/review/approval/step rows form the current owned scoped graph.
- Exactly one reservation-replacement record links original held predecessor to
  successor/run/review/ledger. Predecessor becomes superseded; successor is held.
  Exactly one held reservation remains for that owner.
- Original run becomes canceled per replacement.transfer; its canceled timestamp,
  ledger action_count/last_dispatch/high-water and the successor run/step/attempt
  changes must match the genuine typed replacement/audit/request graph. Enumerate
  actual changed fields from PIN/current code in implementation evidence; do not
  treat every ledger/run mutation as automatically acceptable.
- Original mandate/revision/consent/binding, source/account/store/publication,
  session and unrelated rows remain unchanged. No candidate jobs, feedback,
  synthetic new receipts, additional provider effects or customer API writes.

Any unexpected graph delta blocks qualification and is reported for review.

## Qualification Before Closure

First validate stage1/start/one-command/EOF/time/output/foreign-target fail-closed
protocol with small closed process tests, without a DB bypass or global harness
change. Then exact current case on both databases, including proof that stage2
has not run at the first current read and has completed before the second. Run86
current boundaries plus bounded existing receipt/snapshot compatibility if source
interfaces are touched (they should remain unchanged), whole Ruff/bare mypy/diff.
Preserve raw artifacts, exact original two identities, before/after graph and
statement-preservation proof. No newFull/aggregate, live provider, runtime object
transfer, manufactured transition or timeout increase. Implementation requires
independent interface review first.
