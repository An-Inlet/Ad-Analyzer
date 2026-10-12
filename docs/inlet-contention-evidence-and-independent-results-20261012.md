# Contention Evidence And Independent Results — 2026-10-12

The 47 independent configured cases and all four current instrumented contention
cases passed. The recorder has 13 focused passing tests. The original uninstrumented
PostgreSQL winner expiry remains unexplained, so configured v6 is still unqualified.
These are local results, with no live-environment verification or product deployment.

Branch `codex/inlet-w1-followup`, HEAD `79f15fc5be9c00e7aec1f06ce21b25dd87a02ae4`.
This follow-up changes only test instrumentation and documentation. Application bytes
remain unchanged from the prior blocked checkpoint; earlier preparation changes remain
uncommitted. No push, PR, hosted CI, merge, deployment, provider/model/credential action,
customer advertising change or spending occurred. Default v3 remains unchanged.

## Verified Recorder

[The contract](design/contention-evidence-and-independent-gates-20261012.md) describes
the test-only recorder. It retains both request outcome slots, bounded relative
monotonic timelines, original-fact ordinals and ages at every guard, lock acquisition
including authorization, source/retained/storage/version-read phases, coordinator
subphases, thread CPU durations and shared cgroup numeric samples every 250ms.
It writes in the outer cleanup path after both workers finish, including on request
or assertion failure. No identities, payloads, SQL, backend IDs or exception text are
serialized. There are separate exact schemas for native expiry and route-conflict
events. Sampling failures cannot prevent original dispatch or replace its exception.
`body_failed` and `evidence_complete` distinguish application assertions from invalid
observation. A write failure preserves the original exception and emits a fixed marker.

13 focused tests passed: actual synchronous ASGI propagation/isolation/reset, either
request failing, final assertion failing, successful responses, original-once dispatch
and exception identity, persistence failure, output bounds/redaction, actual expiry,
clock/fact sampling failure, actual route-conflict attribution, and extra-field rejection
for both event schemas. The four parameterized outcome cases and two schema/sampling
variants account for the total. Whole Ruff, configured mypy (1,558 files), exact node
collection and `git diff --check` passed. Exact exits/XML/source hashes and 12 durable
artifacts were independently reviewed.

The first instrumented SQLite different-key case exposed a recorder defect: its body
passed with 200/409, but the parser rejected the legitimate five-field route-conflict
event. Its finally artifact preserved both outcomes, all 1,358 records and 65 resource
samples, with `body_failed=false`, `evidence_complete=false`, and one observer error.
That run remains failed with no acceptance credit; the other three cases were unrun.
The correction adds a separate strict schema and three regression cases. The earlier
import-order and typing failures are also preserved. No application assertion was
weakened and no production change was used to obtain the successor result.

## Independent Configured Coverage

The owner's new instruction superseded the earlier blanket hold on the 47-case cohort.
Independent review confirmed no same-key concurrency prerequisite and isolated fixtures:

| Partition | Passed | Coverage |
| --- | ---: | --- |
| Components | 19 | Configuration selection/defenses and retained document readers |
| SQLite | 14 | Five v6 browser journeys, three input refusals, two history cases, real pre-save expiry, v3/v4/v5 compatibility |
| PostgreSQL | 14 | Exact serial counterparts |

All 47 passed on frozen source, with SQLite before PostgreSQL. No skips, interruptions,
remaining children or source-integrity failures. Both complete-to-partial journeys
passed, including the PostgreSQL serial case that failed before the preparation repair.
74 work artifacts were copied from temporary storage, excluding browser profile/cache
files, and verified byte-for-byte. Subsequent recorder-only changes affect neither
application bytes nor these selected tests; independent source-map review retained
all 47 results. They are separate from the prior focused 59-pass/one-failure ledger.

## Current Instrumented Contention

Four original contention cases passed on the corrected recorder's frozen source.
All original publication, receipt, head, document/export, ownership, side-effect and
cleanup assertions remain. Each case has one version and generation receipt, exact
document/export agreement and distinct closed preparations. SQLite still uses sequential
transactions because its fixture shares one physical connection; no SQLite isolation
claim is made. PostgreSQL records an actual blocker relation without retaining PIDs.

| Database / Key | Responses | Winner Post-Flush Fact Age | Waiting Request Lock Acquisition Duration | Waiting Request Final Guard Age |
| --- | --- | ---: | ---: | ---: |
| SQLite / Different | 200 / 409 | 1.704470s | 0.001700s | 0.017622s at lock |
| SQLite / Same | 200 / 200 | 1.842924s | 0.001914s | 0.690590s at replay |
| PostgreSQL / Different | 200 / 409 | 2.569956s | 2.806329s | 2.828095s at lock |
| PostgreSQL / Same | 200 / 200 | 2.361759s | 2.591468s | 3.297751s at replay |

Lock acquisition durations include current-authorization SQL; they are not exclusive
server wait measurements. For same-key PostgreSQL, the lock guard age itself was
2.611267s. Guard samples bracket original checks without changing facts or clocks.
The winner's source recheck took 1.216355s, retained capture 0.909362s and total save
2.359907s. Timings overlap and cannot be summed as independent costs.

The same-key winner coordinator took 0.028948s, including 0.020480s waiting for loser
entry, 0.006683s observer connection and 0.000895s polling. Different-key coordinator
time was 0.030424s. Thus coordinator work did not induce expiry in these occurrences.
It still runs inside the winner's authority window: loser final refresh/save setup,
up to one second of event waiting, and bounded observer connection/polling can consume
material budget. The sequencing was measured, not redesigned. Its possible contribution
to the historical failure is neither proved nor ruled out.

All four evidence files report complete observations, no drops/unbound samples/observer
errors, balanced per-worker spans and guards, unchanged fact identity across each guard
bracket, and restored observers/stopped workers/sampler. Shared CPU throttle and memory
event counters had no increments. These shared counters do not exclude scheduling or
resource contention and establish no capacity or dependable deadline-margin guarantee.

## Evidence And Remaining Risk

Evidence root: `/workspace/inlet-evidence/20261012/`.

| Packet | Manifest SHA-256 | Result |
| --- | --- | --- |
| `prepared-contention-observer03` | `c8e0d06b609808ac55dc8c23653a3d53a6eb2cbd0a31aed104caa04f9dce87f4` | Original ten recorder tests passed |
| `prepared-independent-configured01` | `a09a90dd3dfa46db8d14aa31969c867834dd1a0a36113c7230815f7a1d998aab` | 47 independent passes retained |
| `prepared-contention-instrumented01` | `12cd553f5f911cb6f21a7479c04f2c6801f2ba8543a73999f6ba283c995e0838` | One observer-integrity failure; three unrun |
| `prepared-contention-observer04` | `e9e88cd3bddf5357fbd14c4d2d15881d7f9b9713dd687ede20b618f22717b77d` | 13 recorder tests passed |
| `prepared-contention-instrumented02` | `9527c4b1260cb0f04105bc7d415d29ace3f24821186e1163c61aa7a68402da42` | Four current instrumented contention passes |

Each execution packet has original logs/exits/XML/resource and source checks. Relevant
packets include durable-outcome indexes; instrumented02 also includes the derived
`measurement-summary.json`. Failed predecessors remain intact. Independent review
closed recorder, 47-case retention and current contention evidence, not qualification.

The known failure in this follow-up was an observer schema defect, now specifically
covered. No fresh application failure was observed in the 47 serial or four instrumented
contention cases. The remaining product risk is unexplained intermittent generation
refusal under contention, with a hard five-second freshness requirement. Earlier
controlled expiry/revocation tests verify refusal and rollback behavior. Current passes
do not explain the original winner's unrecorded phase or justify blaming resources,
changing the deadline, renewing facts under lock, or removing source/ownership checks.
No further behavioral repair is inferred. Overall qualification remains withheld.

The next causal investigation can use the verified recorder rather than lose both
outcomes on failure. Any deliberate contention/load experiment or coordinator redesign
needs a bounded contract that distinguishes induced deadline exhaustion from product
failure. Do not repeat unchanged acceptance merely to accumulate green results.
