# Retired Execution Compatibility — Frozen Test Package

Implement the bounded direction in
[the verified plan](../inlet-retired-test-compatibility-plan-20261008.md), including
its exact historical pin and142-node manifest. This is test qualification, not new
execution functionality. Preserve current application source and default zero-write
boundaries. No shared database reset, network fetch, credential or release action.

First implement one pinned isolated subprocess harness with explicit local-object
and tree provenance checks, exact selected-node manifest, bounded timeout/output,
child JUnit, recursion protection and propagation of every unexpected child failure.
Use the unchanged historical source/tests/assets and current installed dependencies.
Run the exact cohort on the existing isolated SQLite/PostgreSQL fixture mechanisms.
A missing git object or dependency is an explicit failure, not a skip/fallback.

Then replace retired current invocations only with a reviewed, documented one-to-one
coverage map: original assertions run in the named historical cohort; substantive
current route/UI tests prove history, ownership/session denial and absent mutation
controls using actual current paths. Preserve shared fixture/helper imports. No
blanket marker, collection-ignore switch, skip/xfail, guard patch or unexplained
case deletion. If mapping requires additional historical tests, first record their
exact provenance and scope; never select only passing historical cases.

Current lifecycle, erasure, exports, schema and populated restore checks remain on
current production code. Do not archive those modules because their producer fixture
is old. Separately establish a bounded genuine historical producer-to-current-schema
fixture seam, first proving feasibility on both database backends with synthetic
local data only. Return actual row/provenance IDs, not old runtime objects. Keep this
seam distinct from executing archived assertions. If constraints make that infeasible,
report the concrete constraint and affected current cases before broad changes.

Existing current retained-engine tests remain where actual semantics are reachable;
use per-function classification. Preserve current planning-boundary tests unpatched.
Record exact old/new case coverage, commands, skips, failures and artifact paths;
require focused tests, whole Ruff, bare mypy, JS syntax as applicable and diff checks.
W1 aggregate remains a later single frozen run; do not run it inside this package.
