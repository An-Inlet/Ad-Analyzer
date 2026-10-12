# Bounded Concurrency Harness Preparation

Branch `codex/inlet-w1-followup`, committed head
`f8107a9c5f60accb5e73e6d9fa82a5b4e33021dd`. This preparation is uncommitted.
It adds test infrastructure, not production behavior. No external/provider/live,
credential, push, PR, hosted CI, merge, deployment, advertising or spending operation
was performed. V3 is the default; V6/V7 remain technically selectable and release-unqualified.

## Prepared Harness

`tests/planning_concurrency_harness.py` enumerates exactly 18 scenarios:
small/large declared workloads × same key/different keys/distinct workspaces ×
0/50/250-ms nominal arrival offsets. The client-ready barrier and stagger wait both
end before the HTTP callback, authentication or authority refresh. Actual arrival
records are retained. Workers never wait for peer preparation, a winner's lock, or
an observer query. Both callback outcomes are collected even if the first raises.
The 120-second future timeout does not bound executor shutdown; the external
900-second process-group runner remains the final case bound.

The passive observer requires a separately preopened PostgreSQL connection. It
samples asynchronously. Each backend observation is bound to the save epoch and
original final-fact ordinal active when that worker starts SQL. Final-save overlap
counts only when both save scopes and PID/epoch mappings remain unchanged across
the observation query. Earlier, stale, replaced or unrelated bindings count only as
incidental blocking. No request performs extra observer SQL or waits for overlap.
Partial listener installation, thread startup, joining, listener removal and recording
have independent cleanup handling; observer failure cannot mask an existing failure.
Incomplete observation blocks acceptance. This observer has microtest evidence, not
yet a live disposable-PostgreSQL concurrency qualification.

The HTTP contract helper requires exact same-key replay, one success plus the precise
head conflict for different keys, and two correctly scoped successes for distinct
workspaces. Unexpected authority expiry is never an acceptable conflict. These HTTP
checks do not substitute for the required SQL/receipt/export/financial assertions.

`tests/planning_release_evidence.py` is an opt-in pytest plugin covering the whole
setup/call/teardown protocol. It retains fixed stages, response statuses, generation,
preparation, lock/save spans, original fact ordinals/ages and guard phases; no raw
request/response bodies, identifiers, credentials or exception messages. First-failure
reports are durable, including fixture setup and teardown failures. The existing
expiry test now records authority age and phase immediately before its unchanged
six-second deliberate delay when this plugin is enabled. That pre-delay behavior
is microtested; no new V6 negative-control acceptance case was run in this package.

## Checks Actually Run

Evidence is under `/workspace/inlet-evidence/20261012`.

- `release-harness01`: Ruff passed; mypy found nine annotation/re-export issues.
  Remaining checks unrun. Corrected subclass context typing and explicit symbol
  access; the failed attempt is retained.
- `release-harness02`: four statics passed: Ruff, mypy across 1,608 files, exact
  collection and diff check. All **40 microtests passed**: 13 existing evidence
  tests and 27 scheduling, lifecycle, attribution and response-contract cases.
  All 1,926 source hashes verified. Manifest
  `3309a9008fbfdd95830b8b7b9b1754bd142765dd37c7d75f69f76f1a6500a61f`.
- `release-independent-v501`: the exact previously unrun PostgreSQL V5 node
  `tests/test_creative_retained_dispatch.py::test_actual_generic_v5_viewer_unpaid_complete_witnesses[postgres-1]`
  **passed once**, original exit 0, 15.187-second process duration. Setup/call/teardown
  reports passed; complete recorder evidence, clean observer/process cleanup and
  all 1,926 source hashes were verified. Manifest
  `36257fdfaf4b3b74a97cc0cdb341f8bc2fc237c1ef33b19a9df0fd9f4de58ef3`.
  This standalone retained-history fixture performs no V6 generation: its recorded
  generation-worker states correctly remain `not_started`. It supplies independent
  V5 evidence, not V6/concurrency acceptance.

Independent review closed microqualification and the single V5 invocation, including
source/manifest/runner identity and first-invocation evidence checks. The original
**61 passed / one failed / one unrun** remains the historical failed qualification
snapshot. The independent V5 pass and earlier **25 focused passes** are separate
results; neither removes or explains the original V6 failure. Incident
`INLET-REL-20261012-01` remains open. No unchanged green retry occurred.

## Prerequisites At The Earlier Harness Checkpoint

The subsequent implementation and first recorded runtime blocker are documented in
[v6-matrix-preflight-blocked-20261012.md](v6-matrix-preflight-blocked-20261012.md).
The list below preserves the earlier checkpoint, not the current implementation status.

**No matrix acceptance cases were executed.** The independent review found the
request patterns valid, but the current fixture cannot yet support the complete
matrix without altering the workload or shared configuration during requests.

1. **A validated larger combined workload is missing.** The existing owner fixture
   has one Google account, three native campaigns, three ad groups, two budgets,
   one shared owner with two campaign members, one owner intent/scenario allocation,
   one uploaded image, 61 aggregate days and 61 selected campaign-day rows. It has
   no size parameter. Declare and build a larger supported envelope with exact
   campaign/owner/day/capture/fact/receipt/image counts and serialized document bytes.
   Independent caps (200 affected campaigns, 20 owners/accounts, 30 images, 256-KiB
   owner witness and 1-MiB document) do not prove their combination is valid. Do not
   label an arbitrary combination the maximum supported workload.
2. **Stable independent-workspace fixture construction is missing.**
   `prepare_q16_basis` hardcodes slug, shop domain and login identity; `native_account`
   and the owner-discovery chain hardcode native identity and replace encryption,
   transport and runtime configuration. Add a namespace/configuration interface
   through `q16_fixture.py`, `selected_q01_q02_fixture.py`,
   `creative_common_basis_fixture.py`, `google_budget_owner_discovery_fixture.py`,
   `google_budget_input_fixture.py` and `owner_review_runtime_fixture.py`.
   Construct both workspaces and separate owners before opening clients. Use one
   shared, immutable offline routing/configuration and media-store setup for all
   requests. Calling the existing builder twice is not valid isolation evidence.
3. **Actual matrix assembly and assertions must be wired to those fixtures.**
   Bind the 18 descriptors to exact PostgreSQL nodes, plus separately specified
   sequential SQLite parity, unchanged expiry/revocation controls and the
   complete-to-partial journey. Verify real version/receipt counts, exact stored and
   exported document equality, financial/provider invariants, preparation cleanup,
   and independent-workspace ownership. Do not replace planners, repositories or
   authorization in those acceptance cases.
4. **The final execution manifest needs a fresh independent gate.** Pin actual
   PostgreSQL/pool/timeouts, observer connection/query timeout, CPU/memory limits,
   workload counts/bytes and supported arrival tolerances. Require final-save overlap
   for the four simultaneous same-/different-key cases; missing overlap is an
   explicit coverage failure without retry. Enforce a 60-minute package ceiling,
   900-second per-case process bound, one heavy slot, workspace ≥1 GiB, tmp ≥2 GiB,
   runtime headroom ≥512 MiB and diagnostic/browser launch headroom ≥1,536 MiB.
   Stop at the first unexpected result, expiry, nonzero exit, incomplete evidence,
   cleanup/resource/source failure or missing required coverage; preserve both
   outcomes, original exit/XML and every unrun node.

These are concrete fixture/assembly prerequisites, not a request for broader
profiling or weaker deadlines. No new owner decision is needed to implement them.
The matrix must not run against the current single-workspace fixture under a
misleading large or independent-workspace label. Pending HTTP work, migration 0094,
source/security deadlines and the reconnect-retention decision remain unchanged.
