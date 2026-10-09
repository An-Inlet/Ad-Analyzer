# W1 Migration Fixture Repair — Proposed Interface

Read-only proposal from `d85db66`; no implementation/tests/DB work yet.
This six-node package is not a request to alter production migrations or privacy
fallbacks. Root must freeze the producer/schema interface before implementation.

## Exact First Failures

Frozen XML SHA256:
`e3263f5e2bca0d484b4657d6672a32dfdc44539ee1cbed8257bf1a7187488037`.
See external `w1-failure-classification/failed-nodes.json` for every full identity,
terminal message, ordered stack and traceback hash.

| Node | Actual schema / target | First observed mismatch |
| --- | --- | --- |
| `test_budget_mandate_migration::test_real_schema_retains_preparation[postgres]` |0078→0079; populated refusal back to0078|Current first_customer→goal/commerce bind→privacy→0090 erasure queries absent stage-context table.|
| `test_candidate_migration::test_derived_candidate_migration_roundtrip` |0062→0060→0062|Same missing0090 table before candidate fixture reaches legacy approval.|
| `test_commerce_publication_migration::test_publication_migration_roundtrip` |0047→0051+0053→0047→0051+0053|Same missing0090 table from actual commerce publication seed.|
| `test_replacement_migration::test_replacement_migration_preserves_populated_obligations` |0058→0057→0058; populated refusal|Same missing0090 table before legacy optimizer/replacement producer.|
| `test_social_configuration_migration::test_populated_no_dsa_review_roundtrip` |populated0057→0059→0057→0059|Same missing0090 table before social execution producer.|
| `test_reported_feedback_migration::test_phase_constraint_change_preserves_native_staging[sqlite]` |direct0077 parent batch rebuild with0078/0083 dependencies|New0090 trigger references temporarily absent meta_connections during SQLite rename.|

The five PostgreSQL stacks enter `commerce.ledger.bind_store →
commerce.evidence.invalidate → lifecycle.privacy.bump_workspace_export_revision →
meta.presence_staging.erase_workspace_staging`. This is the actual first failure,
not proof that the rest of each test will pass after it is removed.

## Why A Universal Missing-Table Patch Is Wrong

Current semantic erasure now traverses0090 staging,0089 reporting presence,
0087/0088 planning graphs, candidates and initial observations. Skipping only
0090 reveals later missing tables. Skipping all privacy hooks would suppress
real old staged-metric deletion: `erase_workspace_staging` deletes the existing
MetaStagedMetric rows as well as its new context. Installing the entire current
head before old-schema assertions changes their premise and can make later
populated downgrade guards fail at the wrong revision. Inserting arbitrary
empty tables from ORM metadata would bypass the real migration/trigger contract.

The0053/0058/0059/0062 schemas predate0074 performance completions required by0089;
therefore blindly applying0087–0090 as “empty prerequisites” is not self-contained.
Neither a global privacy no-op nor a capability patch is proposed.

## A. SQLite Explicit Dependency Teardown (Ready To Freeze)

Use the exact already reviewed `62d0033` pattern in
`test_reported_feedback_lifecycle.py::prepare_schema`:

1. On SQLite only, inspect/assert both0090 paired staged payload columns are
   null for every retained staged metric and the context table is empty.
2. Inside the test-owned engine's real Alembic Operations context, call actual
   0090 downgrade, then existing0083/0078/0077 downgrade sequence.
3. Preserve and compare the original source ID plus every metric/checkpoint/page
   field through the real0077 batch rename. Snapshot legacy columns explicitly
   while0090 columns are absent; do not query current ORM SELECT * at that point.
4. Run0077/0078/0083 upgrades, then actual0090 upgrade on SQLite only. Compare the
   full initial snapshots including null paired columns, and verify0090 triggers
   and columns restored. PostgreSQL path remains unchanged.

No metadata tables are manufactured; no populated0090 row is downgraded away.
The existing actual0077 phase/refusal test stays current and unchanged.

## B. PostgreSQL Historical Producers, Current Migration Assertions

Recommended shared seam: extend the existing *pinned subprocess* pattern with
closed migration profiles, not current-app authority bypasses. Pin remains
`2155ff3e3ab00cd62057dd86cb49d45359d4f49f`, verified app/tests tree hashes.
Existing exact pinned versions of the historical-schema helpers and these test
seeds are available locally. They predate0087–0090 privacy callbacks and the
planning-only deny boundary, so their genuine producer rows can be created at
the actual old schema. **This is a feasibility proposal, not a passing claim.**

Suggested API:

```python
with retained_migration_producer(engine, artifacts, profile) as producer:
    first_ids = producer.seed()  # child commits/closes its SQL transaction
    # Parent executes current Alembic migration / real assertions.
    final_ids = producer.after_upgrade()  # only the social profile needs this
```

- `profile` is a closed Literal mapping to exact expected physical revisions and
  table/column predicates below; no arbitrary module/callable/query/revision arg.
- Parent owns one UUID fixture schema, configured disposable URL and all current
  Alembic DDL. Child cannot create/drop/reset schemas or change alembic_version.
  Extend the existing exact schema-prefix allowlist only for the five named
  migration fixture prefixes. Reject other schemas and nonempty unexpected seed
  graphs. Never use the aggregate schema.
- Child imports only verified pinned app/tests and uses their actual original
  producer helpers/MockHTTP. Historical mapper/privacy adapters remain inside
  that child and only where the pinned test already used them; none leak into
  the parent process. No current advertising guard patch.
- Only bounded scalar IDs, exact expected table ID sets and measured fixture
  provider-call counts cross the boundary. No ORM instances, runtime callbacks,
  account grants, authority objects or media-store handles cross.
- Parent closes Sessions before phase messages; child commits/closes Sessions
  before returning each phase. Parent reopens fresh current Sessions/SQL for
  assertions. Child process has an explicit finite deadline, bounded log/output
  and mandatory teardown. No tests are selected/removed by this seam.

| Closed profile | Child producer / phase | Current parent assertions retained |
| --- | --- | --- |
| `budget_preparation_0079` |At0079, actual pinned first_customer and HTTP budget preparation201; return preparation ID/workspace and response identity only.|Real0078→0079 empty transition already occurred. Current serializer valid/tampered workspace behavior, update/delete trigger rejection, actual populated0078 downgrade refusal, retained row count. SQLite current API path stays unchanged.|
| `commerce_publication_0053` |At0053, actual pinned complete/CommerceSync with existing target fixture inputs; return publication/store IDs.|Preexisting workspace inserted at0047 survives; actual0051+0053 upgrade/downgrade; publication/evidence removed, commerce order remains; re-upgrade yields empty publications/evidence.|
| `candidate_result_0062` |At0062, exact pinned legacy mapper/without_feedback/review/initial hooks, actual fixture→enqueue→process completed; return result/job IDs and mandate IDs.|Actual0062→0060 deletion and0062 re-upgrade; retained mandate identity set and empty re-created job table. No current candidate runtime activation claim.|
| `replacement_0058` |At0058 after empty roundtrip, exact pinned ReplacementHistoricalSession/prepared/real transfer; return replacement IDs.|Actual current populated0057 downgrade refusal and identical retained replacement IDs.|
| `social_configuration_0059` |Phase1 at0057 produces actual original run/account/catalog/profile and retains runtime context privately in child; commits and yields only IDs. Parent upgrades0059. Phase2 verifies physical0059, uses original private catalog/context to run exact selection/prepare/confirm, returns review ID.|Populated run survives0057→0059; actual current cross-workspace insert FK rejection;0059→0057 drops only review table; run count remains1;0059 re-upgrade has no review but retains run.|

Social needs a bounded two-phase child protocol because the original test creates
its run **before** upgrading0059 and prepares the social review **after** that
upgrade. Moving both to0059 would lose populated-upgrade coverage. Returning a
catalog/runtime to the current parent would violate the scalar-only seam. This
extra complexity must be explicitly frozen; do not silently weaken chronology.

## Scope/Qualification Plan And Open Choice

Recommended order: implement/qualify the standalone SQLite dependency repair,
then a single-phase commerce or budget producer feasibility case, then candidate/
replacement, then the explicitly reviewed social two-phase extension. Keep each
original migration's ownership/FK/immutability/refusal/assertion unchanged or
relocated to the same real SQL boundary. A genuinely unsupported pinned fixture
must be reported with its exact trace, not fixed via blanket capability patches.

Root decision needed before code: approve these **closed pinned producer profiles
and the social two-phase protocol**, or split social out for a separately frozen
seam. This is an implementation-interface decision, not new product scope or an
owner spending policy. No schema or production change is requested.

Bounded qualification: the six exact affected nodes plus existing shared producer
and migration-fixture compatibility selected after the seam is frozen; both
SQLite/PostgreSQL variants of affected parameterized modules where applicable.
Whole Ruff, bare mypy and diff checks after final changes. Preserve original W1
traces; no Full/hosted/aggregate-database retry. Until actual tests run, none of
these proposed remedies count as regression closure.
