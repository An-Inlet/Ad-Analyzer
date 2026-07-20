# Phase 8 Roadmap Supplement

The complete project roadmap is `docs/project-roadmap.md`. This file is a Phase 8 supplement only and must not be treated as the complete project roadmap.

Phase 8 remains limited to read-only analytics: calculations and account-local windows, PostgreSQL aggregation, deterministic findings, analytics API, and read-only dashboard. Phase 8 must not implement recommendations, approval workflow, controlled execution, live Google Ads writes, or production deployment.

Corrected requirements remain: distinguish `window_days`, `days_with_metric_rows`, and `data_coverage_ratio`; derive comparison windows server-side; distinguish observed zero from unavailable or unsynchronized metrics; use integer micros and `Decimal`, never `float`; apply findings pagination only after deterministic rules and sorting; add database indexes only when justified by actual query plans; treat search-term text as sensitive; run migration downgrade testing only against disposable PostgreSQL; never implement Google Ads writes during Phase 8.
