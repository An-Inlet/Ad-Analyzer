# Current Configured Feedback Browser Consumers — 2026-10-09

Approved c1e763d, based on reviewed current configured-runtime7a90f74 and API8d0371f4.
Only the configured browser Python harness changes. Shared JavaScript bytes unchanged;
all original Python assertions retained (assertion-preservation.json).

The reviewed genuine relative-origin helper supplies actual configured API/worker
acquisition and current PlanningConsent, ordinary same-actor login and real V2 baseline.
Actual cookie transfer into local TLS Chromium is unchanged. Rotation replaces exactly
one known token literal with JSON-quoted original actor+:rotated, not a new hardcoded
subject. Actual before/after session-set evidence shows exactly one new session with
that actor, ordinary TTL and revoked_at set after browser logout. No session rows,
subject, job, clock, deadlines or authority were rewritten. Whole-test strict original
financial/confirmation finalizer remains unchanged; current native server permits GET
only. Replica DB/FakeProvider plumbing is distinct from prohibited runtime overrides.

Shared driver retains comparison CPA5/2.5, configured45.75m adjustment, no-compounding,
unavailable handoff, actual held-response invalidation on workspace change and actual
same-owner session rotation, refresh and logout. Browser result JSON is retained in
evidence-local basetemp. Existing90sec deadline, TLS, blocked external DNS and finally
cleanup remain. No production changes or external calls.

Evidence: `/workspace/inlet-evidence/20261009/configured-browser-consumers/`.
Commands use /workspace/inlet-venv/bin/pytest, approved disposable localhost PG
inlet_oct07_next_integration_ci and AD_ANALYZER_CI_DISPOSABLE_POSTGRES=true, isolated
schemas/owned SQLite files. No aggregate DB/source or reset.

- SQLite gate: `-q 'tests/test_reported_feedback_configured_browser.py::test_configured_v2_browser[sqlite]' --basetemp=<evidence>/gate-artifacts --junitxml=<evidence>/gate.xml`:1 passed,0 skips/failures,16.665s.
- Final exact2: `-q tests/test_reported_feedback_configured_browser.py --basetemp=<evidence>/qualified-artifacts --junitxml=<evidence>/qualified.xml`:2 passed,0 skips/failures,35.145s.
- Bounded compatibility: `-q tests/test_reported_feedback_configured_v2.py tests/test_planning_runtime_assembly.py -k 'session or test_actual_configured_api_worker_native_preview' --basetemp=<evidence>/compat-artifacts --junitxml=<evidence>/compat.xml`:6 passed,0 skips/failures,83.165s.
  This command also selects the already closed runtime session2, so six rather than
  planned four overlapping cases. Parent informed; no new recovery credit or rerun.
- Initial Ruff import ordering corrected. Bare mypy exposed cookie.value optional
  through newly typed helper; initial error preserved in mypy-before-cookie-narrowing.log.
  Added explicit non-null cookie assertion; final exact2 includes this change.
- Whole Ruff and bare mypy1191 source files pass (isolated/tmp cache); shared driver
  Node syntax and diff check pass. No later code edits.

selected-original-nodes.json and exact-original-coverage.json prove exact two-node
coverage. Gate/compatibility overlap previous checks and are not additional original
recoveries. This is local actual-browser evidence, not live provider or full quality
qualification. All failures/static corrections are disclosed; no Full rerun.
