# Local Validation Timing Investigation

Observation checkpoint only; the frozen2476b87 Full has not reached a terminal
result at this checkpoint. No coverage, timeout, worker count or test semantics
have been changed. One aggregate Full runs on its own immutable checkout and
PostgreSQL database. Separate focused implementation/review cohorts sometimes
share the same host and PostgreSQL server; therefore this is not an uncontended
benchmark.

## Evidence Captured

The passive sampler writes `assembled-full-resources.jsonl` under the executor's
October7 evidence directory. It records every30 seconds: timestamp, quiet progress,
process CPU/RSS, cgroup CPU counters and memory events/composition. Later samples
also map completed outcome counts to the exact4961-node collection. This gives
approximate group windows only, not accurate per-test durations. The sampler does
not modify the running test process or frozen worktree.

Between12:45:56 and13:04:22 UTC:

- Elapsed1106.21 seconds; entire cgroup used1878.54 CPU core-seconds, approximately
  1.70 cores on a four-core quota. Incremental CPU throttling was0.215 seconds.
  These shared-host measurements do not establish CPU saturation as the cause.
- Full pytest RSS rose from3,271,172 to4,204,012 KiB. Memory-limit reclamation events
  rose from0 to521; no OOM or OOM-kill event occurred. A sampled16GiB cgroup included
  roughly4GiB anonymous memory,7GiB file cache and4GiB reclaimable slab. High total
  usage must not be mislabeled entirely as application heap.
- Sampled groups included native populated backup/restore, Meta runtime APIs,
  multi-provider diagnostics, optimization candidates and provider coordinator.
  Group ranks are incomplete because collection mapping started mid-run and a
  thirty-second sample can straddle multiple groups.

New focused cohorts retain `--durations=20`. Exact examples, not Full rankings:

| Cohort | Actual Result | Slowest Reported Individual Phase |
| --- | --- | --- |
| Owned linked identity/advertiser reads |28passed55.63s|PostgreSQL revoke/identity call1.92s|
| Google envelope and existing diagnostics APIs |171passed183.28s|PostgreSQL ordinary envelope call3.89s|
| Shopify acquisition/new storage/historical0081 |47passed60.50s|PostgreSQL populated proof migration call4.26s; setup1.82s|

Logs remain beside package terminal metadata and checksums. Author and integration
cohorts overlap and must not be summed as distinct acceptance coverage.

## Safe Follow-Up

Complete the original Full unchanged. On the next already-required immutable Full,
add duration reporting and a uniquely named JUnit timing artifact to its recorded
command/environment before launch. This adds measurement, not reduced coverage or
another benchmark-only run. Group exact setup/call/teardown durations and compare
with resource samples before changing the harness.

The common `customer_engine` fixture currently creates the complete schema per
case and drops a unique PostgreSQL schema afterward. This is a concrete candidate
for profiling, not permission to weaken isolation. Any future reuse must preserve
independent sessions, concurrency tests, schema/trigger coverage and teardown;
a single rollback fixture is not automatically equivalent. Likewise, real restore
and HTTPS/provider-contract journeys must not be replaced with stubs for speed.

Sequence larger focused browser/database cohorts when the Full is active. Do not
retry hosted validation or shorten local coverage to investigate this performance
question. Hosted browser startup diagnosis remains a separate owner-pending task.


Additional measured successor UI cohort:45passed244.08s. Slowest individual call
phases were `test_customer_social_execution_ui.py::test_social_execution_real_browser`
TikTok journeys,43.35s PostgreSQL and39.08s SQLite. Meta PostgreSQL journey10.37s
and TikTok clarity9.56s/9.11s followed. These are exact focused-run durations;
they identify worthwhile profiling targets without attributing the whole Full
runtime to them or replacing genuine browser/video validation with mocks.
