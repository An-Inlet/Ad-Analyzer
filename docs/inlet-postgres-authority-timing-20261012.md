# PostgreSQL Authorization Timing — 2026-10-12

Configured v6 remains unqualified and uncommitted on `codex/inlet-w1-followup`,
HEAD `79f15fc5be9c00e7aec1f06ce21b25dd87a02ae4`. This diagnostic supplies a measured
failure phase, not acceptance. The original acceptance result remains 34 passes,
one failure and ten unrun PostgreSQL cases. The 139 focused projection-repair
passes remain separate.

## Resource Recovery And Preserved Attempts

Independent review approved removing exactly 162 task-owned, regenerable mypy cache
files (461,451,264 bytes), retaining current caches and all sibling files. Cleanup
verified 2,725 source hashes, 706 evidence hashes, 65 artifact hashes and 21 sibling
hashes before and after. Measured cgroup headroom rose by 462,249,984 bytes, from
1,141,391,360 to 1,603,641,344. Later samples stayed near 1.40 GB. The shared cgroup
limits attribution; this is observed headroom recovery, not proof of the original
failure's cause. The 512 MiB reserve and disk floors were unchanged.

The earlier reserve interruption remains preserved. Diagnostic attempt02 failed
before application setup because the pytest basetemp parent did not exist. It
recorded exit 1, zero generation operations, clean observer restoration and clean
children. The successor created its own scratch parent and retained every failed
output. Neither attempt earned acceptance credit.

## Observed PostgreSQL Failure

Attempt03 ran the same exact configured complete-to-partial browser once, with
unchanged application/test source, observer and bounded runner. Exit 1; XML testcase
55.816 seconds; subprocess 63.452385 seconds. All 1,860 source hashes matched, no
resource interruption occurred, no child remained, and the observer reported clean
restoration, complete accounting and no truncation.

The fixed privacy-safe event was `generate / pre_cas / fact_age_outside_window`,
HTTP 409 `planning_authority_expired`; the session predicate was not evaluated.
Observer brackets put the fact age at 6.208320–6.211215 seconds. These brackets are
not the predicate's exact internal sample. This classifies this diagnostic failure;
the original uninstrumented PostgreSQL failure still lacks a recorded phase.

| Measured Phase | Wall Seconds | Process CPU Seconds |
| --- | ---: | ---: |
| Entire generation | 16.175001 | 12.216298 |
| Save after final identity refresh | 6.210866 | 4.865334 |
| Entry validation | 0.567108 | 0.566479 |
| Actual bindings | 0.002205 | 0.002010 |
| Owner bindings | 0.249381 | 0.249030 |
| Final source checks | 3.907922 | 2.898772 |
| Retained evidence construction | 1.339669 | 1.094403 |

Save made 2,379 completed SQL calls with 1.708354 seconds inclusive execution time.
Two selected-source rechecks accounted for 701 SQL calls each. Helper counts include
160 joint capture projections (0.998613 seconds inclusive), 22 selected aggregates,
78 current-scope calls and 22 instrumented selected-storage current reads. Helper
times overlap and must not be added or treated as removable savings. SQL execution
time does not distinguish lock waits, transport or server work. CPU is process-wide.
The shared cgroup recorded no CPU throttle or memory-event change during generation;
pressure files were unavailable. None of this proves absence of resource contention.

## Repair Direction And Security Requirements

Main candidate composition already precedes the final identity refresh. Moving only
entry and actual/owner binding work before that refresh would remove at most the
observed 0.818694 seconds before preparation overhead: the observed save would still
be 5.392172 seconds. That arithmetic is not a measured repair and is insufficient
to justify another acceptance attempt. Storage serialization was not reached before
the failure, so moving it alone cannot repair this pre-CAS expiry.

The next design must separate expensive deterministic construction from fresh final
authorization and source revalidation. Any prepared result needs bounded immutable
same-call inputs and exact ticket/bundle/candidate/policy binding. It must confer no
authority and must not become a cross-request or source-currentness cache. Bypass
mutation of frozen models and callback mutation must invalidate preparation. Public
validators and safe behavior for direct save callers remain required.

Fresh session, ownership, entitlement, goal, account, connection, privacy, source and
head checks must still execute at publication. Repeated SQL cannot be dropped merely
because it is expensive. Moving source reads out of the final transaction would
require a separately reviewed exact snapshot/fence protocol proving that concurrent
change, deletion or change-and-restore cannot reuse stale evidence. No provider I/O
while locks are held, timer extension, refreshed fact inside the locked save, or
weakened pre-CAS/post-flush guard is proposed.

Before adoption: independent security review plus mutation, source-race, original
session revocation/expiry, goal/privacy/ownership change, replay/CAS, rollback and
unchanged five-second delay regressions on SQLite and PostgreSQL. Keep default v3
and previously qualified v4/v5 behavior. No feature expansion until this path is
qualified. No new application code or behavioral rerun followed the diagnostic.

## Evidence

Under `/workspace/inlet-evidence/20261012/`:

- `owner-memory-recovery01/`: reviewed proposal, per-file cleanup journal, measured
  outcome, sustained samples and source architecture checkpoint.
- `owner-postgres-timing-attempt02/`: preserved setup failure and disposition.
- `owner-postgres-timing-attempt03/`: frozen manifest, unchanged observer/runner,
  original log/XML/exit, phase report and failure disposition.

Attempt03 manifest SHA-256:
`e1d69d4f208f38761e316d744ac516c0093cc0da2bef14d39625074416ebc4dd`.
Disposition SHA-256:
`1c4cf862b85a58e4f00f889154369057f304420f72f760b07c8531b81eda7a0b`.
No commit, push, PR, hosted CI, merge, deployment, live provider/model access,
credential operation, advertising change or spend occurred.
