# Reported Preview Consumers — Phase 3 Exact Scope

Proposal only after durable stage2 `b80a935`; implementation awaits root review.
Source: original frozen failed-nodes.json in
`/workspace/inlet-evidence/20261009/w1-failure-classification/`.
No new execution behavior, production clock/TTL changes or broad retained marker.

## Scope And Preserved Identities

Select exactly28 original failed identities below: real-preview2, preview-guards6,
revisions20. Existing SQLite concurrency nodes (False/True) remain their two explicit
PostgreSQL-only skips; they are not original failures/recovery credit. The14 negative
retained-proof cases already closed by e09c096 remain unchanged and excluded from
new recovery credit. Default stage2's16 new tests remain separate regression evidence.

```text
tests/test_reported_feedback_preview_guards.py::test_real_feedback_idempotent_not_compounded_and_retracted_with_retained_finance[sqlite]
tests/test_reported_feedback_preview_guards.py::test_real_feedback_idempotent_not_compounded_and_retracted_with_retained_finance[postgres]
tests/test_reported_feedback_preview_guards.py::test_changed_mapping_appends_current_revision_without_invalidating_baseline[sqlite-pointer]
tests/test_reported_feedback_preview_guards.py::test_changed_mapping_appends_current_revision_without_invalidating_baseline[sqlite-current_revision]
tests/test_reported_feedback_preview_guards.py::test_changed_mapping_appends_current_revision_without_invalidating_baseline[postgres-pointer]
tests/test_reported_feedback_preview_guards.py::test_changed_mapping_appends_current_revision_without_invalidating_baseline[postgres-current_revision]
tests/test_reported_feedback_real_preview.py::test_actual_acquisitions_produce_real_calibrated_baseline_and_changed_preview[sqlite]
tests/test_reported_feedback_real_preview.py::test_actual_acquisitions_produce_real_calibrated_baseline_and_changed_preview[postgres]
tests/test_reported_feedback_revisions.py::test_populated0078_roundtrip_preserves_bytes_and_refuses_lossy_history[sqlite]
tests/test_reported_feedback_revisions.py::test_populated0078_roundtrip_preserves_bytes_and_refuses_lossy_history[postgres]
tests/test_reported_feedback_revisions.py::test_pointer_only_accepts_exact_next_owned_revision[sqlite-workspace_id=workspace_id+1]
tests/test_reported_feedback_revisions.py::test_pointer_only_accepts_exact_next_owned_revision[sqlite-revision=revision]
tests/test_reported_feedback_revisions.py::test_pointer_only_accepts_exact_next_owned_revision[sqlite-revision=revision+2]
tests/test_reported_feedback_revisions.py::test_pointer_only_accepts_exact_next_owned_revision[sqlite-slot_id='bad', revision=revision+1]
tests/test_reported_feedback_revisions.py::test_pointer_only_accepts_exact_next_owned_revision[postgres-workspace_id=workspace_id+1]
tests/test_reported_feedback_revisions.py::test_pointer_only_accepts_exact_next_owned_revision[postgres-revision=revision]
tests/test_reported_feedback_revisions.py::test_pointer_only_accepts_exact_next_owned_revision[postgres-revision=revision+2]
tests/test_reported_feedback_revisions.py::test_pointer_only_accepts_exact_next_owned_revision[postgres-slot_id='bad', revision=revision+1]
tests/test_reported_feedback_revisions.py::test_retained_revision_capacity_fails_before_insert[sqlite]
tests/test_reported_feedback_revisions.py::test_retained_revision_capacity_fails_before_insert[postgres]
tests/test_reported_feedback_revisions.py::test_concurrent_replacement_serializes_and_exact_retry_reuses_current[postgres-False]
tests/test_reported_feedback_revisions.py::test_concurrent_replacement_serializes_and_exact_retry_reuses_current[postgres-True]
tests/test_reported_feedback_revisions.py::test_final_authority_failure_rolls_back_revision_and_pointer[sqlite]
tests/test_reported_feedback_revisions.py::test_final_authority_failure_rolls_back_revision_and_pointer[postgres]
tests/test_reported_feedback_revisions.py::test_real_new_unadjusted_baseline_appends_without_compounding[sqlite]
tests/test_reported_feedback_revisions.py::test_real_new_unadjusted_baseline_appends_without_compounding[postgres]
tests/test_reported_feedback_revisions.py::test_downgrade_cannot_reintroduce_a_deleted_current_pointer[sqlite]
tests/test_reported_feedback_revisions.py::test_downgrade_cannot_reintroduce_a_deleted_current_pointer[postgres]
```

## Concrete Shared Fixture And Baseline Seam

New test-only `tests/reported_planning_journey_fixture.py`, no edits to global
reported_feedback_journey_fixture/acquisition_fixture or original producers.

- A `planning_origin` pytest fixture uses existing file-backed customer_engine and
  reviewed retained_reported_planning_relative_fixture for the whole test lifetime,
  yielding typed `PlanningOrigin(ids: RetainedReportedOriginalIds,
  expectation: ExpectedPlanningConfirmation)`. The original strict financial snapshot
  therefore brackets all subsequent sessions, DDL and assertions, not just setup.
- `acquired_current(db, configuration, path, monkeypatch, origin)` calls unchanged
  prepare_reported_read, prepare_reported_acquisition and acquired(data=actual_data).
  Returns the real PreparedReportedAcquisition, runtime and ObservationV1. The final
  tuple field is scalar original IDs, explicitly NOT a fake Server containing prior
  posts. Consumers replace the historical `len(server.posts)==1` check with
  `origin.ids.original_post_count==1` plus the current native MockHTTP server's empty
  POST list. Source/financial final guard provides an independent unchanged-effect
  invariant. No invented current counter contains the historical POST.
- `baseline_current(db, data, runtime, observation, origin, configuration, path,
  monkeypatch)` assembles the actual current profile and operating policy, reads the
  owned V2 native catalog, prepares/confirms one actual PlanningConsent and invokes
  unchanged expectation.bind. This is the reviewed stage2 construction; exact goal
  period/same original ledger, no new execution consent.

### Preserve V1 Direct-Service Behavior Where Asserted

These original consumers are direct V1 service tests, not old V1 HTTP route tests.
Keep genuine PreviewIntentV1/InitialPreviewV1 storage and especially the test that
parses the stored V1 intent and calls preview.prepare_preview again. Do not quietly
switch that test to V2 or count stage2's V2 API evidence as its original assertion.

After real current planning confirmation, construct the existing read-only
ConfiguredOptimizationCatalog/CustomerOptimizationRuntime used by the old helper,
with actual owned Meta target and live MockHTTP GET data. The MoneyContext period
comes from checked_planning_limits on the just-confirmed reference, never the old
clock-minus-one-minute/plus-one-hour synthetic period. Scope/owner/target set must
match that exact prepared policy. Qualification/exposure callbacks remain forbidden;
no approval/claim/executor write capability is supplied or enabled. Keep real original
45m native state and current rule1m step to produce46m through actual native.catalog
and preview.prepare_preview. Bind the same profile to runtime.initial; changing its
native read adapter must not change or bypass the stored profile digest.

Actual source methods preview.amount and checked_planning_limits compare period,
owned scope, target-set digest and current confirmed goal. If an actual current
V1 read fails those checks, preserve trace and return for review rather than copying
V2 rows, coercing digests, activating a mandate or changing a guard. The helper returns
runtime, genuine V1 preview and an explicit current read-only wire recorder.

## Consumer Adaptation Boundaries

Only setup/import/fixture plumbing changes in the three selected modules. Keep every
original function name, parameter matrix and meaningful post-baseline assertion:

- actual calibrated46m/feedback47m, distinct-original count1;
- idempotent same-slot/current-only reads, no compounding, dependency deletion and
  retained financial counts;
- policy revision history, original document bytes, privacy revision stability,
  pointer/current row deletion denial and changed dependency stamp;
- actual populated0078 downgrade/upgrade byte preservation and lossy-history refusal;
- raw SQL exact owned-next-revision rejection; retained-capacity before insert;
- actual independent PostgreSQL session races, same-key retry and exact pointer;
- final authority revocation rolls back appended revision/pointer;
- a newly prepared genuine V1 unadjusted baseline yields a new non-compounded revision;
- missing-pointer downgrade refusal with retained slot unchanged.

The existing focused adversarial clock/hook substitutions inside original tests are
preserved and labeled; no new clock guard patch is introduced by setup. No generic
financial/deletion allowlist is added. These tests delete capsules/slots/pointers,
not the approved planning confirmation. If actual cascades affect strict confirmation
rows, stop with exact evidence and propose a bounded invariant before any guard edit.

Qualify a small actual V1 baseline first on both DBs, then exact28 plus2existing
skips and relevant stage2/guard compatibility. Preserve failures and exact node map,
whole Ruff/bare mypy/diff. No aggregate. Only actual final node passes may count.

## Explicitly Deferred Configured Runtime 10

These original failed nodes are NOT included in this28 package:

```text
tests/test_planning_runtime_assembly.py::test_actual_configured_api_worker_native_preview[sqlite]
tests/test_planning_runtime_assembly.py::test_actual_configured_api_worker_native_preview[postgres]
tests/test_planning_runtime_assembly.py::test_configured_preview_denies_changed_authority[sqlite-session]
tests/test_planning_runtime_assembly.py::test_configured_preview_denies_changed_authority[sqlite-generation]
tests/test_planning_runtime_assembly.py::test_configured_preview_denies_changed_authority[sqlite-profile]
tests/test_planning_runtime_assembly.py::test_configured_preview_denies_changed_authority[sqlite-expiry]
tests/test_planning_runtime_assembly.py::test_configured_preview_denies_changed_authority[postgres-session]
tests/test_planning_runtime_assembly.py::test_configured_preview_denies_changed_authority[postgres-generation]
tests/test_planning_runtime_assembly.py::test_configured_preview_denies_changed_authority[postgres-profile]
tests/test_planning_runtime_assembly.py::test_configured_preview_denies_changed_authority[postgres-expiry]
```

They use planning_runtime_fixture.configured_journey, which deliberately asserts
actual configured API/worker factories (no runtime dependency overrides), uses
run_meta_tick and tests export, generation/profile/session/expiry. Stage2's injected
runtime HTTP regression does not preserve that factory boundary and cannot close them.
Their helper currently changes user.subject, extends login TTL to60days, seeds the
obsolete effect through acquisition_fixture and creates execution consent. A separate
proposal must substitute the reviewed relative original, same existing actor actual
normal login, real current acquisition/configured scheduler and PlanningConsent while
retaining zero runtime overrides and all consumer assertions. Do not edit this shared
helper or include its consumers silently here; request a separate reviewed package.
The present relative IDs/current-session handoff may be reused once that interface is
frozen. Existing fixed helper remains untouched by this phase3 proposal.
