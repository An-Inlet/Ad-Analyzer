# Current Configured Feedback V2 Consumers — 2026-10-09

Approved interface d6be6cf; implementation based on reviewed configured runtime7a90f74.
Only tests/test_reported_feedback_configured_v2.py changes its fixture imports and
passes planning_origin to the reviewed local configured_journey. No helper, runtime,
production, policy, clock, TTL, retained producer or browser changes.

All original function assertions, decorators and the complete post-helper body remain
AST-identical. Exact original eight identities (four adverse modes on both databases)
are retained in selected-original-nodes.json. The genuine relative origin/current
PlanningConsent, ordinary actual same-actor login, configured API factories/scheduler,
actual comparison and feedback, export and strict unchanged financial graph remain.
The baseline-deletion case still deletes the real PreviewRow and asserts denial;
the whole-test finalizer is not broadened. Real configured feedback policy preserved.
Replicas identity/database plumbing is distinct from forbidden runtime/policy overrides.

Evidence directory:
`/workspace/inlet-evidence/20261009/configured-feedback-consumers/`.

Commands use /workspace/inlet-venv/bin/pytest with approved localhost disposable PG
inlet_oct07_next_integration_ci and AD_ANALYZER_CI_DISPOSABLE_POSTGRES=true. SQLite
uses exact owned current.sqlite files; PostgreSQL uses isolated per-test schemas.
All provider reads are MockHTTP, no aggregate source/database/reset.

- Gate: `-q tests/test_reported_feedback_configured_v2.py -k session --basetemp=<evidence>/gate-artifacts --junitxml=<evidence>/gate.xml`:2 passed,0 skips/failures,23.555s.
- Exact selected cohort: `-q tests/test_reported_feedback_configured_v2.py --basetemp=<evidence>/qualified-artifacts --junitxml=<evidence>/qualified.xml`:8 passed,0 skips/failures,92.157s.
- Bounded compatibility: current configured-runtime positive2 plus configuration,
  budget policy and strict planning original guard cases:23 passed,0 skips/failures,28.193s.
  Command: `-q tests/test_planning_runtime_assembly.py::test_actual_configured_api_worker_native_preview tests/test_planning_reporting_configuration.py tests/test_budget_mandate_contracts.py tests/test_reported_planning_original_guard.py --basetemp=<evidence>/compat-artifacts --junitxml=<evidence>/compat.xml`.
- Whole Ruff, bare mypy with /tmp/inlet-configured-runtime-mypy and diff check: passed; mypy1191 source files. No code changed after checks.

Raw logs/XML and assertion-preservation.json retained. Compatibility/probes overlap
previous qualification and do not add original failure credit. Adjacent configured
browser two remain deferred. No live acceptance, Full rerun or quality-completion claim.
