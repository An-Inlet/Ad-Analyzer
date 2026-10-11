# Selected Plan Read And Export Integrity

Plan-version repository reads and customer archive serialization now invoke the
historical validator for v4 documents carrying selected proof. It requires the
exact retained version row and complete dependency/capture graph. Missing proof
dependencies fail reads with 409 and abort archive preparation; export without an
owned database snapshot fails. Old plan policies keep their existing behavior.
V4 generation and capability registration remain disabled.

SQLite and PostgreSQL each passed the strengthened read/export test: an explicitly
assembled and persisted no-selection v4 document survives changed mutable metrics,
appears in the real authenticated consistent-snapshot archive, rejects missing
dependencies, and is removed by semantic privacy erasure, which also revokes the
prepared archive authority. These are actual repository/serializer/archive/privacy
paths, not an HTTP planning route or actual v4 composer result. A chosen-capture
archive and ordinary later-import qualification remain integration work.

Checks: final `test_selected_plan_history_read_export.py -k sqlite` and `-k postgres`
each passed 1 test with explicit PostgreSQL disposable opt-in; 80 pure history and
legacy document-contract tests passed; 2 legacy SQLite storage/migration/export
tests passed. Whole Ruff, configured mypy (1340 files) and diff checks passed.
Evidence: `/workspace/inlet-evidence/20261011/selected-plan-history/`, especially
read-export-sqlite-05, read-export-pg-06, read-export-pure-03,
read-export-legacy-sqlite-04 and read-export-mypy-06. Earlier successful basic tests
and initial static failures are preserved, not counted as additional coverage.

Independent source review closed the preceding current-witness package 5501450.
Future service integration must preserve the existing typed error boundary,
including authentication, permission and billing exceptions.
