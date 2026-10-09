# Financial Origin Retained Source Proposal

Design only, base `ce73dfc`. No implementation, test rerun, production change or
capability override. This closes ten frozen W1 failures only after qualification.

## Exact Current Obligations

| Current node | Cases | Historical source needed | Assertions kept current |
| --- | --- | --- | --- |
| test_optimization_origin_metadata::test_actual_metadata_sqlite_postgres_sqlite_keeps_deferred_origin | 1 | setup only | Same metadata reused SQLite→PostgreSQL→SQLite; actual deferred FK and commit rejection |
| test_optimization_origin_metadata::test_sqlite_marked_insert_denied_if_physical_origin_fk_is_absent | 2, orm/migration | setup only | Actual AddConstraint suppression, absent physical FK, original ORM/frozen migration triggers and exact rejection |
| test_optimization_origin_ddl::test_additive_deferred_digest_fk_preserves_populated_authority | 2, SQLite/PostgreSQL | setup, initial revise and consent | Actual0080 downgrade/upgrade, unchanged original policy bytes/RESTRICT child, all sidecar/FK/immutability/export/refusal assertions |
| test_optimization_origin_ddl::test_marked_origin_denied_when_sqlite_foreign_keys_are_not_enabled | 1 SQLite; existing PG skip preserved | setup only | Original parent connection FK=0 and actual insert/update denial |
| test_provider_execution_mandates::test_unresolved_budget_owner_cannot_get_second_period_reservation | 2 | setup only | Current revise for both periods, real held row and second hold unique-constraint rejection |
| test_provider_period_accounting::test_mixed_currency_prior_hold_is_not_added_as_numeric_micros | 2 | setup only | Current JPY ledger/hold, current revise rejects mixed currency |

The terminal W1 XML traces reach test_provider_execution_mandates.setup →
provider_qualification.seeded → google_action_plans.setup → mandates.seed/approve,
then the planning write guard. They do not reach the intended current assertions.
The populated DDL case has a second blocked step after setup: current consent.
Current execution_mandates.revise has no advertising-write entry guard; consent
has the immutable guard. Therefore eight source-only cases must retain current
revise, while only the two populated DDL cases obtain preexisting historical consent.
No blanket retained_execution marker or current capability patch is justified.

## Closed Producer Interface

New tests/financial_origin_retained_fixture.py and fixed child
 tests/fixtures/retired_execution/financial_origin_seed_driver.py (without the
leading space) use the already verified literal2155 PIN and exact app/tests/scripts
trees. No caller PIN, callable, arbitrary policy, schema DDL, privacy bypass or
fallback. Modes are exactly `source_only` and `consented_origin`.

Both call untouched pinned test_provider_execution_mandates.setup with default
arguments, which calls genuine provider_qualification.seeded: approved legacy
simulation source, real owned actor/account/goal and approved campaign. It returns
original pure ProviderMandatePolicy with total/per-plan/positive caps100/80/20,
5% aggressiveness, ten actions, freshness300 and original default purpose/policy
fields. No candidate publication/session/qualification extras are needed.

`source_only` stops before provider revise. `consented_origin` calls original
execution_mandates.revise then consent exactly as the target test did. Neither
mode dispatches or creates provider attempts/receipts/reservations. Preserve the
initial policy's legacy origin and empty optimization sidecar.

Frozen scalar SourceIds fields:
workspace_id, actor_id, simulation_mandate_id, goal_id, goal_revision, account_id,
native_connection_id, source_draft_id, source_draft_revision, source_draft_digest,
provider_policy_digest. Positive integers and existing exact hex ID/digest bounds
apply. ConsentedIds adds provider_mandate_id, provider_mandate_revision,
provider_consent_id, ledger_id. Exact mode-specific keysets; no old ORM/runtime,
Python callback, serialized authority object or policy JSON crosses the process.

Parent rebuilds the pure current ProviderMandatePolicy from current owned simulation
policy + exact owned Google native connection using the original setup constructor
and the frozen100/80/20 constants; compare its digest with child scalar digest.
Also reread actual current goal, membership, approved source draft/revision and
account. Consented mode rereads current provider policy/consent/ledger, exact revision
and digest, matching that reconstructed policy. Child commits/closes before reply.
No invented provider POST counter: original setup performs local source preparation,
not a provider adapter call. Qualify zero provider execution rows explicitly and use
an explicit child fail-on-network tripwire if instrumentation is needed; never stub
original policy/consent behavior or assert an unmeasured provider count.

## Caller-Owned Physical Schema And SQLite

The current DDL test's SQLite fixture currently creates full ORM schema, removes
EMPTY0080 structures, and runs actual0080 upgrade BEFORE population. PostgreSQL is
actual Alembic heads. The child therefore needs the caller's actual full schema,
not a pre0080 schema adapter. The later populated downgrade/upgrade stays entirely
current. Never import a historical-schema suppression helper or install later tables.

A child cannot share SQLite in-memory databases. Use narrowly scoped file-backed
SQLite engines only for these cases; do not backup/reimport rows or replace physical
DDL with ORM assertions. For metadata order, keep first SQLite and PostgreSQL steps
unchanged; create the final SQLite engine on its unique tmp_path file and execute
the same metadata.create_all there. For malformed-FK cases use that same file-backed
engine under the original before_create suppression callback. For DDL cases, a
module-local fixture creates the file-backed counterpart using the same current
register_models().create_all and executes the unchanged EMPTY normalization/0080
code; shared migration_engine remains untouched. Ordinary two financial functions
can use a local file-engine adapter matching current customer fixture behavior.

No blanket SQLite FK enabling: preserve parent FK settings exactly, including the
explicit FK=0 test. Child may enable enforcement on its own connection only;
validate the actual physical FK/trigger shape before and after child. It must not
repair an intentionally missing FK. There are no live parent sessions/transactions
at child launch. Preserve metadata constraint identity/reuse order and all actual
current DDL calls, parent SQL, existing skips and assertions.

Parent/child agree on closed target shapes: loopback disposable URL with exact
base URL equality, one owned UUID schema (`inlet_test_` or
`inlet_migration_fixture_`); exact file-backed SQLite target under the unique artifact
root, no memory/URI/shared-cache/arbitrary database. Metadata-only PostgreSQL schema
`inlet_origin_metadata_` remains parent-only; producer does not need access to it.
Validate all tables empty except real alembic_version on initial setup, capture
full table/column/FK/trigger fingerprint before/after, and retain actual revision set
without stamping it. Only the explicitly suppressed physical FK variant differs.

Use a new closed SourceLifetime profile for this exact helper/driver with two
fixed modes, leafsource and archivehistorical-source.tar; reuse existing algorithm.
IDs/log/media/current.sqlite stay siblings. Preserve primary failure, bounded180s
child timeout, conservative unconfirmed retention and all owned-schema cleanup.

## Bounded Acceptance And Stop Conditions

First probe source-only malformed-FK SQLite and genuine consented current0080
PostgreSQL separately. Stop on historical model/schema mismatch, changed policy,
trigger shape or incompatible current consent lineage; report trace before adapting
semantics. No fallback to installing tables, disabling privacy or patching guards.
Then qualify both entire origin modules plus exactly the two financial functions
on both DBs, alongside unchanged planning boundary tests, Ruff/bare mypy/diff.
Prove every original assert AST and parametrization preserved; any required fixture
setup-only difference is separately enumerated. Retain exact failure identity map,
raw logs/XML, source PIN/tree/driver and cleanup provenance. No Full rerun.

This proposal does not authorize restoring current execution authority. The current
planning guard remains unchanged and current forward-denial tests remain separate.

## Approved Probe Amendment

The first probe passed malformed-FK SQLite and failed PostgreSQL before source
creation: actual Alembic migrations intentionally install bootstrap rows. For
PostgreSQL with an actual alembic_version table only, validate exactly the rows and
keys from scripts/inlet_restore_bootstrap.expected_bootstrap, excluding only its
existing created_at/updated_at comparison fields. Capture full rows, including
timestamps, and require exact primary-key readback after child completion. Every
other table stays empty; SQLite and PostgreSQL ORM schemas remain all-empty. Do not
reset data, stamp migrations or accept arbitrary nonempty tables. The fixed child
loads this standalone constant-only module by its fixed driver-relative current
path (never through the historical import path or a caller-supplied path). This
is existing migration bootstrap data, not replacement historical producer code.
Retain first probe log/XML. Retry PostgreSQL only after this amendment is frozen.
