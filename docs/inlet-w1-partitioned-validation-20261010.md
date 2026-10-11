# W1 Resource Diagnosis And Isolated Validation

**Final status:** all 52 partitions qualified locally on 2026-10-11: 7,011 parent passes / 83 unchanged skips; separately 404 historical child passes / 3 allowed skips. See [final result](inlet-w1-validation-result-20261011.md). Earlier checkpoints below are historical.

Frozen source remains `9d7aa2e1193ec627b33088764210f94e49cf504d`.
The interrupted aggregate is immutable: 1,554 passes, 26 skips, 5,514 unreported.
It supplies no completion credit to the replacement partition execution.

## Measured Findings

The aggregate's sampled cgroup memory rose from 11,970,580,480 to
16,650,354,688 bytes. After process shutdown, usage fell to about 13.87 GB.
No active pytest or resident-memory-consuming browser process remained. The post-run memory breakdown included
about 5.19 GB of tmpfs/shared memory, 4.73 GB of other file cache, and 3.73 GB
of reclaimable slab. These are cgroup totals, not proof of a particular test leak.
The interrupted runner sampled totals only, so per-test attribution is unavailable.

The archive watcher waited during tests and compressed only after the terminal
result. Core customer fixtures dispose engines and drop temporary schemas;
that source inspection does not prove every fixture or browser journey cleans up.
The new runner records process RSS and the detailed memory breakdown every five
seconds, allowing process, cache and database growth to be distinguished.

Exactly 45 inactive, manifest-listed `.mypy_cache` directories were removed from
scratch: 1,869,467,432 regenerable bytes. No source, database or test artifact was
removed. Their disposal inventory is retained under
`20261010/recovery/regenerable-mypy-disposal.json`. Memory usage afterward was
about 12.02 GB. The 512 MiB reserve remains unchanged.

## Exhaustive Execution Contract

The existing canonical collection defines 7,094 unique parent cases. An external
runner partitions whole files into 32 balanced groups (at most 222 parents per
group), with the 20 historical-snapshot file nodes each independently isolated.
The 52 partitions are disjoint and their exact node-hash union equals collection.
This is process isolation, not a timing or hosted-capacity qualification.

Each partition uses a fresh Python process and newly created, task-owned PostgreSQL
database. Before any tests run, a non-filtering plugin checks the actual collection
against that partition's exact expected node hashes. Synthetic checks verified
acceptance of an exact collection and rejection of omitted, duplicate and unexpected
nodes without modifying collected items. Terminal JUnit must independently match
class/name hashes exactly, with zero failures/errors and exit zero.

After each passing partition, the existing verified archive helper inventories and
stream-verifies all supplemental files into durable storage. Only then is that new
partition's scratch duplicate removed. A custom-format database dump and readable
restore inventory are preserved before its dedicated disposable database is dropped.
Neither the original nor interrupted aggregate database is modified.

The runner stops on any failure, collection mismatch, archive failure, or reserve
breach (512 MiB memory, 1 GiB durable storage, 2 GiB scratch). No automatic retries
or credit for partially completed partitions are allowed. It records commands, source and helper
hashes, resources, terminal results and a running progress ledger. Final acceptance
requires all 52 terminal partitions, exact combined coverage, skip review, verified
archives, separate reconciliation of the 19 historical batches / 407 children, and
the already completed frozen preflight. Until then this remains partial validation.

## Evidence And Status

Evidence and executable local harness:
`/workspace/inlet-evidence/20261010/w1-partitioned-9d7aa2e-c/`.
The continuation controller exited zero; no validation process remains active.
`qualification.json` is the terminal authority. Do not restart completed tests.
`progress.json` and `combined-parent-result.json` retain the completed execution record.

No application, test assertion, frozen checkout or CI workflow changed. No hosted
retry, purchase, budget increase, deployment, provider call or advertising write.
Q01–Q16 and human release/usefulness gates remain open.

## First Partition Environment Correction

Attempt A stopped correctly after partition 00: 217 passed, 3 skipped and two
restore-test failures in 215.00 pytest seconds. Exact terminal identities matched
all 222 expected cases. Minimum memory headroom was 4,408,606,720 bytes; no
resource interruption. All 711 supplemental members were archived and verified.
The attempt, source, database and scratch remain preserved.

Both failures were the same missing launcher setting: native PostgreSQL tools
are inside `inlet-b01-postgres`, but `INLET_RESTORE_POSTGRES_CONTAINER` was unset.
Setting this existing supported option resolved the prerequisite: both PostgreSQL
restore tests passed, with two existing SQLite skips, exit zero in 74.95 seconds.
No application, assertion or frozen-source change was needed.

Attempt B uses separate evidence, fresh database names and scratch paths, and
requires the passing restore prerequisite before starting. It carries no passing
case credit from A and starts the full disjoint union afresh. The safety reserves
and coverage/archive checks are unchanged.

## Verified First Two Cycles

Attempt B partitions 00 and 01 are terminal and fully retained: respectively
219 passes / 3 existing skips and 220 passes / 2 existing skips, with no failures.
All 444 identities match their disjoint planned collections and terminal reports.
Both cycles verified archives and database dumps before deleting only their
new duplicate scratch and dedicated disposable databases. Partition 00 archived
669 members; its database dump is 701,477 bytes.

Minimum memory headroom during their pytest processes was respectively
4,106,690,560 and 4,050,513,920 bytes, substantially above the unchanged reserve.
Their separate archive stages also stayed above 4.8 GB headroom. After the first
cleanup, the second pytest began at 12,061,118,464 bytes cgroup memory, near the
12.02 GB post-cache-disposal baseline. These measurements support bounded process
isolation; they do not prove every remaining partition will fit.

Partition 02 is active. This is 439 passed / 5 skipped out of 7,094 planned parent
cases, not full acceptance. `first-two-resource-analysis.json` records the measured
stage samples. The original interrupted full run remains separate and unchanged.
A 20:46 UTC disconnect notification did not interrupt the executor: a subsequent
check found the controller alive, recent samples, clean frozen source and all
prior evidence intact. No reset or duplicate was started.

## Ten-Partition Checkpoint

Ten partitions have complete, exactly matched and retained evidence: 2,192 passed,
20 existing skips; 4,882 parent outcomes remain pending. Partition 10 (the eleventh)
is running. `ten-partition-checkpoint.json` retains current resource measurements.
No full-suite or historical-child completion is claimed.

A more precise browser-process inspection found 572 defunct Chromium entries
parented to PID 1, all with zero RSS, and no configured cgroup PID cap. This is
an environment process-reaping limitation, not evidence of active browser memory
retention. No reset or process-killing action was taken. Detailed evidence is in
`browser-process-diagnosis.json`. The active validation harness is unchanged.

## FIFO Retention Repair And Exact Continuation

Attempt B stopped at 22:11:30 UTC after partition 13 passed (220 passes / one
skip). The archive helper correctly rejected two unopened FIFO fixtures left by
SQLite target-safety tests. All passing JUnit and scratch evidence remained intact.
No test failure, resource breach, frozen-source change or test rerun occurred.

A separate archive-helper successor now preserves FIFO type/mode/owner/time
metadata without ever opening a FIFO. Sockets, devices and hardlinked FIFOs remain
rejected. Regular-file opens are nonblocking so a file replaced by a FIFO cannot
hang before the identity check. Thirteen operational self-checks pass, including
exact FIFO preservation, forbidden FIFO opening, socket rejection, mutation races,
output caps and existing overwrite/symlink safeguards. One initial self-check
assumed an unrestricted umask; its failed output is retained, and the final
fixture explicitly sets the intended mode. Helper/self-check evidence is under
`/workspace/inlet-evidence/20261010/archive-fifo-successor/`.

Partition 13 was then archived and its owned database dumped and verified before
cleanup. Its original passing test execution is unchanged. Fourteen completed
partitions therefore account for 3,068 passes and 28 skips.

Continuation C reverifies the exact source, terminal identities, exit statuses,
archive hashes and database-dump hashes for all 14 completed partitions. It runs
only the 38 still-unexecuted partitions, with new database/scratch names and the
verified FIFO-aware helper. Its manifest retains all 52 original selectors and
explicit paths to the completed evidence; final reconciliation covers their
disjoint union. Attempt B's stopped controller and original logs remain immutable.
No partial partition receives completion credit, no passing tests are duplicated,
and the 512 MiB / 1 GiB / 2 GiB reserves remain unchanged.

## Twenty-Partition Checkpoint

Twenty partitions have exact terminal and retention qualification: 4,388 passed,
34 skipped. There are 2,672 unreported parent cases, including the historical
wrappers whose 407 children remain separately unqualified. Continuation C is
active at partition 20 (the twenty-first), PID 104868 / session 46704.
No parent test has failed in the qualified B/C execution. B stopped only for the
preserved FIFO archive failure, repaired without rerunning its passing tests.

A 22:27 UTC disconnect callback was notification-only: the same continuation PID
was alive at 22:28:42 with a resource sample four seconds old, clean frozen source
and 4.34 GiB memory headroom. No reset or duplicate was required. Final provenance
will combine exactly the 14 verified B partitions and the 38 C partitions.

## Thirty-Partition Checkpoint — 11 October UTC

Thirty partitions are terminal and retained: 6,561 passed / 71 skipped, all exact
identity matches. Of 7,094 parent cases, 462 remain (two ordinary groups and the
20 individually isolated historical-file cases). The 407 historical children
still require separate reconciliation. Controller 104868 / session 46704 continues
on unchanged frozen source. This remains partial validation, not full acceptance.
