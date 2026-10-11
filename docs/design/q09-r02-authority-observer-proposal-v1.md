# R02 Q09 Authority Expiry: One Observation-Only Probe

Design only after failed qualification `creative-q09-baseline/both03.xml`.
Failure-reproducing source frozen `0b6fd79`. No retry or observer execution yet.

## Known And Unobserved

The exact pytest node `[postgres-complete]` completed real fixture acquisition and
POST input creation (201), then POST `/generate` returned 409 with exact detail
`planning_authority_expired`. Two earlier SQLite cases passed; the PostgreSQL
partial variant was not executed. Both03 reports 2 passed/1 failed in54.719s.
No final document/export exists for the failed generation. Successful SQLite
artifacts, failed log/XML and source hashes were preserved before diagnosis.

`authority.final` emits this same detail for either monotonic identity-fact age
outside inclusive0..5seconds **or customer session wall-clock expiry**. Therefore
the failure alone does not prove which condition fired, which final invocation
failed, or how much time came from SQL, CPU, lock waits, scheduling or other work.
The earlier checkpoint wording identifying the five-second gate is a hypothesis,
not a measured branch outcome. No per-phase timing was captured in both03.

Generation includes multiple authority lifetimes: preparation/read contexts and a
new refresh after candidate composition. `service.generate` passes that latter
fact into `repository.save_generation`; its source callback performs fresh
selected/image checks, then retained witness capture and final authority before
writes, followed by flushes and another final authority before return. Failure
could occur in an earlier nested read/lock as well. The HTTP response does not
identify any of those callsites.

R01's earlier browser Generate action combined POST generation/current GET/version
GET without original route statuses; the original route remained unknown. R02
has an exact POST failure and must remain a distinct incident. Previous later
instrumented successes and query reductions do not establish R02's cause. The
older `creative-portal-browser/inlet_v5_browser_timing.py` observes overlapping
stage totals and does not isolate the original failure or all predicate branches.
Do not add nested times or infer a preparation optimization from those totals.

## Proposed Minimal Experiment (Requires Approval)

Exactly one isolated PostgreSQL complete Q09 test node, on frozen source0b6fd79,
with one external evidence-only pytest plugin. Unique log/XML/basetemp/report;
no screenshot, retries, fixture changes, sleeps, normal-clock replacement,
authority refresh insertion, guard change or parallel pytest. A success remains
an observed success, not resolution of both03. Stop after its terminal result.

Observer boundaries:

- `PlanningDocumentService.generate`: establish request-local ContextVar, aggregate
  wall/process time and SQL counts; only this exact method's interval is observed.
- `authority.refresh`: call original exactly once; upon returned fact assign a
  request-local sequential fact ordinal. Never log identity/session values.
- `authority.final`: call original exactly once and preserve exception unchanged.
  Record fixed allowlisted module/function/line callsite, fact ordinal, before/after
  monotonic age, numeric session remaining seconds, outcome and only an allowlisted
  HTTP409 detail code. Do not log arbitrary exception text, repr, args or payloads.
  Age/session remaining are observations bracketing the original checks, not a
  replacement execution of its decision. Near-boundary samples may be inconclusive.
- `repository.save_generation`: mark enclosing stage and deltas; fresh source and
  witness operations stay untouched. This is an inclusive stage, not an additive
  exclusive-cost classification.
- SQLAlchemy before/after cursor events: count and time executed statements while
  request ContextVar active. Never retain SQL, parameters, rows, URLs or IDs.
  Failed SQL duration must either be separately captured without payloads or
  explicitly excluded. Count metadata only; do not execute extra queries.

Keep events bounded (e.g.5000); overflow marks report incomplete and disables
complete-attribution claims. Restore wrappers and remove event listeners in
pytest teardown even after exceptions. Preserve callable binding/descriptor
semantics. No wrappers may revalidate models, serialize payloads, inspect database
rows, call clocks other than observer samples, or retain principal/fact references
beyond the invocation. Report source/plugin hashes, terminal status and truncation.
Exact plugin source must receive independent review before execution.

## Interpretation And Next Decision

If expiry recurs, use failed-callsite and predicate-bracketing data to locate the
interval; distinguish age from session expiry only where samples support that.
SQL duration is part of wall time; CPU and inclusive nested intervals overlap.
Unattributed wall time is not automatically lock contention. A separate query-shape
proposal may follow evidence, but no optimization is authorized by this document.
If it passes, retain the original R02 failure and report the observed safety margin;
no second probe merely to obtain a desired outcome. All Q09 qualification claims
remain bounded until the original four-case matrix is legitimately completed.
