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
revisions, disconnected provider metadata without grants, and the populated recovery
graph described below. Migration seed records
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

## Populated Recovery Graph

The self-contained `scripts/inlet_restore_fixture.py` imports no test fixtures and
uses only an injected HTTP MockTransport. Workspace A has a service-confirmed synthetic
zero-sales baseline, separately consented contract-test execution mandate, and two
actual coordinator budget operations. The first synchronous mock request completes;
a separate explicit mock terminal-request fact qualifies its replacement. Target-state
readback alone is not treated as original-request finality. The replacement is admitted
through the real atomic transfer service. Its mock request times out with unknown
outcome, retaining its original attempt/fence and successor hold. The graph includes
one superseded predecessor, one held 40,000,000-micros successor, 1,000,000 micros of
reported high-water and 2,000,000 micros of cumulative positive-change charges.
These amounts and bounds are synthetic contract scenarios, never native spending proof.

Workspace B contains typed immutable Meta image source/configuration metadata and an
exact service-created no-DSA configuration approval. This is a metadata recovery
fixture: its declared media object is not backed by restored image bytes, and it does
not qualify media storage recovery or a currently publishable campaign.

Before and after native restoration, behavioral verification checks document hashes,
scalar lineage, exact approval, source commitment, retained financial amounts, scoped
export sections and owner-only receipt/review access. A fully available offline runtime
is supplied to the real coordinator: the unknown successor cannot acquire another
claim, replay its original claim, qualify another replacement, or refund its emitted
hold. No HTTP request is emitted by those verification attempts; the denial is not a
disabled-runtime 503. Cross-workspace replacement, approval and account substitutions
must fail database foreign keys. A final fingerprint verifies behavioral checks did
not change the recovered rows, counters or sequences. Verification assertions must be
enabled; the CLI rejects Python optimized mode.

This does not test a complete downloadable customer archive or workspace closure;
those are separate composed journeys. Both SQLite/PostgreSQL fixture tests include
corrupted hold, charge, approval and audit cases to ensure verification detects damage.

## Offline Evidence

The populated extension passed 29 focused tests without skips across SQLite and
PostgreSQL, including a real native custom-format dump/restore with exact pre/post
schema/data/privilege equality and the behavioral checks above. Failure cases retain
an unrelated sentinel schema and clean up only the generated target. Archive size,
row count and fingerprint are emitted by the CLI; random IDs/schema names and migration
seed timestamps may change them. Equality within the run is what matters.

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
