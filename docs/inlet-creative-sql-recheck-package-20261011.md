# Standalone creative SQL recheck — 2026-10-11

Isolated from reviewed `582d1b2`; implements only the private SQL port in
`docs/design/creative-sql-recheck-interface-v1.md`. No service, policy registration,
PlanVersion, dependency, history, API, migration or runtime activation changes.

`creative_image_row_identity_digest` extracts the original factory implementation
with its identical domain and datetime serialization. Recursive validation rejects
unsafe copies; digest regression compares the old literal formula and existing
proof tests. Creator and creation time remain committed; only observed_at is absent
from the row identity, while the full proof retains the original observation times.

`recheck_collected_creative` accepts a caller-owned active, clean, nonnested root
Session and unchanged underlying Connection transaction. It validates ticket,
saved creative input, complete envelope, original actor/session, and aware UTC now.
The trusted authorize callback is SQL-only and owns the original identity fact;
this port independently checks original-session/owner scope, paid entitlement,
confirmed goal and privacy before and after media locks, including empty input.
Clean root identities are checked before/after callbacks and every SQL phase, with
autoflush suppressed. Media rows reload under locks in customer order; all row
fields including creator/time must match. Fresh database wallclock sampling checks
future ticket/input/image instants and preserves UTC ordering across DST folds.
The original observations are never restamped. No storage, decoder or provider
calls occur, no transaction is opened/committed, and genuine callback failures
propagate. The caller must roll back any failed surrounding transaction.

Tests use actual owned uploads, goal confirmation, original session and
`collect_pinned` before rechecking. They qualify empty/single/multiple images,
metadata and ownership changes, missing rows, scope/paid/goal/privacy revocation,
unsafe copies, no active root/dirty/nested/replaced transactions, callback errors,
UTC fold negatives and offset-equivalent success. Final-boundary injected changes
prove independent rechecks and rollback without partial writes. This is a private
port fixture, not a public generation or v5 authority claim.

Evidence is retained under
`/workspace/inlet-evidence/20261011/creative-sql-recheck`. Initial SQLite gate:
27 passed, 26 PostgreSQL cases deselected, 15.18s. The intentionally sabotaged
underlying Connection test emits SQLAlchemy's expected deassociated-transaction
warning during caller cleanup; no product warning is suppressed.

Final qualification:

- `both01.log/xml`: new actual SQL tests plus unchanged creative proof tests,
  **82 passed, zero skips, 96.58s**; two expected cleanup warnings described above.
- `final02.log/xml`: added final-boundary mutation and absent-root cases,
  **12 passed, 61 deselected, 19.04s**. These are additional cases, not a full rerun.
- Whole `ruff check .`: passed (`ruff-final.log`).
- Configured `mypy --cache-dir=/tmp/inlet-creative-sql-mypy`: passed **1387**
  source files (`mypy-final.log`). `git diff --check`: passed.
- Both database commands use existing disposable test PostgreSQL with random
  per-test isolated schemas and SQLite, unique `/tmp/inlet-creative-sql-*`
  basetemps, durable JUnit and `--durations=20`. No database reset.
- No pytest failure occurred; initial SQLite and static logs retained. No Full,
  live calls, remote push, deployment, or public authority activation.

