# Candidate Read DOM Unit Fixture

The original one-case test exercises the still-present candidate-read.mjs module
using Element, Option and mocked API doubles. It incorrectly sources its unit DOM
inventory from optimization.html, now the deliberately history-only current page.
The current module still exposes clear/invalidate/enable and its original review
request/stale-control behavior. No production change is required.

Replace only the driver DOM inventory with explicit unit fixture IDs: opt-candidates
and opt-candidate-policy/mandate/results/progress/message/load/read/refresh. Preserve
the original Python wrapper and every driver statement/assertion after setup, including
checked status shape, literal label, exact read/review bodies, no automatic requests,
late-response discard and detached stale review control. Remove unused fs import.
This is current module unit evidence with API doubles, not current-page integration,
real successful review authority or a browser journey. Do not restore controls on the
public customer page or alter current 409 server boundaries.

Qualify original one-case wrapper; separately run current history optimization
browser on SQLite/PostgreSQL and default write boundary tests. Preserve source proof
that only inventory/import changed; whole Ruff, mypy, Node syntax and diff checks.
No historical child or retained marker is needed: the current module itself is
executed. Count only the exact original case as targeted fixture repair, and keep
current actual page/browser qualification separate.
