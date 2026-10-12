# Selected Capture Projection Repair

Uncommitted candidate on `codex/inlet-w1-followup`, baseline `79f15fc5`.
This repairs repeated pure validation; configured v6 acceptance remains pending.

## Evidence And Limits

The original configured-v6 browser failed with `planning_authority_expired`.
A separate fixed-event observation located fact-age expiry at `pre_cas`.
Those failures and the original 25 unrun cases remain preserved under
`/workspace/inlet-evidence/20261012/owner-composition-attempt02/` and
`owner-diagnostic-attempt01/`. No deadline or freshness predicate changed.

The independently reviewed successor phase diagnostic is
`owner-timing-attempt02/`: exact single SQLite browser passed with complete
accounting and unchanged source. Generation took 7.283745 wall seconds and
7.287431 process CPU seconds; save took 2.795736 and 2.799867 respectively.
The sampled pre-CAS age bracket was 2.709187–2.709201 seconds. During save,
digest ran 196 times (0.376981 inclusive seconds) and provenance 160 times
(0.266962 inclusive seconds). These inclusive helper totals include more than
validation and are not estimates of removable time. SQL execution measured
0.063472 seconds across 2,385 statements; statement count alone does not justify
removing fresh reads. No recorded cgroup throttling or memory-event increment
occurred in this observation. Pressure files were unavailable; process/cgroup
scope prevents a claim that resource pressure was absent or explains prior failures.

The earlier phase diagnostic's missing-pressure-file observer error is retained in
`owner-timing-attempt01/`; its accounting is incomplete and not acceptance evidence.
Neither later passing diagnostic qualifies v6 or establishes original failure causality.

## Narrow Repair Contract

The adjacent pin digest/provenance projection shares one mandatory validated capture
only in the same call. Callback-free bounded exact-type eligibility excludes custom,
unknown, cyclic/shared, unexpected resident or private/extra-state objects. Missing
state slots decline reuse. Both original and validated values must be eligible.
Public individual helpers retain mandatory validation and unchanged projection bodies.
Digest precedes provenance; unsupported values retain original remaining calls.
Custom graph/capture paths preserve keyword order and reread the capture between
helpers, including when a callback replaces it. No reusable validation capability,
cache, SQL admission, ownership, session, privacy or authority change is introduced.

Unlike the earlier row-admission repair, this does not reuse an immutable SQL-row
decode under an exact fresh statement permit. It shares only a pure same-call
projection. The existing fresh row/owner/source/session checks remain untouched.

## Focused Qualification

Frozen baseline `capture-projection-baseline02/` reproduced **2 validations != 1**.
Final `capture-projection-repair06/` passed 139 exact cases: 135 component,
two SQLite and two PostgreSQL, with no skips. Four static checks passed: whole Ruff,
configured no-path mypy (1,550 files), exact collection and diff whitespace.
All original exits were zero, source hashes verified and process cleanup completed.
Completion freeze SHA256:
`bdf2b0f02fdfd447a16d1117322af612556f0e004cae3b8c80c4dbbf579070dd`.

Coverage includes one-versus-two actual validation calls, legacy/v2 byte and
provenance equality, zero/missing counts, corrupt copies, public validation,
subclasses, custom timezone callback order, capture replacement, second-validation
exceptions and actual history/export/replay on both databases. Initial type errors,
test exception-object identity comparison and Pydantic exception-wrapping mismatch
remain preserved with changed-source dispositions. They are not erased by later passes.

This proves removal of duplicate validation for eligible adjacent projections.
It does not prove the cause of prior expiry or a latency/capacity guarantee.
Next: fresh configured-v6 acceptance, including the previously affected and unrun
cases. No commit, deployment, provider call, advertising action or spending occurred.

## Subsequent Configured Acceptance Remains Blocked

Fresh acceptance stopped with 34 passes, one failure and ten unrun cases across
`owner-composition-after-projection01/` and `owner-composition-after-projection03/`.
All 13 SQLite cases passed. PostgreSQL positive and partial browsers passed, but
complete-to-partial failed generation with `409 planning_authority_expired`:
route 11.978648 seconds, XML testcase 49.870 seconds, process 55.351007 seconds.
The original phase/age/session predicate was not captured. The earlier SQLite
diagnostic cannot classify this PostgreSQL failure. No v6 acceptance or commit.

A test-only ceiling-tampering fixture error was preserved before correction:
the customer request never contains `total_ceiling_micros`, which is server-derived.
The corrected case injects that forbidden field and verifies the actual application's
sanitized 422 response and unchanged state/effects. Independent review approved
retaining 26 unaffected passes and resuming the failed/unrun cases. An intermediate
test assertion was corrected before execution to respect the sanitized response.
All fresh static checks passed; no production change followed the pure repair.

One reviewed diagnostic of the exact failing PostgreSQL journey added bounded
joint-projection and selected ownership/aggregate-read counters. It was interrupted
by the unchanged memory reserve: 536,113,152 bytes available, 757,760 bytes below
the 512 MiB floor. Original exit was -15 after 40.423296 seconds; no XML or phase
report was produced. Source integrity and complete child-process cleanup were verified.
`owner-postgres-timing-attempt01/` retains the exact trigger sample and original outcome.
This is neither an application failure nor phase/causal evidence, and it was not retried.

Next: a reviewed resource-headroom remedy before further targeted profiling.
Shared cgroup file/shmem/kernel counters do not identify an exclusive workload cause;
do not delete retained evidence, relax the reserve, or treat a later pass as causal
closure. The deterministic 139-case pure repair remains valid, but the configured
candidate and its dependencies remain uncommitted. Fresh ownership/source/session
checks, original deadlines, and all no-live/no-spend restrictions remain unchanged.
