# Current Reported Planning HTTP Qualification — 2026-10-09

Branch: `codex/inlet-reported-planning-api`; predecessor production fix `cc02905`,
reviewed clock contract `42f709c`. Explicitly invoked dated October diagnostic,
not default-collected lasting regression and not original failed-node closure.

Actual login/request first demonstrates ordinary session expiry before the acquired
request due date. Fresh actual login uses coherent verified identity and ordinary
TTL at the simulated due time; scoped API issuance and customer access namespaces
read the same time. Global time remains untouched and namespaces restore. No
session, job, original scalar IDs, source dates or TTL rows are rewritten.

Actual initial V2 POST produces 46m; actual GET comparison commits its immutable
assessment; actual feedback POST produces 47m. Both databases also reject revoked
request session (401) and changed planning policy (409), with zero slot/pointer.
Real planning confirmation has no new execution consent. Original one-effect
financial graph remains exact; current native requests are GET only. This is
simulated-request-time HTTP evidence, not real-time browser evidence.

Shared acquisition helper now checks the current requesting principal against the
original actor and the actual job session. Old original-principal callers retain
identical behavior; no arbitrary session override was added.

## Checks And Preserved Failures

Raw evidence: `/workspace/inlet-evidence/20261009/reported-planning-api/`.
Both-DB commands set the existing disposable localhost PostgreSQL URL and flag.

- `pytest -q tests/reported_feedback_planning_api_probe.py`: 6 passed, 62.200s,
  `qualified.log/xml`, preserved basetemp `qualified-artifacts`.
- `pytest -q tests/test_reported_feedback_acquisition.py::test_fixed_windows_preserve_rolling_coverage_and_repeat_spacing`:
  2 passed, 23.340s, `compat.log/xml`; original shared-helper caller compatibility.
- Final affected valid cases after import/local-variable typing repairs:
  `pytest -q tests/reported_feedback_planning_api_probe.py -k valid`:
  2 passed, 25.183s, `final-affected.log/xml`. Overlaps the six cases above.
- Whole `ruff check .`, bare `mypy`: passed (1,181 files), final logs retained.
- `git diff --check`: passed.

Initial `first.log/xml`: 1 failure, 9.751s, original ordinary session expires before
actual due time; led to the reviewed clock-input seam, no expiry extension.
`clock.log/xml`: 1 failure, 11.214s, test called a service read then rolled back its
new comparison before HTTP lookup. Replaced that setup with actual committing GET
comparison route; no production repair for that test error. Initial mypy found two
import/local-name errors; corrected before final static checks. Ruff then found one
long line from the rename; formatting corrected and all final static checks rerun.

The fixed October producer/probe remains deliberately outside default collection.
Durable regression requires a separately reviewed source-before-effect relative
calendar; the actual DB freshness clock cannot safely be replaced by a fixed past
application clock. No full regression, live-provider or product-quality claim.
