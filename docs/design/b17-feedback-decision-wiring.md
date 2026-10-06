# B17 Feedback-To-Decision Wiring Audit

Reviewed assembled `539ce2d79fdf1aa66aff28ed91064b34a7693bbb` on 2026-10-06.
Read-only inspection; no runtime edits, tests, external provider calls or policy changes.
Also inspected the uncommitted0068 candidate-review proposal in
`/workspace/inlet-candidate-review`; its findings are provisional until that head freezes.

## What Exists And What Does Not

- `app/outcome_feedback/service.py`: owned v3 persistence, current assessment reread,
  idempotent feedback CAS and bounded active-score recomputation are implemented.
  `active_score` returns only Decimal/None. It has no production caller outside tests.
  The caller supplies a server-only family and opaque scope digest; a canonical typed
  recommendation-group builder is not yet implemented.
- `app/outcomes/feedback.py`: explicitly parameterized, policy-weighted descriptive
  association scoring exists. Registry defaults to None. Score sign means association
  relative to a declared preferred metric direction, not an increase/decrease budget
  instruction, causal effect, delivery proof or independent observations count.
- `app/optimization_candidates/service.py`: real candidate processing consumes a
  server `CandidateReadPort`, not active feedback. Registered learning profiles default
  empty, and raw owned v2/v3 assessments are explicitly barred from qualified learning.
  `compiler.py` accepts a separately qualified direction and bounds suggested budget
  changes by mandate/aggressiveness/cumulative limits. Feedback has no adapter here.
- `app/optimization_candidates/selection.py`: current target selection is structural;
  it chooses a unique approved native budget owner, not a learned ranking of targets.
  Its default runtime is None. Silently interpreting feedback as target selection or
  direction would introduce an unapproved decision algorithm.
- Candidate-review0068 consumes an already-suggested immutable candidate. It is not a
  feedback consumer. Its link retains commitments while candidate deletion SET NULLs
  the active reference and blocks future authority, preserving financial history.

Therefore ordinary missing code includes canonical feedback scope binding, a typed
aggregate/provenance projection, owned orchestration of assessment→feedback, and an
explicit consumer policy adapter. Missing qualified source/timing producers and
calibrated policy values are additional gates, not explanations for omitting this code.

## Narrow Next Contract (Proposed, Not Enabled)

Implement a server-only `FeedbackScopeV1` and `FeedbackSnapshotV1` in new modules.
No migration or browser inputs are needed for this read projection.

`FeedbackScopeV1` binds workspace/environment; current commerce store, generation,
privacy epoch, metric digest, currency/time zone; goal ID/revision/digest; ad connection
ID/version/account; action purpose and exact server-derived native budget-owner/target
set. Derive fields from owned assessment receipt and original immutable reviewed plan,
not raw caller strings. A helper checks the original plan against the requested current
candidate scope. Unsupported plan kind or absent target association rejects, rather
than falling back to whole-workspace pooling. Exclude attempt ID from the group key so
multiple distinct original attempts can contribute; preserve each exact attempt in
snapshot provenance. Changing goal/source/account scope creates a different group.

`read_feedback_snapshot(db, original_actor, requested_scope, family, authorize, clock,
registries)` acquires the existing workspace fence, recomputes only exact matching
active slots (maximum64, reject excess), and revalidates each current assessment and
stored plan. Return one strict union:

- unavailable: bounded reasons, null score, no invented sample count;
- available: bounded Decimal association score, active contribution count (explicitly
  NOT independent statistical observations), policy digest, scope digest, sorted exact
  slot ID/revision/feedback/assessment commitments, oldest/newest assessment as-of and a
  deterministic content digest. Empty active set is distinguishable from balanced
  nonempty score zero. Interpretation remains association; direction/spend authority
  absent. No persistent numeric aggregate or new privacy retention.

Add a matching `apply_owned_feedback` orchestration wrapper that derives the exact
scope from current owned receipt/plan rather than accepting an arbitrary grouping
key. Keep existing low-level service compatibility for explicitly scoped tests; the
new candidate adapter must use only the typed wrapper and snapshot. Policies None
still return unavailable/no contribution. Assessment production stays outside locks;
wrapper reuses final current owned fences without provider IO or caller commits.

First consumer use should be advisory explanation in a separate named read result,
not insertion into `CandidateEvidence.direction`. An eventual
`FeedbackDecisionAdapterPolicy` must explicitly define calibrated direction mapping,
minimum evidence eligibility, provenance, bounds and qualification profile. No values
ship enabled. A new evidence schema can be registered only when actual producer and
policy qualification are available; do not remove the current raw-v3 block. Pure
adapter mechanics can be tested with clearly labelled synthetic contract fixtures.

If a future candidate uses the snapshot in a decision, its immutable evidence digest
must commit to the snapshot and policy, and its final result admission must reread the
snapshot under the workspace fence after all IO. Subsequent feedback changes already
clear workspace candidate caches, and0068 must block linked future execution when the
candidate disappears. Consumer wiring must not let a stale detached snapshot recreate
a candidate after retraction. CandidateReadPort cannot carry this freshness guarantee
by itself; coordinate a pure local final-current hook with its owner before changes.

## Composition Risks And Required Combined Coverage

1. Migration0064 depends0062 and creates derived feedback plus triggers.0068 also
   depends0062;0066 depends0060. Root must create the reserved single join0069 with all
   current heads and preserve additive model/export/lifecycle registrations. No branch
   should renumber another frozen migration or independently construct the join.
2.0064 dependency deletion erases parent→feedback/slots, deletes workspace candidates,
   and increments export privacy revision. Combined0068 must prove result cascade
   SET NULL retracts linked review authority, without deleting review/receipt/reservation
   history or granting a replacement financial hold. Historical-dependency deletion
   must work even when the candidate's direct anchor is a different publication.
3.0064 PostgreSQL raw derived-row BEFORE guards use workspace NOWAIT. Service paths
   must stay workspace-first. Combined link/receipt cascades need actual contention
   coverage; no deadlock suppression or automatic mutation replay. A failed transaction
   must retain data and export revision together.
4.0066 is protected original-response evidence, deliberately not authoritative delivery
   timing or ClosedOriginalRequest. It references attempts RESTRICT and refuses a
   populated downgrade. Feedback erasure must leave it untouched. Receipt append uses
   existing candidate invalidation, which now erases feedback for that attempt; capture
   alone is not a new qualifying timing producer.
5. Strict publication v2 work is ongoing separately. The current feedback dependency
   validator calls the v1 descriptive validator. Union integration must preserve row,
   scope, digest, epoch and freshness bindings and keep unresolved/full-enumeration
   acquisition unqualified. Do not cast v2 to v1 or promote it just because traversal
   completed. Existing v1 selectors must not be obscured by a newer v2 publication.
6. Downgrades differ intentionally:0064 removes derived data;0066/0068 must reject
   loss of populated protected evidence/forward fences. A joined downgrade test must
   respect these contracts rather than weakening them to get a green test.

## Verification And Acceptance Status

This is an inspection/proposal, not additional test evidence. PR201 focused36 passed,
1 SQLite row-lock skip; root integration reports61 passed,4 skipped and Ruff/mypy557.
A combined0064+0066+0068 regression is still required after0068 freezes. No provider
rate limit or external access restriction prevented this audit. Missing ordinary
consumer code is actionable offline. Actual mature action-learning acceptance remains
incomplete until genuine qualifying source/timing, calibrated policies and the explicit
consumer adapter all exist and are verified; none is supplied by owner intent alone.

## Implemented Scoped Consumer Successor

On integrated base `c2e43b9236a5affeca7516d37783ec80bbc0a3f0`,
`app/outcome_feedback/snapshot.py` implements canonical scope, owned apply orchestration
and a provenance-rich read projection. It checks persisted assessment, original reviewed
optimization plan and current source/session/receipt fences. Scope also binds operation
kind and before/after window lengths. Only existing-campaign optimization is supported;
activation requires a separate safe grouping contract and is rejected here.

A configured empty group returns `empty` with null score. A nonempty zero association
returns `available` with provenance. No policy returns `unavailable`. Each aggregate
rereads all assessments/plans, verifies stored feedback against current policy, rejects
more than 64 contributions, and rechecks policy/session before output. Sorted slot,
revision and document commitments yield a deterministic digest. Assessment timestamps
are historical evidence, not new freshness or independent observation counts.

No migration, customer proof, provider IO or numeric production default is added.
The snapshot does not feed candidate direction. The scheduler owns the separate
pure-local final-current hook; a qualified directional consumer policy remains missing.

`tests/test_feedback_review_composition.py` exercises real candidate review/session/
approval/claim and HTTP-mocked Google code. Explicit schema-only numeric/dependency
fixtures test erasure without claiming qualified evidence. An alternate dependency's
deletion clears numeric parent/candidates and SET NULLs the review link, blocking final
emission after the third context read. Completed real mocked mutation retains original
Google response evidence and financial holds; historical reconciliation stays callable.
These are assembled ORM-schema tests. Existing migration roundtrips and the root's
future joined migration remain separate migration evidence.
