# Planning Customer Service/API Interface — In Implementation

Concrete request DTOs: `app/planning_documents/requests.py`. Freeze for dependent UI,
with implementation/results not yet qualified. Base prefix
`/api/customer/v1/workspaces/{workspace_id}/planning/plans`.

| Route | Input | Successful result |
|---|---|---|
| POST base | CreatePlan | `InputResult` (exact immutable input) |
| GET base | bounded cursor/limit | `{items:[PlanSummary],next_cursor}` |
| GET `/{plan_id}` | none | current PlanReadResult |
| POST `/{plan_id}/inputs` | EditPlan | `InputResult` (exact immutable input) |
| POST `/{plan_id}/generate` | GeneratePlan | `VersionResult` (exact immutable version) |
| GET `/{plan_id}/versions` | bounded cursor/limit | `VersionPage` of exact immutable VersionResult |
| GET `/{plan_id}/versions/{version}` | none | exact historical PlanReadResult |
| POST `/{plan_id}/decisions` | DecisionIntent | `{event_sequence,event:CustomerDecision}` |
| POST `/{plan_id}/assertions` | AssertionIntent | `{event_sequence,event:ManualAssertion}` |
| GET `/{plan_id}/events` | bounded cursor/limit | `EventPage` of separate typed immutable event records |
| GET `/{plan_id}/export?version=N` | explicit version | canonical JSON or safe rendered download |
| GET `/requests/{operation}/{request_key}` | current actor only | exact authorized committed result or404 |

Observation refresh DTO/endpoint follows actual adapter field-comparison support; do not
show a working refresh control before that service exists. Reads are owner/admin/analyst/
viewer, mutations owner-only + CSRF. All no-store. Disabled writes remain unchanged.

`PlanSummary`: plan_id, input_revision, version, event_sequence, created_at. `PlanReadResult`:
summary + `inputs`, optional `document` (null before first generation), independent
freshness (`current`, `expired`, `source_changed`, `goal_changed`, `input_changed`) and
reasons, no folded applied/accepted flag. Never present historical stale evidence as current.
JSON exports include exact version/digest/freshness and independent event history.

`CustomerInputs` carries exact goal ID/revision and selected account IDs, requested windows,
milestone/product/constraints/customer assumptions, optional creative capacity and typed
fixed/alternative allocations. Every target/exclusion is only
`TargetSelector(account_id,canonical_entity_key,selection_key)`; server resolves actual
V2 metadata/reference/owner/name under original source/reporting/actor/session fences.
Changed/missing selection409 is actionable; never silently remap to a new snapshot.
No complete client PlanVersion, TargetRef or evidence artifact is accepted as proof.
No target selections means no native target-resolution IO is needed for input creation.
All target selections, including exclusions, must resolve owned scope before persistence.

Public service orchestrator (engine/provider/adapters configured by trusted server):
`create(principal,wid,CreatePlan)`, `revise(principal,wid,plan_id,EditPlan)`,
`generate(principal,wid,plan_id,GeneratePlan)`, `read(principal,wid,plan_id,version=None)`,
`decide(principal,wid,plan_id,DecisionIntent)`,
`assert_applied(principal,wid,plan_id,AssertionIntent)`.
Each operation owns short transactions and returns typed JSON-ready values; route does
not hold its authentication read transaction over evidence/identity IO. Provider check
captures scalar identity before IO; refreshed fact is discarded across any further IO.
Final exact tuple/local guards + five-second monotonic bound apply after ALL locks and
source/goal rechecks. DB-only source rechecker uses the agreed adapter function.

Creation/edit with target selectors: prepare owned goal/account/current heads and source
fences; release transaction; read actual catalogs; resolve selectors into full immutable
inputs; refresh identity; final recheck/freshness + CAS/receipt atomic commit. Generation
uses frozen GenerationTicket/EvidenceBundle/pure composer ports and exact final resolver.
Same key/body returns same authorized committed result; changed body409. Unknown HTTP
outcome shows explicit request-result lookup, no automatic re-POST. Different-key CAS
conflict shows current revision and requires customer review. Source/privacy/goal changes
abort without partial version/event/receipt. No locks held over provider IO.

## Frozen Runtime Boundary

Module `app.planning_documents.service`, class `PlanningDocumentService`:
`__init__(engine: Engine, provider: IdentityProvider,
clock: Callable[[], datetime] = utc_now)`. These are server dependencies, never
customer body fields. Constructor internally selects the configured descriptive
composition policy/composer and owned evidence reader. No advertising execution
runtime or mandate is involved. Implementation is pending; this freezes the seam.

Methods (all synchronous, principal is CustomerPrincipal, wid is int):

```python
create(principal, wid, request: CreatePlan) -> InputResult
revise(principal, wid, plan_id: str, request: EditPlan) -> InputResult
generate(principal, wid, plan_id: str, request: GeneratePlan) -> VersionResult
read(principal, wid, plan_id: str, version: int | None = None) -> PlanReadResult
decide(principal, wid, plan_id: str, request: DecisionIntent) -> EventResult
assert_applied(principal, wid, plan_id: str, request: AssertionIntent) -> EventResult
listing(principal, wid, *, cursor: str | None = None, limit: int = 20) -> PlanPage
history(principal, wid, plan_id: str, *, cursor: str | None = None, limit: int = 20) -> VersionPage
events(principal, wid, plan_id: str, *, cursor: str | None = None, limit: int = 20) -> EventPage
request_result(principal, wid, operation: str, request_key: str) -> InputResult | VersionResult | EventResult
export(principal, wid, plan_id: str, version: int) -> PlanReadResult
```

Core service owns these methods; API/controller/runtime dependency wiring belongs
to the API lane. API authentication transaction closes before service invocation.
Export returns a checked historical projection for JSON attachment serialization;
it does not falsely assert current applicability. Events are separately paginated.
Operations for receipt lookup are `create`, `revise`, `generate`, `decide`, `assert_applied`.
Unknown operations fail422. Limits1..100; invalid cursors fail422.

InputResult and VersionResult are immutable mutation results: exact committed
input/version even on later replay. They deliberately omit mutable head, freshness,
and event sequence. Replay still checks current authorization and retained privacy
graph; it cannot resurrect erased data. Customers explicitly fetch current read
before current decisions. PlanReadResult and VersionResult expose computed
`document_digest` and `action_digests` (action key to digest), derived from reparsed
actual document/action contracts. These hashes are never accepted as projection
constructor overrides or trusted stored copies. A missing document yields null
and an empty mapping. Decision requests still bind their supplied hashes against
the current server-owned document inside the locked acceptance transaction.
