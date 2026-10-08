# Current-Policy Settlement Regression Adaptation

`test_provider_settlement.py` now explicitly uses `planning_boundary`. Only authentic
historical creation/admission/MockHTTP activation setup runs inside short test-local
write-guard patches. Those patches end before settlement, proof invalidation, held
exposure, no-effect preservation and default-runtime assertions. Cancellation remains
available with the production guard restored. No production source change or whole-
module retained-engine bypass; all existing assertions preserved.

Checks on SQLite and approved disposable PostgreSQL: 29 passed in 68.41s, covering
settlement plus advertising capabilities; no skips. Whole Ruff and prescribed mypy
passed (1,024 source files), diff check passed. Raw evidence:
`/workspace/inlet-evidence/20261008/planning-settlement.log` and `.xml`.
No live advertising, remote update or deployment. Full-suite classification still
pending other mixed APIs, retired execution UIs and initial planning fixtures.
