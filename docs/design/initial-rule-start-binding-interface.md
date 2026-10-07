# Exact initial-rule Start binding

Proposed integration supplement to the approved first automatic operational rule.
No schema change is implemented by this document. Migration number awaits root
reservation; 0084 is frozen and remains owned by the source package.

## Why a stored link is needed

`SessionAutomationRun` stores original session, mandate and named policy scalars.
It has no preview/work field. The 0084 dependency tables bind a candidate to all
initial evidence and retain a consumed opportunity, but do not identify which
candidate was explicitly selected by a particular Start. Choosing the latest preview
or an arbitrary queued candidate at worker time would silently change customer intent.

## Minimal relation

`initial_rule_session_starts`:

- `session_run_id` PK, `workspace_id`; composite FK to
  `session_automation_runs(id,workspace_id)` RESTRICT.
- `candidate_job_id`, `candidate_workspace_id`, both nullable; composite FK to
  `optimization_candidate_jobs(id,workspace_id)` SET NULL. Same paired-null and
  equality-to-workspace constraint as existing `optimization_candidate_reviews`.
- `input_digest`, `preview_digest`, `semantic_key_digest`, `policy_digest`,
  `created_at`, `expires_at` (bounded by original preview/session/mandate/policy).
  No observation/report body, provider ID, duplicated session secret or numeric result.

Insert validation joins the exact run, candidate work, original actor/session,
mandate/consent/ledger, policy and initial basis. Immutable after insert except the
paired FK nulling caused by genuine candidate erasure. No row may be rebound to a
new job/preview. No missing-link fallback. Its minimal customer Start commitment
follows existing protected session-run audit retention; the referenced candidate and
all never-admitted opportunity/evidence dependencies retain 0084 expiry/erasure.
Export is strict scalar-only and excludes internal session identifiers. Lifecycle
classification and closure deletion ordering are explicit; populated downgrade refuses.

## Exact consumer sequence

The additive `StartInitialReportedRuleAutomationV1` requires the separate initial
basis, exact preview ID/digest, separately consented execution mandate binding,
named automatic policy reference and expected policy digest. No client source proof.
A server helper performs the owned current preview/source checks, then the existing
bound native catalog read outside locks. It rebuilds exact selection/work through
`resolve_initial_work`, rechecks current original authority and all source facts,
and atomically inserts candidate + session run + Start link under the workspace fence.
No provider mutation occurs during Start. Identical current Start reuses the exact
link; a changed/expired basis requires a new explicit Start and cannot rewrite an old one.

The existing automatic worker uses this exact initial job instead of generic target
selection. Candidate result, review and semantic admission remain distinct stages.
`consume_origin` is called after admission flush and before provider-run creation in
the same transaction. Every initial forward check compares the protected Start link,
result/work/opportunity, exact review/admission and existing source dependencies.
Deletion/nulling blocks forward work but cannot release exposure or prevent historical
reconciliation. The original stable opportunity excludes policy/session/report refresh.

## Acceptance

Both databases: actual configured preview + separate execution consent → explicit
Start → exact linked work → worker → one automatic admission/native operation, zero
human approval rows; duplicate Start and concurrent admission; privacy/source/session
and expired-preview denial; nullable FK erasure; no retry after unknown; Stop/read after
erasure; migration round-trip and lossless downgrade refusal. Numerical/financial
fixture scenarios remain explicit, with no production registration or defaults.
