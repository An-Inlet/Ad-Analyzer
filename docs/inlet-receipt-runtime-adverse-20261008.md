# Catalog Receipt Runtime — Adversarial Offline Acceptance

Branch `codex/inlet-receipt-runtime-adverse`, base root `95a9ec1` (reviewed runtime
`5c0252e` integrated). This package changes only
`tests/test_catalog_receipt_runtime_adverse.py` and this ledger. No production defect
was found and no production files, deadlines, caps or authorization rules were changed.

## Actual Boundaries Exercised

Every case sends the real authenticated/CSRF-protected customer V2 API request against
real receipt helpers, registered SQLite/PostgreSQL models and immutable triggers. Native
observations use the actual Google collector with MockHTTP, not preconstructed catalogs.
Existing runtime coverage already exercises positive selection/generation for Google,
Meta and TikTok, identity/HTTP outside transactions, mixed targeted/untargeted accounts
and same-key PostgreSQL races. This focused package avoids repeating those cohorts.

* Native-response boundary: after an actual Google Ads response, inject +5 minutes and
  1 second into the request's wall clock, crossing the existing native read bound while
  the synthetic OAuth grant remains within its one-hour lifetime. Return 409, no receipt.
* Final identity refresh: collect a genuine native+metadata result, then reach its exact
  original expiry during the subsequent real identity callback. Return 409, no receipt.
* Selection persistence: the actual SQL selection INSERT hook reaches original expiry;
  the header/selection transaction rolls back, leaving no partial rows.
* After writer return: run the real helper to completion, then reach the original expiry
  before the route's final check. The route rejects and rolls back the inserted receipt.
* Final authority age: after actual selection INSERT, inject 5.001 seconds into the
  planning-local monotonic clock. Final authorization rejects `planning_authority_expired`
  and rolls back, without changing the shared five-second requirement.
* Independent maintenance: seed three genuine V2 receipts and save a real exclusion-only
  plan referencing one. Expire receipts with an explicit injected clock. Exactly one
  maintenance invocation requests limit=100 and deletes the two unused receipts. A NEW
  DB connection in the subsequent HTTP callback observes those deletions already committed.
  Both actual later quota denial and Google Ads HTTP503 (AFTER successful OAuth) preserve
  cleanup, the linked receipt, its selection rows and original input/plan/link. No new
  receipt, plan version or execution attempt is created. Quota is explicitly reduced to
  one in this test only, to exercise the real capacity calculation with bounded fixtures.
* Maintenance authority denial: after actual expired-unused deletion, inject 5.001 seconds
  before final authority acceptance. Deletion rolls back, old rows remain, and no native
  HTTP request starts.

Tests assert the requested hook was reached, the actual HTTP denial, and exact persisted
row counts. Clock injection models boundary crossing deterministically; these are not
latency measurements or claims about a production operating envelope. The maintenance
visibility assertion is qualified on both databases, including a distinct PostgreSQL
connection. No fake receipt tables, helper bypasses, commits mocked as success, runtime
write enablement, or fabricated current proof were introduced.

## Checks Actually Run

* Initial new cohort: 16 passed in 37.47s.
* Final full new cohort after test-only mypy import correction: **16 passed in 30.83s**,
  no skips; `final.log`.
* Final cleanup refinement, requiring the failure to reach Google Ads after OAuth:
  **4 passed, 12 deselected in 17.85s**; `final-cleanup.log`.
* Whole Ruff: passed. Full configured mypy: **1065 source files**, passed.
* `git diff --check`: passed.

Evidence directory: `/workspace/inlet-evidence/20261008/receipt-runtime-adverse/`.
SQLite and disposable PostgreSQL used isolated fixture schemas; no shared reset, Full
suite, hosted CI, live provider calls, credentials, advertising mutations or deployment.
Customer target-picker browser work remains a separate root-owned package.
