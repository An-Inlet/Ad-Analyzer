# Initial Creation And Activation Lineage: Closed Historical Source

Proposal only, following afc4d5e and prior-budget2 candidate76548dc. Exactly four
remaining original identities: creation-history and activation-history functions
in test_initial_rule_prior_lineage.py, each SQLite/PostgreSQL. No implementation,
new historical batch, tests or source execution in this proposal.

## Historical Prefix, Current Suffix

Use literal2155ff3e3ab00cd62057dd86cb49d45359d4f49f app/tests/scripts. The original
module exists at that PIN (file SHA256
e3711e44b2976447a553103d94ec81d4697f14d5d587cbb95f3592d462bdef80).
New closed child accepts only mode Literal['creation','activation']; provider is
literal meta_ads, video None, no generic function/fixture selector or callback.

Creation invokes unchanged original SocialServer/ready then the original loop:
claim_creation_step → execute_claim, every outcome verified_effect, count==5.
Activation invokes unchanged original Server/approved (which itself genuinely
creates the paused five-step parent), then original claim_step → execute_claim,
every outcome verified_target_state, steps==3. These loop assertions remain in
the child and their AST is compared with the exact original test prefix. Original
NOW and fixture configuration remain unchanged; no timestamps/session extensions.
Only actual offline MockHTTP adapters are used. Creation posts==5; activation
server.posts==5 and server.activations==3. No current advertising guard override.

Stop before `template, _, _, _ = fixture()`. The parent current process retains the
ENTIRE original suffix from that line, including original template/scope copy,
MAX_PRIOR_BUDGET_ATTEMPTS=1, no_prior_budget is None, run/reservation lookup and held
assertion. The creation parent obtains wid/run_id from validated scalars. Activation
obtains wid and a freshly loaded CURRENT ProviderExecutionRun, never a child ORM
object. Do not rewrite the synthetic scope account IDs or claim this tests complete
execution admission. Its purpose is the actual workspace-scoped discriminator scan.

## Private Types And Functions

New tests/initial_lineage_retained_fixture.py and fixed child
 tests/fixtures/retired_execution/initial_lineage_seed_driver.py (no leading space).

`InitialLineageIds` frozen dataclass, exact JSON keyset:
mode ('creation'/'activation'), provider (literal 'meta_ads'), workspace_id/account_id
(strict positive ints), actor_id/run_id/review_id/reservation_id (32 lowercase hex),
parent_run_id/parent_review_id (None for creation;32hex for activation), native_id
(positive decimal string), plan_digest/review_digest (64hex), creation_posts (int5),
activation_posts (int0 or3 matching mode). Output regular nonsymlink ids.json,
1..4096bytes checked BEFORE parse; bool never accepted as int. No requests, cookies,
session digests, secrets, policy payloads, runtimes or callback transport objects.

`InitialLineageSource(engine: Engine, ids: InitialLineageIds, artifacts: Path)`.
`retained_initial_lineage(original: Engine, artifacts: Path,
 mode: Literal['creation','activation']) -> ContextManager[InitialLineageSource]`.
`load_initial_lineage(db: Session, source: InitialLineageSource)
 -> ProviderExecutionRun`: same engine identity required, current row validation
below, no provider IO or commit. Caller uses returned current ORM only within its
own Session. No current ready runtime reconstruction is necessary.

One new closed SourceLifetime profile `initial_lineage`, fixed helper/driver above,
leaf source and historical-source.tar, same exact PIN/tree identities and existing
180s/16MiB runner bounds. Do not broaden social_producer, whose zero-attempt and
zero-post contract stays untouched. Register only this one literal profile.

## Exact Current Validation Before Yield/Read

Fresh current ownership checks reload actual workspace, actor membership, account,
Meta native connection and typed CreationExecutionReview/SocialPublishPlan.
Account/native/workspace/actor and plan/review digests must match scalars and rows.
Activation additionally parses ActivationExecutionReview, exact parent_run_id and
parent review, and confirms the same owned reservation is reused. Validate actual
mandate/revision/consent/ledger scoped links from typed review, without invoking
current spend authorization or claiming an old mandate is currently spendable.

Creation: exactly one run/review/approval, five steps/attempts/responses/receipts,
created_paused run, no parent, one held reservation. Activation: exactly two
runs/reviews/approvals, five creation plus three activation steps/attempts/responses/
receipts, parent created_paused and child activation_observed, one shared held
reservation. Parent/child scope, step ordering and IDs come from actual typed plans.
No unrelated attempts, second receipts or replacement rows allowed.

For each actual attempt validate scoped run/step/fence plus request_digest against
current SocialBoundRequest (creation) or ActivationRequest (activation); parse each
current SocialProviderResponse/ActivationResponse and its fingerprint. Parse
SocialProviderReceipt/ActivationReceipt; bind actual sequence1/no supersedes,
request/fence/step/plan and digest, exact successful outcome. Validate the normalized
stored projection against these same source rows (or compare current read-only
owned outcome projection after direct typed checks). Do not call current coordinator
claim/execute/reconcile to reconstruct proof. Any incompatibility stops the package.
The live schema/graph is evidence, not trust in copied scalar counters.

Capture all registered Base table rows in deterministic PK order after validation
and before consumer. Exit requires exact equality, including every financial,
authorization, native and receipt field; NO allowed current row mutations.
Use schema_snapshot before child, after child and after consumer, checking full
physical DDL/index/constraint fingerprint rather than table-name equality.
Default advertising write capability must remain false before/after all current
validation/consumer stages. Source has original mock effects only, no current IO.

## Storage And Lifetime Boundaries

Match reviewed social source isolation: validate absolute unresolved artifact path,
no dotdot/symlink in any ancestor BEFORE mkdir. SQLite exclusive current.sqlite,
plain exact file URL checked in parent and child BEFORE engine/DDL; regular owned
file, no query/credentials/alias. Current Base creates empty FK-enforced tables.
PostgreSQL parent/child both use validate_disposable_url, loopback/noquery, exact
parent engine URL, actual isolated inlet_test_<32hex> search_path, no public/reset.
Every table except alembic_version must be empty before child. No copying rows from
a different engine or ignored caller engine. Parent bootstraps only current schema;
PIN child must use it compatibly or fail, never patch schema/adopt a foreign graph.

Keep run_bounded and SourceLifetime failure/reap behavior unchanged. Success cleanup
is only the verified duplicate extracted PIN/archive, never ids/log/media/SQLite.
Existing SourceLifetime may remove verified duplicate source/archive after a reaped
child, including failure. Unconfirmed/unreaped or cleanup-error sources remain.
Unique IDs/log/media/SQLite are retained; copy child logs/IDs/lifetime and failures to
/workspace/inlet-evidence before checkpoint because/tmp can disappear on restart.

## Bounded Qualification After Review

1. Pure closed mode/DTO/path/unsafeURL tests reject before engine/child launch.
2. Creation SQLite positive, then activation SQLite positive; inspect genuine
   counts5/8 and single held reservation before expanding. Stop any incompatibility.
3. Exact current four bothDB cases plus86 default boundaries. Original prefix loop
   assertions remain in child, original suffix/decorators AST-identical in current
   tests. New validation is additive; no historical-only replacement or skips.
4. Existing source lifecycle/path focused tests for the new profile, whole Ruff,
   bare mypy/diff, exact original identity intersection4 and durable logs/XML.

No need to repeat source6/prior-budget2 or existing19 without a changed dependency.
No generic source protocol, historical manifest expansion, Full, hosted/live work
or production advertising change is proposed. Implementation requires review.
