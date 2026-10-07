# Migration Fixture History Repair

Isolated repair based on root `56514e7`. Production migrations are unchanged.

The privacy identity/backfill test populated an ORM `create_all` schema, stamped it
as the latest Alembic revision, then downgraded. Those schemas are not equivalent:
revision0061 creates the named `pk_customer_workspace_billing` constraint, whereas
the ORM-created table has an unnamed primary key. On original baseline `9e56413`,
the unmodified test was independently reproduced failing when0061 attempted to
drop that missing named constraint (`/tmp/inlet-privacy-pk-baseline.log`). On root
`56514e7`, it fails earlier because `stamp("head")` is ambiguous across0062/0063.

A bounded search identified the same stamp-head pattern in six more test definitions:
commerce privacy tombstones and replay/export (two parameter variants), customer
goals, Meta child metrics, Meta checkpoint staging, and TikTok account preservation.
All seven additional PostgreSQL cases failed on unmodified `56514e7` at the same
stamp-head ambiguity (`/tmp/inlet-migration-fixtures-baseline.log`).

[The dedicated fixture](../tests/migration_engine.py) now builds each PostgreSQL
schema from empty using actual `upgrade("heads")` before any populated test setup.
It requires the existing explicit disposable flag and guarded test-database URL,
creates a uniquely named schema and drops only that schema during cleanup. No public
schema reset, other-schema access, fictitious stamp or general customer fixture
change is introduced. SQLite retains the existing offline ORM behavior; migration
round trips remain PostgreSQL-only where they already were.

The seven affected test definitions use this fixture, retain their explicit downgrade
targets, and re-upgrade real `heads`. This supports the current independent migration
branches and a later merge revision. The historical identity/key/domain-alias,
tombstone/reconciliation, goal snapshot erasure, campaign metric, compound parent
ownership, checkpoint cleanup and refuse-to-orphan-account assertions are unchanged.
No missing production constraint was suppressed or conditionally ignored.

Two other stamp calls remain intentionally untouched: the billing scope/offer tests
use them only in their explicit SQLite reconstruction of the historical billing0031
schema. Their PostgreSQL paths already run actual migrations, so they do not share
this create-all/head-stamping failure.

## Verification

The exact affected-node matrix ran on the explicitly disposable PostgreSQL service
and SQLite: **15 passed, one expected PostgreSQL-only SQLite skip**, with23 existing
Alembic path-separator deprecation warnings,17.83seconds. This includes all eight
affected PostgreSQL cases. Log: `/tmp/inlet-migration-fixtures-final.log`.

Whole-tree `ruff check .`, configured `mypy` (538 files), and `git diff --check`
passed. No Full, live provider request, production migration, deployment or merge
was performed. The earlier baseline failures remain evidence, not pass results.
