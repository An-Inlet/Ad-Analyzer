# Open Reliability Findings

## R01 — Original Browser Generate-Action 409: Unresolved

Observed in `creative-portal-browser/both-02` on PostgreSQL after four SQLite cases.
The user action runs POST generate, GET current plan and GET versions. Its generic
409 message does not identify the failed route or reason. Original route details,
server/browser output and disposable database state are unavailable. Authentication-
bearing browser profiles are not inspected. The original failure is preserved.

Later ordered and integrated passes establish their own scoped results only. The
separate UTC receipt defect, allocation-currency correction and forthcoming Q08
changes are not explanations or repairs for R01. The separately captured API
`planning_authority_expired` is also not evidence of this browser event's cause.
Measured costs and the deferred preparation optimization remain separate findings.

Next diagnostic opportunity is one coherent post-Q08 integration milestone after
reviewed changes freeze. Select exact explicit nodes in original order: SQLite
Google, Meta, TikTok, safety, then PostgreSQL Google. Append new Q08 browser cases
only if implemented and reviewed; otherwise state Q08 API-only coverage. One serial
`-x` cohort, normal clocks, existing browser deadlines, no timing/screenshot plugin,
no concurrent database job. Preflight reserves:512MiB memory,1GiB workspace,2GiB
scratch. Preserve original artifacts and use a new evidence directory.

The observer retains only bounded fixed route classes, ordinal, HTTP status,
allowlisted fixed reason and elapsed time, at most100 records. No identifiers,
query strings, authentication material or successful response bodies. Completed
records must persist even if browser completion times out; a shutdown that cannot
join is labeled incomplete. Output failure must not replace the original exception.
No exception text or private browser profile is captured as a shortcut.

On first failure, stop. Use the route/detail and any already-authorized bounded
state assertions to design a failure-specific investigation before another run.
On success, record current milestone evidence and keep R01 unresolved. Do not
retry until green or infer a historical cause from later success. The missing
original facts cannot be recovered by instrumentation added afterwards.

[Original safe analysis](/workspace/inlet-evidence/20261011/creative-portal-browser/original-409-analysis.md)
and [all portal attempts](inlet-private-portal-checkpoint-20261011.md) remain the
source record. Closure needs an evidence-supported diagnosis; current passing
observations alone do not meet that standard.

## Q08 Milestone Observation — 32852e2

The planned exact ordered seven-node run passed once in68.60s, with no skips or
failures and no concurrent database job. All44 bounded route records returned200;
all seven observer shutdowns completed. Fourteen safe artifacts and exact manifest
are retained in `/workspace/inlet-evidence/20261011/q08-browser-integration/`.
No historical cause was established. R01 remains OPEN; no extra retry is planned
from this successful observation. Normal-path artifact persistence was exercised;
forced-timeout persistence remains source-reviewed, not runtime demonstrated.

## R02 — Q09 PostgreSQL Generate Authority Expiry: Open

The local `creative-q09-baseline/both03` cohort stopped after two passing SQLite
cases when the PostgreSQL complete case's POST generate returned409 with the exact
fixed reason `planning_authority_expired`. The fourth PostgreSQL partial case did
not run under `-x`. XML records2passed/1failed,54.719s. The earlier corrected
SQLite-only cohort passed2; neither that success nor this narrower failure qualifies
the planned four-case Q09 baseline. Tests used the integrated owner-input consumer,
real local customer API/database paths, and mocked provider acquisition.

Logs/XML, exact source hashes and successful SQLite document/export artifacts are
retained in `/workspace/inlet-evidence/20261011/creative-q09-baseline/`. An earlier
fixture failure parsed a capture header as a full document; it was corrected to the
existing strict historical_capture reader, with the failed attempt retained. That
fixture correction is not a runtime authority repair.

No retry or authority-limit change followed the PostgreSQL failure. Read-only
failure-specific diagnosis is authorized: identify the exact failing phase from
available facts, inspect the unchanged five-second boundary and previous measured
costs, then propose bounded safe phase instrumentation before another execution.
Any diagnostic execution requires review of that concrete proposal; use normal
clocks, unchanged authority limits, no concurrent DB job and retained failure output.
No inferred performance cause is established by the fixed error alone.
The same error covers either monotonic fact age outside0..5seconds or session
wall-clock expiry; both03 did not distinguish those branches. The reviewed observer
proposal is [a separate diagnostic design](design/q09-r02-authority-observer-proposal-v1.md).
Failure-reproducing source remains isolated at `0b6fd79`; no four-case pass is claimed.

R02 has a known route/reason and is tracked separately from R01's original generic
browser action409. It does not retroactively explain R01. No broader Q09, live,
provider, hosted or release qualification is claimed. Independent standalone owner
review-contract work can proceed while diagnosis is prepared.

### R02 Single Observation — Probe04

The reviewed plugin `7a5bd4ca025fbcfdf322bb7f78823ad43025de71a0d20afd0e7a0171c8b41a38`
ran exactly once on frozen `0b6fd79`, one PostgreSQL complete node with normal
clocks and unchanged guards.1 passed21.668s; no retries. Both generation calls
(including replay) returned; no events truncated. Maximum observed final fact age
was3.042576s at repository save line640, session remaining28,782.63s. First
generation wall9.233794s included8,628 SQL statements/2.349233s measured SQL time;
save inclusive wall3.042459s included3,146 statements/0.656306s SQL. Replay wall
0.093005s included26 statements. Nested times overlap; failed SQL duration is
excluded. CPU/wall differences do not identify lock contention.

The original failing run had no such observations. This success does not explain
it or close R02, and the PostgreSQL partial case remains unexecuted. No optimization
or deadline increase is justified as an incident fix. A separate source-only
query-path proposal may address the observed statement count without weakening
authority, ownership, privacy or source revalidation. Original Q09 source stays
isolated/unqualified. Exact report, XML, manifest and successful document/export
are retained under `creative-q09-baseline/probe04*`.

## R03 — Private V6 SQLite Generate Authority Expiry: Open

The new service integration's first actual SQLite owner-review case stopped at
POST generate with exact409 `planning_authority_expired`. `sqlite-01.xml` records
one failed case and no passes; 25 other API cases were not run. The first failure
source and logs are preserved under
`/workspace/inlet-evidence/20261011/google-owner-v6-runtime/`. The source subsequently
froze as diagnostic-only `d594cb9`: two production formatting changes and test-only
typing repairs, no behavioral fix. It is not integrated into the root branch.

A separately reviewed, explicitly authorized single diagnostic ran the same node
on that clean freeze with unchanged observers `7a5bd4...` and `6adaed...`, normal
clocks and unchanged limits. It passed; first generation took7.652052s with6363
successful SQL statements, including save3.854336s/2385statements. Maximum observed
final fact age was3.854484s, with about28789s remaining on the session. Replay took
1.934163s/30statements. No event truncation occurred. Save's measured SQL duration
was0.044450s; its census-exclusive wall3.186895s includes unwrapped work and observer
overhead and cannot identify a specific expensive function. Inclusive/exclusive
and nested timing values must not be added together.

This successful observation does not explain the original failure, qualify the
held service matrix, or close R01/R02. R03 tracks a separate new source/database
incident. There is no evidence-supported failing invocation or predicate yet.
Further work must preserve these failures, avoid unchanged-case pass chasing, and
retain original-session, fresh-source, privacy and five-second checks. The existing
portal implementation remains dependent on service qualification.

### R03 Instrumented Zero-Ceiling Occurrence

The reviewed continuation ran only previously unrun nodes, with one observer process
per node to avoid the base observer's ten-report retention limit. SQLite explicit
empty passed; the next zero-ceiling case failed and stopped the remaining23 cases.
At `repository.save_generation:572`, after retained-source capture and before CAS
or version writes, the original fact's measured age bracket was5.028596–5.028617s,
with28785.66s remaining on the session. The prior authority-lock return measured
2.752946s. This occurrence therefore exceeded the fact-age limit, rather than
session expiry. No events were truncated. Save inclusive wall5.028442s/CPU5.021001s
included2379successful statements/0.073374s SQL time.

The retained interval needs narrower stage attribution before a repair. The separately
reviewed canonical storage-pair proposal applies after CAS and was never reached
here; it cannot repair this occurrence. No deadline, refresh, source pass or cache
has changed. The original SQLite-owner failure and R01/R02 remain unexplained.
Evidence: `google-owner-v6-runtime/remaining-04/02-sqlite-observer.json`. The four
changed pure registry cases passed separately; they do not qualify actual generation.

### R03 Retained-Stage Observation And Bounded Changes

The one authorized stage observation on unchanged production source (`27046fb`,
docs-only child of `d594cb9`) also failed, but later: the pre-CAS guard passed at
4.919881–4.919896s, then the final post-flush guard failed at5.473398–5.473451s.
Session lifetime remained positive. One generation report,492helper calls and no
truncation were recorded; evidence summary/docs freeze `f34f0e2` was independently
reviewed. This invocation differs from the prior pre-CAS failure.

Retained capture took1.937800s with774successful SQL statements. Its adjacent owner
document wrapper took0.102388s including its nested owner validator; eight owner
validators within the retained subtree totaled0.800709s with noSQL. Four owner
validators after retained capture totaled0.385767s with noSQL. These nested and
inclusive values cannot be added or treated as predicted removable time.

The reviewed next work removes only two source-proven adjacent duplicates:
[context validation](design/owner-retained-context-restriction-v1.md) and
[canonical storage serialization](design/planning-version-storage-pair-v1.md).
All remaining validators, fresh SQL/source passes, CAS, rollback and final authority
checks stay intact. No cache, refreshed deadline or wider time limit is proposed.
Both changes require focused regression coverage and qualification on their new
source; no further unchanged-source diagnostic retry is planned. The historical
failures remain in the record without a retroactive cause or reliability claim.

### R03 Combined Qualification Remains Blocked

Combined06 tested context restriction plus canonical storage-pair changes on
`ee6ef59` with recorded source diff `93103576`. Sixteen pure tests passed. The
first actual SQLite zero-budget case failed before CAS at the original authority
guard: fact age 6.519859–6.519885 seconds, with positive session lifetime. The
remaining 27 API cases were not run; PostgreSQL and actual storage-pair rollback
remain unqualified. Storage serialization was not reached. No unchanged retry ran.

Diagnostic-only freeze `69865572ba17608f111c4ca725ce7161239bf72d` preserves
production bytes from that attempt. Whole Ruff, configured no-path mypy (1,476
files), and diff checks passed after test-only style/type corrections; initial
static failures remain recorded. Independent review and root verification checked
six source hashes and 20 evidence hashes. Evidence lives in
`google-owner-v6-runtime/storage-pair-final-qualification.json`. The failing service
changes are not integrated; root's context-only code remains `788edfc`.

Workspace recovery at 17:49 UTC confirmed preserved clean integration HEAD
`ea49d6c`, readable evidence and no active tests. No reset or duplicate run occurred.
The next source-only contract reviews moving original-data validation before the
existing final identity refresh, with complete private graph ownership and exact
deferred error precedence. All fresh SQL, source, receipt, retained, CAS and final
five-second checks must remain. Implementation awaits technical review; sufficient
timing improvement is not established. R01/R02 remain independently unresolved.

### R03 Extracted-Phase Observation

A single authorized phase-cost observation on frozen `606d38b` failed at the
post-flush guard. Fact 11 passed the pre-CAS guard at 4.962805 seconds and failed
at 5.197661 seconds; session lifetime remained positive. One report, 491 helper
calls, no truncation, no retry. Source and observer checks were unchanged during
the run. Independent review and root verification checked all 11 evidence hashes.

The three non-overlapping pure phases took 0.216883, 0.005185 and 0.566632 seconds,
each with zero SQL. Their observed sum is 0.788700 seconds, not predicted removable
time. Save took 5.197482 seconds with 2,385 SQL statements; retained capture took
1.757764 seconds with 774 statements, included within save. Nested timings/counts
must not be summed. Evidence: `google-owner-v6-runtime/extraction-07-summary.json`.

This occurrence is located, but service qualification remains failed and R01/R02
retain their original evidence. Next investigation is source-only inspection of
adjacent duplicate validation within the owner-binding pure call. It grants no
permission to remove checks across SQL/callback boundaries, extend deadlines or
claim a fix before changed-source acceptance tests pass.

### R03 Changed-Source Uninstrumented Acceptance Failed

Same-call owner-validation reuse froze at `6df589b`, with 24 focused tests passing
and whole Ruff/configured mypy (1,478 files) clean. The unchanged fallback and fresh
validation across database boundaries were independently reviewed.

Acceptance08 then ran without external profiling on that changed source. Its first
SQLite zero-budget case failed with `409 planning_authority_expired`; no cases
passed and 27 remained unrun. The runner stopped immediately and did not retry.
The internal guard location and fact age were not recorded, so no phase is inferred
from earlier instrumented runs. Process duration was 24.831 seconds; XML duration
was 21.304 seconds. Source stayed clean and all later output paths remained absent.

Independent review and root verification checked the 11 evidence hashes in
`google-owner-v6-runtime/acceptance-08-summary.json`. The actual service remains
unqualified and isolated from the integration branch. Next work is source-only
review of validation handoffs and query boundaries; no further observation or
unchanged retry is authorized, and the five-second guard remains unchanged.


## Current Successor And Diagnostic Boundary

The earlier failed-source sections remain historical evidence. The current
[service integration](inlet-owner-service-integration-20261011.md) qualifies the
exact disjoint 6+1+21 API union; later browser cohorts are separate. These passes
do not close R01/R02/R03 or establish timing margin. The updated
[definition and critical path](inlet-reliability-critical-path-20261011.md) separates
the original unknown R03 predicate from later located fact-age failures and
identifies a new actual V6 post-flush authority-rollback coverage gap. No unchanged
diagnostic rerun or retention-policy change follows from this review.
