# Owner Save Authority Window — Next Boundary Proposal

Status: source-only proposal, not implementation or execution authorization. Based on
reviewed context `fb2d864` and inspection of the current combined service worktree.
The parent supplied combined06 observations; this document does not remeasure them.

## Observed Failure And Attribution Limits

Combined06 still refused before CAS at `repository.save_generation`'s authority final
check following retained capture, at fact age 6.51986 seconds. Save elapsed was about
6.515 seconds. The storage pair site was not reached. Retained capture was about
2.3258 seconds; seven nested owner-document validations occupied about .7958 seconds.
The save-exclusive interval of about 2.378 seconds includes 878 SQL calls, unwrapped
work and observer overhead: it is **not a pure-validation measurement**. Nested
intervals must not be added to enclosing intervals.

The restriction change eliminated one adjacent validation; it did not establish
adequate headroom. Even eliminating the measured .7958 seconds entirely would not
bring this particular 6.51986-second interval below five seconds, and most of those
validations cross freshness boundaries and cannot simply be eliminated. There is no
basis to promise that another small duplicate-call deletion will qualify the flow.
The observed run fails acceptance; it does not prove that every deployment or valid
input can never finish within five seconds. R01/R02 and the owner-flow incidents retain
their distinct evidence and unresolved original causes.

## Actual Save Boundary

`PlanningDocumentService.generate` composes outside the final fact window, then calls
its existing `authority.refresh(principal, provider)` once. It constructs the final
source callback and opens the save transaction. `repository.save_generation` performs:

1. Strict ticket/candidate parsing, exact capability dispatch, bundle/ticket binding and
   generation lower bounds, then the first authority lock.
2. Receipt replay, plan/input/parent checks against SQL; candidate/ticket bindings;
   pure reference, proof, target, allocation, empty-catalog and owner-bundle checks.
3. Paid/goal/account/privacy checks; final source callback; retained-source capture;
   authority final and current expiry; CAS.
4. Canonical row construction, dependencies/request receipt, flush, current expiry
   and authority final again.

Some pure work in step 2 uses only the original candidate/ticket/bundle but is currently
interleaved with SQL. Other work consumes freshly loaded SQL documents. These are not
interchangeable. No proposal moves SQL-derived validation, the source callback,
retained capture, or their guards outside the original fact window.

## Recommended Next Package: Establish Pure Admission Boundary And Its Cost

Do **not** implement a prepared-object bypass yet. The old V5 pure admission probe
found only about .09 seconds; that did not justify the ownership mechanism then. V6
has additional work, but combined06's exclusive residual is not evidence of its cost.
The smallest justified next package is a reviewed extraction of the existing pure
admission computation into an ordinary internal function, still called at the same
logical validation boundaries inside `save_generation`, plus a payload-free cost
observer at that exact function. This makes a later placement decision falsifiable
without introducing any trusted prevalidated object.

Proposed internal functions (names subject to source review):

    _validate_generation_packet(*, ticket, bundle, candidate)
        -> tuple[GenerationTicket, GenerationEvidence, PlanVersion]

    _validate_generation_candidate_bindings(*, ticket, bundle, candidate) -> None

The first performs exactly the existing initial strict parse/capability/assert-ticket/
UTC checks and returns those validated values. The second performs only original
packet comparisons: actor/version/parent/input relation; selected and creative proof;
full reference/cardinality/expiry/privacy; targets; allocation; empty-catalog binding;
owner generation-bundle binding. Its call remains at the existing post-SQL position.
Current plan/head/input/parent comparisons, receipt replay ordering, and SQL helpers
stay in their current positions. No new model, schema, version, cache, callback or
public entry point is introduced. Public `save_generation` must invoke both functions;
callers cannot supply a success flag. If extraction cannot preserve error/replay
ordering exactly, split the second function at those boundaries rather than move it.

An observer wraps only these ordinary functions, original-once and exception-preserving.
Report exclusive and inclusive time, SQL counts (expected zero), calls and enclosing
save/fact ages; never SQL text, arguments, graph contents or principal identifiers.
One coherent next source milestone may be selected by the parent for qualification;
this proposal does not authorize a retry of combined06 or any execution now.

Required checks for the extraction: exact V1–V6 rejection/output parity; unsafe copied
primitive/nested fields; original proof/ref/target and private-image pins; exception
ordering and exact completed-request replay; unchanged retained/currentness call order;
actual atomic rollback on late source/fact expiry. A real six-second delay must still
produce `planning_authority_expired` with no durable writes. No changed wall clock.

## Consequential Follow-On, Only If Measured Worthwhile

If the measured original-packet-only work offers useful margin, separately approve the
already designed private preparation mechanism in
[creative generation save preparation](creative-generation-save-preparation-interface-v1.md),
updated explicitly for V6. The intended location is **before the existing single final
identity refresh**, not a refresh after a failed/elapsed fact and not a second refresh.
It requires deeply owned strict snapshots, type-aware commitments including excluded
session/private pins, no alias/callback escape, one-use consumption before callbacks,
and tamper checks through final flush. Public unprepared save remains fully validating.
The new risk is trust in a previously checked in-process graph: ordinary frozen
Pydantic objects are insufficient because unsafe copies and object mutation exist.
No source/currentness result may be carried in that packet. All SQL checks, fresh
independent passes, original observation expiries and five-second acceptance remain.

If those pure costs are too small, do not build that mechanism or claim it fixes the
incident. The next decision needs actual attributed fresh-reader costs and a separately
reviewed **same-pass bounded query batching** proposal; not cross-pass caching. The
available aggregate measurements do not identify such a query change yet.

## Decision And Blocker Classification

This is an engineering qualification blocker, not a missing credential or a customer
permission problem. Current tested source cannot be called reliably qualified while
normal accepted inputs hit the five-second guard. There is no demonstrated remedy yet
that guarantees adequate margin under the preserved rules.

The recommended extraction/measurement requires parent technical review, not an owner
product decision: it changes no acceptance boundary. Moving pure validation before the
single fact acquisition is a consequential internal trust-boundary change and requires
its own reviewed ownership/mutation contract, even though it need not change public
policy. AGENTS prioritizes safety/isolation over speed; it does not authorize treating
a timeout as success or bypassing fresh checks. If later evidence shows mandatory fresh
work itself cannot fit, bring the owner a concrete architecture/acceptance choice with
measurements; do not silently extend/renew the deadline, remove passes, or label a
repeated successful retry as qualification. No such owner decision is requested now.
