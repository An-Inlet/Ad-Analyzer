# Current Configured Runtime — Exact Ten-Case Fixture Interface

Proposal from reviewed `cacaa6c`; implementation requires root review. This is a
separate current-consumer package, not an extension of the closed28 V1 consumers.
Read-only investigation only: no test, runtime, provider, schema or clock changes.

## Exact Scope

Original identities come from the frozen failed-nodes.json under
`/workspace/inlet-evidence/20261009/w1-failure-classification/`. Select exactly these10:

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

No new probe counts as an original recovery. No aggregate invocation or database.

## Existing Boundary And Obsolete Setup

`tests/planning_runtime_fixture.py::configured_journey` deliberately loads actual
canonical planning profiles through API runtime dependencies and MetaSyncService,
then runs the actual `run_meta_tick(engine)` scheduler. Its consumers verify current
API reads, native V2 persistence/export and session/source/profile/expiry denials.
Replacing those factories with a supplied runtime would lose the tested boundary.

The obsolete setup instead calls acquisition_fixture (current execution guard),
changes the retained user's subject, extends customer login TTL to60days, and calls
execution_mandates.revise/consent. Those setup operations are not required assertions
of current read behavior. Preserve the actual configured path while replacing only
this source/identity/consent setup with the already reviewed relative original.

## New Local Helper And Ownership

Add `tests/configured_planning_read_fixture.py`, leaving the shared old
`tests/planning_runtime_fixture.py` and its other consumers untouched. Only the selected
module changes its helper import, imports the existing `planning_origin` fixture,
and passes that fixture to the new helper. Preserve every original test function,
parameterization, post-setup assertion and denial mutation.

```python
def configured_journey(
    db: Session, engine: Engine, configuration: Settings, path: Path,
    monkeypatch: pytest.MonkeyPatch, replicas: Any, *, origin: PlanningOrigin,
) -> tuple:  # unchanged ten-value consumer shape, concretely typed in implementation
    # alice, provider, wid, principal, runtime, job, value,
    # clock, native_requests, configured
    ...
```

Reuse `PlanningOrigin(ids, expectation, native)` and its whole-test relative-original
context. The only old effect is the pinned authentic optimization/receipt/anchor
chain created before current work; only scalar IDs cross. The unchanged
ExpectedPlanningConfirmation guard brackets the entire consumer, including adverse
reads. It permits exactly one genuine current draft/preparation/PlanningConsent,
requires the original ledger unchanged, and prohibits new execution consent/effects.
No new generic guard exemption or financial callback parameter.

## Ordered Actual Workflow

1. Call unchanged prepare_reported_read and prepare_reported_acquisition using the
   original scalar IDs. These supply owned current source/vault/GET MockHTTP wiring,
   the bootstrap comparison and its actual request windows. Do not call acquired(),
   which intentionally substitutes a different feedback fixture policy. Assert
   original actor/source/account/campaign/attempt lineage. Bootstrap setup is not
   evidence of configured worker execution.
2. Reuse exact profile() from test_planning_reporting_configuration, with only the
   existing fixture initial.preview_lifetime_seconds=300 setting. Write the canonical
   profile and actual digest to unique fixture paths; configure real global and runner
   settings, including the existing offline Meta configuration. Do not replace the
   configured feedback policy: adjacent configured behavior uses46m→45.75m, not the
   unrelated phase3 helper's46m→47m mapping. Preserve native observationTTL30,
   window policy and every remaining profile field.
3. Use the existing supported assembly.planning_clock closure and existing scheduler
   cadence only. Actual ordinary login is `ids.actor_id + ':first'`, with unchanged
   customer TTL_SECONDS, issuance/access clocks, verified identity and DB time floor.
   Assert returned user is the retained actor and its stored subject was not edited.
   Relative source windows are already closed; no future-issued login or dated guard.
4. Register actual initial-planning, reported-feedback and budget-mandate routers.
   Preserve replicas' normal database/identity test plumbing; explicitly prohibit
   overrides of initial runtime, feedback runtime and budget policy dependencies.
   No worker/factory override. This is zero runtime/policy dependency overrides, not
   a false claim that replicas has no database/identity overrides at all.
5. POST the actual comparison using original attempt/goal/revision/objective. Reload
   its returned job and original principal from real DB rows. It must differ from
   bootstrap job and bind the new login's existing actor/session. Never edit job,
   subject, session or scalar DTO to manufacture the binding. Assert its before/after
   windows equal the bootstrap windows used by the GET response closure; mismatch
   is a setup failure, never rewritten report dates or an adjusted callback.
6. Construct `MetaSyncService(db, configured_settings)` without reported_feedback
   injection. Assert its configured profile. Run the original actual scheduler
   sequence: first tick0 completed; second tick1; actual capture; then +1,+61,+1
   seconds/ticks gives ready4. Preserve source rolling frontier equality after fixed
   reads and global meta_sync_pages=3. Retain transaction commits/expiration and actual
   worker claims/checkpoints. A pending bootstrap job is handled by real request and
   scheduler behavior; no direct job deletion/state seed to force the sequence.
7. Run the actual current empty-page commerce refresh, then actual captures and
   calibration POSTs. Calibrate the API request's owned goal. Install NativeWireReads
   with real Meta MockHTTP budget4500 cents (45m), using GET-only transport; retain
   the request objects for the original `len(requests)`/no-new-read assertions.
8. Read the owned native budget catalog through actual runtime.initial (native=None,
   configured native reader). Write a real canonical operating_policy artifact whose
   planning_reporting_profile_digest is this exact profile digest. No policy override.
   POST budget-mandate preparation using calibration/observation/native option,
   total_cap_micros50m and balanced aggressiveness. POST actual confirmation using
   the returned revision/policy/preparation digests. No execution consent call.
   The confirmed goal determines the period; never clock−1minute/+1hour.
9. Assert draft state, exactly one PlanningConsent, no ProviderExecutionConsent for
   this new reference, and same original ledger/counters. Bind unchanged
   origin.expectation against the actual runtime/principal/reference. Current owned
   scope/period/profile/target-set checks must pass naturally.
10. Preserve actual native-options POST and returned choice/mandate reference, +1sec
    rediscovery, actual previews POST, native V2 schema and45m→46m result. Final count
    semantics are original scalar POST1 plus current wire POST0, never a current mock
    counter preloaded with historical calls. Return the same ten-value shape.

The new helper may adapt the existing native recorder to also retain outgoing request
objects locally without editing its public class. Its assigned origin.native still
ensures GET-only calls and empty current POST list at teardown.

## Assertions That Must Remain

Positive consumer: runtime.initial.native isNone; actual profile equality; exact
saved-preview GET; review request unavailable; no stored native_state_digest or choice
in intent; at least9 native requests; bind_preview_row digest; exact lifecycle export
and no original session digest; current_preview rejects specifically
initial_preview_native_read_unqualified. Do not convert the read-only preview to an
execution-qualified artifact.

Negative consumer: actual provider revocation of this original subject, actual source
generation increment, actual canonical profile revision/digest replacement, or existing
+301sec clock advancement. Preserve GET401/403/409 and unchanged native call count.
No early preparation failure is counted as these final-read denials.

## Qualification Gates

First run the actual positive consumer on SQLite and PostgreSQL. A genuine configured
policy/scope/window/period/rolling-frontier/auth/expiry failure must retain its full
trace and be reviewed; no alternate profile, runtime injection, source-row alteration,
TTL extension, fabricated readiness or broadened exemption to make it pass.

Then run the exact10 selected cases with durable log/JUnit and identity mapping;
relevant current planning consent/configuration/strict-original guard compatibility;
whole Ruff, bare mypy with an isolated `/tmp` cache, and diff check. Preserve original
assertions by source/AST comparison. Report overlapping compatibility separately.
No full suite or neighboring browser run is authorized by this proposal.

## Adjacent Interfaces — Enumerated, Deferred

These original failures are not selected and their current helper remains untouched:

```text
tests/test_reported_feedback_configured_v2.py::test_configured_v2_adjustment_export_and_current_fences[sqlite-session]
tests/test_reported_feedback_configured_v2.py::test_configured_v2_adjustment_export_and_current_fences[sqlite-generation]
tests/test_reported_feedback_configured_v2.py::test_configured_v2_adjustment_export_and_current_fences[sqlite-expiry]
tests/test_reported_feedback_configured_v2.py::test_configured_v2_adjustment_export_and_current_fences[sqlite-baseline]
tests/test_reported_feedback_configured_v2.py::test_configured_v2_adjustment_export_and_current_fences[postgres-session]
tests/test_reported_feedback_configured_v2.py::test_configured_v2_adjustment_export_and_current_fences[postgres-generation]
tests/test_reported_feedback_configured_v2.py::test_configured_v2_adjustment_export_and_current_fences[postgres-expiry]
tests/test_reported_feedback_configured_v2.py::test_configured_v2_adjustment_export_and_current_fences[postgres-baseline]
tests/test_reported_feedback_configured_browser.py::test_configured_v2_browser[sqlite]
tests/test_reported_feedback_configured_browser.py::test_configured_v2_browser[postgres]
```

The configured V2 eight cases additionally exercise actual feedback options, comparison
GET, preview creation/replay/read, export and baseline/session/generation/expiry fences.
They require their own later consumer approval, preserving the configured45.75m mapping.
The browser two cases use actual TLS and session transfer; the existing driver hardcodes
`configured-planning:rotated`. A later same-existing-actor driver seam must replace that
specific fixture assumption explicitly, not silently create a different identity.
Neither family is closed by this ten-case design or earlier injected-runtime API tests.
