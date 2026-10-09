# Retained Accounting And Dispatch Classification

Base2847724. Sixteen individually reviewed functions cover41 frozen failures:
seven legacy simulation claim/dispatch/reconcile functions in test_mandates (13),
four explicit execution-consent/accounting functions in test_provider_execution_mandates (16),
three settled-period/consent-pinning/race functions in test_provider_period_accounting (7),
and two dispatch/reconciliation race functions in test_publication_dispatch_revalidation (5).

Bodies directly test retained execution state machines: actual claim/consent,
financial holds and high-water totals, stop interleaving, scope revisions, no replay
and no overspend. Reads are assertions on those same engine transitions. The
mixed modules' current API, pure constraint/draft and populated migration functions
are deliberately excluded; setup ancestry alone is not enough to classify them.

Only32 decorators added: existing per-function retained_execution/usefixtures pair.
AST comparison after removing the added decorators proves all original signatures,
parameters, bodies, other decorators and statements unchanged. In particular global
seed helpers stay unmarked and untouched. The test-scoped capability fixture restores
both guards; no deployed authority or provider calls are introduced.

Actual both-database command selected16 functions plus whole unchanged planning
provider-transport/execution boundary modules in the same process. Result:
**130 passed, 4 existing SQLite PostgreSQL-only skips, zero failures/errors,
76.955s JUnit**. Counts include41 repaired frozen failures,86 current boundary
cases, and3 existing SQLite early-return cases; those3 do not qualify PostgreSQL
concurrency. Four skips retain their original row-lock/commit-interleaving reasons.
Exact selectors, frozen XML identities, command JSON, raw log/XML/exit0:
`/workspace/inlet-evidence/20261009/retained-accounting-regression/`.

Whole Ruff, bare mypy1129 and diff checks passed. Independent review is required
before integration; no Full rerun or current mixed-module repair is implied.
