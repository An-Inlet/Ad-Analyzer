# Reliability Definition And Remaining Critical Path

Checkpoint: local `138daab`, following current-policy fresh-consent qualification.
No retention semantics are authorized to change. The parent now recommends
retaining historical plans marked stale after ordinary reconnect, requiring fresh
data for new advice, and retaining explicit privacy erasure. That recommendation
is pending owner decision; it supersedes the earlier engineering recommendation,
not the implemented policy or frozen acceptance criteria.

## Exact R03 Definition

R03 originated in the first actual private V6 SQLite owner-review API integration:
POST generate returned `409 planning_authority_expired`; `sqlite-01.xml` records
0 passes, 1 failure, with 25 remaining API cases unrun. Source subsequently froze
as diagnostic-only `d594cb9` after nonbehavioral formatting/typing repairs.
Original evidence: `/workspace/inlet-evidence/20261011/google-owner-v6-runtime/`.
The original failure did not record guard location, identity-fact age or session
time remaining. Its precise predicate and expensive operation remain unknown.

`authority.final` currently refuses if monotonic identity-fact age is outside
0..5 seconds OR the session wall-clock expiry has passed. Later distinct
instrumented occurrences located actual age-limit failures before CAS and after
flush while session lifetime remained positive (5.0286, 5.4734, 6.5199 and
5.1977 seconds respectively). These establish those occurrences' failed
predicate, not the original incident's cause or attribution of all elapsed cost.
Nested timings and observer overhead cannot identify an expensive function by
subtraction. Acceptance08 was another uninstrumented 409 with no captured phase.

Subsequent checked owner-domain derivations preserve strict external/fresh-pass
validation and have 194 pure passes. Successor service qualification is the exact
disjoint 6+1+21 API union, followed by separate customer browser cohorts. Those
qualify bounded current behavior; they do not reconstruct the original event or
establish a performance margin. Historical statements that service is unqualified
in the reliability log describe earlier sources; the successor integration ledger
is the current scoped status.

## Cause-Oriented Work Without Pass Chasing

- R01 lacks the original failed route/reason and disposable state. Its later seven
  observed browser passes cannot recover missing historical facts. Keep open; do
  not rerun unchanged cases solely to obtain another pass.
- R02 has exact POST/refusal but no original fact-age/session branch. Its single
  frozen-source probe passed and recorded high statement counts. A statement
  count alone does not identify the original expiry cause.
- R03 has later located guard failures but no original attribution. Preserve each
  source/occurrence separately. Never renew a fact, extend five seconds, shift
  clocks or remove fresh reads to make acceptance green.

One concrete current coverage gap is real-clock authority expiry on actual V6
after the final persistence flush. Existing V6 post-flush coverage shifts
the evidence database clock and proves `generation evidence expired`; existing
real six-second authority coverage is V5 before CAS. A separate reviewed test-only
proposal will use normal clocks, exactly one deliberate delay, original session
and actual V6 generation, observing the final authority guard and asserting exact
authority refusal and atomic unchanged
planning/financial state. Qualify SQLite first, then PostgreSQL only after the exact
first pass; stop on any earlier unexpected failure. This is safety acceptance, not
a spontaneous-timeout reproduction or historical root-cause closure.

## Remaining Critical Path

1. Complete the bounded V6 authority-rollback coverage above; then freeze fixes
   before selecting a coherent integration cohort. Preserve the original
   `9d7aa2e` exhaustive qualification separately from every newer cohort.
2. Reconcile actual Q01–Q16 evidence against frozen inputs. Q09 still lacks
   qualified social selected-event/known-attribution producers. Unknown semantics
   cannot be filled with guessed purchases, windows or generic conversion counts.
   Q06 remains investigation-only and does not qualify native daily-to-period
   spending. Existing newer Q08, Q10, Q11 correction and Q16 evidence remain scoped.
3. Await the reconnect retention decision, then design/migrate/test any approved
   change explicitly against privacy erasure, stale decisions, historical export
   and nonresurrection. Current erasure passes do not satisfy historical retention.
4. Complete the six human judgments using existing actual artifact packets.
   Artifact sharing is pending; all evidence stays local. Agent assertions are
   not human usefulness verdicts.
5. After changed sources settle, review one exact integration manifest spanning
   positive/zero diagnostics, original-session/workspace isolation, planning
   revision/replay/decision, source correction/reconnect/privacy and customer
   browser/export. Use serial first-failure stopping, resource floors and bounded
   route/reason observation. Do not infer exhaustive current-head qualification
   from combining old cohorts, or rerun full suites per small package.
6. Live identity/billing/provider/storage/pilot and commercial/release acceptance
   remain separate explicit gates. No credential, advertising, hosted retry,
   push, merge, deployment or budget action is authorized.
