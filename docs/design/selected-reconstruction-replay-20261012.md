# Fresh Selected-Capture Reconstruction Reuse

## Delivered Change And Invariant

One final generation transaction now retains a privately owned, validated selected
capture and reuses its pure reconstruction only after freshly read scalar dependencies
compare exactly equal. This serves the repeated selected-source checks and retained
capture in the real generation flow. It does not cache currentness, authorization or
successful SQL reads.

The safety invariant is:

> A reused pure capture was reconstructed successfully from exactly the same fresh
> header, ordered fact membership/values, and referenced campaign identity/scope/native
> values in this generation's original Session, root transaction and Connection.
> Every returned graph is detached. Selection and completion are freshly read and
> validated on every call, and all outer dynamic checks remain in place.

All five historical SQL reads remain in their original order and failure positions:
header/scope, fact membership/count, referenced campaigns, selection, completion. The
pure reconstruction stays between the third and fourth reads. Only after the fifth
read's dependency validation succeeds is a new result promoted into the private
cache. No queries are combined, omitted or moved. All lock-scope, current-selection,
aggregate, private-grant, identity, privacy, entitlement, goal and media-boundary checks
remain. The five-second authority rule is unchanged.

The intended benefit is eliminating repeated JSON parsing, model validation, digest
and canonical-encoding work for an unchanged capture. In the actual workflow, twelve
historical reads performed one full reconstruction instead of one per read. This is
an implemented reduction in repeated work, not a claim that generation now meets the
two-second target or that the historical expiry incident is resolved.

## Implementation Boundary

`selected_storage._reconstruct_capture` contains the original pure reconstruction
body. `historical_capture` still performs the original SQL, scope/count checks and
fresh selection/completion validation. `selected_reconstruction` provides the lexical
final-generation scope used by `PlanningDocumentService`. Entering it does not acquire
a connection or introduce an earlier engine/transaction event. Connection binding is
lazy, after the original reads have acquired one.

The comparison includes every consumed header and fact column and complete ordered
fact membership. Campaign comparison includes its dictionary identity, row identity,
account, native campaign ID and platform; incidental DISTINCT query order is not a
dependency. Only already loaded, exact built-in scalar values are admitted. No deferred
ORM load, representation or serialization callback constructs the snapshot.

Pure results are detached before promotion and on every hit. The existing inert
selected-capture check moved into the campaign-performance layer and is re-exported
from its previous location. It admits the audited exact model/container/scalar types
and rejects undeclared/private/extra/custom state, unsafe time zones and non-inert
field-set state. Reuse also checks the audited core validators, serializers, public
model methods, class helpers/properties, declared field descriptors, consumed ORM
field descriptors and reconstruction helpers. Changed or missing supported behavior
falls back to ordinary decoding; this is not a security boundary against arbitrary
hostile Python code executing inside the application process.

Reuse is confined to the exact invocation/session/root/connection transaction. Dirty,
nested, replaced or closed transaction state invalidates the cache and falls back.
There is no persisted token, source revision claim, cross-request cache or writer-lock
assumption. Scope cleanup clears retained values on normal return and exceptions.

Optional admission limits are 512 facts per capture, 20 retained entries and 4 MiB of
conservative raw-snapshot accounting units. These units are **not total Python heap
bytes**; model structure/fact/entry bounds additionally bound retained and copied
object graphs. Larger captures, unsupported values and capacity exhaustion use the
ordinary decoder, preserving product limits and refusals. Promotion checks capacity
again after dependency callbacks, and existing keys are not replaced/double-charged.
No new input rejection is introduced by these optimization limits.

## Qualification Actually Run

Source branch: `codex/inlet-w1-followup`; pre-package HEAD:
`0c02f6e2c0a723f5a6e379ca8142c32eecf7c18b`.

Frozen qualification:
`/workspace/inlet-evidence/20261012/selected-reconstruction02`.
Manifest:
`631d9f96fe18254b71ced48009d204f47220c581f0ff5fc07eab55a13337c313`.

- Whole-repository Ruff passed.
- Whole-repository mypy passed: 1,601 source files.
- Exact test collection and `git diff --check` passed.
- Existing projection regression cases: 20 passed.
- New SQLite cases: 19 passed.
- New PostgreSQL cases: 20 passed.
- All 59 exact cases passed, without skips, with original exits, XML identities,
  source integrity and process cleanup verified by the bounded runner/finalizer.

The tests demonstrate three calls still execute fifteen SELECTs while decoding once
for both zero-fact and one-fact captures; byte-identical output; first-result and
cache-hit mutation isolation; ordinary error and SQL-position parity for explicit
loaded-row fault seams; real fact insertion/deletion and cascade handling; independent
PostgreSQL committed erasure; replaced transactions; capacity fallback; changed helper,
model method, model field and ORM field behavior; exception cleanup; no early connection
acquisition; promotion-time capacity and failed-dependency nonpromotion.

The loaded-row corruption cases are explicitly simulated after SQL loading. They do
not bypass immutable-row database triggers. Real membership changes use the actual
insert/delete paths. The independent-connection erasure case is PostgreSQL-specific;
its SQLite counterpart was deliberately not selected because that fixture uses a
shared in-memory connection. The 59 selected cases themselves contain no skips.

Attempt `selected-reconstruction01` is preserved: Ruff passed, mypy failed on seven
new-test typing errors, and all later phases remained unrun. Only those annotations
were repaired before freezing attempt 02. No unchanged retry replaced the failure.

## Actual Workflow Result And Cost

One enabled actual PostgreSQL HTTP/browser workflow passed, original exit 0:

```
tests/test_google_budget_http_admission.py::test_assembled_http_observation_browser[postgres]
```

Evidence:
`/workspace/inlet-evidence/20261012/generation-reconstruction-enabled01`.
Manifest:
`4ea86c86a85365c03a56b4d654b5e832525351ce05cadb2d3b36224c04b5bc7c`.
Observer:
`7eeec8347ebe979662dbbc053236197fd473c5df7b1eceb507d27def6eb23bb6`.
Profile:
`6c651131027c22cc474b2094734c138806f00f5bea53409aa19d0113f4b4dcee`.
Timing report:
`ec73cd84a714e929ab1029e904d6ec1db447e23ca2c480271167385e91871df9`.
Checked summary: `reconstruction-summary.json` in that directory.

| Observed scope | Calls | Inclusive wall seconds | SQL executions |
| --- | ---: | ---: | ---: |
| Full reconstruction | 1 | 0.008496 | 0 |
| Reconstruction/reuse including guards and copies | 12 | 0.027193 | 0 |
| Historical capture | 12 | 0.085683 | 60 |
| Complete final generation phase | 1 | 3.203478 | 2,385 |

Nested rows are nonadditive. The complete final phase measured 2.736942 seconds of
worker CPU and includes transaction entry, repository work, response construction and
transaction exit. Every historical read still executed exactly five SQL statements.
The final source checks took 1.432709 seconds and retained capture 1.492879 seconds;
these remain the dominant scopes. This narrow reconstruction repair does not eliminate
the wider pipeline's cost.

The observer uses local code start/return events plus a global unwind callback filtered
immediately to exact code and worker; it does not wrap or relax production decoder
guards. It retains only fixed labels/counts/times, with no arguments, return values,
SQL text or rows. The runtime rejected a local PY_UNWIND registration during an isolated
probe, before any application run; the revised supported registration was then tested
against the actual observer. Normal/raised bodies, foreign-thread exclusion, partial
setup failure, stop-clock failure, cleanup-inspection failure and a reserved foreign
tool were covered by the microfixture before independent preflight closed.

The workflow process took 80.401467 seconds. It produced 365 complete returned coarse
frames, no expiry, no observer error/truncation/incomplete restoration, and clean process
cleanup. All 1,919 frozen source hashes remained unchanged during qualification and the
workflow. Launch/runtime/disk reserves and the 900-second bound remained unchanged.
Clean page-cache release for task-owned cache/evidence recovered launch reserve without
changing/deleting files; `reconstruction-cache-release01.json` records the exact scope.

This is one instrumented fixture, not a paired speedup benchmark or maximum-cardinality
latency guarantee. No additional control run was needed to establish the concrete
12-to-1 work reduction and observed guard/copy cost. Do not subtract its total latency
from earlier differently instrumented runs or claim the two-second target is met.

## Durable Status And Next Package

This package changes application behavior and has focused verification; it is not
just test infrastructure. It does not authorize live operations or change publication,
spending, billing, onboarding or retention policy. Migration 0094 and every earlier
failed artifact remain intact. Pending HTTP work remains separately uncommitted;
only the additive generation scope in its shared service file belongs to this package.

Release inventory remains **57 passed / 1 unresolved** and **INLET-REL-20261012-01 open**.
V3 stays default; V6/V7 selectors remain technically available but release-unqualified.
No provider, credential, live-advertising, spend, push, PR, hosted-CI, merge or deployment
operation occurred. Reconnect retention still awaits the existing owner decision.

The remaining engineering gap is the larger repeated source/retained-document pipeline,
not this pure decoder. The next package must integrate the existing prepared immutable
candidate with retained-document construction, with explicit value ownership and fresh
SQL equality at unchanged observation boundaries. It must demonstrate meaningful
whole-phase savings and supported-cardinality behavior before release qualification.
Do not reopen the rejected scope-query fast path or weaken the authority deadline to
turn this passing fixture into an incident-closure claim.
