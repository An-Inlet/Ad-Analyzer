# Current Configured Runtime Consumer Qualification — 2026-10-09

Implementation follows approved c08ade0, based on closed cacaa6c. This package
selects only the ten original test_planning_runtime_assembly identities listed in
`design/configured-planning-runtime-read-fixture-v1.md`. Adjacent configured V2 eight
and browser two remain deferred; the old shared planning_runtime_fixture is untouched.

## Change And Preserved Boundaries

New local configured_planning_read_fixture uses the reviewed relative original and
whole-test ExpectedPlanningConfirmation guard. Only scalar authentic original IDs
cross; the original financial ledger/effect graph remains exact. Normal login uses
the existing actor/subject and ordinary TTL. No subject, session, job or clock/TTL
rewriting, no dated acceptance assertion, no runtime/policy dependency override.
Replicas still supplies its normal database and FakeProvider dependencies.

Actual canonical profile loading, MetaSyncService factory and run_meta_tick scheduler
remain. Actual request creates a new same-actor session-bound job, matching the real
bootstrap request windows. Tick/capture sequence yields four observations and retains
the rolling source frontier. Actual current commerce refresh, capture/calibration APIs,
owned native catalog, canonical operating policy and budget preparation/confirmation
APIs create current PlanningConsent, a draft using the same original ledger, and no
execution consent for the new reference. Native-options/rediscovery/previews produce
45m→46m V2 through the real configured reader. The existing preview300 setting is
preserved; no new lifetime extension. Configured feedback policy remains untouched.

Every original consumer assertion/decorator is AST-identical: exact preview/export,
no stored choice/native-state digest, no disclosed session, unqualified execution
review, and post-creation session/generation/profile/expiry denials before native I/O.
Original POST1 is scalar provenance; the current native MockHTTP server has POST0.
No manufactured historical server counter. No production changes.

## Evidence And Commands

Raw artifacts: `/workspace/inlet-evidence/20261009/configured-runtime-consumers/`.
`selected-original-nodes.json` retains all ten original identities;
`assertion-preservation.json` records both unchanged function assertion/decorator sets.
SQLite uses its exact owned current.sqlite; PostgreSQL uses per-test isolated schemas
on inlet_oct07_next_integration_ci, never the frozen aggregate database.

Commands use `/workspace/inlet-venv/bin/pytest`. Database runs set
AD_ANALYZER_TEST_POSTGRES_URL to the approved disposable localhost database and
AD_ANALYZER_CI_DISPOSABLE_POSTGRES=true. All fixtures use MockHTTP only.

- Initial gate: `-q tests/test_planning_runtime_assembly.py::test_actual_configured_api_worker_native_preview --basetemp=<evidence>/probe-artifacts --junitxml=<evidence>/probe.xml`.
  Two passed, zero skips/failures,22.682s. Actual job/window/scheduler sequence required
  no interface adjustment. probe.log/xml retained.
- Selected package: `-q tests/test_planning_runtime_assembly.py --basetemp=<evidence>/qualified-artifacts --junitxml=<evidence>/qualified.xml`.
  10 passed, zero skips/failures,117.735s. Raw qualified.log/xml retained.
- Bounded compatibility: `-q tests/test_planning_reporting_configuration.py tests/test_budget_mandate_contracts.py tests/test_reported_planning_original_guard.py --junitxml=<evidence>/compat.xml`.
  21 passed, zero skips/failures,2.232s; compatibility overlaps prior qualification
  and does not add original recovery credit.
- First bare mypy found three nullable-source-timestamp type errors now exposed by
  the typed local helper. Preserved mypy-before-timestamp-narrowing.log. Added explicit
  source.last_sync_at non-null assertion; no behavior/guard weakening. Final affected
  positive both-DB repeat:2 passed, zero skips/failures,22.962s (final.log/xml,
  final-artifacts). The restart notification did not interrupt this completed run;
  its terminal XML was verified after reconnect. The completed10 were not rerun.
- Whole `/workspace/inlet-venv/bin/ruff check .`, bare
  `MYPY_CACHE_DIR=/tmp/inlet-configured-runtime-mypy /workspace/inlet-venv/bin/mypy`,
  and `git diff --check`: passed; mypy reports1191 source files. Final static logs
  retained as ruff-final.log and mypy-final.log. No further source edits after these
  checks; documentation completion only.

No aggregate, live provider, advertising mutation, deployment, or full quality claim.
Only matching original passing identities may contribute ten recovery nodes; probes,
compatibility and repeats are separate overlapping evidence.
