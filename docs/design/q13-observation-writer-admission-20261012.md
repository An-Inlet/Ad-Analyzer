# Q13 Observation Writer Admission And Blocked Prerequisites

Assessed at `ae030a34`. The writer is not dependency-ready. Production source has no
`ProposedField(...)` constructor and no `FieldSnapshotV1(...)` producer outside its
DTO definition. `compare_fields` accepts normalized facts but explicitly does not
qualify their provider extraction. Current descriptive/creative/owner actions cannot
be relabeled as native edits. Separate optimization observations are not this contract.

Missing precisely: a versioned, independently reviewed native read adapter that binds
an owned account/connection generation and full target topology to each supported
proposed field, plus its native semantics and fixture provenance. Raw/effective status
cannot be assumed to mean `delivery_status`; resolved creative landing-page semantics
and effective/inherited country targeting are not defined. Missing/unknown/partial
response behavior, exact units/order/URL treatment and observation time/completeness
must be specified. Credentials or synthetic normalized facts cannot fill these gaps.
Current action schemas admit at most one supported field, so a partial-match positive
case is separately unavailable without a reviewed multi-field action contract.

## Future Service Interfaces (Design Only)

- Customer request: exact workspace/plan/version/document/action digests and opaque
  idempotency key. No customer-supplied observed values, provider evidence, source digest,
  actor/implementation time or qualification flag. Customer reports use the existing
  assertion API and never become provider observations.
- Server ticket: original authenticated session/user, paid owner scope, immutable action
  binding, account/connection generation/privacy revision, expected event sequence,
  source binding and a specific qualified extraction-contract identifier. The future
  reader registry must fail closed unless that exact adapter is admitted. Dependency
  injection alone is not qualification; tests may inject only an implementation of the
  reviewed contract and may not turn arbitrary snapshot JSON into trusted evidence.
- Reader output: bounded read-only normalized facts, exact target, native source proof,
  original interval/expiry and explicit unavailable/missing fields. Preserve sufficient
  normalized proof bytes to revalidate history/export; a bare digest is insufficient.
  No SQL transaction remains open across provider/identity IO. No provider mutation port.
- Commit: refresh the original session outside locks, then lock/recheck original session,
  owner/paid scope, account/source generations, privacy, version/action and original
  evidence deadline. Append observation, retained proof dependency and exact request
  receipt atomically. Unknown binding, mismatched source or stale proof refuses without
  an event; qualified missing fields may produce explicitly unavailable comparisons.
  Mismatching values mean conflicting fields, never proof of implementation or lift.
- Replay: same actor/workspace/operation/key and exact intent returns the original result
  after fresh authorization; changed input under the key conflicts. Replays do not read
  providers or append new events. Revocation/erasure overrides replay availability.
- Corrections: provider observations are immutable historical reads, not editable customer
  reports. A new qualified read appends a new observation without rewriting the old one.
  Evidence-integrity correction/withdrawal needs a distinct append-only server-authored
  invalidation contract linking the original event, reason and source; current
  ReadObservedStatus has no such field. Define its reader/migration contract before code.
  Customer correction/retraction retains the existing assertion chain and never retracts
  or supersedes provider facts. Concurrent chain changes use expected sequence/head CAS.
- History/export/erasure: preserve distinct unions and original interpretation at event
  time; do not recompute old status from current evidence. Export normalized proof and
  validation metadata; privacy deletion erases events, retained proofs and receipts in
  one transaction and invalidates unfinished exports. No actor or causal lift inference.

Do not introduce a writer, route, synthetic production adapter or activation before
these dependencies close. V6/V7 remain release-unqualified; the authority incident
INLET-REL-20261012-01 stays open.

## Selected Independent Acceptance Gap

Existing PostgreSQL repository races and V6 serial report/retraction tests do not
qualify configured V7 concurrent customer-report corrections through actual HTTP,
readable archive and erasure. Close that bounded gap using real services/SQL, configured
media and synthetic provider transport, without new observations or proposal types.

Create/generate one real Meta V7 plan. Record a customer statement about completing
creative review, never an implemented native edit. Two independent original-session
clients correct the same report head: PostgreSQL overlaps requests at a barrier before
service identity refresh/locks; this is concurrent-request CAS coverage, not proof of overlapping database
locks. SQLite is explicitly sequential CAS parity. Exactly one
wins; loser has no partial event/receipt/head. Preserve both outcomes in finally, no
retry-to-green. Test exact replay, changed intent under the same key refusal, rejected spoofed verification,
stale-input correction refusal and allowed historical withdrawal. Verify scoped history,
actual workspace archive, revoked-session refusal, atomic privacy erasure and no new
provider/financial/execution effects. This is customer-report acceptance, not an
observation-writing service or native provider qualification.
