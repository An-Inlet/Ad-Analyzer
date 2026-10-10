# Customer Social Execution API — Exact Historical Ten / Current Read Four

Docs-only interface proposal. No code/tests or capability changes. Original file
`tests/test_customer_social_execution.py` has two test functions whose complete ASTs
(including decorators/parameters/assertions) are currently identical to PIN
`2155ff3e3ab00cd62057dd86cb49d45359d4f49f`. Its ten original failed nodes are not in
existing historical manifests inspected at baseeb8afe0. Integrate additively with
root's newer highwater/financial packages; never reset their manifest/profile union.

## Exact Original Identities And Meaning

```text
test_social_customer_paused_creation_and_activation[sqlite-meta_ads]
test_social_customer_paused_creation_and_activation[sqlite-tiktok_ads]
test_social_customer_paused_creation_and_activation[postgres-meta_ads]
test_social_customer_paused_creation_and_activation[postgres-tiktok_ads]
test_social_creation_rechecks_authority_after_io[sqlite-session_during_catalog]
test_social_creation_rechecks_authority_after_io[sqlite-expiry_during_qualification]
test_social_creation_rechecks_authority_after_io[sqlite-server_configuration_guard]
test_social_creation_rechecks_authority_after_io[postgres-session_during_catalog]
test_social_creation_rechecks_authority_after_io[postgres-expiry_during_qualification]
test_social_creation_rechecks_authority_after_io[postgres-server_configuration_guard]
```

All prefix `tests/test_customer_social_execution.py::`.

The first four mix positive CURRENT configuration/options/review/confirmation and
foreign access/CSRF with forward execution. Meta then creates/approves a publication
review, starts/advances a paused campaign, performs same-attempt reconciliation,
creates/approves activation, advances to three native activations, reads and logs out.
TikTok intentionally stops at the old custom-identity creation-unavailable409 with
zero posts; it does not reach Meta's activation/logout tail. Preserve that asymmetry.

The six race nodes mutate original-session authority DURING execution catalog IO,
advance execution qualification time, or inject execution server-configuration denial.
CURRENT creation stops before those callbacks, so an early409 cannot qualify those
old race boundaries. No module-wide retained marker or patched current capability.

## Original Preservation

Rename only the two original functions to `historical_contract_*`; preserve bodies,
parameters and decorators byte/AST-equivalently. Keep `setup_social`, `configure` and
`confirmed` bodies unchanged: adjacent social-execution UI consumers import them and
are explicitly outside this package. Old helper's stored identity rewrite remains
only an original historical behavior, not a model for new CURRENT tests.

Add closed historical batch `social_execution_api`, exact ten original PIN nodes,
with exact current-to-historical mapping. Extend BATCHES, partition collection
provenance paths and focused partition/map checks additively; derive successor counts
from current union, not a hardcoded obsolete9/364. Run ONLY this new ten-node batch;
no old batches or frozen aggregate artifacts changed/rerun. Historical source/DB/API/
assertions remain authentic at PIN, isolated from deployed current behavior.

Original Meta same-attempt reconciliation positive stays historical here; the new
source has no emitted effect and cannot pretend to qualify that retained outcome.
Existing current reconciliation packages remain separate evidence.

## Current Positive Counterpart: Four Cases

New `test_current_social_configuration_history_and_execution_boundary`, Meta/TikTok ×
SQLite/PG, planning_boundary marker. Reuse reviewed `retained_social_producer` and
`load_source`, with a NEW closed consumer literal `execution_api` and typed optional
`SocialExecutionReadEvidence`; no generic callbacks or broad table exclusions. Existing
producer/configuration/api/ui branches/defaults stay unchanged. Existing scalar IDs
suffice: current fresh DB reads recover exact owned ProviderExecutionReview/Run and
its actual mandate reference; no new child, no financial runtime, no fabricated IDs.

New helper module `social_execution_read_current_fixture.py` owns only this consumer,
local replica fixture and exact expected current configuration. Original runtime's
non-DSA profile/option adjustment and original `offline-v1` wording are reproduced
using current typed selection/requirements; precompute expected document/hash before
any current mutation. The source is genuine pinned provenance in CURRENT tables with
native_posts0. Media/current source reconstruction stays real and owned. No old native
Server/captured CreationRuntime, activation runtime, exposure reader or adapter needed.

Replicas use source.engine and real customer/configuration/social-execution/generic
execution routers. Current dependency overrides are only owned DB/identity/media and
explicit offline discovery runtime, matching existing current read fixture seams.
Local FakeProvider issuer/email match actual retained mock identity; normal login
uses retained actor subject `actor_id:1`. Bob signs in `stranger:1` with same email,
remaining a distinct foreign customer. No stored issuer/subject/user rewrite, auth
clock replacement or TTL extension. Close both clients before source finalizer.

Actual workflow:

1. Real options200, create configuration review201 and explicit confirmation200 for
   each provider, reusing unchanged `confirmed` request/response logic with current
   source. Assert exact expected saved document/hash and current non-executable state.
   Missing-CSRF current configuration mutation403 must not create a row.
2. Actual owned GET configuration review and GET `/social/confirmed-configurations`
   return the exact current row/digest, no-store and no raw private credential data.
   Foreign Bob GETs are403 (or established route-specific404 if actual source uses
   that owned denial), with no source or auth graph changes beyond his genuine login.
   Expected status for existing confirmed-configurations path remains original403.
3. Read actual pre-existing owned execution review/run through current read routes;
   preserve their exact IDs/digests/state. This source state is retained, not a newly
   created_paused outcome. No new attempts or response/receipt invented for this read.
4. Authenticate each forbidden action with valid CSRF and exact real references:
   social creation, original execution review approval, run start, source-run advance
   and activation-review preparation. Expect exact409 detail
   `advertising_writes_disabled_in_planning_mvp`. No current stage/callback success
   claim. Set forbidden execution runtime and execution-media factory dependencies;
   while testing these actions also replace direct media dependency with forbidden
   sentinel. All counters stay zero. Restore only real current media for allowed
   reads as necessary; no replacement of the actual planning denial guard.
5. Missing-CSRF forbidden action stays403 before runtime/factory; foreign owner scope
   denial remains403; authenticated forbidden actions cannot fall through even with
   a currently confirmed configuration or source review/mandate. Extra client plan
   data is denied by the current predependency409 boundary; old422 assertion remains
   in untouched historical body. Do not mislabel that as current payload-validation
   equivalence. Missing-runtime/source-configuration execution branch assertions also
   remain historical; current cannot legitimately reach those retired branches.
6. Actual Alice logout204, then current configuration/list/source-run reads401;
   Bob still cannot read Alice's scope. Both providers exercise this positive current
   privacy tail even though original TikTok historical branch stopped before logout.

Every allowed current read must succeed before current denial checks count. Do not
replace the full current positive path with generic early-denial tests.

## Exact Closed Graph/Identity Delta

Take distinct complete original snapshots before current work; exact equality
required at final acceptance, not a shared mutable object. Source model/physical
schema and all financial/mandate/source/media/draft/run/review/attempt/reservation/
response/receipt rows stay byte-exact. This package adds only:

- One new Bob CustomerUser with exact mock issuer/subject `stranger`, same source
  email and active status; no memberships/workspaces. Original actor unchanged.
- Exactly two actual ordinary login sessions and known token receipts. Cookie/CSRF
  digests, exact actor IDs, bounded real creation/auth times and standard TTL/receipt
  expiry checked by single-use binder; no secrets written to artifacts. Final only
  Alice revoked_at changes within actual logout request interval. Bob unchanged.
- Exactly one current SocialConfigurationReview plus exact one approval derived
  from independently precomputed offline-v1 document/digest, exact source IDs/actor/
  NOW and approval fingerprint. No legacyV1 manually seeded row in this counterpart,
  unlike separate API4. No second review from failed CSRF or forbidden execution.

Compare whole graph before/after EACH forbidden request, not just final counts.
Copied negatives reject changed original auth/source, duplicate or foreign records,
wrong current digest/approval, unbound/repeated auth binding and unexpected financial
rows. Never relax existing API4's two-review/legacy-row contract for this one-review
case. No new SourceLifetime profile is needed: existing social_producer lifecycle
covers the unchanged child; only a closed current consumer is added.

## Staged Qualification And Coverage Claims

After review, freeze new mapping/closed consumer implementation. SQLite current
Meta/TikTok2 gate; then current4 plus default predependency/owned-history compatibility
and relevant existing social read consumers. Historical new batch10 separately, strict
map/partition checks, whole Ruff/bare mypy/diff. No Full or old batch reruns. Preserve
raw logs/XML and unique source/failed artifact manifests durably before checkpoint.

Only the ten exact original identities count toward historical regression recovery;
current four are explicit meaningful positive read/privacy/boundary counterparts,
not four extra original recoveries and not proof that retired race callbacks run
under current policy. No advertising writes, public feature claims, provider calls,
new execution capability or production changes are proposed.
