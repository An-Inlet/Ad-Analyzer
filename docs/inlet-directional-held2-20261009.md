# Current Directional Held-Successor Regression

This test-only package implements the reviewed staged interface in
[directional-new-held2-staged-source-v1.md](design/directional-new-held2-staged-source-v1.md)
from `d5e247f`. It repairs exactly the two original SQLite/PostgreSQL identities
of `test_newer_held_original_without_receipt_blocks_old_qualified_anchor`.
It does not change production or advertising-write availability.

## Temporal And Storage Proof

The pinned child creates the genuine original Google receipt, commits and closes
its Session, then waits. Current code reconstructs the original work from owned
rows and successfully resolves that original opportunity. Only then does the
parent send the single literal `claim` command and EOF. The child reopens a Session
and uses its original retained runtime to prepare, approve, create and claim the
46m successor without executing it. No runtime or authorization callable crosses
the process boundary. Current code then resolves the same original work and
rejects it with the original `verified current original action` assertion.

All current metadata tables are snapshotted. Current reads must change no rows.
The transition permits only the reviewed typed additions and exact predecessor
reservation, canceled original run and ledger deltas. Typed plan/request/audit,
approval, step and reservation bindings are checked against actual owned rows.
The original response and receipt remain identical; there is no successor response
or receipt. SQLite uses its actual owned file consistently; PostgreSQL uses the
validated disposable loopback database and isolated schema. Neither copies rows
into an unrelated engine.

The helper has a closed SourceLifetime profile, bounded scalar output/logs and
180-second operation deadline including the first current read. Invalid commands,
duplicate commands, EOF, parent deadline and output overflow reject without adding
a successor. Child processes are reaped; unsuccessful operations preserve source
artifacts. These negative cases occur before a successful claim and do not claim
that arbitrary interruption during a committed transition rolls it back.

## Checks Actually Run

Evidence directory: `/workspace/inlet-evidence/20261009/directional-held2/`.

- `closure.log/xml`: 2 passed, 16.51s. Preliminary genuine child Session-close/reopen
  compatibility probe only; not current-reader acceptance.
- `positive.log/xml`: 2 passed, 18.42s. Initial current staged acceptance before
  additional typed graph checks and strict path validation.
- `protocol-positive.log/xml`: 7 passed, 37.65s. Five protocol negatives plus both
  current database cases; superseded by the final cohort below.
- `qualified.log/xml`: **111 passed, 0 skipped, 0 errors, 55.820s**. Final source:
  2 staged cases, 5 protocol negatives, 86 current planning boundaries,
  16 SourceLifetime cases and 2 existing receipt-erasure compatibility cases.
- Whole `ruff check .`: passed (`ruff-final.log`). Whole mypy: passed,
  1210 source files (`mypy-final.log`, explicit `/tmp` cache). Standalone lifetime
  script mypy: passed (`mypy-script.log`). `git diff --check`: passed.
- `verify_ast.py` / `ast-proof.json`: all other module statements and target
  arguments unchanged; original initial current read, claim assertion and final
  rejection preserved; four original transition calls moved AST-identically into
  the child. `coverage.json` intersects the final JUnit with exactly the two
  original frozen failed identities. Compatibility counts are not extra credit.

The final pytest invocation selected the named directional case,
`tests/test_directional_held_protocol.py`, both planning boundary modules,
`tests/test_producer_source_lifetime.py`, and
`test_optimization_candidates.py::test_receipt_append_erases_derived_only`.
Both database variants used the existing disposable PostgreSQL fixture schema;
there was no reset or external provider traffic.

Initial Ruff construction findings and 12 mypy errors (Session variable reuse,
explicit import typing and scalar dictionary inference) are retained in
`ruff-initial.log` and `mypy.log`; they were corrected before final qualification.
No pytest failure was observed in this package. Cohorts overlap and must not be
summed. No Full, aggregate, hosted or live qualification was run. Independent
review of this frozen successor remains required before integration.

## Reviewed Storage Followup

The review of `e650295` required stricter pre-I/O storage ownership and physical
DDL preservation. Artifact paths now must be absolute, contain no `..`, and have
no symlink in the path or ancestors before mkdir. The parent exclusively creates
the SQLite file, then validates its exact unresolved owned path, regular-file
status and plain SQLite URL before constructing an engine. The child independently
checks the same exact path and all ancestors; resolved aliases are not accepted.

The existing `schema_snapshot` physical columns/FKs/indexes/checks/triggers/revision
fingerprint is captured before stage1 and compared after stage1, before and after
stage2, and after the current consumer returns. It supplements the full row graph
and replaces table-name-only preservation. Error-source retention is unchanged.

`storage.log/xml`: **16 passed, 0 skipped, 62.21s**: both current database cases,
five existing protocol cases and nine pure path/URL negatives. Parent path tests
fail if mkdir occurs; child URL tests fail if the engine factory is reached.
Initial followup mypy found three explicit-export typing errors in those new tests
(`storage-mypy-initial.log`). They were corrected by importing the same stdlib
modules/PIN directly, with no fixture behavior change. The affected pure tests
then passed **9, with 5 intentionally deselected, 2.31s**
(`storage-pure-final.log/xml`). Whole Ruff and mypy1210 passed
(`storage-ruff.log`, `storage-mypy.log`); diff check passed. The earlier111 run is
preserved as predecessor evidence, not asserted to be a rerun on this successor.
No new aggregate or external calls occurred. Independent followup review required.
