# Generation Dependency And Writer Inventory — 2026-10-12

Status: contract investigation; production reads and authorization unchanged. This
inventory establishes concrete gaps, not permission to reuse dynamic currentness.
The incident remains open; HTTP acceptance57passes/1unresolved failure is separate.

## Scope And Completeness

The accompanying machine-readable reference census enumerates52 row models in13
families,1346 model/table reference bindings across app/migrations/scripts, declared
columns and file hashes. It includes explicitly marked transitive writers/publication
rows. It is a conservative source-reference index, NOT a callgraph, all-writer proof,
or executable list of fields safe to cache. Inherited columns and generic/dynamic SQL
must be considered separately. No customer data, grants or row values are captured.

The reader roots are PlanningDocumentService._generate, repository.save_generation,
selected_paired_local.recheck_selected_paired_sources, creative_finalization,
owner_review_generation, google_budget_owner_retained and selected_plan_witnesses.
The following table defines required read sets, including empty results. Every scalar
field used in validation/serialization must be included; the table is not a license
to select only named example fields.

| Family / Rows | Query Membership And Dynamic Predicates | Writer Paths / Current Coordination |
| --- | --- | --- |
| Workspace, CustomerUser, CustomerSession, CustomerMembership | Exact original workspace/user/session/member; absent/deleted membership, role/status, issuer/subject/auth-time, expiry/revocation; no replacement session | customer API login/logout; provisioning; lifecycle quiescing and closure; canonical workspace→user→session→membership locks. External IdP requires actual refresh outside SQL; SQL cannot fence external revocation. |
| AdvertisingAccount, WorkspaceIntegration; GoogleCustomerConnection, MetaConnection, SourceConnection | Exact workspace/account/integration/platform/native ID; source cardinality; connected state/generation/errors; selected currentness also compares FULL private source row before/after proof passes, transient and unpersisted | imports.scope, Google service/selection/sync/disconnect; Meta service/acquisition; sources.service and lifecycle. Normal writers coordinate workspace/account/native locks; credential/read-scope rotations must be mapped, not inferred from public generation alone. |
| WorkspaceBilling plus active account/integration set | Paid status, qualified price, verification freshness, billing period and account-limit count including newly inserted accounts | billing.service owned/reconcile/refresh/checkout; account selection/import/disconnect. Workspace billing locks do not replace time/config checks or membership-set checks. |
| PlanRow, PlanInputRow, PlanVersionRow, PlanRequestRow | Plan ownership; exact input/version head and original parent bytes; receipt tuple workspace/actor/operation/key/digest including absent receipt; original saved input | planning service/repository creates/revises/generates; lifecycle privacy erases; CAS plus unique receipts, atomic version/dependencies/receipt. PlanEventRow is an adjacent publication writer, not a reason to accept changed version/input. |
| CatalogReceiptRow, CatalogReceiptSelectionRow, InputCatalogReceiptRow | Exact original receipt IDs, payload and metadata; complete selected-key and input-link sets, original session/source/privacy, expiry, catalog/owner binding; no latest receipt substitution | catalog_receipts.write_catalog_receipt/bind_input_receipts/cleanup_expired_unused_receipts; receipt trigger immutability/bindings/cascades; privacy erasure. Both retained owner loads remain. |
| EventSelectionRow, CurrentEventSelectionRow | Exact immutable selection plus current head by account; absent/invalidated head matters; scoped selection status/digest | selected_storage.store_selection/invalidate_selected_account/erase_workspace_selected; selected triggers transition/delete; publisher and selection APIs take workspace/account locks. |
| SelectedCaptureRow, SelectedFactRow | Exact capture, complete fact set by capture (bounded50000), selection/aggregate references, canonical bytes, source provenance and membership | selected_storage.store_selected_capture; Google/Meta selected publication; transition/erasure triggers and FK cascades. Immutable existing rows do not prove no insertion/deletion. |
| Campaign, DailyMetric | Complete campaign map by account (bounded10000), including campaigns with NO metric facts; manifest joins account/platform and date interval; metric inserts/deletes and campaign moves change membership; all mutable metadata used by retained capture | imports/service and provider publishers, collectors/sync fixture paths, account erasure and cascades. Current reads reconstruct manifest and full map; privacy is not universal update/insert epoch. |
| PerformanceCompletion, CurrentPerformance | Exact requested aggregate completion and current pointer; range/semantics/currency/timezone/generation/privacy/query/manifest/count/time | campaign_performance.service.publish_meta, Google range/acquisition and source publishers; replacement/invalidation/deletion. Workspace/account locks required; exact source head and complete metrics remain dependencies. |
| RangeReceiptRow, JobRun | ALL request IDs for workspace/account/completion:0gap/1receipt/2refuse; receipt payload/dependency consistency; job workspace/account/connection/name/status and completion relation | range_receipts.store_range_receipt (workspace/account lock), Google range_publication atomic job/receipt path, lifecycle deletion; receipt update forbidden, DELETE advances privacy, INSERT does not. Job status/metadata updates are transitive writers. |
| ReportingSemanticsRow, MetricPresenceRow | Absent/present header and COMPLETE fact set by completion; producer contract, original scalar/null semantics, count/digest, campaign/date set | presence_storage.store_presence/erase_workspace_presence; raw Google/Meta presence publication, completion/account cascades; binding/immutable/delete triggers. No absence cache. |
| Goal, GoalRevision, GoalPreview, CommerceSnapshot | Goal head, original confirmation preview and canonical definition, confirmed state, baseline assessment/snapshot; missing/deleted rows refuse | goals.service create/revise/preview/confirm (goal lock); reporting snapshot creation, lifecycle erasure. GoalConfirmation/GoalCreation are transitive request writers; they are not substitutes for referenced current rows. |
| CommerceStore, CommerceOrder, CommerceEntry | Scoped active store/integration, coverage/watermark/import state/revision/errors; any incomplete order for store (not just requested range), complete entries by happened_at interval and orders by created_at interval; monetary/customer aggregates, clocks/retention/timezone | commerce.ledger bind/ingest/revise_days/sync/privacy; store/workspace locks; SourceLink/DailyRevision/ShopifyConnection as transitive writers. A store revision alone needs all-writer proof. |
| CommerceSuppression, CommerceShopAlias, ShopifyPrivacyIdentity | Suppression existence by workspace/shop; alias domains for store AND mapped domains over other stores in workspace; non-scope privacy markers for mapped/unresolved domains | commerce.privacy, shopify.privacy_identity remember/preserve/record_erasure/prepare_source; ShopifyPrivacyRequest/Tombstone/Order, reconnection/domain mapping, ledger/lifecycle writers. Cross-store alias insertion can change a NOT-IN membership predicate. |
| MediaObject | Exact selected IDs and complete identity/creator/hash/size/MIME/dimensions/time, before/after source callbacks; no substitution of blob availability for SQL identity | campaign_review.service.upload, privacy/local-work erasure and storage cleanup. Workspace/media row locks; file/object-store effects are separate. |
| PlanDependencyRow; CommerceEvidenceState/CommerceMeasurementPublication | Publication outputs and transitive invalidation/measurement paths must not mutate prepared dependencies via callbacks; original dependency sets and privacy erase cascades | repository insert, lifecycle registry/local_work/privacy, commerce.evidence invalidation/publication. Inventory schema cascades and SQLAlchemy flush/transaction/commit callbacks. |

ProviderExecutionConsent is NOT a generation dependency: no ad-write authority is
created by planning. Read-consent changes are represented through existing source,
integration and private-source checks. Do not add an execution-consent requirement
or store encrypted grant bytes in a new token, hash record or diagnostic artifact.

## Minimal Candidate Mechanism And Proof Gates

Use one invocation-local owned raw read set with exact query membership, followed by
real fresh provider authorization and current full-row comparison under canonical
scope locks. Perform expensive pure validation/projection over the owned non-secret raw copy
before final authorization. Keep private-source comparisons in their existing transient
currentness scope; private grant material must not enter a prepared token or artifact. No cache lookup, cross-request reuse, timestamp renewal,
provider call under locks or untrusted prevalidated flag. Keep clocks, session status,
paid/goal/source/privacy/consent checks fresh. Neither digests of previous results nor
an erasure epoch prove the result set is still current.

For PostgreSQL, the normal workspace gate demonstrably coordinates the range writer;
then account/source/goal/store/media/plan locks follow existing order. For SQLite,
future publication would need an explicit physical write reservation (BEGIN IMMEDIATE
before dynamic reads), not SQLAlchemy transaction identity or FOR UPDATE text. Waiting
counts against the ORIGINAL five-second fact. Such a change is NOT made here.

This strategy is complete only if every mutation of the read set is fenced: normal
writers, bulk imports, jobs, admin/maintenance, trigger cascades and generic lifecycle
DML. A writer committed before the final lock must be detected by complete raw values
AND membership comparison. A writer after the lock must block or cause refusal.
If any writer bypasses scope locking, close that path with a shared database-enforced
scope gate or dependency mutation revision BEFORE removing reconstruction. A universal
privacy revision is rejected. A new revision should not be added speculatively to mask
an incomplete dependency inventory; its INSERT/UPDATE/DELETE/old-and-new-owner trigger
coverage and rollback behavior would itself require proof.

No complete all-writer closure is claimed yet. The52-model census identifies candidates,
but alias-based/generic DML and cross-family cascades require manual closure. Keeping
existing source rereads is the currently proven choice. The measured2.568319s save
contains1.377696s source checks and0.950314s retained capture; these inclusive intervals
include SQL and pure computation. They do NOT establish savings from the proposed
split. No unverifiable optimization layer is introduced without measured benefit.

## Security And Concurrency Acceptance

A bounded final publication must retain original-session equality, real IdP validation,
local revocation/membership/ownership, read consent, private native-row bracketing,
paid/goal/privacy/TTL checks, complete membership and current evidence on both sides of
creative callbacks. Same-key replay and different-key CAS use current transaction state;
head/version/receipt changes cannot be hidden by preparation. Pre-CAS, post-flush and
response-preparation expiry must roll back every published row. Include ORM before_commit
and transaction callbacks; commit invocation is the claimed boundary, not guaranteed
wall-clock commit completion. Preserve unsupported-graph and oversized-set refusal.

Existing configured mutation tests in test_prepared_generation_runtime cover committed
session/membership/privacy/head/candidate/connection/goal-confirmation changes during
final refresh, media-bracketing changes and real pre-CAS/post-flush expiry. Existing
concurrency and lock-expiry tests remain relevant; this inventory does not retroactively
award them new execution credit. Their original evidence and unresolved generation
incident remain separate from the new membership contracts.


## Closure Queue (No Dynamic Reconstruction May Move Yet)

1. Classify the457 distinct referenced files from the census by direct reader, normal
   writer, generic writer, trigger/migration, or non-mutating dependency; inspect aliases
   and dynamic SQL. Name the exact affected row predicate and lock gate per writer.
2. Close all foreign-key cascades and cross-workspace ownership moves with old/new scope
   ordering; close Shopify alias/marker NOT-IN predicates across the whole workspace.
3. Map every private source rotation/disconnect/read-consent change, paid config/time
   predicate and lifecycle raw DML to final currentness, without retaining secrets.
4. Prove physical transaction and callback semantics for publication, including the
   currently identified response-construction work after repository final authorization.
5. Measure a single closed family's raw-read/parse split. Only implement if exact parity,
   complete mutation fencing and material benefit are demonstrated. Keep other families
   on original rereads; no implicit expansion of an eligible token's scope.

This queue is engineering work under existing authorization, not an owner-permission
request. A source census cannot close it automatically. The current safe mechanism is
unchanged full rereads; the proposed shorter boundary remains unqualified.

## Catalog Family Writer Walk

The census references for the three catalog models were inspected. Runtime mutations
are `catalog_receipts.write_catalog_receipt` (receipt and selection inserts),
`bind_input_receipts` (input-link inserts), `cleanup_expired_unused_receipts` (unlinked
expired selection/receipt deletes), and `invalidation.erase_workspace_plans` (ordered
semantic deletes). `catalog_runtime` calls cleanup under owner/workspace authority in
its separate maintenance transaction and writes after its source/identity checks;
`PlanningDocumentService._save_inputs` calls binding under its existing authority.
`lifecycle.privacy.bump_workspace_export_revision` calls planning erasure before
advancing the workspace revision. Owner-discovery, input-receipt, storage and export
references are readers/validators, not additional catalog mutation entry points.
Migration0088 defines the corresponding tables/constraints/triggers.

All three catalog tables reject UPDATE. Receipt/input-link INSERT bindings are checked
by triggers; selection membership also has owned FK and unique-key constraints.
Catalog account deletion is RESTRICT; workspace deletion CASCADEs receipts; selection
rows CASCADE from receipts; input links CASCADE from input revisions and RESTRICT receipt
deletion while linked. Catalog DELETE does not itself acquire a workspace gate or
advance a privacy epoch in these table triggers. The normal helper's caller-lock rule
is material. Future prepared use must prove every caller/generic delete and transitive
parent deletion, not infer deletion fencing from update immutability.

PostgreSQL FK/key locks may supply additional coordination for particular inserts, but
that is not a blanket phantom proof. Updates moving an existing row into a date or
status predicate can change query membership without changing its parent FK. Such
predicate transitions require normal-writer gate proof, a suitable database-enforced
revision/gate, or retaining complete current reconstruction. No FK-lock shortcut was
implemented or claimed by the six tests.

## Qualification And Durable Evidence

`generation-dependency02` manifest
`96da26c3aa560d05401b056c562d98731c83ac88740ea2a0fe391ba038d2239a`:
whole Ruff, mypy1593files, exact six-case collection and diff check PASS; all three
new contracts on SQLite and PostgreSQL PASS. Six retained dependency-contract.json
artifacts bind actual normal-writer receipt insertion, immutable-update refusal with
unchanged digest after rollback, deletion epoch advancement, complete campaign-map
change, and physical writer-blocking/release behavior. No production transaction changed.
Attempt01 preserves Ruffpass and mypy3optionaldriver errors; no runtime test ran there.
Corrections narrowed optional driver connections, explicitly closed the backup connection,
and tightened immutable-error/rollback assertions before the fresh02freeze.

`generation-dependency-security01` manifest
`e58f808a34c6d6f2acb388f737d5a7a4fcb608890596cee5f83bc9dada494ee5`:
18 additional existing regressions PASS, nine per database: session/membership/privacy/
source changes during final refresh; same/different-key publication; raw sidecar loss,
metric changes and receipt deletion. Eight retained contention/outcome artifacts.
PostgreSQL contention verifies actual overlap; SQLite's existing StaticPool publication
cases intentionally sequence final transactions and are NOT simultaneous-write proof.
The new separate-file SQLite contract tests actual independent physical connections.

Together:24tests,4statics,28successful commands,1910source hashes verified,14retained
artifacts. No skips, unexpected runtime failures, resource interruptions or surviving
children. Original/final exits and XML identities verified. No benchmark benefit or
incident resolution claimed. No checks from the separate57pass/1unresolved HTTP
inventory are silently replaced; the diagnostic pass remains non-acceptance evidence.
No product-code change, dynamic reconstruction move, new cache, credentials, live calls,
push, PR, hosted CI, merge, deployment, advertising write or spend occurred.

## Range Receipt / JobRun Family Writer Walk

Independent review traced the actual range publisher and low-level helper callers:
`range_receipts.store_range_receipt` validates and locks workspace/account, validates
JobRun/completion/current aggregate, then replays or inserts/flushes/readbacks in a
nested transaction. `range_publication.acquire_range` creates the successful
`google_customer_range_read` job, completion, receipt and traffic proof atomically,
rechecking source/authority/runtime/expiry. Semantic erasure enters via
`privacy.bump_workspace_export_revision`, which locks workspace before receipt deletion.

`AdvertisingMetricsRepository.create_job_run/finish_job_run` supply no independent
workspace lock or epoch. Google service.tick, sources.advertising.tick, meta.detail.
sync_window, meta.sync.page/_publish, jobs.reliability._create_authoritative_job_run
and GoogleAdsSyncService._collect_and_persist are transitive callers with scope/native
fencing. Some callers are absent from a direct-model text census, proving why manual
call tracing is necessary. The failed-job finalizers in jobs.reliability rollback,
merge/load, finish and commit WITHOUT reacquiring the workspace gate. They target
background google_ads_read_only_sync jobs, not normal range-receipt jobs; this is not
a claim of a current reader vulnerability, but defeats a universal JobRun lock claim.

Receipt INSERT triggers validate bindings/job/completion/size, not a workspace mutex
or insert epoch. UPDATE is forbidden. DELETE advances privacy/removes calibration;
PostgreSQL also takes workspace FOR UPDATE NOWAIT. Receipt cascades come from account,
completion, JobRun and initiating-user deletion. JobRun parent workspace/account/
integration FKs restrict deletion, while JobRun deletion cascades import-completion
rows and receipts; AnalysisRun references restrict it. Quiescing preserves JobRuns,
cancels queue entries and deletes receipts indirectly through privacy invalidation.
Registry/inventory/export code is read-only, not a generic eraser. Historical migrations
are privileged maintenance and do not establish ordinary writer fencing. No normal
application direct JobRun DELETE/raw SQL UPDATE was found in this family review.

This closes the source-level family map with explicit gaps, not every parent-deletion
writer or privileged SQL path. Keep receipt membership plus mutable JobRun/completion
checks fresh. The first concrete writer-closure follow-up is the failed-finalizer
scope contract (including closing workspaces and legacy jobs) and parent deletion paths;
it is not permission to start a prepared-source cache.
