# Selected Reporting Foundation Integration — 2026-10-11

Local branch `codex/inlet-w1-followup`, code head `9ed8fbb`. Storage author
`cc35fdc` integrated as `551e5d6`; injected catalog author `4e348f0` integrated
with its interface/implementation predecessors through `9ed8fbb`. Independent
review closed both packages with no remaining P1/P2 findings in their stated
internal/offline scopes. No remote push, hosted CI, merge, deployment, credentials,
provider/model call, advertising write or spending occurred.

## Behavior And Checks

Storage adds migration0091 and four ownership-scoped tables, immutable selected
evidence, exact current aggregate/source validation, explicit invalidation/CAS,
privacy erasure and strict historical export. Raw fact deletion retracts the full
capture; prepared export authority is revoked. Invalidation is idempotent; raw
active-head changes and stale old-choice readoption are blocked. A bounded capture
index prevents repeated full-graph export validation for every fact.

Google catalog remains an injected offline adapter. It checks same-customer account
metadata and complete event pagination, offers both metric families explicitly,
binds options to original session and current scope, and excludes private session
data from normal serialization. UTC normalization closes DST comparison ambiguity.
No public route or default factory is enabled; actual v24 compatibility is unverified.

Root integrated checks, all using `/workspace/inlet-venv/bin`:

- `pytest -q tests/test_selected_reporting_contracts.py
  tests/test_selected_raw_observations.py tests/test_selected_summary.py
  tests/test_google_selected_http.py tests/test_selected_storage.py
  tests/test_reporting_presence_storage.py --durations=20 ...`:
  **226 passed, zero failures/errors/skips, 70.324s**. Actual SQLite and explicitly
  disposable local PostgreSQL with per-test schemas. Includes actual migration0091
  upgrade/downgrade/populated refusal, concurrent PostgreSQL CAS/NOWAIT, complete
  archives and delivery privacy. An existing Alembic deprecation warning remains.
  Evidence: `/workspace/inlet-evidence/20261011/selected-integration01/`.
- After adding the reviewed catalog, `pytest -q
  tests/test_google_reporting_catalog.py tests/test_google_selected_http.py
  tests/test_selected_raw_observations.py tests/test_selected_reporting_contracts.py
  tests/test_selected_summary.py ...`: **194 passed, zero failures/errors/skips,
  0.896s**. These overlap the earlier cohort; do not sum them as unique cases.
  Evidence: `/workspace/inlet-evidence/20261011/selected-catalog-integration02/`.
- Whole-repository `ruff check .`: passed after each integration.
- Whole-project `mypy`: passed 1,293 files after storage, then **1,295 files** after
  catalog. Cache resides in scratch. `git diff --check`: passed.

JUnit and logs are durable in the evidence directories. Author initial failures
and repair checks remain preserved in their package ledgers. No broad exhaustive
baseline was rerun. Frozen9d7aa2e, its 52 partition archives/JUnit files and df89d75
qualification remain unchanged. Workspace/scratch/memory reserves were maintained.

## Next Package And Limits

Implement the original-session owned Vault/OAuth resolver and customer discovery,
explicit invalidation and confirmation service using
`design/selected-customer-confirmation-interface-v1.md`. Then integrate complete
selected-page staging/finalization before plan consumers. The service must prove
the actual refreshed aggregate completion/manifest at post-invalidation privacy;
the internal selection storage port alone does not enforce that refresh obligation.

Missing wider date-range acquisition must be implemented, never relabelled from
existing seven-day evidence. Missing rows cannot become zero. TikTok generic counts
still do not establish selected-event meaning. Customer activation, Q01–Q16 closure,
six human usefulness/release gates and a purchasable production release remain open.
Public website remains owner-managed and outside this work. All hosted/live/release
holds continue; no new owner decision was needed for these internal foundations.
