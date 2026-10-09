# Current Provider DDL Regression: Original Source Phases

Proposal from `545e15a`. **Docs only; no implementation or tests run.** Scope is
three exact failed PostgreSQL nodes. No retained_execution marker, historical
replacement, production/schema repair, arbitrary producer or current guard patch.

## Evidence And Current Obligations

Frozen W1 XML: `/workspace/inlet-evidence/20261008/w1-aggregate/aggregate.xml`.
All three traces terminate in `provider_qualification.seeded` →
`google_action_plans.setup` → `test_mandates.seed` → current legacy approve →
`AdvertisingWritesDisabled`. They have not reached their intended database checks.

| Exact node | Current behavior retained |
| --- | --- |
| `tests/test_provider_qualification.py::test_populated_provider_migration_roundtrip` | Actual head→0040→head, prepare/approval data, second head→0040→head; exact current review counts1 then0, actor survives, re-prepared source_revision1. |
| `tests/test_provider_qualification.py::test_database_rejects_cross_workspace_qualification_reference[postgres]` | Actual current PostgreSQL composite FK: unchanged foreign Workspace and ProviderReviewRecord insert/flush inside the original nested transaction must raise IntegrityError. Original SQLite-only limitation/skip stays. |
| `tests/test_provider_execution_mandates.py::test_populated_execution_migration_roundtrip` | Actual head→0043→head twice; **current** revise, checked and ledger.spent_high_water_micros=30 remain current; actor survives, current ledger count0 after re-upgrade, current revise works again. Only consent production is historical. |

Current `execution_mandates.revise` and `checked` are unguarded and must not move
into an old runtime. `consent` is guarded. Current `provider_service.prepare_google`
and `approve` are guarded; `checked_review` is a read and stays available for
current owned validation. Thus moving entire test functions/modules is unnecessary.
Keep every original assertion/decorator (add planning_boundary only), every actual
Alembic command/order and the complete FK adversarial insert unchanged. Expected
AST assertion counts: qualification roundtrip4, execution roundtrip2; the FK
case's raises/nested transaction, complete row payload and flush are its assertion.

## Reuse Before New Mechanism

Reuse unchanged `financial_origin_retained_fixture.retained_financial_source`
with **source_only**, and its reviewed SourceIds/current_policy. It invokes
untouched original `test_provider_execution_mandates.setup`, whose only additional
step beyond original `seeded` is pure policy construction (no additional SQL).
It already validates real owner/goal/account/native/approved campaign and exact
policy digest, current physical schema, fresh full-table/bootstrap content and
literal2155 source trees.

For reuse without broadening its URL allowlist, change only the two migration
tests' private random schema prefixes from provider_review_/provider_execution_
to `inlet_migration_fixture_<32hex>`; each still creates/drops its own random schema
and executes the identical DDL. The cross-workspace case already uses the accepted
`inlet_test_<32hex>` fixture. No SQLite source adapter is needed for these three
PostgreSQL cases. Retain original SQLite FK skip; never synthesize physical FKs.

After seeding, parent rebuilds p once with current_policy and checks the source
policy digest. The parent keeps that pure current p across its DDL, as the original
execution test did. No old Python object, policy JSON or authority crosses back.

A new **one-shot**, not persistent, closed `provider_ddl` SourceLifetime profile
is justified for guarded steps against this already owned source. Separate child
processes finish/reap before any subsequent parent DDL. This avoids keeping a
Session, connection or original runtime alive through downgrade/upgrade. Existing
financial, social, candidate and campaign producers remain unchanged.

## Closed Phase API And Data

New `tests/provider_ddl_retained_fixture.py` and fixed
`tests/fixtures/retired_execution/provider_ddl_seed_driver.py`. Literal verified
`2155ff3e3ab00cd62057dd86cb49d45359d4f49f`, existing exact app/tests/scripts trees;
no caller-selected PIN/callback/transport/policy. SourceLifetime profile uses
leaf `source`, archive `historical-source.tar`; private input/output/log/media
references remain outside extraction. Existing extraction/runner/lifetime utility
semantics unchanged. Each child has existing180s/16MiB bounds, no retry-on-failure.

Public phase helper inputs: `(engine, source_ids: SourceIds, source_artifacts,
phase_artifacts, mode, provider_mandate_id=None)`. Exact closed modes:

1. `qualification_only`: untouched pinned `prepare(db,wid,draft,actor,store)`.
2. `qualification_approved`: that exact prepare followed by untouched original
   provider_service.approve with returned exact review/plan digests.
3. `execution_consent`: consent on the **one exact current draft revision1**
   already created by parent current revise; no child revise/setup. Original
   execution_mandates.policy reconstructs the actual row and must match the
   source's policy_digest. Invoke original consent with that row/revision/digest,
   original actor and original fixed NOW. No origin override.

`provider_mandate_id` is required only for mode3; reject it in other modes.
`source_artifacts/media` is derived, absolute, nonsymlink and owned; no arbitrary
media path or serialized store. Source scalar input must equal the retained source
ids.json, with current owned SQL correspondence revalidated. Strict input/output
JSON <=8192 bytes, exact keys, IDs32hex, digests64hex, strict positive integers,
revision exactly1. No session token, grant, runtime, provider data body or authority.

Qualification output: echoed workspace_id, actor_id, source_draft_id,
source_revision, plus qualification_id, review_id, review_digest, plan_digest,
and exact mode. Parent loads current rows, parses actual evidence/review/plan,
validates digests/scope/source/actor and current checked_review at original NOW;
approval exists and binds exact digests only for qualification_approved.

Consent output: echoed workspace_id, actor_id, provider_mandate_id, revision1,
provider_policy_digest, provider_consent_id, ledger_id, exact mode. Parent uses
actual current owned row/policy/consent to reconstruct the current binding and
calls **current checked**, as in the original test. No returned binding grants
current forward execution permission.

## Storage, Content And Exact Delta Guards

PostgreSQL only: validate existing explicit disposable marker, loopback
postgresql+psycopg base with no query. Candidate URL must equal base apart from
no query or exactly `options=-csearch_path=<actual validated UUID schema>`;
reject other query keys/values before connection. Schemas limited to the two
existing inlet_test_/inlet_migration_fixture_ forms above. Parent and child verify
actual current_schema; migrated sources require actual full current Alembic head
SET (read current ScriptDirectory), not a supplied arbitrary revision. FK fixture
has no Alembic table and its actual current metadata schema is retained. Child
must verify pinned app import path. No create_all, migration, stamp or reset in child.

Initial source helper retains its full fresh-table/exact bootstrap check. Before
each later phase, revalidate original SourceIds/owned source and require empty
target qualification tables or, for consent, exactly one original workspace draft
mandate/revision/ledger matching the requested ID/policy and no consent. There must
be zero provider execution review/approval/run/step/attempt/response/receipt/hold
rows. Snapshot all existing rows and actual schema immediately before each phase.
Snapshot/fingerprint agrees again in the child before it starts; no blanket
nonempty-schema allowance. Preserve exact migrated bootstrap rows within a phase.

Permitted changes within a phase are only:

- qualification_only: one exact ProviderQualificationRecord + one exact
  ProviderReviewRecord; all original rows unchanged.
- qualification_approved: the above plus one exact ProviderReviewApproval.
- execution_consent: one exact ProviderExecutionConsent and only the identified
  ProviderExecutionMandate.state draft→active. Ledger, revision/policy/origin,
  source and every other row unchanged. No source-origin sidecar or new hold.

Parent independently validates the new rows and exact full before/after delta;
physical schema/revisions identical across each child. Qualification uses the
original MockHTTP search-only adapter; no fabricated mutation counter is emitted.
Original caller-owned DDL occurs **outside** these phase checks and legitimately
drops/recreates tables. Do not compare a whole data graph across intentional DDL
or erase rows to satisfy it. Bootstrap recreation across DDL is also intentional.

## Exact Parent Sequences

Qualification migration: current upgradehead → authentic source_only → current
downgrade0040/upgradehead → original qualification_approved phase → current
count1 → current downgrade0040/upgradehead → current count0 and surviving actor
assertions → original qualification_only phase → current source_revision1.

FK case: authentic source_only on actual current metadata → qualification_only →
current unmodified foreign-row nested insert raises IntegrityError.

Execution migration: current upgradehead → source_only/current p reconstruction
→ current downgrade0043/upgradehead → current revise → original consent phase →
current checked and spent30 mutation → current downgrade0043/upgradehead →
current surviving actor/ledger0 assertions → current revise → original consent
phase. All parent Sessions close/commit before each child/DDL and re-open fresh.

0043 downgrade intentionally removes qualification/review/approval;0046 downgrade
removes execution consent/ledger and downstream graph. Newer retention-refusal
migrations must remain real and unmodified; those graphs are empty in this source.
Never assume an intermediate singleton revision: the actual DAG includes merged
0040/0041/0043/0044/0045 branches. Preserve original downgrade/upgrade commands;
only source phase calls at restored full head are permitted. Unexpected actual
migration/refusal/source mismatch is a blocker to report, not a reason to bypass it.

## Proposed Qualification

After review only: probe the FK case first (current constraint, no migration),
then qualification migration, then execution migration independently. Stop on any
unplanned schema/model/delta mismatch. Run all three current nodes together plus
the unchanged default86 boundaries, existing source/lifetime guards and focused
new phase-input/strict URL/delta negatives. Preserve the existing SQLite skip if
selecting that FK counterpart. Whole Ruff/bare mypy in /tmp/diff, exact assertion
AST proof and durable logs/XML. Unique explicit /tmp basetemps; no aggregate,
Full, hosted, live provider or historical partition expansion. No implementation
or qualification is claimed by this proposal.
