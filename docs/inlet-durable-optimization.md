# Durable Existing-Campaign Optimization

The common coordinator in `publication.optimization` executes one exact server-compiled
budget or pause operation under separate production consent. Google Search/manual CPC
uses an independent native campaign budget; Meta and TikTok use their registered exact
budget-owner topology. Existing simulation Google actions remain a separate fixture.

`prepare_optimization` takes owned scope, target, typed action and rationale reference.
Server qualification supplies current money/profile lineage; the real adapter reads
complete current state; the server exposure reader supplies bounded portfolio evidence.
The resulting `OptimizationExecutionReview` freezes intent/state/qualification/exposure,
computed positive budget delta, exact target-set and native budget owner. No API accepts
customer-provided evidence or runtime objects as authority.

`approve_optimization`, `create_run`, `claim_step`, `execute_claim`, and
`reconcile_attempt` use the existing protected production tables. Admission checks
current workspace, owner, goal, separate consent/revision, account generation,
entitlement/master control, target-set, freshness, action count/cooldown, aggressiveness,
positive-change cap and total portfolio cap. Cumulative positive changes are derived
from admitted immutable runs on the original period ledger, including canceled or
settled runs and older policy revisions. Aggressiveness cannot increase total authority.

An original native-owner reservation is committed before the original attempt and all
authority is rechecked after that commit gap. A fresh provider preflight and validation
run outside the transaction; authority/session/qualification are checked again before
the durable one-emission marker. The exact original request/fence is retained after
unknown results, with append-only responses/receipt supersession. Old state and absent
readback do not establish no effect. Cancellation blocks future emission and late
read-only reconciliation cannot reopen the canceled run.

The existing owned normalized receipt boundary now handles optimization. It binds the
original production consent, goal, account generation, native budget owner, target-set,
request/fence and before/after digests. `verified_target_state` does not claim causal
effect or treatment time. Effective timestamps remain unavailable.

## Session-Bound Customer Entry Points

`execution_authorization.ExecutionAuthorizer(db, workspace_id, actor)` is a server-bound
callback. Creation and optimization runtimes carry it; activation uses its contained
creation runtime; qualified settlement also carries it. Each transaction reentry calls
it before downstream ledger/source locks. An API binds its already authenticated
principal to `lock_customer_mutation` and an owner check, preserving workspace→user→
session→membership→ledger/source ordering. These locks last through the durable commit
and are reacquired after provider IO. The internal default is workspace-first owner
checking; API assembly must bind its actual session instead. No client chooses it.

## Explicit Limits

Default runtimes remain unavailable. Real adapter wire behavior is tested with mocked
HTTP; concrete live native portfolio/exposure and terminal-request/reporting sources
remain missing. No daily budget is treated as a hard period cap. Provider CAS is
unavailable; current-state preflight does not protect against external UI edits after
the read. Runtime qualification must account for that limitation.

Any same native-budget-owner held reservation blocks a subsequent optimization,
including after a successful target-state observation. Qualified terminal settlement
or a separately designed safe ongoing rebudgeting protocol is needed before releasing
that hold. No emergency over-cap/unknown pause authority or post-period mutation is
invented. Customer API/UI/scheduler wiring remains a separate integration package;
this is a callable durable coordinator, not a live launch claim.

## Verification

Focused durable optimization + real session revocation + creation/activation/settlement
regressions: **100 passed, 1 expected SQLite concurrency skip** on disposable PostgreSQL
and SQLite. Separate concurrent optimization worker test: **1 passed, 1 SQLite skip**.
Actual Google/Meta/TikTok budget and pause HTTP journeys, unknown original-fence
reconciliation, duplicate/foreign claims, generation/state/expiry drift, cancel commit
gap, held-owner rejection, aggressiveness, and cumulative positive-cap preservation
through cancellation/settlement/revision are covered. Revocation during creation
qualification and optimization provider preflight uses real persisted customer sessions.
Whole Ruff/mypy and diff checks passed. No Full, workflow dispatch, live provider call,
spend, merge or deployment occurred. Logs: `/tmp/inlet-durable-optimization-final.log`,
`/tmp/inlet-optimization-concurrency.log`, `/tmp/inlet-durable-optimization-ruff.log`,
`/tmp/inlet-durable-optimization-mypy.log`.
