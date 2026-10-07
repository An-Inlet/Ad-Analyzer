# Proposed Session-Bound Candidate Selection And Provenance

Status: proposed shared contract; no implementation changes to frozen PR191.
Reviewed code:83e136220774dec6048dd26cd1f13cdd7610186b.

## Concrete Gap

The manual customer path already discovers `TargetCatalog`, lets the customer
choose `TargetOption.identifier`, and prepares exact optimization review. The
candidate queue accepts a fully assembled server `CandidateWork`; no application
producer currently assembles it from a current mandate, goal, catalog, source
fence and registered policy. Thus automatic read preparation/target selection and
durable selection provenance are missing code, independent of live exposure proof.
The old `app/learning/decision.py` acceptance-history tie-breaker is not mature
performance evidence and must not become directional spending policy.

## Narrow Next Package

Implement a server-only, explicitly called session-bound batch planner and
non-emitting enqueue path. Reuse current `TargetReader` and actual provider
current-state adapters. No periodic registration, mutation transport, approval,
reservation, grant, new numerical policy, ranking by inferred performance or
logout-independent authority.

Inputs from caller: current `CustomerPrincipal`, exact mandate binding and
registered candidate policy identity/revision. Account IDs, native IDs, target
sets, goal/source/privacy fences, numerical policy and catalog evidence must be
resolved on the server. Runtime factory remains None.

Proposed typed ports:

- `CandidatePolicyRef(policy_id, revision)`.
- `SelectionReadRequest(account, mandate, goal_id, goal_revision, goal_digest)`.
  Existing `TargetRequest` is the catalog projection of this request.
- `CandidateSelectionRuntime(candidate_runtime, catalog:TargetReader,
  source_fence_reader, clock)`. The source reader accepts the exact owned request
  and returns current `SourceFence`; no learning/exposure qualification is implied.
- `CandidateSelectionProvenance`: version, method literal
  `exact_mandate_native_owner_v1`, full mandate/goal/account binding, catalog
  canonical digest, option identifier, state digest, native-owner key, exact full
  affected-target digest, policy/source digests, observed/expiry and environment;
  actor ID is attached from session, not caller JSON. `authority=none`.
- `CandidateSelectionBatch`: deterministic selected entries and explicit blocked
  account/reason entries, bounded counts and manifest digest; never `dispatch_ready`.
- `plan_candidate_reads(db, principal, binding, policy_ref, runtime)` rechecks
  current authority/source after catalog I/O and returns the complete batch.
- `enqueue_candidate_selection(...)` recomputes/revalidates the batch and queues
  exact selected entries. No browser-supplied batch proof accepted.

## Selection Algorithm And Bounds

Read all current accounts already in the consented mandate (existing max20), each
catalog complete with existing max50. Reject truncated catalogs. Only states with
an exact approved full target-set digest, current owned account/generation,
currency/period, complete supported native topology and confirmed goal can form
read work. This is structural scope eligibility, not spending qualification.

Select the exact native budget-owner target only. If the catalog only offers
children under a campaign-owned budget, record `native_owner_option_unavailable`;
never synthesize an unobserved owner or select one arbitrary child. Duplicate
owner entries with contradictory snapshots block that owner. Identical owner
entries deduplicate by exact account/native-owner/state commitment. Sort by stable
account/native-owner identity solely for deterministic processing; this is not
performance ranking or action preference. No target outside mandate consent is
selected; no widening of the existing single target-set digest contract.

Unconfigured numeric policy and unqualified learning may still yield read jobs
whose eventual decision is explicitly blocked, matching PR191. Selection does
not transform `operational_as_of`, association-only v3, diagnostic inventory or
acceptance history into mature learning.

## Persisted Provenance Without New Tables

Add a strictly versioned `CandidateWorkV2` document with selection provenance;
retain existing CandidateWork v1 bytes/digests and allowlist it as historical
input. The existing job JSON/input_digest columns can store either version.
Use one discriminated parser in service/export and bind v2 provenance to every
scope/policy/source field. The compiler and CandidateDecision v1 remain unchanged.
No migration required for this additive JSON version, and no edits to pending0064
feedback models/hooks. A separate committed interface will precede dependent API
or inventory-adapter work.

Atomic batch admission should not call the current committing `enqueue` in a
loop. Extract a noncommitting owned insert helper; keep public v1 enqueue behavior
unchanged. After all bounded reads, reacquire workspace/session then sorted
ledger/source locks, revalidate the entire selection and fresh time, insert all
jobs and commit once. Failed revalidation admits none. If a batch is intentionally
partly blocked structurally, return those explicit reasons and persist only exact
selected entries from the same validated manifest.

## Acceptance

Actual mocked Google/Meta/TikTok catalogs→server selection→persisted v2 job→current
candidate read→non-authorizing result; no provider mutation/reservation/approval.
Changed catalog, target topology, scope/generation, source/privacy epoch, policy,
mandate, role or original session during reads/lock waits must block admission.
Verify owner-only selection, stable ordering/dedup, bounded/truncated inventory,
foreign account rejection, manifest tamper rejection, whole-batch rollback,
idempotency and exact old v1 hash preservation/export compatibility. Current
source/receipt/privacy erasure applies unchanged. Factories stay None.

## Still Deliberately Missing

This closes structural candidate assembly and selection provenance only. Genuine
performance-qualified direction, exposure/terminal/replacement sources, numerical
decision policy, automatic emitting scheduler and separately consented long-lived
worker authority remain independent engineering/policy work. It does not complete
automatic advertising optimization and does not require pretending those sources
are merely awaiting credentials.

## Implemented Successor

The implementation uses explicit `wid` beside the existing mandate binding (that
binding does not itself contain a workspace ID). `SelectionReadRequest` wraps the
existing `TargetRequest` and exact mandate. `CandidateWorkV2` is a separate strict
model; `parse_work` discriminates v1/v2 without modifying v1 bytes or digest rules.
The export adapter uses the same parser. No schema migration is needed.

Catalogs are read twice around source observation and compared by canonical
content commitment (excluding separately checked observation timestamps). All
provider/storage I/O precedes final workspace/session/ledger/source locks.
Final clock sampling rejects an expired catalog after those locks; current
candidate source fences and policy/session checks run again before atomic insert.
The subsequent read worker compares the current observed state digest to the
persisted v2 selected state before saving any suggestion. No provider CAS exists:
external edits after the last read can still happen, and this non-emitting layer
cannot claim otherwise. A mismatching fresh worker state blocks the suggestion;
future execution must independently repeat its own admission and exact review.

Only the actual observed native owner matching the mandate's complete target set
is selected. Stable ordering is deterministic bookkeeping. Missing owner options
and contradictory owner observations yield explicit blocked entries. Rollback
removes even an already flushed candidate insertion; v1 standalone enqueue retains
its original commit behavior. No queue rows create optimization attempts,
reservations, approvals or provider mutations. Factory remains None.
