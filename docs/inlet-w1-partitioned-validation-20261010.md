# W1 Resource Diagnosis And Isolated Validation

Frozen source remains `9d7aa2e1193ec627b33088764210f94e49cf504d`.
The interrupted aggregate is immutable: 1,554 passes, 26 skips, 5,514 unreported.
It supplies no completion credit to the replacement partition execution.

## Measured Findings

The aggregate's sampled cgroup memory rose from 11,970,580,480 to
16,650,354,688 bytes. After process shutdown, usage fell to about 13.87 GB.
No pytest or browser process remained. The post-run memory breakdown included
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
or resumed partial credit are allowed. It records commands, source and helper
hashes, resources, terminal results and a running progress ledger. Final acceptance
requires all 52 terminal partitions, exact combined coverage, skip review, verified
archives, separate reconciliation of the 19 historical batches / 407 children, and
the already completed frozen preflight. Until then this remains partial validation.

## Evidence And Status

Evidence and executable local harness:
`/workspace/inlet-evidence/20261010/w1-partitioned-9d7aa2e/`.
The controller is running in tool session `31866`; `started.json` identifies its
process. Never launch another copy. Consult `progress.json`, `controller-stopped.json`
or `combined-parent-result.json` before taking further action.

No application, test assertion, frozen checkout or CI workflow changed. No hosted
retry, purchase, budget increase, deployment, provider call or advertising write.
Q01–Q16 and human release/usefulness gates remain open.
