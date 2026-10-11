# Genuine v5 retained-source dispatch — 2026-10-11

Isolated child of approved `f509f3a`. Implements internal retained-source dispatch
only, not generation service/capability registration, public defaults or API
activation. No migration.

The exact-v4 `capture_selected_retained_sources` wrapper remains unchanged in
meaning. Its original reporting/commerce body is shared through
`capture_selected_reporting_sources`, which parses genuine exact-v4/v5 documents
using the reviewed pure contract. It never makes a fake v4 copy or drops creative
proof. Its subset is explicitly incomplete for v5.

New `creative_retained_sources` combines actual complete selected/traffic/reporting
and commerce currentness with the separately frozen image metadata currentness
port. It requires exact root Session and underlying Connection identity, clean and
nonnested throughout, strict UTC time and final checks after DB clock sampling.
It retains READ_ROLES, no paid restriction, original SQL session/goal/privacy
checks, and no provider/storage/decoder IO. The creative witness is exact, retaining
original generation commitment and image observation times even for empty images.

Generic v5 recheck reaches clean transaction preflight BEFORE the old generic first
SQL guard. Legacy/v4 guard ordering and error boundaries remain unchanged. Complete
historical dependency validation runs before current comparison; no filtering out
creative, ordinary refs, selected, traffic or commerce evidence. Reporting/commerce
comparison excludes only their save observation time under the existing interval
rule; creative comparison includes every original field. Unexpected DB/runtime
errors propagate; expected malformed/source errors keep existing classifications.

Tests reuse actual reporting/range/media history/currentness fixture ports and
exercise generic capture/recheck directly. This direct retained-persistence fixture
is not a claim of enabled v5 customer generation. Planned evidence includes viewer/
unpaid empty/multiple, every missing/extra dependency, metadata/reporting/goal/
privacy/session loss, no IO, dirty/nested/replaced transactions, final DB-clock
Connection replacement and unchanged v4/event/history regressions.

Dependency: frozen reviewed currentness `841b587` was cherry-picked as `0121337`
before any imports/tests. No WIP currentness code was copied. Initial actual SQLite
viewer/unpaid empty/single/multiple gate: **3 passed, 19 deselected, 23.48s**.
Evidence retained under `/workspace/inlet-evidence/20261011/creative-retained-dispatch`.
First mypy log retains one test-only implicit imported-symbol access error; importing
the same database clock directly from its defining module fixes typing without
changing test or product behavior. Final whole Ruff and configured mypy passed,
**1402 source files**. Database final outcome follows after process termination.
Fresh-process imports of combined, generic retained and selected witness modules
also passed (`import-final.log`), avoiding reliance on test bootstrap import order.

Final bounded qualification: **70 passed, zero skipped, 309.82s**, terminal exit0
(`both01.log/xml`), covering new22 SQLite/PostgreSQL dispatch cases plus existing
`test_selected_retained_dispatch.py` and `test_planning_retained_sources.py`.
Four SQLAlchemy cleanup warnings come solely from deliberate underlying Connection
transaction replacement in two both-database tests; no product warning suppressed.
No pytest failure occurred. Test command used `--durations=20`, unique
`/tmp/inlet-creative-dispatch-both01` basetemp and durable JUnit on the existing
per-test isolated disposable PostgreSQL database (no reset). Whole Ruff/configured
mypy1402/fresh import/diff outcomes retained alongside the initial static log.
No Full, live calls, hosted CI, push, merge or deployment performed.
