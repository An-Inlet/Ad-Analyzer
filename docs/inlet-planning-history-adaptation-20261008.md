# Retained Activity And Export Under Planning Policy

Three existing current-product test modules now seed authentic historical provider
records with setup-only overrides, then restore the unconditional write prohibition
before exercising the behavior under test:

- `test_customer_activity.py`: owned latest receipts, corrupt-projection privacy,
  membership/session revocation and bounded activity.
- `test_export_execution_domains.py`: strict complete owned historical execution
  serialization, mismatched original-completion fields and unsupported future/raw data.
- `test_export_optimization.py`: Google/Meta/TikTok historical optimization archives,
  ownership/digest tampering and secret exclusion.

All three modules are explicitly `planning_boundary`. No retained-engine fixture,
production source change, skipped assertion or execution-consent fallback was added.
Temporary setup contexts end before activity/export/readback; explicit checks confirm
the write guard raises again. Existing MockHTTP writes create synthetic pre-MVP
history only and never touch a real provider.

Named three-module cohort with SQLite and approved disposable PostgreSQL:
**21 passed in56.38seconds**. Whole Ruff, prescribed mypy (**1011 files**) and diff
checks passed. Raw log/JUnit:
`/workspace/inlet-evidence/20261008/planning-history-adaptation.{log,xml}`.

This is additional historical-regression preservation, not whole-suite qualification.
The remaining mixed history, API, UI and0086 fixture adaptations listed in
`inlet-planning-test-partition-20261008.md` remain. No hosted, live, push or deployment.
