# Failed Job Finalization Fence — 2026-10-12

Completed locally on `codex/inlet-w1-followup`, following inventory commit b6f3f127.
This closes the reliability failed-finalizer writer gap, not all JobRun writers or
the generation incident. HTTP acceptance remains **57 passes / 1 unresolved**;
INLET-REL-20261012-01 remains open. Source reconstruction is unchanged.

## Contract And Implementation

After known-successful authoritative job creation, the worker freezes ID, workspace,
connection, account, platform, job name and original creation/start timestamps.
All failure paths retain this identity, including shutdown, exhausted/permanent
failure, retry-wait interruption, advisory-lock loss and fresh-connection recovery.
No identity is inferred from a post-failure ORM reload or job ID alone.

The finalizer owns rollback and a replacement transaction. SQLite reserves a physical
write transaction with BEGIN IMMEDIATE before lookup. PostgreSQL takes the canonical
workspace lock before the current JobRun lock. It matches every original identity
field and updates only RUNNING, unfinished rows. It never merges stale state,
recreates deletion, substitutes a different job, or rewrites terminal rows. Historical
failure recording remains available after workspace closing or source revocation;
this grants no collection authority. Missing/mismatched/terminal rows are preserved.
`finalization_completed` means no further attempt is needed, not necessarily that a
failure row was written. Commit exceptions retain UNKNOWN_COMMIT_OUTCOME semantics.

## Executed Checks And Evidence

22 distinct focused tests PASS: 14 existing worker lifecycle/recovery regressions,
plus four new cases on each database. New cases exercise both entrypoints, original
scope/timestamps, missing jobs, terminal success/failure, malformed/pending state,
rollback of flushed mutations, closing/revoked sources, physical workspace contention,
late failure after competing success and actual commit-acknowledgement loss.

The separate lock-timeout case proves blocking on PostgreSQL and independent file
SQLite connections with foreign keys enabled. The success-race case proves terminal
preservation; its pre-helper event alone is not proof of database blocking. No claim
is made that arbitrary successful writers cannot overwrite failed rows later.

Final whole-repository Ruff, mypy (1594 files), exact collection and diff check PASS.
Evidence root: `/workspace/inlet-evidence/20261012/`; aggregate:
`failed-finalization-aggregate.json`. Original/final exits, exact XML identities,
resource cleanup and 1911 source hashes verified. No skipped cases or interruptions.

- Attempt01 manifest `66e1d3dc6d7f75a65fd72d8612d9d8ccde5e4c9aa5556f4d65f54e80a3848749`:
  statics and 14 worker tests passed; first new SQLite case failed on test slug
  `other-False`; remaining new cases unrun.
- Attempt02 manifest `1d6a32a91e482819dcd88ab5effbd56f4936824660bd975dff2cc6f269500259`:
  statics and four SQLite cases passed; first PostgreSQL case failed on the test's
  implicit workspace ID colliding with explicitly seeded ID1; three PG cases unrun.
- Attempt03 manifest `b4b3780b318734022ba4ff2a0039c8fc25ac246fa13633be43ac530718e8ca50`:
  explicit distinct test IDs; statics, corrected SQLite case and all four PG cases pass.
  Production code stayed identical through all attempts. Carry-forward of the other
  three SQLite cases is bound by unchanged module AST outside the corrected case;
  all other source hashes match. The original failures remain preserved.

Independent read-only review confirmed the narrow production contract and required
the FK, timeout-reset, mismatch and worker-callsite coverage now exercised.

## Next Package And Remaining Gates

Verify parent-delete cascades against published range data, including rollback,
privacy advancement and reader refusal; qualify linked catalog/input restrictions
and normal ordered semantic erasure. Continue manual alias/helper writer tracing
within the existing 52-model inventory. Completion update immutability is migration
0074-only; metadata fixtures cannot qualify that invariant. No shorter reconstruction
or universal mutation epoch is justified by this package.

Only local code, tests and documentation changed. No external/provider calls, pushes,
PR, hosted CI, merge, deployment, customer-account changes or advertising spend.
Existing uncommitted HTTP-admission work remains separate and release-unqualified.
