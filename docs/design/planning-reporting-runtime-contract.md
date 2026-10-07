# Planning And Reporting Runtime Assembly Contract

Proposal for root review; no implementation or runtime activation. Inspected base
`9396839`. This is a concrete full-MVP assembly package, not a recommendation-only
release decision. The source assessment is
`/workspace/inlet-design/PLANNING-REPORTING-RUNTIME-ASSEMBLY.md` (executor design
artifact). Repository contracts referenced below are the durable implementation
baseline.

## Boundary And Existing Behavior

The [initial runtime](../../app/initial_planning/runtime.py) configuration getter
and [reported runtime](../../app/reported_feedback/runtime.py) getter return
`None`. The [Meta worker](../../app/meta/sync.py) already consumes the latter;
there is no new scheduler or queue to build. Ordinary API and worker assembly,
owned credential access and an independent native read contract are missing code.

The existing [optimization catalog](../../app/publication/customer_optimization_catalog.py)
requires qualification identifiers and a financial `MoneyContext` to construct an
`OptimizationState`. Those fields must not be invented for planning. The new
read lane does not construct that state, an exposure certificate or write runtime.
Existing optimization approval/claim/handoff gates remain intact.

## Frozen Types To Implement After Review

All new committed models are frozen, reject unknown fields and non-finite numbers,
and use schema-specific canonical digests. These names are proposed public ports.

| Type | Required contents and invariant |
| --- | --- |
| `PlanningReportingProfileV1` | Schema, profile ID/revision, environment, `initial: InitialPlanningConfiguration`, `windows: ReportedWindowPolicyV1`, explicit `feedback: ReportedFeedbackPolicyV1 | None`, and `native_read: NativeBudgetReadPolicyV1`. No missing-key defaults for these fields. |
| `NativeBudgetReadPolicyV1` | Required HTTP timeout, total read deadline, maximum pages/targets, observation lifetime and credential minimum remaining lifetime. Bounds limit resource use; all selected numeric values are explicit deployment configuration. |
| `NativeBudgetRequestV1` | Profile digest/environment, exact `ExecutionAccount`, `CohortV1`, goal ID/revision/definition digest, and target derived from the current imported campaign. Account/cohort/platform identities must agree. No caller-supplied resource JSON, credential, qualification ID or financial period. |
| `NativeBudgetObservationV1` | Exact request; provider target; complete `BudgetOwnerRef` and affected target set; currency/exponent/timezone; daily or lifetime budget amount; configured/effective status, native schedule and relevant sharing/rebalancing flags; unaffected-settings digest; fixed unsupported-reason enum; started/completed/expiry timestamps. Complete topology is required for eligibility. Content digest commits every field. `spending_authority=none`, `financial_qualification=unavailable`. |
| `NativeBudgetOptionV1` | Server label, observation and opaque identifier derived from request plus observation digest. A named complete supported option is offered; incomplete collection is unavailable, never a truncated complete catalog. |
| `NativeBudgetCatalogV1` | Exact request, bounded options, observation/expiry bounds and complete collection marker. This is distinct from `TargetCatalog`/`TargetOption`; it cannot be passed to optimization execution. |
| `InitialPreviewV2` | Explicit `inlet.initial-efficiency-preview.v2`; existing baseline/observation/calibration/policy commitments and arithmetic fields, plus profile digest and exact native observation commitment. No `native_state_digest` masquerading as qualified state. Review/handoff remain unavailable and spending authority remains none. |

Profile validation requires equal environments, matching selected event, supported
query version, and (when present) feedback comparison-policy digest equal to the
window-policy digest. The currently supported feedback minimum distinct original
attempt count is exactly one; unsupported configured counts fail clearly. This is
an implementation limit, not a new audit requirement. Existing rule selection,
training/holdout, report age, window/repeat/capacity and contribution validators
remain authoritative. No 5/10/20 mapping or data-selected policy is supplied.

Proposed callable ports (type names, not executable code):

```python
load_planning_reporting_profile(settings) -> PlanningReportingProfileV1 | None

assemble_planning_reporting(
    sessions: Callable[[], Session],
    profile: PlanningReportingProfileV1,
    *, clock: Clock,
) -> PlanningReportingBundle

class NativeBudgetReader(Protocol):
    def read(self, request: NativeBudgetRequestV1, now: datetime) -> NativeBudgetCatalogV1: ...

@contextmanager
def owned_meta_budget_reader(
    sessions: Callable[[], Session],
    authorize: OriginalSessionAuthorizer,
    profile: PlanningReportingProfileV1,
    *, clock: Clock,
) -> Iterator[NativeBudgetReader]: ...

parse_initial_preview(document) -> InitialPreviewV1 | InitialPreviewV2
```

`PlanningReportingBundle` contains the immutable profile, initial runtime and
reported runtime. The initial runtime gains a separate optional native-budget
reader factory; the factory takes the original request authorizer and owns client
lifetime. Its existing `.native` legacy injection stays compatible. No principal
is cached in the bundle. The reported runtime references that same initial runtime
and exact window/feedback policies. Worker authorization continues to use the
persisted job's original session; assembly never substitutes a process owner.

## Concrete Configuration And HTTP Assembly

Add optional deployment settings `planning_reporting_profile_path` and
`planning_reporting_profile_digest`. Both absent means unavailable with no native
IO. A partial pair, malformed/oversized JSON, duplicate keys, unknown fields,
unsupported policy, or digest mismatch is a sanitized configuration error, not a
fallback policy. File size has a finite engineering ceiling. Profile contains no
secrets. Canonical digest pins the parsed profile; read once per process startup,
with no implicit hot reload. API and worker deployments must use the same pinned
profile. Persisted job policy digests still reject incompatible work; configuration
changes do not relabel existing jobs or grant retry authority.

The API constructs private sessions from its actual database bind. The shipped
`run_meta_tick(engine)` constructs them from that same supplied engine, passing
the frozen bundle into `MetaSyncService`. A pure assembly function is shared, not
a global session tied to a different engine. The FastAPI no-argument dependency
wrapper must not expose factory parameters as public query inputs.

Implement a GET-only Meta collector, factoring the bounded account/campaign/adset
wire parsing from [Meta optimization](../../app/executors/meta_optimization.py).
A neutral parsed snapshot feeds both the unqualified read observation and the
legacy adapter. The legacy adapter adds its real qualification and financial
context unchanged; golden state/preview digests must remain identical. Do not
maintain a second, divergent topology parser or inherit mutation operations into
the collector. Pagination cycles, unknown ownership, missing fields and capacity
exhaustion fail closed. Currency exponent comes from the repository's supported
currency mapping, not an assumed two decimals.

Use the concrete owned-vault/private-session pattern in
[account diagnostics](../../app/collectors/account_diagnostics.py) and
[native diagnostics](../../app/collectors/native_diagnostics.py). Before HTTP:
check original session/membership, master sync and paid-work gates, current goal,
owned account/integration/source generation and token validity. Close the database
transaction before bounded fixed-endpoint HTTP. After HTTP: open a fresh private
session, repeat authority/current scope checks, and compare the exact request.
Native source status/currency/timezone must match the owned cohort. Final consumer
read repeats current inputs before committing. Constructors open no sockets;
clients/transports close on success and error; redirects and hidden retries remain
disabled. No identifiers, tokens or provider response bodies enter diagnostics.

## Preview, Financial Boundary And Compatibility

The read observation has currency metadata, not a synthetic mandate period. A v2
nominal budget proposal still uses the real current consented mandate and preserves
existing goal/revision, exact allowed target set, currency/timezone, positive
amount, quantum, per-plan/total cap, positive-change and aggressiveness checks.
A nominal cap check is not a portfolio exposure or billed-spend guarantee. Native
observation alone cannot enable any write, automatic action or reviewed handoff.

Keep `InitialPreviewV1` serialization, digest and existing 0076 handoff unchanged.
Use version dispatch for reading/exporting new v2 rows; never parse v2 as v1. The
existing preview JSON storage may suffice, but scalar bindings and lifecycle
validators must explicitly recognize the v2 observation commitment. Do not reuse
a qualified-state field silently. If existing constraints cannot represent this
honestly, return the concrete schema delta for review before a migration.

The review bridge returns an explicit unsupported-version/unqualified reason for
v2 until a separate real qualified reread bridge is implemented. This package must
not break existing qualified v1 journeys. Reported comparison/feedback consumers
need a version-aware baseline reader while retaining their exact dependency,
expiry and original-session checks. The scheduler owns that adaptation; this
proposal does not edit its service, models or migration0078. Export/privacy
parsers must reject stale or misbound v2 documents, not drop commitments to gain
compatibility. No compounded adjusted baseline is introduced.

## File Ownership And Delivery Order

1. Freeze new contracts in `app/initial_planning/native_budget_contracts.py`,
   `preview_v2.py` and `app/planning_reporting/contracts.py`; no edits to existing
   v1 serialization. Publish exact parser/reader signatures before dependent work.
2. Collector lane: new `app/collectors/meta_budget.py`, a shared pure Meta budget
   parser and minimal legacy adapter delegation; actual HTTP and hash regression
   tests. Own no feedback service/models/migrations.
3. Assembly lane: `app/planning_reporting/configuration.py` and `runtime.py`,
   explicit settings, API getter and existing worker injection. Preserve injected
   legacy test runtimes. No new financial tables or scheduler.
4. Planning lane: native read catalog path, v2 proposal/strict parser, public named
   option projection and version-aware privacy/export/read guards. Coordinate
   reported baseline union with scheduler before touching consumer code.
5. End-to-end assembly tests and a durable ledger entry distinguishing local
   shipped wiring from live verification. Do not claim acceptance from isolated
   port fixtures.

## Acceptance Through Actual Assembly

- Boot ordinary FastAPI and shipped Meta worker using only a fixture profile file,
  low-level MockTransport/clock seams and fixture credentials in existing encrypted
  vaults. Do not override runtime dependencies or return invented native proof.
- Exercise actual owned report import/capture, chronological calibration, native
  named option read and exact v2 amount. Exercise comparison request, the real
  worker's repeated fixed windows and explained adjusted preview with version-aware
  consumer. Where an original optimization receipt is required, use the existing
  actual mocked provider journey; assembly must not manufacture one.
- Verify SQLite and PostgreSQL ownership/transactions, and authenticated browser
  projection. Every provider write remains unavailable through this bundle.
- Configuration absent means no native calls; malformed or inconsistent profile
  is unavailable/error. API/worker observe identical policy digests. Wrong engine,
  environment, profile, goal revision, original session, source generation,
  membership, master pause and account ownership fail before IO or at the fresh
  post-IO guard as applicable. Existing fixed-run disable/retry semantics remain.
- Verify account/currency/timezone/topology mismatch, cursor/capacity bounds,
  expiry during IO, transport errors and client cleanup. Preserve old qualified
  state/v1 preview hashes and 0076 handoff tests exactly.
- Verify v2 expiry/privacy deletion/export/session guards and reported baseline
  dependency invalidation. No provider finality, causal lift or exposure claims.

## Genuine Inputs And Remaining Work

Owner policy inputs before a real profile is installed: named rule thresholds and
budget step; retention, train/holdout and report ages; window/repeat/spacing and
tolerances/minimum events; feedback direction mapping, weight and clamps. Required
numeric configuration can be implemented and tested without selecting these
product values. Operational timeout/capacity settings are explicit engineering
configuration, not spending consent. Credential setup and approved live validation
are separate later steps, not permission needed for this offline implementation.

Native exposure/finality/replacement qualification and actual automatic execution
remain unfinished work; missing credentials alone do not explain those gaps. This
assembly neither relaxes them nor declares the full product complete. Keeping
work alive after the original session closes would require a separate delegation
policy; this package preserves current session-bound authority.
