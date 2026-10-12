# V6 Matrix Preflight: Authority Expiry

Branch `codex/inlet-w1-followup`, head
`f8107a9c5f60accb5e73e6d9fa82a5b4e33021dd`. Fixture and harness work remains
uncommitted. The executor was confirmed available after the reported disconnect;
all runner outcomes are resolved and no operation remains pending. No quota cause
is assumed. No provider/live access, credentials, push, PR, merge, deployment or
advertising operation occurred.

## Implemented Fixture And Assertions

The optional `FixtureIdentity` interface now flows through Q16 bootstrap, selected
reporting acquisition, creative upload, native owner discovery and owner inputs.
Existing callers retain their prior defaults. Two owners use separate workspaces,
Shopify domains and Shop GIDs, Google customer identities, billing customer/session/
subscription/event identities and uploaded media. A single synthetic encryption and
runtime configuration is installed before requests. Provider responses are
namespaced before acquisition; retained receipts are never rewritten. The frozen
provider routing map is installed before concurrent requests. No planner,
repository or authority replacement is used by the matrix; preparation is only
observed and returned unchanged.

The configured V6 test assembly now has the 18 PostgreSQL descriptors and sequential
SQLite parity for each workload/request pattern. It checks exact version/head and
create/generate receipt bindings, request and response/export digests, owned media,
unchanged provider/financial counts, ten reporting/catalog source families, complete
untouched-workspace planning rows, cross-owner denials and preparation cleanup.
These are implemented assertions, not a claim that every branch has run.

Independent review closed the sequential inventory preflight. The runtime runner
uses one persistent 60-minute clock across runtime phases (statics excluded), a
900-second per-process-group bound, one heavy slot, workspace ≥1 GiB, tmp ≥2 GiB,
runtime memory headroom ≥512 MiB and diagnostic launch headroom ≥1,536 MiB.
The recorder retains setup/call/teardown, original ages/phases and HTTP statuses from
the first invocation. Its 4,096 resource samples cover the per-case time bound.
The client scheduler's requested offsets are 0/50/250 ms; actual arrival records
must be reported separately. The ±1-second scheduling tolerance is not proof of
precise staggering. Four simultaneous same-plan cases require observed final-save
blocking regardless of arrival tolerance, with no retry for missing overlap.

## Observed Workload Cardinalities

Each size uses two independently owned workspaces. Counts below are **per workspace**
and were checked through the actual acquisition/upload and SQL paths on SQLite.
This is a declared workload, not maximum-capacity qualification.

| Property | Small | Larger |
| --- | ---: | ---: |
| Google accounts | 1 | 1 |
| Reporting campaigns | 1 | 4 |
| Native campaigns / adgroups | 3 / 3 | 4 / 4 |
| Budgets / shared owners | 2 / 1 | 2 / 2 |
| Owner intents / scenario allocations | 1 / 1 | 2 / 2 |
| Owned distinct images | 1 | 2 |
| Reporting days | 61 | 61 |
| Aggregate / selected fact rows | 61 / 61 | 244 / 244 |
| Selected captures / range receipts | 1 / 1 | 1 / 1 |
| Catalog receipts / selector rows | 1 / 6 | 1 / 8 |
| Successful document bytes retained | 57,696 in each workspace | Not retained; see gap below |

Full scoped table counts are retained in
`/workspace/inlet-evidence/20261012/matrix-preflight03/retained-inventories/`.

## Exact Runs And First Runtime Failure

Evidence root: `/workspace/inlet-evidence/20261012`.

- `matrix-preflight01`: Ruff passed; mypy stopped on two new fixture typing errors.
  No API tests ran. Original logs/results remain preserved.
- `matrix-preflight02`: four statics and 40 harness tests passed. The first SQLite
  inventory case failed before generation because synthetic billing IDs contained
  schema-invalid hyphens. Three inventory cases stayed unrun. Recorder evidence
  was complete. A changed-source fix used underscores and incorporated independent
  review's distinct Shopify identity and stronger assertion requirements.
- `matrix-preflight03`: **four statics passed** (Ruff, mypy across 1,611 files, exact
  collection, diff check); **40 harness tests and the small SQLite inventory passed**.
  The larger SQLite inventory **failed once**, original exit **1**, process duration
  **52.247644 seconds**. Both PostgreSQL inventory cases and all **18 matrix cases
  remain unrun**. No unchanged retry followed.

The larger case's first workspace generation returned **200**, prepared in
3.090576 seconds, saved in 3.637071 seconds and passed stored/history/export checks.
Its second workspace generation returned **409 before reaching preparation or save**.
The original authority recorder reports `planning_authority_expired`, route
`generate`, phase `lock`, cause `fact_age_outside_window`, `final_fact=false`, and
fact age **5.049541–5.050144 seconds**. The final lock wrapper itself lasted only
**0.002539 seconds**: this is not evidence of a five-second lock wait or contention.
The five-second authority deadline was unchanged and correctly refused the request.

Failure evidence is complete: zero observer errors, dropped records or unbound
facts, restored observers, stopped sampler, clean process cleanup and all **1,929
source hashes verified**. Both HTTP outcomes were retained. Initial larger workload
counts were persisted before generation. **Artifact gap:** the first successful
larger document's byte count was only updated in memory and was not rewritten before
the second failure. No exact larger document size is claimed. Post-pair financial,
provider, source and preparation-cleanup assertions were not reached for this failed
case; individual first-workspace assertions do not turn it into a passing test.

Manifest: `e57aaa6a8199d13135c31cc07c1d9122db2b370d6fcb442af65dbe61a9784022`.
Runner: `471d784c8b61f68f60a1a3e0de7bdaf25eee59ed401c3953220407343be7b029`.
Failed-case recorder: `f336870c4209774de6a9c341fca9e09b86dfdd3c9df06225ddeff39b1a814fb8`.
Original exits, XML, logs, retained inventories, unrun nodes and disposition are in
`matrix-preflight03/failure-disposition.json`. The current checkpoint is
`/workspace/inlet-evidence/20261012/matrix-progress-checkpoint.json`.

## Qualification State And Next Package

The larger envelope has not passed preflight, so the final independently reviewed
matrix manifest cannot yet be approved. Qualification stopped on the observed
unexpected expiry as required. Next work is a narrow inspection of the second
larger request's source-reading path **before preparation**, using the retained
original fact/stage timing. Preserve authority lifetimes, fresh authorization,
source equality, rollback and spending boundaries. Persist per-workspace verification
results immediately in the next evidence implementation so a later request cannot
lose an earlier document-size observation. Any changed-source diagnostic or fix
needs a fresh manifest; do not rerun this freeze unchanged to seek green.

The historical **61 passed / one failed / one unrun** V6 snapshot, separate **25
focused passes**, prior **40 harness passes** and independent **one V5 pass** remain
separate inventories. This newly explained expiry does not establish the cause of
the earlier unexplained failure. `INLET-REL-20261012-01` stays open; V3 remains the
default and V6/V7 remain technically selectable but release-unqualified. The HTTP
inventory remains **57 passed / one unresolved**, all 21 pending HTTP files are
preserved (allowing only already committed `f8107a9c` service lines), migration 0094
is unchanged, and the reconnect-retention owner decision remains pending.
