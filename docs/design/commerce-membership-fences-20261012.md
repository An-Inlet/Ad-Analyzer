# Commerce Membership Writer Fences — 2026-10-12

Local implementation on `codex/inlet-w1-followup`, following `90d2c651`.
Bounded writer coordination for three existing models: CommerceStore,
CommerceShopAlias and ShopifyPrivacyIdentity. No new model or product feature.
The owner's reconnect-retention decision is still pending; this package preserves
existing disconnect, deletion, erasure-marker and reconnect behavior.

Full reconstruction remains unchanged. HTTP acceptance is still **57 passes /
1 unresolved**, INLET-REL-20261012-01 remains open, and existing release/execution
holds remain. Nothing here qualifies V6/V7 or authorizes live operations.

## Guard Contract

Forward migration0094 and matching metadata registration install PostgreSQL row
triggers on every INSERT/UPDATE/DELETE of these three tables. Distinct old/new
workspace IDs are locked in order with FOR NO KEY UPDATE NOWAIT, conflicting with
the existing reader workspace gate. Fail-fast acquisition avoids waiting for a
workspace while holding a child row lock. No active-status filter prevents historical
privacy handling in closing workspaces. No epoch, new retention rule or retry is added.

Alias guards resolve both old/new store IDs under sorted FOR KEY SHARE NOWAIT locks;
the unique `(id, workspace_id)` parent key stabilizes ownership. Missing parents
refuse. Store BEFORE DELETE removes exactly the aliases its existing FK cascade would
remove, while the parent is still visible to the alias guard. All effects remain in
the same transaction. Missing workspaces are allowed only for DELETE under the normal
nondeferrable, enforced workspace-FK cascade; the parent deletion owns that row lock.

The bound is ordinary enforced-FK DML with guards enabled. It excludes TRUNCATE,
disabled triggers, replication bypass and privileged schema modification. SQLite has
no new row-lock trigger: its writers already reserve the database, and reader fencing
still requires an owned physical BEGIN IMMEDIATE. Tests prove that boundary using
independent file connections; the production reader boundary is NOT changed here.

These locks do not make earlier data fresh. Changes committed before the final lock
still require complete current value and query-membership comparison. Cross-store
NOT-IN membership cannot be reduced to a store-local revision or cached marker set.

## Qualified Behavior

Four new cases on each database, plus three existing privacy regressions per database:
14 distinct tests PASS. Whole Ruff, mypy (1597 files), exact collection and diff check
PASS. Independent review examined the source contract and adversarial cases.

- Another workspace's alias cannot classify this workspace's unresolved marker;
  another store in the same workspace can. Deletion restores applicability.
- Actual ConnectionService.disconnect revokes the retained store while preserving
  alias and minimal privacy identity history. Direct store deletion is tested
  separately; its alias cascade does not erase workspace-owned identity markers.
- Generic INSERT/UPDATE/DELETE for each table refuses conflicting workspace readers.
  Moves are checked against both old and new workspace owners. Fifteen mutation
  cases per database preserve full row snapshots of these three tables after refusal/rollback.
- Alias insertion competes with store ownership movement and store deletion in
  both orders. Independent connections demonstrate refusal, not simulated ordering.
- Both populated migration fixtures actually completed the owned workspace cascade;
  exact retained rows in these three tables were restored by rollback. The tests allowed an exact FK
  refusal as an alternative for restrictive graph variants, but that branch did not
  occur in these fixtures. Outcome artifacts explicitly record the observed branch.
- Frozen migration SQL equals metadata SQL; populated downgrade/upgrade preserves
  rows, and direct deletion/rollback still works. No migration ran outside disposable
  test schemas. Existing pre-enable erasure, reconnect suppression and legacy
  reconciliation regressions passed without changing their semantics.

## Evidence And Preserved Failures

`/workspace/inlet-evidence/20261012/commerce-membership-aggregate.json` verifies
original/final exits, exact XML identities, process cleanup and1915 source hashes.
Two retained cascade outcome artifacts record SQLite and PostgreSQL results.
Final manifest: `2a59936f4db5d97d57feddcf089752266dd14f822b10642a14d2da23715d3b4c`.
No skipped case, resource interruption or surviving child process.

Earlier attempts remain intact:

1. commerce-membership01: Ruff rejected long frozen SQL literals; later checks unrun.
   SQL serialization was wrapped without changing SQL values.
2. 02: Ruff passed; mypy identified untyped DDL calls and FromClause/Table annotations.
   Existing repository DDL typing conventions and metadata table lookup resolved them;
   later checks unrun. Review also required explicit SQLite FK enforcement and actual
   alias/delete contention, added before runtime qualification.
3. 03: statics and seven SQLite cases passed, then three new PostgreSQL cases passed.
   The migrated PostgreSQL fixture failed seeding workspace ID1, already created by
   Alembic. Its remaining three PostgreSQL privacy cases were unrun.
4. 04: test-owned IDs501–503 avoid migration seed collisions. Final statics, all eight
   new cases and three PostgreSQL privacy cases pass. The three existing SQLite
   privacy cases carry forward from03 with all other source hashes unchanged;
   no other test imports the changed new test module. Production code is identical
   between03 and04. The original failed setup is not counted as passing evidence.

## Exact Remaining Inventory

The historic census stays at52 models; its original hashes remain an audit snapshot,
not a claim to describe today's changed model files. Current source is evidence-bound
above. The following49 models still require complete writer/dependency closure beyond
any previously qualified individual contracts. This is a proof queue, not a claim
that their implementations or prior tests are absent:

| Dependency Family | Remaining Inventoried Models |
| --- | --- |
| Workspace and identity | Workspace, CustomerUser, CustomerSession, CustomerMembership |
| Source ownership and credentials | WorkspaceIntegration, AdvertisingAccount, GoogleCustomerConnection, MetaConnection, SourceConnection, ShopifyConnection |
| Billing | WorkspaceBilling |
| Goals and request bindings | Goal, GoalRevision, GoalPreview, GoalCreation, GoalConfirmation |
| Commerce financial and publication state | CommerceOrder, CommerceEntry, CommerceDailyRevision, CommerceSnapshot, CommerceSourceLink, CommerceSuppression, CommerceEvidenceState, CommerceMeasurementPublication |
| Legacy reconciliation | ShopifyOrder, ShopifyTombstone, ShopifyPrivacyRequest |
| Advertising imports | Campaign, DailyMetric, JobRun |
| Selection and capture | EventSelectionRow, CurrentEventSelectionRow, SelectedCaptureRow, SelectedFactRow |
| Aggregate and raw reporting | PerformanceCompletion, CurrentPerformance, RangeReceiptRow, ReportingSemanticsRow, MetricPresenceRow |
| Plan publication and replay | PlanRow, PlanInputRow, PlanVersionRow, PlanDependencyRow, PlanEventRow, PlanRequestRow |
| Catalog membership | CatalogReceiptRow, CatalogReceiptSelectionRow, InputCatalogReceiptRow |
| Media callbacks | MediaObject |

The three guarded models also retain full comparison requirements. Cross-cutting work
still includes real provider freshness, private source rotation, billing/goal/time
predicates, parent/generic cascades, global domain-owner discovery races, physical
SQLite transaction ownership, media/ORM callbacks and response preparation before the
final authorization/commit boundary. None can be replaced by these three row guards.

Next bounded package: CommerceSuppression and legacy reconciliation ownership,
including their financial/order/entry membership effects and existing parent paths.
Keep the same52-model scope and the pending owner decision; do not shorten reads
until complete reviewed closure for a specific proposed optimization.

No push, PR, hosted CI, merge, deployment, provider call, customer-account change or
advertising spend. Existing pending HTTP-admission work remains outside this package.
