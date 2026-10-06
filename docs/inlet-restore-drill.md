# Synthetic PostgreSQL Restore Drill

B19 engineering qualification preparation; not a production backup configuration or
an intended-environment recovery sign-off. No customer data, provider grants, tokens,
or external provider calls are used. Existing operational runbook guidance remains
subject to the release and owner approval gates.

Run from the repository root with PostgreSQL `pg_dump`, `pg_restore`, and `psql`
on PATH, using the existing explicitly disposable test URL:

```sh
export AD_ANALYZER_CI_DISPOSABLE_POSTGRES=true
# AD_ANALYZER_TEST_POSTGRES_URL must already identify a local disposable test database.
python -m scripts.inlet_restore_drill
```

If tools are available only in an existing local test PostgreSQL container, explicitly
select it with `--postgres-container <test-container-name>`. The drill proves that the
SQLAlchemy connection and PostgreSQL tools refer to the same PostgreSQL system and
database before creating or dropping any schema. It creates no containers, databases,
roles, credentials, paid resources, or live backup schedules. It never accepts an
existing archive, source schema, target schema, or arbitrary restore command.

The existing destructive-test guard requires the exact disposable marker and controlled
`_ci`/`_test` database naming, rejecting names containing production/staging markers.
This drill additionally requires loopback addressing and forbids URL options. It uses
a newly generated UUID schema, applies the repository migrations, and seeds two
synthetic workspaces with users, memberships, session/revocation metadata, goal
revisions, and disconnected provider metadata without grants. Migration seed records
are included in the comparison. No existing schema is selected as a backup source.

Native custom-format `pg_dump` output is held in memory and supplied only to the
paired `pg_restore`. After checking the archive header and size, the drill drops only
its generated schema, restores it, verifies the head revision, runs upgrade-head, and
checks customer membership isolation and the actual PostgreSQL provider ownership FK.
The generated schema is cleaned in a finally block. Failure tests cover invalid
archives and restore failures while checking an unrelated sentinel schema survives.
The archive is not written, uploaded, or retained. Error output contains fixed messages,
not raw PostgreSQL output, DSNs, rows or archives. Existing disposable passwords, if
configured, are passed only in the subprocess environment, never command arguments.

Pre/post fingerprints include every row, columns, primary/foreign/unique/check
constraints, indexes and partial predicates, sequence state, effective schema ACLs,
and table privileges. ACLs are included in the dump. PostgreSQL can redistribute
unbounded varchar-to-text casts across string-array literals during dump/restore;
only that specific equivalent form is normalized. Boolean grouping/operators,
comparison changes, different literals and bounded varchar casts remain distinct.
Default versus explicit-but-equivalent schema ACL representation uses PostgreSQL's
`acldefault`/`aclexplode`; it does not omit privilege checks. Restoring as the same local
test role does not qualify real multi-role ownership recovery.

## Offline Evidence

Native PostgreSQL 16.15 custom archive restored successfully in the local disposable
container. The final CLI report verified **82 tables, 44 rows and two synthetic
tenants**, including schema/data/privilege equality, session revocation metadata,
owner isolation and rejection of cross-workspace provider ownership. The synthetic
archive was 348330 bytes in this run. Archive size and fingerprint can vary with the
random schema and migration seed timestamps; equality within the run is what matters.

Focused tests cover target guards, container identity mismatch, private subprocess
arguments, sanitized errors, refusal of arbitrary archives, narrow expression
normalization, real native restoration and cleanup after failure. Local runs without
native tools may explicitly select a test container through
`INLET_RESTORE_POSTGRES_CONTAINER`. Hosted CI requires native tools; missing tools
fail rather than silently skip. No broad Full run is claimed by this package.

## Remaining Intended-Environment Qualification

This is a logical restore of a generated schema on one disposable server. It does not
prove production backup configuration, point-in-time recovery, offsite durability,
real backup integrity, encryption-key recovery, media-object restoration, alerting,
RPO/RTO, or intended-environment IAM/network/application readiness. Those require a
separate approved operational drill using the actual release artifact and approved
infrastructure. Keep traffic, workers and advertising execution disabled during that
drill. Before serving restored data, reconcile deletions, consent changes and session/
provider revocations that occurred after the snapshot; preserving a revocation already
inside this synthetic backup does not prove post-snapshot reconciliation. Validate
role ownership/privileges and key availability separately. No live release readiness
or purchasability claim follows from this result.
