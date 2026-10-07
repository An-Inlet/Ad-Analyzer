# Confirmed Goal Currency Guard

The shared `initial_planning.calibration.current_objective` now compares the canonical
confirmed goal target-window currency to the owned reporting cohort currency. The goal
schema already requires consistent target/baseline currency. A mismatch returns409
`initial_objective_currency_mismatch` before calibration or preview admission. Explicit
customer CPA input does not authorize FX or reinterpret the goal's spending currency.
No extra goal constraints, conversion rates or policy defaults were introduced.

Actual owner login → confirmed Shopify goal → Meta HTTP import → retained captures →
calibration API tests passed for matching USD and mismatched EUR on SQLite and PostgreSQL:
4 passed in6.93s. Only provider fixture facts differ; no high-level service mocks or
prebuilt observations/calibrations are used. Rejection leaves no calibration/preview rows.

Final rerun after correcting a test import's explicit-export typing:4 passed in5.48s.
Whole Ruff and mypy (657 source files) passed. Local only; no live/remote/Full run.
