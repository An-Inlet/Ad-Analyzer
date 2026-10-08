# Planning Customer Service/API Interface — In Implementation

Concrete request DTOs: `app/planning_documents/requests.py`. Freeze for dependent UI,
with implementation/results not yet qualified. Base prefix
`/api/customer/v1/workspaces/{workspace_id}/planning/plans`.

| Route | Input | Successful result |
|---|---|---|
| POST base | CreatePlan | `{plan_id,input_revision,version:0,event_sequence:0,inputs}` |
| GET base | bounded cursor/limit | `{items:[PlanSummary],next_cursor}` |
| GET `/{plan_id}` | none | current PlanReadResult |
| POST `/{plan_id}/inputs` | EditPlan | new current PlanSummary + inputs |
| POST `/{plan_id}/generate` | GeneratePlan | PlanReadResult with exact committed version |
| GET `/{plan_id}/versions` | bounded cursor/limit | version summaries |
| GET `/{plan_id}/versions/{version}` | none | exact historical PlanReadResult |
| POST `/{plan_id}/decisions` | DecisionIntent | `{event_sequence,event:CustomerDecision}` |
| POST `/{plan_id}/assertions` | AssertionIntent | `{event_sequence,event:ManualAssertion}` |
| GET `/{plan_id}/events` | bounded cursor/limit | separate typed immutable event records |
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
