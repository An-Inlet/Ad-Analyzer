# Bounded V6 Concurrency Release Qualification

Proposed future release evidence, not an execution request or a retrospective-cause
experiment. V6 stays default-off and unqualified. INLET-REL-20261012-01 remains open.
No execution in this package; review this exact contract before reserving a heavy slot.

## Fixed Workload And Setup

Use the configured customer route, actual composition, PostgreSQL transactions and
original session/connection/entitlement/privacy/receipt behavior. Inject only offline
identity/provider/media fixtures; never override the planner or repository. Freeze
commit, dependencies, environment limits and exact node IDs before starting. Retain
current synthetic database/export fixtures, including the complete-to-partial journey.
Run SQLite semantic parity first; do not claim SQLite concurrency isolation.

Use small and largest currently supported bounded owner fixtures, with exact campaign,
day, receipt and creative counts declared in the manifest before execution. Do not
choose smaller fixtures after failure. Pin PostgreSQL version, pool size and timeouts;
record CPU/memory allocations and database settings. Qualification is limited to those
recorded bounds. If the intended deployment's bounds are unknown, retain that release
gap rather than call an arbitrary local environment production-representative.

Proposed finite matrix: two fixture sizes x three patterns x three fixed arrival
schedules = 18 scenarios. Patterns are two same-key requests to one workspace, two
different-key requests to one workspace, and two requests to distinct workspaces.
Schedules are simultaneous client release, second arrival after 50ms, and after 250ms.
Run each scenario once; no adaptive retry, additional seeds or soak extension. HTTP
start barriers occur before final authorization. Preopen any observer connection and
sample blocking asynchronously; no winner-held wait for the other client or observer.
Such a harness change needs focused evidence that assertions and overlap observability
remain intact. It is not a product repair. Do not require a blocker for deliberately
staggered requests that naturally finish without overlap; classify and retain overlap.
Designated simultaneous same-/different-key PostgreSQL scenarios must demonstrate
actual lock overlap or leave an explicit concurrency-coverage gap, without retries.
Pin expected-head/request-key setup and exact SQLite parity/negative-control node
counts alongside the 18-scenario manifest before execution.

## Assertions And Evidence

Use the verified bounded recorder for both outcomes and every original guard. Preserve
original fact identity, one final refresh, unchanged five-second authority deadline,
request/response status, version/receipt counts, exact document/export agreement,
ownership isolation, financial invariants and closed preparation/worker/sampler state.
Same-key successes must replay exactly with one receipt/version; different-key same-head
competition must retain exactly one winner and the expected conflict. Distinct workspaces
must both complete without shared-state contamination. Unexpected expiry in these normal
workloads fails the package; do not recategorize it as an acceptable conflict.

Keep deliberate six-second lock expiry and session revocation as separately labeled
negative controls, not success-workload samples. Their existing exact refusal and
rollback assertions stay unchanged. Report each duration/fact age, overlap and resource
measurement; this small matrix provides no statistical availability or p99 guarantee.

## Stopping Conditions And Disposition

One heavy slot; workspace >=1GiB free, tmp >=2GiB free, cgroup headroom >=512MiB.
Use the bounded process-group/subreaper runner, maximum 900 seconds per scenario and
a predeclared 60-minute whole-package ceiling. Stop at first unexpected assertion,
nonzero original exit, resource-floor breach, timeout, incomplete evidence, worker
leak or source drift. Persist finally artifacts, exact original exit/XML and unrun IDs.
No ignored failure, weakened assertion, deadline extension, fact renewal under locks,
smaller replacement fixture or automatic rerun. Observer failure also blocks acceptance.

A failure leads to source/evidence review and a concrete causal repair proposal or
specific remaining gap. A completely passing matrix permits only review of this
bounded workload. It does not explain or automatically close the historical incident,
authorize activation, or replace broader default-path, security, live integration and
human release gates. Further load/capacity evidence requires a separately scoped plan,
not an open-ended continuation of this one.
