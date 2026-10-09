# Reported Feedback Current Preview Regression Interface

Proposal against `3fb6474`, following reviewed source/acquisition/composition fixtures.
This package repairs current reads and non-authorizing displayed previews. It does
not enable execution or change reporting policy, clocks, TTLs or provider writes.

## Exact Consumer Map

| Current test module / function | Failed nodes | Required seam and preserved boundary |
| --- | ---: | --- |
| `test_reported_feedback_real_preview::test_fixed_current_report_requires_retained_owned_terminal_proof` | 14 | Existing scalar original → current request/acquisition; seven exact retained-proof mutations, current reader denial |
| `test_reported_feedback_real_preview::test_actual_acquisitions_produce_real_calibrated_baseline_and_changed_preview` | 2 | Genuine current planning confirmation/baseline, displayed 46m → 47m; original one historical MockHTTP effect remains separately measured |
| `test_reported_feedback_preview_guards::test_real_feedback_idempotent_not_compounded_and_retracted_with_retained_finance` | 2 | Exact retry, policy rejection, actual capsule erasure, retained finance |
| `test_reported_feedback_preview_guards::test_changed_mapping_appends_current_revision_without_invalidating_baseline` | 4 | Current revision mapping, original immutable slot, pointer/current-slot erasure without fallback |
| `test_reported_feedback_revisions::test_populated0078_roundtrip_preserves_bytes_and_refuses_lossy_history` | 2 | Actual current DDL, JSON bytes/digests/revisions and populated-history refusal |
| `test_reported_feedback_revisions::test_pointer_only_accepts_exact_next_owned_revision` | 8 | Four raw SQL scoped/exact-next constraint negatives |
| `test_reported_feedback_revisions::test_retained_revision_capacity_fails_before_insert` | 2 | Actual append limit before insertion |
| `test_reported_feedback_revisions::test_concurrent_replacement_serializes_and_exact_retry_reuses_current` | 2 | PostgreSQL identical/different replacement races; retain two existing SQLite skips |
| `test_reported_feedback_revisions::test_final_authority_failure_rolls_back_revision_and_pointer` | 2 | Session revocation after append, actual rollback |
| `test_reported_feedback_revisions::test_real_new_unadjusted_baseline_appends_without_compounding` | 2 | Genuine new V1 service baseline, unchanged nominal adjustment; not a V1 HTTP route claim |
| `test_reported_feedback_revisions::test_downgrade_cannot_reintroduce_a_deleted_current_pointer` | 2 | Actual deleted-pointer downgrade refusal |

Total: 42 original failures, plus two existing SQLite concurrency skips. No original
function asserts that current feedback must require active execution consent. That
was obsolete fixture setup, not a retained forward-execution expectation. Keep all
current storage/authorization/erasure/concurrency assertions; do not classify these
modules as historical. Original V1 HTTP routing is separately covered by the
reviewed pinned initial-native batch, not implied by direct V1 service tests here.

## A: Independent Fourteen Source Negatives

Only change the setup of the named proof-negative function. Import the existing
`reported_original` fixture and `RetainedReportedOriginalIds`; use a fresh current
Session, `prepare_reported_read(db, ids)`, then
`prepare_reported_acquisition(db, configuration, prepared, monkeypatch)`, then the
unchanged `acquired(..., data=prepared_acquisition)` body. No new shared fixture
signature or modification of `reported_original_fixture.py` is needed.

Preserve original seven changes: capsule deletion, job deletion, expiry at the
actual capsule deadline, superseded job, source generation, original session,
and another native campaign. Preserve actual current-pointer/capsule lookup,
current `read_current` and scoped authorization. The inherited strict original
effect graph must remain unchanged. No baseline, planning or execution consent is
needed. Qualify both databases and relevant current acquisition compatibility.

## B: Reachable Current Production Inconsistency

The registered authenticated POST
`/api/customer/v1/workspaces/{workspace_id}/reported-feedback/previews` calls
`app.api.customer_reported_feedback.apply_preview` →
`app.reported_feedback.service.apply_feedback_preview`. Current options advertises
preview updates when a configured feedback policy exists. Configured planning
runtime supports genuine current V2 baselines.

`apply_feedback_preview` first invokes `initial_planning.preview.read_preview`.
Both its amount and final readback use `checked_planning_limits`, which requires
a current **draft** mandate plus genuine preparation and PlanningConsent. The
feedback service subsequently calls `customer_intents.binding` and
`execution_mandates.checked` on the same reference, requiring active execution
consent. This is a current reachable inconsistency, not just retired V1 routing.

Minimal production repair: import and call the existing
`checked_planning_limits(db, principal, provider, workspace_id, *reference,
runtime.initial)` instead of the execution binding/check pair. No new checker,
fallback, permission, policy or money calculation. Preserve comparison/source
validation, positive amount, V2 currency quantum, min(per-plan,total) ceiling,
positive-change ceiling, baseline digest, active-set/expiry and final rereads.
The returned policy is limits data only, never authority to spend.

## C: Genuine Baseline Fixture Contract

Add a local current fixture module rather than changing legacy journey helpers or
shared historical producer lifecycle. It consumes current acquired scalar lineage
and returns the existing `(runtime, initial)` shape plus explicitly named local
read-request instrumentation where tests require it. It must:

1. Keep the original confirmed goal/revision, original source and actual acquired
   comparisons/capsules. Never revise the goal to make preparation succeed.
2. Load a coherent explicit PlanningReportingProfile and budget operating-policy
   file before calibration/preparation. Preserve existing initial step and feedback
   policy inputs, including 46m baseline and 47m displayed result. Actual native
   Meta MockHTTP begins at the retained post-effect 45m state; it has zero new
   posts, not a fabricated copy of the historical post counter.
3. Use actual owned native catalog selection, `prepare_budget_mandate` and
   `consent_budget_mandate`. Use returned policy period (derived from the genuine
   confirmed goal), not the obsolete clock-minus-minute/plus-hour fixture period.
   Preserve current source, profile, currency, target-set and goal checks.
4. For existing direct V1 service consumers, configure the actual read-only legacy
   catalog with that same genuine prepared period and native source. Construct the
   baseline through real calibration/discovery/`preview.prepare_preview`. Financial
   runtime builders remain forbidden. A separate current API positive constructs
   its baseline through the real V2 endpoint and calls the reported-feedback API.
5. Assert the new planning mandate remains draft and has PlanningConsent but **no
   ProviderExecutionConsent for that reference**. The original historical effect
   necessarily retains its own old execution consent; do not claim global zero.

A reviewed narrow graph guard extension is needed for this later fixture: allow
only the exact newly prepared draft mandate/revision and immutable planning
preparation/confirmation rows; original financial rows remain byte-for-byte
unchanged, with no new attempt/run/reservation/execution consent. Do not weaken the
existing shared strict-default `effect_graph` guard. Coordinate its implementation
with the capacity author before shared-file edits; a local wrapper is preferred.

If genuine goal limits, profile rules or native selection reject this construction,
report the actual earlier boundary before changing expectations. No synthetic
consent, expiry extension, old execution-consent substitution or early-denial
credit. Any necessary fixture interface refinement must be reviewed first.

## Repair Acceptance And Sequence

First freeze/qualify A independently. Then reproduce B through real baseline
construction and authenticated current API before the narrow production change.
Positive: current nominal feedback with no execution consent for its planning
reference; no new native POST or financial authority. Negatives: current planning
confirmation removed/stale (revision/profile/goal/source as applicable), revoked
current session and nominal-cap/native-quantum constraints; controlled rejection
and no new slot/current-pointer change. Use real preparation inputs to reach
numeric boundaries, not malformed profile or fabricated preview records.

Then adapt remaining 28 failed nodes plus two existing skips with that reviewed
fixture and preserve their specific final assertions. New regression counts remain
separate from original-node recovery. Run scoped planning-consent/current feedback
compatibility, whole Ruff, bare mypy and diff checks. No aggregate rerun, no summed
overlapping counts, no production or full-suite success claim from this proposal.

## Evidence At Proposal Freeze

Read-only source and policy inspection only. No tests or production edits were
performed for this document. The original failed-node evidence remains under
`/workspace/inlet-evidence/20261009/w1-failure-classification/failed-nodes.json`.

## Closed Planning-Only Graph Delta (For Review Before B/C Implementation)

Add a dedicated `ExpectedPlanningConfirmation` test-only expectation, default off,
not an arbitrary callback/table allowlist. Its one-shot `bind(db, mandate_id,
revision)` is invoked only after actual `consent_budget_mandate` and successful
`checked_planning_limits`; bind requires the original workspace/goal/account and
captures the exact new mandate/revision/preparation/PlanningConsent scalar/document
rows. Reject original mandate ID, revision other than one, active state, absent or
inconsistent preparation/confirmation, or any execution consent for the new ID.

The outer original context accepts this closed expectation as mutually exclusive
with `ExpectedUnknownReadback`; strict default behavior stays byte-for-byte equal.
At exit, all original `effect_graph` rows must equal the pre-yield snapshot. Exactly
one new `provider_execution_mandates` row and one matching
`provider_execution_revisions` row may equal the bound records. Every other
provider table and mandate_actions remains exactly equal, including old consents,
responses, receipts, attempts, reservations and runs. Preparation and PlanningConsent
are additionally bound to that exact reference and digest, with no unbound rows.
No authority derived from copied expected JSON: bind follows the real checker and
exit independently validates structural bindings/canonical digests.

Tests that intentionally invalidate/remove the current planning confirmation use a
separate narrow negative fixture assertion outside this strict positive expectation;
do not add arbitrary expected deletion/mutation knobs. Existing revision/capsule
privacy tests must be inspected for actual deletion of the new planning rows;
if they do erase them, freeze an exact semantic-erasure outcome first rather than
relaxing this equality contract. New-row mutation/revision acceptance is not part
of this initial closed expectation.

Coordinate the optional parameter and finally branch with the capacity author's
SourceLifetime integration. Do not modify extraction lifetime, URL validation,
strict original scalar interface or historical driver to implement this delta.

### Actual Retained Dates: Preparation Gate Still Open

Read-only inspection of an actual A14-produced SQLite graph on October 9 found the
original ledger period October 5 11:00 UTC through October 6 12:00 UTC (action_count
one), while its unchanged confirmed goal has budget dates November 1–December 1
UTC, 50,000,000 micros and balanced aggressiveness. The periods do not overlap.
`execution_mandates.revise` would therefore need a new zero-counter November ledger
if genuine preparation reaches it; the proposed two-provider-table delta above is
NOT sufficient and is not approved for implementation.

Separately, `checked_planning_limits` requires `starts_at <= now < ends_at`, including
inside actual `consent_budget_mandate`. October current acquisitions cannot confirm
this November planning period. These are inspected actual stored dates plus source
predicates, not a claimed end-to-end preparation failure. Preserve the existing goal
and evidence; do not advance clocks, enlarge source lifetimes or synthesize consent.
Before C implementation, reproduce the exact preparation boundary and review a
coherent original fixture chronology. A possible separate closed historical producer
would create a genuinely current-budget goal before the original effect/anchor, but
its exact input seam/ledger compatibility is not frozen here. No alteration of the
already retained original goal/ledger is authorized. A14 remains independent.
