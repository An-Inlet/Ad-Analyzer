# Initial Rule Storage And Consumer Interface (0084)

2026-10-07. Reserved 0084 down0083. Shared dispatcher owned by scheduler;
initial package owns its new contract/source/compiler and schema only.

## Tables And Ownership

`initial_rule_opportunities`: id32 PK; workspace_id, environment, ledger_id,
native_account_identity_digest64, budget_owner_identity_digest64,
semantic_key_digest64 UNIQUE, created_at, pending_expires_at. Unique canonical
(workspace,environment,ledger,accountdigest,ownerdigest). Owned composite FK
(ledger_id,workspace_id,environment)→provider_period_ledgers(id,workspace_id,environment)
RESTRICT. Canonical identity columns immutable. ID is the first32 hex of its full
SHA256 domain-separated semantic commitment, not an alleged original attempt.
Insertion/read checks full digest + all scalars and rejects collisions.

`initial_rule_admission_origins`: admission_id PK, workspace_id, opportunity_id;
(admission_id,workspace_id)→provider_automatic_decisions(id,workspace_id) RESTRICT;
(opportunity_id,workspace_id)→initial_rule_opportunities(id,workspace_id) RESTRICT.
Immutable owned linkage inserted atomically with actual automatic admission. Triggers
check matching ledger,environment,native-account digest,whole-owner commitment and
initial source reference. It stores no reports or customer session secret.

`initial_rule_candidate_dependencies`: candidate_job_id PK, workspace_id, account_id,
campaign_id, opportunity_id, preview_id, calibration_id, selected_observation_id.
(candidate_job_id,workspace_id)→optimization_candidate_jobs(id,workspace_id) CASCADE;
(opportunity_id,workspace_id)→initial_rule_opportunities(id,workspace_id) CASCADE;
for preview/calibration/selected observation, each exact composite
(id,workspace_id,account_id,campaign_id) references the corresponding existing
initial_plan_previews/initial_calibration_runs/initial_observations unique tuple,
CASCADE. Immutable. Insert additionally validates preview's calibration/selected
observation, original actor/session, source account/campaign and job environment.
Deleting this row retracts the candidate job/results, which nulls existing forward
review provenance. It never deletes protected financial review/attempt/hold records.

`initial_rule_candidate_observations`: PK(candidate_job_id,observation_id), plus
workspace/account/campaign. Composite candidate dependency scope FK CASCADE;
(observation_id,workspace_id,account_id,campaign_id)→initial_observations exact
owned tuple CASCADE. One row for EVERY calibration input, including selected input;
insert checks actual CalibrationDependency membership. Any deletion retracts the
parent candidate dependency/job, never leaves a numerical result detached.

All derived edges must be complete before committing queued work. Work document
commits exact sorted observation IDs/digests; worker and review gates check set equality
against DB membership and current retained documents. An incomplete graph fails
closed before compilation or admission. Raw graph deletion obtains the same
workspace-first NOWAIT fence before erasure/export revision advancement as 0075;
no inverted blocking wait or financial-history deletion.

## Retention / Privacy / Export

Never-admitted origins are derived bookkeeping: pending_expires_at is bounded by
all selected current input deadlines. Cleanup deletes only genuinely DB-expired
unconsumed origins; no policy-dependent sweep activation is required. A fresh
explicit basis can recreate an expired unconsumed origin with the SAME deterministic
key/reference. An existing active origin's deadline is not silently extended.

Consumed origins/admission links follow existing protected admission retention.
No infinite retention of preview/calibration/capsule bodies is introduced. Privacy,
source correction or closure deletes all derived graph edges/jobs and unused origins;
consumed minimal identity references and financial records remain. Original-session
and current-input readers also deny expired bodies before a sweep.

Register every table in canonical model/lifecycle inventory. Derived edge export
contains only owned references after strict binding; never session digests. Protected
origin export contains scalar key/ledger commitments and timestamps, not native raw
IDs/reports. Candidate strict export uses new typed document unions owned by scheduler.
Prepared archives use existing privacy revision and earliest evidence expiry fences.

## New Modules / Signatures

`initial_planning/automatic_contracts.py`: InitialReportedRulePolicyV1,
InitialRuleBasisV1, InitialReportedRuleWorkV1, InitialReportedRuleEvidenceV1,
InitialReportedRuleObservationV1, InitialReportedRuleCandidateV1.

`initial_planning/automatic_source.py`:
- resolve_initial_work(db,principal,provider,scope,selection,preview_id,expected_digest,
  policy,planning) -> InitialReportedRuleWorkV1
- bind_initial_dependency(db,job,work) -> None
- require_initial_dependency(db,job,work) -> None
- read_initial_rule(db,principal,provider,work,native,planning,clock)
  -> InitialReportedRuleObservationV1
- assert_initial_rule_current(db,principal,provider,work,decision,planning,clock) -> None
- initial_rule_epoch(db,principal,provider,work,decision,planning,clock)
  -> SemanticDecisionEpoch

`automatic_compiler.py::compile_initial_rule(observation,policy,mandate,
positive_changes_used_micros,actions_used,now) -> InitialReportedRuleCandidateV1`.
No IO/commits in compiler or final reader. Scheduler adds only explicit new variants
and typed dispatch to documents/service/review/configured session assembly after this
package freezes; no generic proof callback or qualified_learning casting.

## Expiry And Export Refinement

Both candidate dependency tables additionally retain immutable `expires_at`, no later
than the preview, calibration, all observations, and pending opportunity deadlines.
Any raw pre-expiry deletion advances the workspace export revision; PostgreSQL
always takes the NOWAIT workspace fence first. Actually DB-expired deletion uses
UTC wallclock and may omit that counter increment because exports capture the earliest
edge/pending deadline and recheck fresh DB/app time during delivery. This avoids
making unchanged current campaign reports stale merely because short-lived derived
work expired. Consumed origins are excluded from pending export deadlines; they are
protected admission history, not retained expired report bodies.

Existing retention ticks run a bounded independent origin/edge cleanup, even when
planning capture is disabled. Semantic source/privacy erasure removes unused origins
and the derived candidate graph; consumed minimal origin/admission references survive.

The source runtime parameter is `InitialPreviewExecutionRuntime` (configured planning
plus actual optimization runtime), so the existing `policy_pair` can revalidate the
separate 0079 and 0080 consents. This is not a generic source callback or a fabricated
financial qualification. `consume_origin(db, principal, work, decision, admission_id,
clock)` is called after the actual admission flush and before creating the provider run,
in the same workspace/ledger transaction. A trusted forward-review context will allow
only that exact own consumed admission to continue; ordinary reads/Start still reject
any prior budget/admission lineage.
