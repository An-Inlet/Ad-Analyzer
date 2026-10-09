# Configured Candidate Source And Current Session Split

Design only from `c0e8532`, refining section C of `57dff89`. Scope is exactly the
16 Google/Meta × unqualified/scenario/revoked/revoked_during_read × SQLite/PostgreSQL
identities in test_configured_candidates_api. No implementation yet.

## Exact Original Source Before Enqueue

Add fixed helper tests/configured_candidate_retained_fixture.py and child
 tests/fixtures/retired_execution/configured_candidate_seed_driver.py (no leading
space). Literal2155 verified app/tests/scripts trees. Closed arguments platform
{google_ads,meta_ads} and mode {unqualified,scenario,revoked,revoked_during_read}; no
arbitrary callback, PIN, path selector or policy. Mode affects original registered
candidate descriptor, not permission to run work in the child.

Child invokes untouched original configured_candidates_customer against original
replicas, with original configuration fixture, mock HTTP and scoped monkeypatch.
That fixture genuinely builds approved simulation source/owner, revises and confirms
its goal budget_start to NOW.date, runs actual CommerceSyncService, constructs the
original candidate and optimization manifests, POSTs target-options, prepares the
origin-bound budget mandate and consents it. Stop exactly at its return BEFORE
/candidates/reads. Close both clients and original sessions before returning IDs.
No enqueue, worker, prepared candidate, candidate review, approval, execution run,
claim, attempt, receipt, response or reservation. Assert zero rows in those tables
and measured Google writes/Meta posts zero. Existing original mandate consent is
historical source. Do not substitute Candidate29 or the raw durable.ready fixture:
those do not carry this configured0080 preparation origin.

## Frozen Scalar Source Contract

`ConfiguredCandidateIds` fields:
platform (closed literal), workspace_id/account_id/goal_revision/mandate_revision
(positive strict integers), actor_id/goal_id/mandate_id/consent_id/ledger_id/store_id/
publication_id (32hex), native_connection_id (exact platform mapped str for Google,
integer for Meta), policy_digest/preparation_digest/goal_digest/account_scope_digest/
operating_policy_digest/optimization_manifest_digest/candidate_policy_digest/
candidate_manifest_digest/evidence_descriptor_digest/publication_manifest_digest
(64hex), provider_posts (exact integer0).

No session token/digest/cookie, policy/measurement/provider body, ORM/runtime or
callback in output. JSON≤8192, exact keyset. Source manifest files remain private
artifact siblings produced by original fixture, not authority loaded from arbitrary
paths. Current parent parses them with actual models, checks DTO digests and exact
original constants; only known fixed filenames may be read.

Parent loads actual current owner membership, account/native generation, goal
revision/definition digest, active provider mandate/revision, exact consent/ledger,
0080 origin row and typed preparation document. Compare provider policy/preparation/
operating/goal/account commitments, 50m total cap, original chosen option and exact
source publication ownership/manifest. The original optimization operating rules
have per-plan50m, positive-change10m, action_limit10, freshness120. Do NOT use
configured(..., existing=...) because it silently switches positive-change to5m.
All no-enqueue/no-effects checks run before and after the producer boundary.

## Fresh Current Login Is Legitimate, Not Original-Session Substitution

Source evidence: OptimizationMandatePreparationV1 has no session field;
ConfiguredOptimization.origin_guard validates exact retained operating/evidence/
goal/account/period and authorizes its CURRENT principal. execution_mandates.checked
validates exact stored consent, current actor ownership and consent actor ownership,
not equality to a historical consent session. Neither allows changing the mandate
origin. Therefore a fresh genuine same-owner login may use these existing records.

Current fixture recreates replicas on the yielded engine and performs the actual
customer login endpoint for existing configured-google/configured-meta subject
using a new test identity token. Assert returned user equals actor_id and actual new
session row exists. Capture old session-row identities privately before login and
prove the new token/session was freshly issued, without importing child cookies or
updating any existing session's authority fields. Leave stored consent/origin intact.
If current origin checks reject it, preserve the concrete failure; do not edit
session rows, bypass identity/ownership checks or reuse a child token.

Actual /candidates/reads binds its newly enqueued job to this CURRENT principal's
session; current status() explicitly requires row.actor_id/auth_session_digest to
match that session. Actual run_customer_tick must recover/use that new job session.
This original-job-session requirement starts at current enqueue; it does not bind
new jobs to the historical mandate setup session. Revoked-before/during cases
continue mutating/revoking the actual current login row exactly as original tests.

## Current Post-Seed Runtime Wiring

Use a new local setup helper, leaving original shared fixtures unchanged. Reproduce
only original post-seed wiring: exact offline encryption/client config, original10m
operating policy/manifest, actual current configured optimization assembly, provider
Wire/MockHTTP routes and transport lifetime counters/callback. Load matching
candidate descriptor/policy/manifest and registered evidence binding for the mode;
scenario transform remains explicit contract_scenario/decrease/2 observations,
never commercial evidence. Bind current provider identity and existing NOW clock
as the original test; no session TTL/global production clock changes.

Candidate reads may need original read-side qualification callbacks to match the
stored0080 origin qualification ID/revision/digest. Do not reuse A30's current
read helper's forbidden qualification/exposure callbacks blindly: that helper
qualifies target discovery only. Carry the exact original controlled qualification
contract where current configured candidate reading needs it; all actual mutation
sinks stay immutable always-deny. Never invoke a spending coordinator. No callback
may fabricate a candidate result; actual API selection/enqueue and job tick produce
it through current code and SQL.

## Preserve Both Old And Current Acceptance

Preserve all16 original function cases with unchanged PIN source/assertions in one
explicit new historical16 batch using the reviewed harness. Keep the local original
function bytes as the normal framework's preserved callable and verify its AST
against2155. Update exact manifests/wrapper coverage/provenance/partition closed
counts together against the then-current baseline; do not assume B40 has already
integrated or blindly claim a349-node union. Qualify only the new16 historical
nodes, not all existing batches. Historical success remains separate from current
read/worker proof and counts original failures once.

New current16 cases preserve capabilities, actual POST /reads201, exactly one job,
real run_customer_tick, current status/decision digest roundtrip and forged digest
rejection, no result after actual pre/during revocation, balanced transport closure,
and zero provider effects. For scenario only, replace old successful review/approval
with exact current review409 advertising_writes_disabled_in_planning_mvp and unchanged
review/approval/run/attempt/receipt/hold counts. Also directly exercise the owned
current approval endpoint using a syntactically valid nonexistent review ID and
exact request shape: it must deny409 before review lookup/runtime/effects. This is
current policy denial, not successful approval or a claim of an existing review.
The original meaningful successful review/approval sequence survives only historical16.

## Isolation, Lifetime And Qualification

Use new empty current file-backed SQLite with FK enforcement or exact validated
loopback disposable PostgreSQL inlet_test UUID schema, no URL query/foreign target.
Both parent/child reject nonempty source tables (version only allowed), preserve
schema and require zero downstream work/effects. One closed configured_candidate
SourceLifetime profile, fixed driver, source/archive only cleanup after reap;
IDs/log/media/manifest files/SQLite remain siblings. Bounds180s/16MiB runner unchanged.

Probe genuine Google and Meta sources then current scenario positive read+denial on
SQLite before expanding. Stop origin/session/schema mismatch with raw trace. Final
current16 +86 immutable boundary cases; historical16 separately; static checks,
original AST proof, exact failure identity mapping, scalar/session provenance and
cleanup proof. No aggregate/live calls or unrelated consumer expansion.
