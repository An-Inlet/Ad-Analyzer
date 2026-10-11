# Plan-version storage pair — source preparation

Base: diagnostic-only service branch at `f34f0e2`, preserving the failed API
qualification and all original evidence. Interface: root-reviewed `5e5d9da`
(`docs/design/planning-version-storage-pair-v1.md`). No service qualification or
incident closure is claimed.

The new exact-PlanVersion-only helper calls existing `canonical` once, including
all existing model and checked-serializer validation. It hashes precisely the
resulting UTF-8 bytes with the existing PlanVersion fingerprint domain and returns
two immutable strings. The repository uses the pair only at its existing adjacent
row construction after CAS; public digest/canonical, original source checks,
retained capture, all authority clocks and final guards remain unchanged.

Source-only test plan awaiting review/slot: 15 new pure cases cover genuine V1–V6
and explicit-empty V6 equality, invalid copies, exact model, one canonical call,
no PlanVersion.digest call, no cross-call cache, and canonical size bound. Preserve
the existing immutable V4/V5 golden test without snapshot changes. The already
planned actual positive API journeys additionally compare stored JSON/digest to
the pair; they are not separate positive reruns. Two new database fault cases
observe the actual caller transaction after CAS (head1, version rows0), raise a
fixed controlled error at pair production, and require complete planning and
financial rollback. These retain normal authority clocks and can still fail at
an earlier unrelated authority boundary; such a result must not count as pair
rollback qualification.

No tests have run for this source preparation. Independent source review precedes
execution. Google owns the disjoint retained-context change and current test slot;
root coordinates the combined source and exact actual API manifest. Neither nested
observer timing nor adjacent call-count removal proves a latency improvement or
resolution of R01/R02/R03.

## Authorized combined06 outcome — qualification stopped

Context repair author `fb2d864` was integrated as local ancestor `ee6ef59`.
Exact collection confirmed 16 pure and 28 API nodes. The final source manifest
retains 20 source hashes and the WIP binary diff; the unchanged stage observer and
runner were independently reviewed before root authorized execution.

All 16 pure cases passed (JUnit 10.124 seconds). The first actual case, SQLite
zero, failed with `409 planning_authority_expired`; the runner stopped immediately.
The other 27 API cases did not run. No retry, source change or limit change occurred.
The report contains one generation and no truncation. Failure was at the existing
post-retained/pre-CAS guard (`repository.save_generation:572`), fact age 6.519859
seconds, with roughly 28,780.96 seconds of session lifetime remaining. The new
storage-pair callsite was not reached, so actual paired-row storage and post-CAS
fault rollback remain unqualified.

Retained capture took 2.325768 seconds/774 SQL, nested owner capture 2.158192,
creative capture 1.746337 and selected reporting capture 1.098874. Seven owner
validator calls within retained capture totalled 0.795831 seconds with zero SQL.
Save inclusive was 6.515955 seconds/2,379 SQL; exclusive residual 2.378344 seconds
still includes 878 SQL statements and unwrapped work. Nested times are not additive.
This is no performance improvement or R01/R02/R03 closure. The controlled pure
single-serialization checks passed; customer flow remains blocked.

Durable evidence and exact hashes:
`/workspace/inlet-evidence/20261011/google-owner-v6-runtime/combined-06-summary.json`.
The sole test slot was released on terminal failure. Further actual runs require
root's cause-oriented plan; no ordinary retry is planned.

## Final static preparation

Whole Ruff first reported three test-only import/line-length findings, preserved
in `combined-06-ruff-01.log`; routine import sorting and formatting corrected them.
Configured no-path mypy first reported one test-only SQLAlchemy union typing issue
in the never-run post-CAS fault hook: `Update.table` can statically be a Join with
no `name`. The hook now reads `getattr(statement.table, "name", None)` before the
same exact PlanRow table-name comparison. For the actual intended Update(Table)
this is operation-equivalent; no production behavior, guard, clock or test result
was changed. The original mypy failure is retained in `combined-06-mypy-01.log`.
No actual case was rerun for these formatting/type corrections.

This package is a diagnostic-only local freeze. Pure byte/hash/unsafe-copy checks
passed, but actual service integration is not ready and rollback qualification
remains unrun. The separately reviewed context dependency remains an ancestor;
this commit adds only the storage pair, its focused tests, actual positive row-pair
assertions and this ledger.

Final whole Ruff (`combined-06-ruff-03.log`) passed; configured no-path mypy
(`combined-06-mypy-02.log`) passed across 1,476 source files; `git diff --check`
passed. Required checks are terminal. This static success does not qualify the
failed actual flow or the unexecuted rollback case.
