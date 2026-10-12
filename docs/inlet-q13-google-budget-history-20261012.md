# Q13 Injected Google Budget Read And History

Continues local `ab3e5f44` on `codex/inlet-w1-followup`. One narrow fixture-backed
Google DAILY shared-budget hypothesis now has a service-to-history path. It is not
an activated production reader, provider-authenticated observation or implementation
verification. There is no new writer route, network default or production factory.

## Implemented Boundary

The [reviewed contract](design/q13-google-budget-read-history-20261012.md) pins Google
Ads v22, exact GAQL/profile, owned account/source/privacy/action binding, field presence,
int64 micros, pagination completeness and monotonic timestamps. Selected pages are
bounded and retained. The fresh catalog derives only queried facts, never old names or
unqueried settings. Missing amount/false is not synthesized as zero/false. Unknown,
foreign, duplicate, non-JSON, incomplete, inconsistent and expired evidence refuses.

The injected service prepares under current customer authority, releases SQL for reads,
refreshes the original identity, then atomically rechecks ownership, input/version,
source/privacy and deadline before appending an event and request receipt with sequence
CAS. SQLite starts a physical read transaction before SELECT; PostgreSQL locks the
owned source row. No partial head/event/receipt survives failure.

Observation and invalidation have explicit schemas, separate from customer reports and
legacy field observations. Only server-proven source_generation_changed is admitted as
invalidation; the exact prior observation remains immutable. Both schemas work through
storage, API receipt/history readers, browser and workspace archives. Current reliance
and implementation remain not_assessed. Equality means matches_hypothesis only, not
customer enactment, spend-limit compatibility, causality or lift. Partial history warns
that later invalidations may be on another page. Retained evidence follows existing erasure.

Exact replay and invalidation now prepare retained proof between authorized short
transactions. They retain original strict parsing and result validation, then refresh the
original identity and compare every receipt/event scalar and canonical byte before
acceptance. Prepared results are invocation-private, with no global cache, trusted-data
bypass or enlarged authority window. Historical replay does not pretend the old source
is current. A receipt discovered during final publication follows the same recovery path.

Event-page reads use a dedicated prepared-read context (leaving unrelated readers
unchanged): copy the exact ordered page plus lookahead under authorization, strictly
decode and build the page outside SQL, then refresh the original identity and requery
all row bytes/scalars before return. Budget-only receipt GETs use the same boundary
with original actor scope. SQLite begins a physical transaction before authorization.

## Qualification

Frozen evidence: `/workspace/inlet-evidence/20261012/q13-budget-history12/`.
Manifest SHA-256 `32a5b40a155aa77028e48766deaa2c1a5332398d62f43f819d17e8fc3c889d39`;
1,898 source hashes verified before and after each command. All 22 commands exited
zero, with exact ordered XML identities, no skipped tests, interruption, escalation or
surviving subprocesses. Checks actually run:

- Whole-repository Ruff and configured mypy (1,581 source files).
- Exact collection of 44 selected nodes and `git diff --check`.
- 30 components: 21 acquisition/projection/refusal tests, seven new event/storage/export
  tests, one existing legacy report/export test and one extended Chromium history test.
- Seven SQLite cases, then seven PostgreSQL cases: six new service/HTTP cases and the
  existing configured V7 report-correction lifecycle on each backend.

The database cases verify actual service, HTTP history/receipt and archive joins; strict
replay without reacquisition; mixed legacy decisions and budget events; unchanged-intent
recovery when a receipt appears during acquisition; changed-intent/foreign access refusal;
provider revocation during acquisition/preparation; final-authority rollback after both
inserts; source/expiry changes; privacy erasure; and simulated snapshot-mismatch refusals
for retained event, invalidation prior, page lookahead and HTTP receipt. Snapshot mismatch
is fault injection, not a claim that immutable SQL history can normally be updated.

PostgreSQL's two overlapping requests produce one success and one exact
`budget event sequence changed` conflict, with one event/receipt and no loser rows.
SQLite has sequential conflict parity. At the final read/write boundary, SQLite WAL
refuses with a locked snapshot and rolls back; PostgreSQL's actual writer-to-mutator
blocking edge is verified through bounded `pg_blocking_pids`, and the source mutation
finishes after the observation transaction. Backend IDs are not retained in artifacts.

`qualified-summary.json` binds all check outcomes and four copied synthetic history/CAS
artifacts by SHA-256 and test node; `prior-attempts.json` indexes every original prior
outcome/unrun phase. These files and original logs/XML remain beside the manifest.
Independent contract/source/test review closed; final evidence/docs review is recorded
in the local commit binding. The two observed PostgreSQL expiry failures remain preserved.
Successful bounded qualification does not establish their measured CPU cause, general
load reliability, production transport provenance, or closure of the generation incident.

## Preserved Attempts

All original exits, logs, JUnit where produced, manifest/source hashes and unrun phases
remain under `/workspace/inlet-evidence/20261012/`.

| Attempt | Actual result and correction |
| --- | --- |
| q13-budget-read01 | Ruff stopped on three long lines; later checks unrun. |
| q13-budget-read02 | Ruff passed; mypy stopped on seven fixture typing issues. |
| q13-budget-read03 | Static checks and 20 acquisition tests passed. |
| q13-budget-history01 | Ruff stopped on four embedded-JavaScript long lines. |
| q13-budget-history02 | Ruff stopped on one remaining 101-character line. |
| q13-budget-history03 | Ruff passed; mypy stopped on four fixture Any returns. |
| q13-budget-history04 | Static and 30 components passed; first SQLite lifecycle stopped at receipt GET 422. Added the two read-only operation literals; remaining SQLite/PostgreSQL unrun. |
| q13-budget-history05 | Static and 30 components passed; first SQLite lifecycle stopped at export POST 404. Mounted the existing router in the minimal test replica; remaining databases unrun. |
| q13-budget-history06 | Static and 30 components passed; first SQLite lifecycle stopped at archive download 503. Configured the existing local test media store; remaining databases unrun. |
| q13-budget-history07 | Static passed. Source review found the fixture's nested media directory before runtime; corrected it and left all component/database phases unrun. |
| q13-budget-history08 | Static, 30 components and all three SQLite cases passed. First PostgreSQL lifecycle stopped at exact replay with planning_authority_expired; remaining two PostgreSQL cases unrun. Full proof validation repeatedly ran inside the five-second fact window. Moved strict retained-proof preparation outside that window with complete-row rechecks; call-graph evidence identifies plausible cost, not measured CPU attribution. The original failure is retained, not incident closure. |
| q13-budget-history09 | Ruff passed; mypy stopped on the test's implicit imported-attribute re-export. Imported the original storage function directly; later checks unrun. |
| q13-budget-history10 | Static and 30 components passed; first SQLite lifecycle stopped because the existing immutable-history trigger rejected deliberate SQL corruption. Replaced that invalid fixture operation with simulated later-snapshot mismatch injection, preserving the trigger; remaining databases unrun. |
| q13-budget-history11 | Static, 30 components and all four SQLite cases passed. PostgreSQL passed revised service replay/invalidation but stopped at history GET 409 planning_authority_expired; remaining three then-selected PostgreSQL cases were unrun. Moved strict event-page/budget-receipt preparation outside their final authority window, retaining fresh authorization and complete page/receipt rechecks. |

These are not unchanged retries or hidden acceptance evidence. Only the final frozen
packet qualifies the resulting service/history package. No full-suite or live check claimed.

## Remaining Work And Holds

Production transport authentication and provider qualification remain absent. API v22 is
an extraction profile here, not a claim of current live support. A live adapter needs an
explicitly authorized provenance/authentication design and qualification before activation.
No other field or platform was broadened. No current-reliance projection or customer
observation control is exposed. Default V3 and the V6/V7 release holds remain unchanged.
INLET-REL-20261012-01 remains open; these event-CAS/source-fence tests do not qualify
concurrent generation or close its original unexplained authority-expiry incident.

Next package: review this completed narrow offline path and define the remaining
provenance/activation qualification prerequisites while preserving the live and release
gates. No push, PR, hosted CI, merge, deployment, live provider/model call, customer
advertising change or spend occurred.
