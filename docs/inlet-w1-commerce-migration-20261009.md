# W1 Commerce Migration Producer Feasibility

Approved single-phase interface `698f9e4`, sibling-head correction approved after
the first bounded probe. Tests only: one closed producer mode and six-scalar DTO.
No production code, current guard/privacy patch, schema fabrication, social
phase protocol or Full run.

The original test creates its UUID PostgreSQL schema and runs current real0047,
0051 and0053 DDL. The helper verifies the exact0051+0053 Alembic head set and empty
commerce graph, extracts locally verified PIN2155ff3 app/tests, then runs the
original pinned commerce complete/CommerceSync producer under the pinned test's
historical candidate adapter. Child closes its committed Session before writing
IDs/counts. Parent checks strict output fields/types/counts and fresh owned SQL
readback, unchanged table names and exact revision set. Existing modes retain
their allowlists; only the commerce mode admits inlet_publication_UUID.

All original current downgrade/re-upgrade assertions remain: publication/evidence
tables disappear, preexisting workspace and actual commerce order survive, then
re-created publication/evidence tables are empty. The producer's exact IDs now
strengthen the former nonnull checks. No old ORM objects or authority cross.

First probe: **1 failed, 0 skips, 2.992 seconds**, before child startup. The initial
interface assumed0053 was a singleton head. Source inspection proves0051 and0053
are sibling revisions, both down_revision0047; the original test installs both.
The correction requires exactly both heads before and after, not an arbitrary
superset. Next actual case: **1 passed, 0 skips, 8.140 seconds**.

Evidence root: `/workspace/inlet-evidence/20261009/w1-migration-commerce/`.
`initial.log/xml` preserves the failed contract probe; `heads.log/xml` and
`heads-artifacts/` retain the first passing real migration and producer output.
Final compatibility result is recorded below after terminal completion.

This closes only a historical-schema producer mismatch when qualified. Frozen
W1 remains unchanged. Four other PostgreSQL migration profiles, especially the
social populated two-phase chronology, require their separate approved work.

Final bounded command (explicit disposable PostgreSQL environment):

```text
pytest -q tests/test_commerce_publication_migration.py \
  tests/test_retired_producer_current_lifecycle.py \
  tests/test_retained_initial_rule_lifecycle.py
```

**5 passed, 0 failures/errors/skips, 61.351 seconds**: actual PostgreSQL commerce
migration plus existing genuine review/current-privacy and initial-rule/current
0085 refusal on SQLite and PostgreSQL. `final.log/xml` and `final-artifacts/`
retain the test and pinned-child evidence. Whole `ruff check .`, bare `mypy`
(**1127 source files**) and `git diff --check` passed after the source changes.
Initial Ruff line-length/import formatting findings were corrected; no assertions
or production behavior changed for those static repairs. Independent review is
required before integration; no aggregate green claim follows from these cases.
