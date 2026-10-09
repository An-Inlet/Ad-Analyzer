# W1 Next Migration Producers — Interface For Review

Base `d665feb` (root9b6f6dc plus reviewed commerce e4749fd equivalent).
Docs only; no implementation or qualification. Preserve the frozen W1 traces.
Use the reviewed commerce pattern: parent current Alembic DDL, one bounded local
PIN2155ff3 subprocess, closed mode/schema/revision checks, committed and closed
child Sessions, strict scalar JSON, fresh current SQL readback, no child DDL.
No arbitrary callable/profile, current privacy/capability patch, or social phase.

## Common Boundary

Each public helper takes only `(engine: Engine, artifacts: Path)`. PostgreSQL
only, explicit disposable marker/validated local URL. Exact expected revision
SET, required/absent tables and empty target graph checked before producer; table
names and revision set unchanged afterward. Each prefix is accepted only for its
own closed mode. Output validates exact keys, strict positive integers, bounded
nonempty IDs/digests, sorted unique nonempty ID arrays (maximum64), actual count
agreement and parent-owned SQL relationships. No runtime, Session, catalog,
provider object or current authorizer crosses. Keep180-second/16MiB subprocess
bounds. A timeout is failure evidence, not automatic permission to raise limits.

The exact pinned `tests` and `app` trees remain verified. Historical mapping
adapters below are those already used by the pinned original migration test;
install/cleanup occurs only inside the pinned child, never the current process.

## Budget Preparation0079

`retained_budget_preparation_fixture(...) -> RetainedBudgetPreparationIds`:
`workspace_id:int, mandate_id:str, mandate_revision:int, preparation_digest:str,
policy_digest:str, response_status:int, provider_posts:int`.

Closed mode `budget_preparation_0079`; only
`inlet_migration_fixture_[a-f0-9]{32}`, exact revision set `{20261007_0079}`.
Require initial_budget_mandate_preparations present/empty and optimization mandate
preparations absent; real revision columns lack0080 origin markers. Parent keeps
actual0078 downgrade/table-absence assertion then0079 upgrade. Child installs
pinned install_legacy_origin, obtains pinned replicas/configuration, invokes
pinned budget_mandate_fixture.first_customer, POSTs the actual budget-mandates
route with original body/CSRF, requires201, then reads exact preparation key and
digests. The pinned native wire already accepts GET only; provider_posts=0 must
be measured/established by that fixture, never inferred from successful status.
No current route success claim.

Parent loads the composite-key row and preserves current serialize valid-document
and foreign-workspace omission checks, UPDATE/DELETE trigger rejection, populated
0078 downgrade refusal and exact retained count1. Current SQLite test path remains
unchanged, including actual current HTTP route and assertions. Only PG producer
is replaced; replicas and historical mapper need not run in parent PG branch.

## Derived Candidate0062

`retained_candidate_result_fixture(...) -> RetainedCandidateResultIds`:
`workspace_id:int, job_id:str, result_id:str, mandate_ids:tuple[str,...],
job_count:int, result_count:int, provider_posts:int`.

Closed mode `candidate_result_0062`; only
`inlet_candidates_[a-f0-9]{32}`, exact set `{20261006_0062}`. Require empty
candidate job/result tables, absent later candidate review/initial tables and
pre0080 revision shape. Child uses pinned install_legacy_origin, without_feedback,
without_candidate_reviews and without_initial_planning, then actual pinned
fixture→enqueue→process and requires completed. Preserve runtime privately until
process completes; return actual result/job/workspace and full mandate ID set.
Assert one job/result and zero actual mock writes, as read-only candidate work.

Parent executes current0062→0060 downgrade, verifies both candidate tables gone
and exact mandate IDs preserved, then0062 upgrade and empty jobs. Add current
owned job/result correspondence before downgrade; do not move any current DDL or
retention assertion into the child.

## Reservation Replacement0058

`retained_replacement_fixture(...) -> RetainedReplacementIds`:
`workspace_id:int, run_id:str, predecessor_id:str, successor_id:str,
replacement_ids:tuple[str,...], provider_posts:int`.

Closed mode `replacement_0058`; only `inlet_replace_[a-f0-9]{32}`, exact set
`{20261006_0058}`. Parent preserves actual empty0058→0057→0058 roundtrip and
replacement-table absence check. Child installs pinned without_candidates and
install_legacy_origin, then uses pinned ReplacementHistoricalSession and actual
prepared→replacement.transfer. Original prepared fixture performs one real
MockHTTP original execution before transfer; capture/require its actual write
count1 and exact retained predecessor/successor/run linkage, not synthetic rows.
No replacement provider dispatch is added. Commit/close before returning IDs.

Parent retains current replacement ID-set equality, actual populated0057 refusal
and unchanged set afterward. No current transfer authority claim. Physical
pre0076 mapping remains child-only; no newer origin marker is fabricated.

## Qualification And Freeze Request

Recommend implement sequentially budget, candidate, replacement, one bounded
actual migration probe each before combined affected modules/shared producer
compatibility. Preserve SQLite budget path. Run whole Ruff/bare mypy/diff before
freeze. Report exact missing-schema/pinned-helper failures; no automatic scope
expansion or production fallback. No tests run for this proposal. Social two-phase
remains explicitly outside this interface and needs a separate freeze.
