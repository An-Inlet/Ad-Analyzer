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
