# Optimization Origin Metadata Repair

Local follow-up to `59a1235`; no runtime enabling, provider calls, schema rebuild,
provenance document changes or numeric policy changes.

## Reproduction

Reusing the actual registered ORM metadata in SQLite → PostgreSQL → SQLite order
omitted `fk_optimization_origin_digest` from the final SQLite database. SQLAlchemy's
PostgreSQL schema generator constructs `AddConstraint` with its default
`isolate_from_table=True`, which permanently suppresses later inline creation on
that shared constraint. SQLite cannot add it through ALTER.

On the unchanged predecessor, the regression failed inspecting the missing FK.
A separate synthetic actual-mandate reproduction then showed that a marked parent
without a sidecar could INSERT and COMMIT: the expected `IntegrityError` did not
occur. This is an authority-integrity defect, not merely a migration-test fixture
failure.

## Repair

A table `before_create` listener restores only the named origin constraint's DDL
creation rule. It preserves `use_alter`, the constraint name, deferred semantics
and PostgreSQL ordering. The narrow private SQLAlchemy attribute is documented
because the library's schema generator does not expose its `AddConstraint` option.
The actual cross-dialect test protects this compatibility assumption.

The SQLite insert trigger additionally requires the physical exact single-column
origin FK, independently of `PRAGMA foreign_keys`. The ORM trigger and the separately frozen SQL in the unreleased 0080 migration
both enforce this check. Migration SQL remains literal and imports no application
trigger definitions. The initial repair omitted that frozen SQL update; this
follow-up corrects it and tests both installed variants independently. Existing sidecar
immutability, populated financial relationships and lossy-downgrade refusal stay
intact. No deployed database repair is claimed.

## Verification

- Before repair: actual cross-dialect test failed on missing final SQLite FK;
  separate baseline missing-sidecar COMMIT was accepted.
- After repair: metadata, actual 0080 DDL, optimization contracts and provider
  mandate suite: **28 passed, 1 expected PostgreSQL skip**, terminal exit 0.
- Regression verifies physical FK columns/target/deferral, successful parent
  INSERT followed by missing-sidecar COMMIT rejection, plus independent malformed
  SQLite schema denial with FK enforcement enabled.
- Whole-repository Ruff passed; mypy app plus new test passed (455 files);
  `git diff --check` passed.
- No Full run, remote actions or live provider calls.
