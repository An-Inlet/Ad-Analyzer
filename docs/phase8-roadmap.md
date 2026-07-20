# Phase 8 Roadmap Supplement

The complete project roadmap is `docs/project-roadmap.md`. This file is a Phase 8 supplement only and must not be treated as the complete project roadmap.

Phase 8 remains limited to read-only analytics and uses the approved four-PR split:

1. **8.1 Analytics foundations**: calculations, schemas, account-local windows, settings, and tests. No database migration and no read-only tables.
2. **8.2 Repository aggregation and query safety**: PostgreSQL aggregation, account isolation, pagination, and query-plan-justified index migration only.
3. **8.3 Deterministic findings service and API**: rules, service, API endpoints, authorization, and no-write tests.
4. **8.4 Dashboard analytics views**: dashboard route, templates, CSS, and dashboard tests only.

Phase 8 findings should be calculated live unless a later human decision explicitly approves persistence. Phase 8 must not implement recommendations, approval workflow, controlled execution, live Google Ads writes, or production deployment.

Corrected requirements remain: distinguish `window_days`, `days_with_metric_rows`, and `data_coverage_ratio`; derive comparison windows server-side; distinguish observed zero from unavailable or unsynchronized metrics; use integer micros and `Decimal`, never `float`; apply findings pagination only after deterministic rules and sorting; add database indexes only when justified by actual query plans; treat search-term text as sensitive; run migration downgrade testing only against disposable PostgreSQL; never implement Google Ads writes during Phase 8.
