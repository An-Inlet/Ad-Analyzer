# Validation Overlap And Critical-Path Audit — 9 October 2026

Docs-only proposal from successor `5114261`, branch `codex/validation-overlap-audit`.
No harness, assertion, collection, workflow, timeout, database or frozen W1 source
changed. No test or hosted retry ran. This audits current code and retained local
measurements; it does not qualify a faster workflow or establish a performance cause.

## Finding

There is no evidence that current nested validation reruns the complete suite.
The old recursive Full regression has already been replaced by command-shim tests.
The expensive historical harness runs three disjoint, explicitly bounded sets of
necessary historical assertions, not three copies of Full. Small named gate overlaps
are real but do not explain the multi-hour critical path. Recommend explicit CI job
partition preserving every current and historical node, not increasing the90-minute
step or120-minute job caps, hiding failures, or removing historical coverage.
Splitting work reduces wall time only when jobs run concurrently with sufficient
resources; it does not necessarily reduce billed minutes or total CPU work.

## Parent And Child Inventory

| Boundary | Actual execution / unique assertion | Overlap and disposition |
|---|---|---|
| CI `Validation` | `.github/workflows/ci.yml` runs one ordinary `python -m pytest -ra ...` aggregate,90-minute step within120-minute job; Ruff/mypy, browser/media prerequisites and explicit gates surround it. | No second `validate.sh Full` is invoked by CI. Default parent collection includes all current tests and three historical wrapper nodes. |
| `test_pinned_pre0086_execution_contracts[original]` | `retired_execution_harness.qualify` extracts exact2155ff3, validates exact collection, then executes142 listed original nodes. |142 unique nodes; separate old runtime, not a current-policy substitute. |
| Wrapper `[ui_supplement]` | Same pin;19 separately listed UI nodes. |19 unique nodes; no intersection with either other child manifest. |
| Wrapper `[initial_forward]` | Same pin;88 separately listed forward/source nodes. |88 unique nodes; no intersection with either other child manifest. Known PostgreSQL unknown-response failure remains a failure. |
| Current preserved function bodies | `coverage-map.json` has36 original functions; each current preserved callable is renamed `historical_contract_*`, not `test_*`. AST mapping test checks equivalence and named current coverage. | These original bodies are not also directly pytest-collected in current code. Current boundary/history/source tests listed in the map test different current behavior and must remain. |
| Child collection | Each batch first invokes exact nodes with `--collect-only`, then executes those nodes once. | Two interpreter starts, but collection does not execute the cases. Keep completeness/provenance checks; no evidence supports treating this as duplicate assertion execution. |
| Historical producer-to-current-schema fixtures | `retired_producer_fixture` calls pinned `seed_driver.py`, not child pytest. Modes create genuine retained records; CURRENT lifecycle/export/privacy/mandate-read assertions then run. | Some historical setup semantics also occur in snapshot tests, but current-schema consumers and their assertions are distinct. Removing these loses current compatibility coverage. No authority/ORM/runtime object crosses the private scalar seam. |
| Orchestration regression | `test_validation_orchestration.py` runs bash/PowerShell Full through PATH shims for python/alembic/Ruff/mypy/git. Only the disposable-target stdin guard uses real Python; it does not connect to DB. | This is not nested Full. It proves exact order, bounded replay and failure propagation. One shim trace contains at most one nominal pytest command. |
| Narrow real migration compatibility | `test_automation_foundation.py::test_postgresql_tests_followed_by_migration_validation_succeed` runs the3 PostgreSQL transaction tests then real Migrations; the missing-application-tables test runs Migrations before/after its deliberate partial schema state. | Repeated small transaction/migration operations establish sequence/recovery behavior. They are not complete-suite recursion or safely removable merely because ordinary migration/transaction tests also run. |
| Explicit ReadOnly/Security/Privacy/Focused/PostgreSQL gates | Current same-source subsets also covered by ordinary default collection. | Real duplicate test invocations, but retain their safety/sequence contract now. Their measured cost is small; optimization here cannot close the principal time gap. |

Manifest comparison was read-only JSON set arithmetic:142+19+88=249 unique
historical node IDs, all pairwise intersections zero. The current W1 collection log
contains per-module counts rather than exact node IDs, so it cannot be used to
claim a measured parent/child node-set intersection. The36 renamed bodies and
explicit wrapper source establish the structural separation described above.
No semantic duplicate removal is approved by this audit.

Sources: [historical harness](../../tests/retired_execution_harness.py),
[wrapper and AST mapping](../../tests/test_retired_execution_snapshot.py),
[pinned extraction/bounds](../../tests/retired_snapshot.py),
[producer fixture](../../tests/retired_producer_fixture.py),
[orchestration tests](../../tests/test_validation_orchestration.py),
[actual migration compatibility](../../tests/test_automation_foundation.py),
[CI](../../.github/workflows/ci.yml), [shell wrapper](../../scripts/validate.sh).

## Measured Durations And The90-Minute Gap

| Observation | Exact retained result and duration | What it establishes |
|---|---|---|
| Earlier primary suite,2476b87 |4881pass/77skip/3fail,4961 total;6198.77s =103.31min; overall Full6383.57s =106.39min. | Already798.77s over90min before the later historical additions. This is a local, shared-host run, not hosted timing. [Timing ledger](../inlet-validation-timing-20261007.md). |
| Historical original142 |139pass/1skip/2fail,1570.06s reported terminal (JUnit1570.036s); outer wrapper1603.51s. | Approximate parent/extraction/collection/startup difference33.45s for that observation; do not add parent and child times together. Original failures retained; narrowly repaired two browser nodes later36.81s. |
| Historical UI supplement19 |19pass,410.44s. | Distinct child set. |
| Historical forward88 |85pass/2skip/1fail,1080.84s. | Distinct child set; unknown-response reason remains unproved. |
| Three earlier child durations |1570.06+410.44+1080.84=3061.34s =51.02min. | Arithmetic critical-path contribution if serialized under comparable conditions, not a measured fresh combined run or a forecast. Leaves only38.98min of a90-minute aggregate for all current tests/overhead. |
| Explicit current gate observation,6a3b0f1 |PostgreSQL3pass3.60s; ReadOnly75pass6.60s; Security99pass5.42s; Privacy14pass2.09s; Focused43pass42.05s; orchestration43pass18.00s. | Reported pytest times sum77.76s; runner start/end span about90.22s including startup. These are separate gate observations, not aggregate timings or unique acceptance counts. |
| Active frozen W1 observation |Started2026-10-08T23:48:43.958618Z; at2026-10-09T01:26:51Z still nonterminal, log at84%, first historical child active. Elapsed approximately5888s =98.13min. | Local continuation already exceeds hosted step cap; no terminal total or attribution. Original-batch provenance file mtime01:20:31Z is91.79min after aggregate start, not an exact process/test timing. |

Historical raw [original](../../../inlet-evidence/20261008/retired-compatibility/original-historical.xml),
[outer](../../../inlet-evidence/20261008/retired-compatibility/original-outer.xml),
[supplement](../../../inlet-evidence/20261008/retired-compatibility/ui-supplement.xml),
[forward](../../../inlet-evidence/20261008/retired-compatibility/forward.xml), and
[ledger](../inlet-retired-execution-compatibility-20261008.md) preserve failures.
Gate [results](../../../inlet-evidence/20261008/w1-aggregate/gates/results.json)
and individual XML/logs give exact selections. Their277 testcase occurrences
cover173 unique `(classname,name)` pairs:104 repeated placements across named
invocations, not104 missing assertions. Examples: ReadOnly/Security intersect74,
Focused/Security15, Privacy/Security13. These subsets are also ordinary current
suite tests. Removing required gate commands needs a separately reviewed contract;
the observed cost does not justify prioritizing that over long-path partitioning.

W1 [recorded start](../../../inlet-evidence/20261008/w1-aggregate/aggregate.started.json)
explicitly says local continuation does not reproduce CI timeouts and uses local
Node24 versus hosted Node22. All observations above leave W1 unchanged. File mtime,
progress percentage and case duration are not evidence of the underlying cause of
any failure or proof of host contention. The earlier shared-cgroup sample averaged
1.70 cores on4-core quota with0.215s throttling over1106s, reclaim events but no OOM;
it does not prove CPU saturation. No snapshot extraction hotspot is established.

## Concrete Bounded Proposal — Review Before Implementation

1. Preserve the existing default full local pytest behavior. For a future reviewed
   CI run, partition execution explicitly: current-runtime jobs plus a three-entry
   historical matrix, each invoking only its exact existing wrapper node. Each
   historical job gets its own PostgreSQL service/database, browser/media/dependency
   prerequisites, existing1800s child/output bounds, unchanged manifests, pin and
   narrow asset plugin. Do not run all three wrappers again in every current shard.
2. Current-runtime selection excludes only the three wrapper nodes that the required
   historical jobs execute. Keep the AST/coverage-map validator and current lifecycle
   producer tests in the current group. A collection/provenance gate must prove
   disjoint union equals original exact collected parent node set; no silent skip,
   xfail, missing DB backend, browser fallback or new missing-prerequisite allowance.
   Child nodes remain validated against their own249-node manifests, separately
   from the three parent wrapper identities. Preserve failure exit status.
3. Separating historical jobs alone is insufficient evidence of90-minute feasibility:
   earlier current primary suite already exceeded90min. After the existing W1 run
   terminates, use its JUnit per-case durations to propose a small number of explicit
   current file-level shards, balancing measured costs rather than guessing from
   source size. Preserve every parameter/backend and fixture isolation. Give each
   shard an independent disposable database; do not introduce xdist/shared-DB
   concurrency or reuse mutation-prone ORM/session/authority fixtures. Exact setup/
   call/teardown profiling remains needed before changing fixture construction.
4. Keep Ruff, mypy, bundle/browser/media checks and all existing safety/migration
   gate commands. A final required `Validation` result depends on every partition
   and fails for any failed/cancelled/missing result. Artifact retention must include
   each parent and historical JUnit/provenance/terminal log with unique paths. Update
   the existing orchestration tests to assert this exhaustive fail-closed contract,
   not merely delete their single-aggregate assertions. Repository required-check
   naming/release policy needs review before workflow changes.
5. Qualify the proposal in a bounded local orchestration/collection proof first;
   do not launch another Full or hosted retry merely for this audit. The one active
   immutable W1 must finish and keep its actual failures. A later approved validation
   can demonstrate complete preserved coverage and measured job durations. Until
   then, there is no claimed saving or all-green result.

## Setup Opportunities Not Yet Qualified

Current per-case full schema creation, immutable snapshot extraction per batch,
real HTTPS/browser/media setup and genuine producer graphs repeat work. Existing
measurements do not isolate their costs or prove cached/reused state equivalent.
The original batch's roughly33s outer overhead is much smaller than its1570s child
runtime and includes more than extraction. Do not replace real native adapters,
archive/privacy/restore behavior, independent-session races or genuine consent
history with DTOs/stubs/rollback-only fixtures for speed. An immutable extraction
cache or shared database template would need its own digest, isolation and cleanup
proof before any implementation. These are profiling candidates, not approved
optimizations or evidence that contention caused the known failure.
