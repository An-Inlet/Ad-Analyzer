# Generation Whole-Cost Assessment

## Outcome

The actual configured PostgreSQL HTTP/browser workflow passed once with a reviewed,
worker-specific sampling observer. The complete final generation phase took 3.976392
seconds wall time and 2.968357 seconds of worker CPU. This phase begins after the final
identity refresh and includes transaction entry, repository work, response construction
and transaction exit. It does not meet the proposed two-second engineering target.

No application optimization was made. In particular, the rejected current-scope
40-millisecond query fast path is not implemented. No largest *safely removable* cost
has yet been established. That is an evidence limitation, not a finding that all
meaningful savings are impossible or conflict with required semantics.

The architectural target is the repeated source-read/validation pipeline as a whole,
not another isolated catalog decoder or redundant-scope-query contract. The observed
final source checks plus retained capture account for 3.537841 seconds wall and
2.598163 seconds worker CPU in disjoint outer spans. Both include ORM work, pure
validation, hooks, fresh authorization/privacy checks and database work. These are not
all removable costs. No lower bound or performance guarantee follows from one run.

This assessment supersedes the narrow next-package recommendations in
`generation-critical-path-assessment-20261012.md` and
`generation-scope-query-contract-20261012.md`; their evidence remains valid within its
original limits. No additional speculative micro-optimization is authorized by this
assessment.

## Exact Checks And Evidence

Branch `codex/inlet-w1-followup`, source HEAD
`5b21e0b2793e0efc214655e01fe9dc564eba8276`. The pending HTTP work was included in the
1,916-source frozen inventory, remains uncommitted and is not release-qualified.

Evidence root:
`/workspace/inlet-evidence/20261012/generation-worker-sampling01`.

- Manifest: `385220126b7763496f8259a18f8bcb9a6e2bccc194bd068a7946c952ab59a522`.
- Observer: `8412b11531452b6056e147b571303c58b74d9c74e0a6502ff24583afcdc7c0f1`.
- Runner: `92afed5526fe4927d7debb307c895f8b8a7207fb2fa6a13025c92abfbdc04d76`.
- Profile: `53e86382f8f22c73caffa3fb6194de9be5067ab576155f2d41e82960622418b5`.
- Timing report: `dfe0c534bf0b2db809bcef14d4f6d6e162c1a7368e6eb7ca0b8c28ff2a8501d6`.
- Checked summary: `whole-cost-summary.json` in that root.

The one exact executed node was:

```
tests/test_google_budget_http_admission.py::test_assembled_http_observation_browser[postgres]
```

Original exit 0; exact JUnit identity passed; process duration 79.481462 seconds.
The runner verified original Git/source state before and after execution, no resource
interruption, no kill escalation and no remaining process-group members. The report
contains 365 complete returned frames, no expiry, no observer error, no truncation and
complete restoration. Both repository save and generation returned.

The normal/raising-body microfixtures prove worker selection, exclusion of a concurrent
foreign marker, accounting and cleanup. Additional fixtures cover a failing observer
CPU clock and an incomplete-join branch. Sources and results are preserved in
`worker_sampler.py`, `check_worker_sampler.py` and `worker-sampler-microfixture04.json`
under `/workspace/inlet-evidence/20261012`. Independent preflight required and verified
unconditional shutdown before observer clocks/exports, a bounded join, rejection of
live mutable sample data after incomplete cleanup, and exclusion of post-stop samples.

Resource floors were unchanged: browser launch reserve 1,536 MiB, runtime headroom
512 MiB, workspace free 1 GiB, scratch free 2 GiB, execution bound 900 seconds. Launch
was held below reserve. Releasing clean page-cache copies of task-owned evidence files
recovered reserve without changing/deleting files. The first attempt targeted
`/tmp/inlet-root-mypy` and produced no measured improvement; the second targeted task
evidence files. They are recorded in `sampler-cache-release01.json` and
`sampler-cache-release02.json`. The runner rechecked
reserve immediately before launch. This does not establish production capacity.

No Ruff, mypy or wider application regression suite ran for this source-unchanged
observer diagnostic. This documentation receives `git diff --check` separately.

## Whole-Phase Attribution

These are directly measured intervals on the worker. Nested rows are nonadditive;
final source checks, retained capture and storage pair are separate spans within save.
Thread CPU is measured directly, never allocated proportionally from stack samples.

| Scope | Wall seconds | Worker CPU seconds |
| --- | ---: | ---: |
| Entire generation invocation | 12.923151 | 10.154204 |
| Pure preparation before final refresh | 1.161533 | 1.152338 |
| Final refreshed phase through generation exit | 3.976392 | 2.968357 |
| Repository save | 3.921904 | 2.920023 |
| Final source checks | 2.045556 | 1.443051 |
| Retained-source capture | 1.492285 | 1.155112 |
| Storage pair | 0.160946 | 0.160769 |

The final phase minus repository save is approximately 0.054488 seconds in this
observation, including transaction entry/exit, response construction and observer
boundary overhead. It is not an isolated transaction-hook measurement. Save minus the
three disjoint child spans is approximately 0.223118 seconds; that residual includes
its other guards, bindings, writes and bookkeeping, not exclusively Python overhead.

The sampler recorded 1,047 worker stack samples with 725 distinct stacks and 285 code
labels. Requested interval was 2 ms; actual p95 gap was 9.43 ms and maximum gap 90.86 ms.
Unassigned startup was 12.89 ms and tail 2.45 ms; one post-stop sample was excluded.
The 3.961049 seconds assigned to sampled intervals plus these gaps equals measured
phase wall time. Exclusive estimated stack occupancies sum to assigned time; inclusive
occupancies overlap. The sampler retained bounded code labels/ordinals only, never
locals, arguments, SQL, row values or frame objects.

The largest inclusive application stacks traverse `final_sources`, selected paired
rechecks, selected reporting pins and retained-source capture. Leaf samples are heavily
concentrated in psycopg calls. They cannot establish database CPU or network wait:
Python sampling is GIL/scheduling-biased, and native execution retains the enclosing
Python frame. In particular, it would be incorrect to classify roughly three seconds
of sampled psycopg occupancy as three seconds of removable database wait when measured
worker CPU itself is roughly three seconds. Individual model/ORM function rankings are
hypotheses only. Raw timestamps, proportions, elapsed-weighted estimates and explicit
limitations are preserved in the profile, not promoted to exact execution times.

Earlier query diagnostics counted 2,385 cursor executions per save. That count is from
a different instrumented run and must not be combined with these timings to manufacture
per-query costs. Together the observations justify examining the complete repeated
read/validation pipeline; they do not justify removing its dynamic checks.

## Preserved Failed Profile

`generation-whole-save-profile01` remains unchanged and **unqualified**. Its actual
workflow exited 1 with pre-CAS `planning_authority_expired`; profile wall time was
8.235600 seconds. Its observer erroneously used `sys.getprofile()` to detect cProfile
ownership on Python 3.12.14, which uses `sys.monitoring` for this profiler. The observer
reported an error. `pstats.Stats` later disabled profiling as part of snapshotting;
that does not qualify the lifecycle accounting retroactively.

The isolated `cprofile-thread-probe.py` and its JSON result additionally prove that
this runtime's cProfile captured a foreign thread's marker. Thus that report cannot
provide exact worker-specific exclusive/cumulative cost attribution. Its failed
application outcome remains evidence, but the observer's overhead and process-wide
capture prevent a historical-cause claim. The replacement sampler changes the
measurement method; it is not an unchanged retry or a release acceptance rerun.

## Recommended Architectural Repair And Alternatives

The next implementation should treat generation as one preparation and source-read
pipeline, with shared interfaces agreed before dependent parallel work. The intended
boundary is an invocation-owned immutable generation snapshot, not a cache of mutable
Pydantic/ORM objects and not a new persisted trust token.

The current code already has `PreparedGenerationChecks`: preparation snapshots and
validates pure graphs before refresh, while `_match` reconstructs snapshots at its
consumers. Retained-source entry and nested creative contexts separately call
`PlanVersion.model_validate`, and selected pins independently perform complete repeated
reads. The proposed change must integrate those boundaries, not add another proof-token
layer beside them. It must not globally disable Pydantic instance revalidation. Measured
worker CPU includes ORM and database-driver CPU as well as pure model work; it is not
an estimate of validation-only savings.

A concrete design must establish all of these together:

1. Preparation owns bounded immutable scalar representations of candidate, inputs and
   pure source evidence before the final identity refresh. It validates the whole
   document once at a defined boundary and prepares storage bytes and response data.
   No caller-owned mutable graph, custom serializer or subtype may silently inherit
   this trust. Unsupported inputs retain the ordinary validated path or fail with the
   established semantics.
2. Dynamic acquisition still performs fresh authorized reads at required positions,
   including before/after media boundaries and complete row membership. Each returned
   scalar snapshot includes the exact workspace/account/connection/capture and privacy
   bindings. Private grant comparison stays transient and private; it is never added
   to durable snapshots or evidence.
3. Pure reconstruction consumes those owned snapshots and shares validated results
   across final source checking, retained witness construction and storage. Reuse
   requires fresh identical scalar content, including membership. It cannot be based
   on ORM identity, an unchanged parent row, or an earlier helper's success. Compare
   the aggregate cost of copying/comparing/revalidating against the current whole
   pipeline; repeated defensive snapshots can erase the benefit.
4. Preserve the exact transaction, clean-session requirements, hooks, source/error
   ordering, membership revocation, fresh privacy/goal/paid checks and original
   five-second authority fact. No renewal under locks or expired-waiter retry. Prepare
   the response before the final authority gate wherever its semantics allow, so
   expensive response work cannot sit beyond the freshness check unnoticed.
5. Cover the complete pipeline on SQLite and PostgreSQL: mutable/subtyped inputs,
   malformed retained rows, membership additions/removals, old/new ownership,
   source replacement, privacy/session revocation, custom ORM/transaction hooks,
   rollback, response construction and maximum supported cardinalities. Then run
   the actual workflow under a fresh reviewed manifest and measure the same complete
   final phase. A two-second fixture target is a proposed gate, not a promised result.

This is a proposed architectural direction, not a completed interface or proven safe
optimization. It needs the complete read-set/data-ownership design before code changes;
this diagnostic does not establish which validations can be removed. The largest
measured scopes are known, but exact removable pure-work cost remains unresolved.

A broader alternative is transactional query consolidation or a single locked source
snapshot. Removing dynamic rereads requires separately proven writer/membership
closure, including raw SQL, insert phantoms, deletion, ownership moves and parent
cascades. Migration 0094 proves its narrow commerce group; it is not an all-writer
proof. Do not mechanically add guards to every model or assume existing workspace
locks cover all writers.

A lower-risk interim alternative is to retain the V3 default and avoid activating
V6/V7 while the integrated repair is qualified. V6/V7 selectors remain technically
available; this is nonactivation guidance, not an existing technical disable gate or
release approval for V3. Increasing the identity window or renewing
identity under held locks is not an authorized repair. There is no evidence supporting
relaxing these semantics to make the diagnostic pass.

## Durable Status And Next Package

HTTP release inventory remains **57 passed / 1 unresolved**;
**INLET-REL-20261012-01 remains open**. V3 stays default, V6/V7 remain release-unqualified.
Migration 0094, prior failed artifacts and pending HTTP work are preserved. Reconnect
retention still awaits its existing owner decision. No provider, live advertising,
credential, spend, push, PR, hosted CI, merge or deployment operation occurred.

Completed package: bounded whole-phase diagnostic, preserved failed instrumentation,
reviewed worker sampler and integrated architectural assessment. Next package: a
complete snapshot/read-set design and its integrated implementation only when the
required semantics and meaningful whole-phase savings are demonstrated. Do not resume
the rejected query fast path or claim this passing diagnostic closes the incident.
