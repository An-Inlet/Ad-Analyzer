# Plan-Bound Sales Progress Backend — 2026-10-08

Base: `19c7717`; branch: `codex/inlet-plan-sales-progress`.
Interface: `docs/design/planning-plan-bound-sales-progress-v1.md`.

The additive `PlanSalesProgressV1`, `PlanningDocumentService.sales_progress`, and
required-version, no-store customer GET bind current Shopify merchandise net sales
to the exact retained plan document and confirmed goal. The existing hardened read
session refreshes identity before SQL and checks final authority after all locks.
Changed goal identity yields an explicit unavailable binding; source unavailability
retains the existing goal-progress reasons. Manual application and attribution remain
unassessed/unavailable. No schema, saved document, event, import, native advertising
request, or advertising write is introduced by the GET.

The computed output `net_sales_micros_exact` preserves signed integers beyond both
JavaScript's safe range and signed 64-bit range. It is derived from revalidated sales,
not accepted as input. The old nested goal contract remains unchanged.

## Evidence

New pure tests cover exact amount/null/zero/refund output, unsafe nested copies,
wrong goal binding and fingerprint domains. Actual SQLite/PostgreSQL service/API
tests generate an owned plan, import a real ledger correction and later closed day,
and reread the same immutable plan. They cover unavailable goal/source states,
viewer/foreign/session/privacy boundaries, expired plan readability, identity IO
outside SQL, and actual PostgreSQL goal-lock waiting past final authority expiry.
The SQLite lock-wait case is intentionally skipped.

The defensive missing-goal lookup case injects the lookup's 404: current plan input
foreign keys prevent physically deleting the referenced goal. Actual semantic plan
erasure separately proves a 404. Closing workspaces use the existing 404 behavior.
Read roles retain existing read entitlement semantics; no new paid-work gate is added.

Final cohort: **68 passed, 1 expected SQLite lock-wait skip, 1 intentional unsafe-copy
serializer warning in 124.46s**. The warning accompanies rejection of a copied float
where the old nested contract requires an integer. Retained raw artifacts:
`/workspace/inlet-evidence/20261008/plan-sales-progress/backend.log` and
`/workspace/inlet-evidence/20261008/plan-sales-progress/backend.xml`.

Commands:

```text
AD_ANALYZER_TEST_POSTGRES_URL=postgresql+psycopg://postgres@127.0.0.1:55432/inlet_oct07_next_integration_ci AD_ANALYZER_CI_DISPOSABLE_POSTGRES=true /workspace/inlet-venv/bin/pytest -q -o addopts='' tests/test_plan_sales_progress_contracts.py tests/test_plan_sales_progress.py tests/test_planning_documents_api.py tests/test_planning_document_responses.py --junitxml=/workspace/inlet-evidence/20261008/plan-sales-progress/backend.xml
/workspace/inlet-venv/bin/ruff check .
/workspace/inlet-venv/bin/mypy
git diff --check
```

Ruff and diff check passed; configured mypy passed 1,087 source files. Earlier narrow
authority/IO/later-day cohort: 13 passed, 1 expected SQLite skip, 18 deselected in
43.60s. Earlier exploratory failures were fixture due-time, an impossible physical
goal deletion under existing FKs, and an incorrect closing-status assertion; these
were corrected without changing production authority, cadence, or foreign keys.
The reported environment disconnect did not interrupt the active process or lose
files; its normal terminal assertion result was inspected before continuing.

No Full, hosted, live Shopify/native provider, browser or expert-quality acceptance
is claimed by this backend package. Browser integration is a separate reviewed lane.
