# Q13 V24 Mock HTTP Admission — Qualification Blocked

Uncommitted implementation from b273e3e4 on `codex/inlet-w1-followup`. Source and
contract review closed, but qualification is incomplete. The original stopped packet
is preserved as 55 passes, one failure and two unrun. Those two cases subsequently
passed in independent runs: cumulative acceptance coverage is 57 passes and one
unresolved failure. A separate diagnostic pass does not replace that failure. After safe memory recovery, the resumed
PostgreSQL browser test failed at genuine plan generation with
`409 planning_authority_expired`, before reaching HTTP observation. Do not describe
this package as fully qualified or commit it as a completed delivery yet.

## Implemented, Pending Final Qualification

The [reviewed contract](design/q13-http-admission-20261012.md) adds a distinct
`inlet.google-budget-http-observation.v1` event, HTTP-profile intent and
`budget_http_observe` receipt operation. The strict customer route is
`/api/customer/v1/workspaces/{workspace_id}/planning/plans/{plan_id}/budget-http-observations`.
The server selects the profile. New proof/ticket schemas remain unchanged; a direct
v24 projection derives the comparison witness without constructing a v22 proof.
Every new event retains mock_http, provider_authentication not_verified,
implementation/current_reliance not_assessed and no advertising authority.

An explicitly installed immutable bundle supplies bounded synthetic pages through
exact MockTransport and dummy headers only. The existing HTTP mode defaults to
disabled; mock_http plus V6 and the exact installed bundle are required. Current
owner/session, paid entitlement, source/account/connection, privacy, goal and plan
head are checked before acquisition, around IO and before atomic append. SQL scopes
close before transport dispatch. The original 60-second ticket is never renewed and
is checked again after both event and receipt inserts. Replay uses the exact original
receipt without reacquisition; disabled acquisition POST, including replay, refuses.
Authorized history and receipt GETs remain available after mode disable.

Exact schema/operation/proof dispatch extends storage, prepared history/recovery,
workspace archive serialization and browser rendering/recovery. The portal labels
mock HTTP as synthetic and not provider-authenticated. V22 canonical bytes/digests
are pinned against pre-admission artifacts and preserved. V24 invalidation is excluded;
the old injected_fixture invalidation schema cannot be reused for it. The existing
plan-version download remains unchanged; observation export is the workspace archive.

## Exact Evidence And Stop

Evidence directory: `/workspace/inlet-evidence/20261012/q13-http-admission05/`.
Manifest SHA-256 `e3af167fcdc27584a61afb6ae7f4098802c0dcd2ff2901871e883237900fd25c`.
All 1,909 source hashes verified. `partial-summary.json` records 15 passing commands,
one interrupted command and two unrun commands, with 11 retained synthetic artifacts.

- Whole-repository Ruff, mypy (1,592 files), exact collection and diff check passed.
- All 48 components passed: 39 HTTP protocol cases, existing Chromium renderer,
  pre-admission v22 byte/profile check and seven legacy event/storage cases.
- All five SQLite cases passed: new mixed durable history/replay/archive/erasure;
  late authority/configuration/rollback; actual new browser recovery; legacy API and
  browser regressions.
- First two PostgreSQL cases passed: mixed history/replay/archive/erasure and late
  authority/configuration/rollback.

The third PostgreSQL command stopped after 30.632s when cgroup memory headroom was
533,606,400 bytes, below the required 536,870,912-byte reserve. Original process exit
was -15; XML was incomplete and supplies no test/assertion outcome. Cleanup required
no kill escalation and left no surviving test children. Source hashes still matched.
The interrupted browser case is not a pass and is not an application assertion failure.
Independent review verified all 55 exact passing identities and this classification.

The new tests verify distinct same-key receipt operations, strict provenance/version
refusal, mixed paginated history, original v22 rows, no reacquisition on replay,
revocation/foreign-access refusal, erasure and zero advertising/financial effects.
Post-insert tests confirm both rows exist before injected disable, ticket deadline
or final-authority refusal, then prove full rollback. The authority refusal is an
injected exception; event-sequence conflict is serial preflight refusal, not concurrent
CAS or capacity qualification. Actual per-IO disable/revoke uses one mock dispatch.

Each export download builds a new ephemeral archive. The erasure test verifies a newer
snapshot, the exact privacy revision read from the erasure transaction, empty planning
events and absence of both old event IDs. Original and rebuilt archive files are retained.

Earlier attempts are preserved in `prior-attempts.json`: 01 stopped at three long
lines/two callback bindings; 02 stopped at two strict import-typing errors. 03 stopped
at a mistaken assumption that an ephemeral export URL must return 404 after erasure.
04 stopped at a mistaken +1 privacy-counter assumption; cascading deletion triggers
advance it multiple times (observed 67 versus expected 2). Review confirmed both
test-only corrections against existing export/privacy contracts; assertions now bind
the actual database revision and erased content. No production privacy gate was relaxed.

## Required Continuation And Live-Read Gap

The owner requested checking the previously approved safe cache recovery before
asking for additional memory. Independent review approved deletion of 352 inactive,
task-owned regenerable mypy SQLite cache files (975,491,072 bytes) in two exact
inventories. Source, evidence, unrelated files and services were preserved. Foreign
service FD inspection exclusions are explicit; universal FD visibility is not claimed.
Proposals, cleanup journals/results and reviews are retained in
`q13-http-admission-recovery/` and `q13-http-admission-recovery02/`.
Six samples over 50 seconds had minimum headroom 1,694,973,952 bytes, above the
1.5 GiB launch reserve. No capacity purchase or reconfiguration was needed.

Continuation `q13-http-admission06/` binds all 55 prior passing identities, four static
checks, original/final records, both cleanup inventories/results and unchanged 1,909
source hashes/runner. Its manifest SHA-256 is
`82081d4baddb2318da3152d357238e23a2aeb5377f9494155df26e9522f0727d`.
Only the three interrupted/unrun PostgreSQL cases were selected, with the original
512 MiB runtime floor and timeouts. The first case failed and immediately stopped:
original exit 1, process 74.470196s, valid XML with one failure/no skips. No resource
interruption, cleanup escalation or surviving children occurred. The retained route
trace shows discovery/create/current/versions succeeded, then genuine generation
returned 409 planning_authority_expired in 12.292752s. HTTP observation was not reached.
Route elapsed is not identity-fact age; the precise expiry predicate/phase and root
cause are not captured. Independent review confirmed this classification.

`blocked-summary.json` preserves the continuation failure; the original memory stop
remains separate. Two legacy PostgreSQL API/browser cases remain unrun. There is no
unchanged retry, source fix, timer relaxation or completed-package commit. No heavy
test remains active. This is another configured-V6 generation authority-expiry
manifestation relevant to INLET-REL-20261012-01, not proof of that incident's exact
cause or an HTTP admission defect. Next bounded work is a separately reviewed
diagnostic plan for generation phase/authority age; preserve existing authority fences.

The exact next engineering gap after mock qualification is a separately versioned
provider-read provenance contract and an owned credential/account coordinator for this
budget ticket. Existing `OwnedGoogleReportingContext` and `source_pin` are reusable
patterns, not already-connected budget authority: bind the original ticket/deadline,
session/workspace/account, source generation, encrypted-grant revision and manager
context around token resolution and every read; never persist credentials in evidence.
A production read transport must preserve all bounds and refusal behavior. Its evidence
must remain distinct from mock records; HTTP 200/request-id is not authentication proof.
Offline contract/adapter tests can proceed separately; real credentials/provider calls
and intended-environment verification need explicit live authority and setup.

V3 remains default. V6/V7 remain release-unqualified, INLET-REL-20261012-01 stays open,
and this memory stop is not its diagnosis or closure. Six expert usefulness decisions,
unfinished Q01–Q16 work, commercial/live-service setup and customer pilots remain gates.
No push, PR, hosted CI, merge, deploy, real credentials, live provider/model/payment
call, advertising write or spend occurred. Public webpage work remains owner-managed.


## Architectural Review Successor

The owner prioritized the authorization boundary over feature expansion. See the
[reviewed two-stage assessment, independent-case evidence and diagnostic limits](design/generation-authorization-boundary-20261012.md).
The two legacy cases previously recorded as unrun passed independently with unchanged
source. The diagnostic run of the failed workflow passed but supplies no acceptance
credit or closure of the original incident. Complete dependency/writer inventory and
both-database membership contract tests are the next package; preserve full current
rereads and the five-second rule until that architectural proof is complete.
