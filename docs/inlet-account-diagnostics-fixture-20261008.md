# Read-Only Account Diagnostic Fixture Repair

Isolated branch `codex/inlet-diagnostic-read-fixture`, base `6a3b0f1`.
The ongoing W1 checkout and dedicated aggregate database remain unchanged.
This successor changes only the account-diagnostics API test and this ledger.

## Reproduction And Cause

One exact original SQLite case,
`tests/test_account_diagnostics_api.py::test_real_account_diagnostic_api[sqlite-None-google_ads]`,
failed in4.41s before API or native-provider I/O. Durable `baseline.log/xml` records:

```text
account_diagnostics_api -> native_diagnostic_assembly.seed
 -> durable_optimization.ready -> provider_execution_mandates.setup
 -> provider_qualification.seeded -> google_action_plans.setup
 -> test_mandates.seed -> app.mandates.service.approve
 -> AdvertisingWritesDisabled:409 advertising_writes_disabled_in_planning_mvp
```

The immutable planning-policy guard behaved correctly. The read-only API test was
using an execution fixture that first approved a legacy mandate (and would later
consent to an execution mandate). This is fixture coupling, not evidence that the
current diagnostic API itself requires advertising authority.

## Bounded Repair

The API module now imports the existing source-only
`tests.test_planning_target_catalog_api.seed`, already used by the actual account
diagnostic browser test. Its signature remains `(engine, config, path, provider)`
and its returned namespace supplies `actor`, `workspace_id`, and `account_id`.
It creates only owned identity/workspace/integration/account/native credential rows.

The module is explicitly `planning_boundary`; before and after every case it proves
zero legacy mandates, execution mandates and execution attempts. Every original
CSRF, cross-workspace, session, role, source generation, OAuth-session, billing,
expiry, credential, date-bound, response-redaction and MockHTTP assertion remains.
There is no retained-engine marker, capability override, production change, or
change to the separate legacy `NativeDiagnosticRequest`/assembly contracts.

## Qualification

Exact module command uses the existing nonaggregate disposable PostgreSQL fixture
and its own UUID schemas, plus SQLite:

```text
pytest -q -o addopts='' tests/test_account_diagnostics_api.py
ruff check .
mypy
git diff --check
```

Raw evidence: `/workspace/inlet-evidence/20261008/diagnostic-read-fixture/`.
The exact66-case SQLite/PostgreSQL module passed in77.80s, with no failures or
skips (`qualified.log/xml`). Whole Ruff passed; bare mypy passed1,117 source files;
`git diff --check` passed. The original single-case failure remains in
`baseline.log/xml`; it was not rerun or removed.
No aggregate rerun, hosted qualification, live provider action, or deployment occurs.
