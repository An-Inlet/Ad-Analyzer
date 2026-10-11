# Original-Session Selected Capture API — 2026-10-11

Branch: `codex/inlet-w1-followup`. Predecessor: `5db16ca`.

## Implemented Behavior

The explicitly injected customer runtime exposes POST
`/api/customer/v1/workspaces/{workspace_id}/reporting/google/captures`. Customer
CSRF/session/owner checks precede original-session acquisition. The request binds
an explicit account, immutable selection pair, 32-hex request/capture ID and local
closed dates. The retained current capture is the receipt: identical semantic
replay reads the whole current graph without provider HTTP. Changed, stale and
foreign selectors fail without silently fetching replacement evidence.

Actual Google selected HTTP and the bounded collector execute outside SQL. The
final transaction compares the original selection, aggregate completion/manifest,
source grant/login, full native/local campaign mapping, privacy and deadline before
saving a complete graph. Private source pins also protect event options and
confirmation before the resolver's first read and after its last callback. No
private grant or manager-login value enters a customer DTO or retained receipt.

Only exact capture-header uniqueness errors are recoverable after savepoint
rollback. The current owner/session and semantic receipt are checked again; a
foreign request-ID winner produces a generic conflict, never a foreign receipt.
Other integrity errors propagate. This is bounded request replay, not permanent
cross-erasure deduplication or an acquisition-actor provenance claim.

SQLite explicitly starts its outer transaction before authorization SQL: its
legacy driver otherwise permits a SAVEPOINT release to commit before the final
session check. PostgreSQL keeps its existing transaction behavior.

## Evidence And Limits

All paths below are under `/workspace/inlet-evidence/20261011/`.

- `selected-capture-api01`: 91 tests, zero failures/errors/skips, 149.751 seconds.
  Initial actual API/capture/customer/resolver cohort before the private pin repair.
- `selected-capture-api02`: retained unsuccessful expanded run: 50 failures among
  109 cases due to a wrong source-scope attribute in the new pin comparison.
  Static checks independently caught the same field typo. No passing claim.
- `selected-capture-api03`: corrected 109-case overlapping cohort, zero
  failures/errors/skips, 144.029 seconds in JUnit. The shell session was interrupted
  during a resource pause after complete JUnit/output; do not claim clean shell exit.
- `selected-capture-api04`: retained collision regression failure exposed SQLite
  early savepoint commit. Two PostgreSQL cases skipped because the disposable-DB
  opt-in was missing from that command. This is failure evidence, not qualification.
- `selected-capture-api05`: final expanded cohort and whole static check evidence;
  terminal result recorded after completion below.

The collision regression uses real database duplicate-header INSERT errors and a
deterministic post-error foreign-winner seam; it is not a simultaneous multi-process
cross-workspace load test. Actual membership/CSRF/stale receipt rejection is tested
separately. Provider transports, credentials and identity are local fixtures.
No live provider, browser-flow, range-to-plan or purchasable-release claim is made.

A resource pause preserved the 1 GiB workspace reserve by relocating inactive
regenerable pytest caches to `/tmp/inlet-cache-relocation-20261011/` with original
symlinks and a manifest. The frozen baseline checkout cache, qualification archives,
database snapshots and original failure evidence were not deleted or replaced.
PostgreSQL suites are serialized across authors to avoid overlapping growth.

Next: reviewed 0092 range receipts plus atomic genuine range publication, then
persisted selected capture input and the additive v4 planning evidence consumer.
Q01–Q16 remain partial. Remote/hosted/live/merge/deployment holds remain in effect.

Final qualification: `selected-capture-api05` exited 0: **118 tests passed, zero
failures/errors/skips, 147.035 seconds** across SQLite and disposable PostgreSQL.
This overlaps the earlier 91/109 cohorts; do not add their counts. It includes real
HTTP receipt replay, positive/zero/absent observations, CSRF/foreign ownership,
source/privacy/session races, final grant/login changes, exact uniqueness recovery
and zero-write rollback after released storage savepoints. Whole-repository Ruff
and mypy passed (1299 source files); `git diff --check` passed. Independent source
review closed the private pin, collision translation and SQLite transaction fixes.
