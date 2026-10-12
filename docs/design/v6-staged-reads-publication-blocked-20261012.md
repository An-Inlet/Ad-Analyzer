# V6 Staged Reads: Verification And Publication Blocker

Branch `codex/inlet-w1-followup`, HEAD
`f8107a9c5f60accb5e73e6d9fa82a5b4e33021dd`. The staged-read fix, fixtures,
prepared-candidate changes and pending HTTP work remain uncommitted. No push,
external provider operation, credentials, hosted CI, merge, deployment or
advertising change occurred. All execution sessions are resolved.

## Implemented And Verified

The [staged-read contract](v6-staged-preparatory-reads-20261012.md) explicitly
changes only V6 generation's preparatory collection. Each reporting → media →
reporting stage obtains full fresh authorization before SQL, checks the original
fact after its work and closes the context before another refresh. A refused or
expired stage stops collection. The original identity, immutable retained inputs,
reference deadlines and exact source comparisons remain binding. The collected
bundle is provisional. Final publication still uses a separate fresh authorization
and one atomic transaction with joint currentness checks and the original
five-second limit. No fact is renewed under locks.

The default collector, including V5/V7 callers, retains its joint final context.
The configured V6 service alone selects the private staged path. Regression tests
cover revocation and identity/workspace/membership/privacy/connection/goal changes
between closed stages, real stage expiry, exceptions and a media change after the
media stage that must be rejected during publication. The inventory test now
persists each verified workspace result immediately.

Evidence roots below are under `/workspace/inlet-evidence/20261012`, except the
PostgreSQL inventory's real root at
`/tmp/inlet-evidence-20261012/staged-postgres-inventory01`.

| Package | Actual Results |
| --- | --- |
| `staged-source02` | 24 boundary regressions passed: 12 SQLite and 12 PostgreSQL. |
| `staged-large-once01` | The single changed-code rerun of the previously failed SQLite larger preflight passed. Both documents were 100,846 bytes. |
| `staged-compatibility01` | Ten existing compatibility cases passed: default collector/proof/second reporting checks and real pre-CAS/post-flush expiry on both databases. |
| `staged-postgres-inventory01` | Small workload passed; larger workload failed on its first generation. Qualification stopped. |

Each package above passed Ruff, mypy (1,612 files), exact test collection and
`git diff --check`. Original exits, exact XML identities, unchanged source hashes
and clean process cleanup were verified. Independent read-only review covered the
fix, frozen runtime gates and final blocked disposition. The earlier
`staged-source01` mypy failure remains retained; its test-only typing errors were
fixed before the fresh successful package. No failed freeze was retried unchanged.

The compatibility post-flush cases reached their intended six-second delay and
passed their rollback assertions. This is changed-code qualification, not an
explanation or erasure of the older incomplete failure record.

## Workload Evidence

Each size has two independent owners/workspaces, one Google account, 61 reporting
days and one retained selected capture. Small uses one reporting campaign,
61 aggregate and 61 selected rows, three native campaigns/adgroups, two budgets,
one shared owner/intent/allocation/image. Larger uses four reporting and native
campaigns/adgroups, 244 aggregate and 244 selected rows, two budgets and two shared
owners/intents/allocations/distinct images. These are declared tested workloads,
not maximum-capacity claims.

Small PostgreSQL documents were 57,696 bytes in both workspaces. Larger SQLite
documents were 100,846 bytes in both workspaces. The larger PostgreSQL run produced
no verified document size. Full initial larger SQL cardinalities were retained.

## New Blocking Result: Final Publication

The first larger PostgreSQL generation returned **409** after successful
preparation (4.716000 seconds). Its final authorization fact 12 expired at the
**pre-CAS** guard, age **5.623817–5.624141 seconds**. Final save lasted
**5.623164 seconds**, with **4.863329 seconds** of worker CPU. Within that span,
the observed source recheck took **3.325690 seconds** and retained-source capture
took **1.974428 seconds**. These timings identify boundaries, not a completed
root-cause diagnosis or permission to omit checks.

Original process exit was **1**; process duration **56.336152 seconds**, XML
testcase **49.944 seconds**, suite approximately **51.45 seconds**. The recorder
is complete: 839 records, 184 resource samples, zero observer errors, dropped
records or unbound facts, restored observers, stopped sampler and clean process
cleanup. All **1,930 source hashes** matched. No intentional delay or resource
interruption occurred. This was sequential execution; no contention was shown.

This failure is distinct from the repaired pre-preparation refusal. The second
workspace generation was never invoked. The failing inventory stopped before its
persistence/export and post-pair financial/provider/source/cleanup assertions;
it does not independently prove rollback. Separate expiry regression tests do.

All **18 PostgreSQL concurrency cases**, **six SQLite sequential parity cases**,
four proposed final-refresh revocation controls and the complete-to-partial browser
journey remain unrun in the proposed next matrix package. No final matrix gate was
issued, and no unchanged retry followed the failure.

## Evidence And Continuation

Manifest hashes:

- Boundary regressions: `93d1979400765ee7cfae5e3bd65ad42e0030a85b9838092940abee9ae7f67a3a`.
- Single SQLite larger rerun: `2435d04aba0a15a86bb2655d1e9415dc69a8c53bbd7ea47841723beb6cad067c`.
- Compatibility: `c50c661cb6271255605cce643d0c26a876f9f0f2c926e70e04955542e31de401`.
- PostgreSQL inventory: `a22578c7bca0d2bfdd4c4fb3fc1e707e6cc65df2d8c04b7687fa7938c1f14073`.
- Failed recorder: `6b46d89916104c53126cca746aad80529a1326c7ce4589bac80e0ffc52de586e`.

`failure-disposition.json` retains exact results, original timing, both inventory
files, limitations and all 29 proposed unrun nodes. Because workspace storage is
close to its reserve floor, the new package used real absolute temporary paths;
the workspace symlink is navigation only. A complete compressed package copy is
retained at `staged-postgres-inventory01-preserved.tar.gz`, with its hash and scope
in `staged-postgres-inventory01-archive.json`. These are executor-local artifacts,
not uploaded or guaranteed beyond environment retention. No prior evidence was
deleted or moved. Both filesystem floors remain unchanged.

Actual runtime: PostgreSQL 16.15, QueuePool size 5 plus 10 overflow, pool timeout
30 seconds, read committed; server statement/lock/idle-transaction timeouts zero.
The passive observer uses NullPool, one-second connect and 500-ms statement timeout.
Cgroup limits are four CPUs and 16 GiB. The runner retains one heavy slot,
900-second cases, a persistent 60-minute runtime-package ceiling and all previously
reviewed disk/memory floors.

Next package: inspect final publication's source recheck and retained-source capture
using this first-invocation evidence. Move only demonstrably pure work outside the
authority window or reuse exact immutable inputs after fresh dependency equality;
preserve fresh SQL authorization/currentness, atomic publication and the original
five-second fact. Any fix needs independent review, focused regressions and a fresh
single failed-node invocation before another matrix gate.

`INLET-REL-20261012-01` remains open; V3 stays the default and V6/V7 remain
release-unqualified. Preserve the historical 61 passed / one failed / one unrun
snapshot, independent V5 result and HTTP 57 passed / one unresolved inventory.
All 21 pending HTTP files and migration 0094 remain preserved, allowing the narrow
authorized V6 dispatch addition in `service.py`. The reconnect-retention owner
decision remains pending. No live behavior or purchasable production release is
claimed.
