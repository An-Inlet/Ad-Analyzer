# Current Provider DDL3 Qualification

Implementation follows approved `40789f8` interface on
`codex/inlet-provider-ddl3-interface`. Three original failed PostgreSQL nodes retain
current Alembic operations, current database constraints, and all original
assertions. This is fixture compatibility qualification, not new execution
functionality or live-provider verification. No historical manifest changed.

## Source And Current Boundary

The unchanged financial `source_only` producer supplies original owned source
rows. New closed `provider_ddl` phases use the verified literal2155 source and
only original prepare, prepare+approve, or consent. Every phase ends before the
parent changes schema. Parent and child require owned disposable PostgreSQL
schemas, exact current migration heads (or the existing metadata-only FK fixture),
exact scalar source, physical schema fingerprint and full row snapshot. Only the
specified qualification/review/approval append or consent+draft-to-active delta
is permitted. No execution review, approval, run, step, attempt, response, receipt
or hold is created. Current `revise`, `checked`, and the original spent-high-water
mutation remain in the current parent.

The approved migration bootstrap correction admits exactly the owned source
workspace plus the actual `expected_bootstrap()` workspace, only for validated
`inlet_migration_fixture_<uuid>` schemas. Every bootstrap projected value is
checked. Metadata `inlet_test_<uuid>` still requires one workspace. All original
bootstrap and other full row bytes remain unchanged across each child phase.
Extra workspaces, changed bootstrap values and unapproved URL queries are rejected.

SourceLifetime has one additive fixed profile; its utility, generic runner and
extractor remain unchanged. Only verified reaped source extracts are removed;
source IDs, input hashes, provenance, media and child logs remain outside extracts.
No runtime object or authority crosses the subprocess boundary.

## Preserved Evidence And Initial Failures

Durable evidence root: `/workspace/inlet-evidence/20261010/provider-ddl3/`.
All pytest runs use unique explicit basetemps; copied artifact directories retain
unique IDs, media, source hashes and child logs outside temporary storage.

- Original cross-workspace FK probe: **1 passed,44.47s**, `fk-probe.log/xml` and
  `fk-artifacts/`.
- First qualification migration probe: **1 failed,24.88s**,
  `qualification-probe.log/xml` and `qualification-artifacts/`. Both actual initial
  downgrade/upgrade operations completed; the new fixture's one-workspace
  precondition rejected the real migration bootstrap workspace before child IO.
  This was not a production DDL failure. The approved exact bootstrap correction
  is described above; this failure remains preserved.
- Corrected qualification migration probe: **1 passed,42.50s**,
  `qualification-probe-02.log/xml`, `qualification-02-artifacts/`.
- Execution migration probe: **1 passed,52.47s**, `execution-probe.log/xml`,
  `execution-artifacts/`.
- Initial targeted typing found eight errors from reusing one local name for two
  ORM model types (`initial-mypy.log`). Distinct local names repaired these; no
  product semantics changed. A later targeted Ruff check found one101-character
  SQL string; splitting adjacent literals preserved its bytes.

`assertion-preservation.json` proves all four qualification and two execution
original assertion ASTs remain, exact Alembic call AST/order remain, and the
entire original foreign insert/nested transaction/flush is unchanged.

## Final Qualification

Final combined and static results are recorded after their terminal output below.
This package does not rerun W1, modify its result, or claim broader test-suite
success. Existing SQLite FK limitation remains outside the three PostgreSQL nodes.

Independent review additionally required exact full new qualification/review/
approval row equality, rather than allowing complete rows after selected-field
checks. The final successor validates all columns from the typed plan/evidence,
source and output IDs, fixed original NOW and NOW+5minute evidence expiry.
Timestamp and extra-column negatives exercise that exact-row boundary. Results
from before this strengthening remain separately identified.

- Pre-strengthening combined cohort: **118 passed,0 skipped/failures,18 Alembic
  warnings,140.66s**, `qualified.log/xml`: the3 current PG cases,13 new guard
  cases,86 unchanged planning execution/transport boundary cases and16 unchanged
  SourceLifetime cases. Artifacts copied to `qualified-artifacts/`.
- Final exact-row strengthening: **20 passed,0 skipped/failures,9 Alembic
  warnings,95.41s**, `strengthened.log/xml`: the2 affected current qualification
  cases plus18 pure guard cases, including5 copied timestamp/extra-column
  negatives. Artifacts copied to `strengthened-artifacts/`. The unchanged
  execution migration was not redundantly rerun after qualification-only edits.
- Final whole Ruff: exit0 (`ruff-closed.log`). The first strengthened Ruff run
  flagged local import ordering; sorting imports only repaired it after pytest
  finished. The initial finding remains in `ruff-strengthened.log`.
- Final bare mypy: exit0, **1234 source files** (`mypy-closed.log`), cache only in
  `/tmp/inlet-ddl3-mypy`. Final `git diff --check`: exit0 (`diff-closed.log`).

Exact combined/strengthened commands and local environment are in external
`commands.json`. Both used `/workspace/inlet-venv/bin/pytest -o addopts= -q` and
unique explicit `/tmp/inlet-provider-ddl3-*` basetemps; no default-temp rotation.
These results qualify the three current regressions and their closed fixture
seam. They do not change or replace the original frozen W1 observation.
