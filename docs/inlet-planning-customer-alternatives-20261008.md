# Three-Platform Customer Alternatives Acceptance

Date: 2026-10-08. Base: `1d3179a`. Branch: `codex/inlet-planning-alternatives`.

This test-only package is partial Q05/Q07 contract acceptance, not comprehensive
planning-quality qualification. No production code, schemas, provider permissions,
or execution guards changed.

## Actual Path And Fixture Boundary

`tests/test_planning_customer_alternatives.py` runs on SQLite and disposable
PostgreSQL. It uses the existing real Google reporting/Shopify fixture, owned Meta
and TikTok connection records, and concrete HTTP mock native collectors. It edits,
previews, and confirms the goal through customer APIs with a USD 1,000 ceiling,
reads a retained V2 target catalog for each account, then creates and generates
the plan through the actual API, service, composer, and SQL storage.

The two customer hypotheses allocate Google/Meta/TikTok USD 400/300/200 with USD
100 unallocated, and USD 300/400/200 with USD 100 unallocated. Assertions preserve
each exact target selector, platform, amount, and independent reconciliation.
Generated alternatives retain `customer_supplied_hypothesis` provenance,
`independent_alternative` semantics, no forecast, and unassessed native conversion.
The output has no spending authority, no enabled advertising writes, and no native
budget proposals; its explicit non-causal reporting limitation remains present.
Generation reuses the three retained catalogs without new native requests. Social
HTTP requests are GETs; execution run and attempt counts remain zero.

Separate requests with USD 400/400/200 plus USD 100 unallocated, a negative amount,
and a fixed allocation contradicted by the second alternative each return 422.
After each rejection, all plan, input, version, dependency, event, request receipt,
input-catalog link, execution run, and execution attempt tables remain empty.
Previously obtained source/catalog receipts are intentionally retained.

Connection fixtures do not create planning documents or execution artifacts.
Meta/TikTok reporting history is intentionally absent; native catalogs are read
from MockHTTP and account ownership is real local SQL. This is not a complete
cross-platform performance basis, optimized allocation, causal conversion total,
native-budget translation, forecast, or live-provider qualification. No customer
purchase, deployment, or full aggregate test run is claimed.

## Checks Actually Run

- `AD_ANALYZER_TEST_POSTGRES_URL=<local disposable PostgreSQL> AD_ANALYZER_CI_DISPOSABLE_POSTGRES=true /workspace/inlet-venv/bin/pytest -q -o addopts='' tests/test_planning_customer_alternatives.py --junitxml=/tmp/inlet-alternatives-final.xml`: **2 passed in 16.72s**, no skips.
- `/workspace/inlet-venv/bin/ruff check .`: passed.
- `/workspace/inlet-venv/bin/mypy`: passed, 1,067 source files.
- `git diff --check`: passed.

The initial run failed both database cases because the new TikTok connection
fixture omitted required reporting-window dates. Adding those fixture fields
fixed the setup; no reporting coverage was fabricated and no product code changed.
The subsequent two-database run passed, followed by the final run above after
strengthening native-budget and causal-limitation assertions. Initial and final
JUnit evidence and final output are retained under
`/workspace/inlet-evidence/20261008/planning-alternatives/` outside git.

Next: independent review and integration, followed by the separately specified
evidence-semantics and comprehensive planning-quality work. This package does not
resolve missing source-presence semantics or claim the full frozen quality basis.
