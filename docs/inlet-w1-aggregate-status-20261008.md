# W1 Aggregate In Progress

Frozen implementation `6a3b0f16f9ebc9c0a80dbab60140c0b8f9324f46` is running in
`/workspace/inlet-w1-validation-final`. Its source is not changed by this successor
status record or by subsequent focused repairs.

The single actual full pytest invocation began at **2026-10-08 23:48:43 UTC**,
with 6,581 collected top-level cases and no exclusions. The three historical wrapper
cases additionally execute their explicitly recorded 249 pinned cases. Those counts
are hierarchical and are not summed as independent acceptance evidence.

Evidence root: `/workspace/inlet-evidence/20261008/w1-aggregate/`.
`aggregate.started.json` records the command, exact source, prerequisites and local
CI differences; `aggregate.log` captures ongoing output. On terminal completion,
`aggregate.xml` and `aggregate.result.json` record the result and process exit.
Runner PID 137720, pytest PID 137734, execution-tool session 28006. Never delete
the exclusive start marker or silently restart the run after a reconnect.

At the 23:51 UTC disconnect callback, the same container `913600e4263d` was usable,
the frozen checkout remained clean, both processes were still running, and progress
had reached roughly 4%. No corresponding shell/test interruption was observed.
There was no reset, replacement environment, or aggregate restart.

## Observed Failures And Separate Successor Work

The aggregate is already reporting failures; it is not an all-pass result. Its
initial account-diagnostic API group failed. One exact SQLite case was separately
reproduced on `codex/inlet-diagnostic-read-fixture`: the old fixture reaches guarded
spending-consent approval and raises `AdvertisingWritesDisabled` before the read-only
API or native reads run. A bounded repair reuses the existing source-only catalog
fixture, preserving every current authorization and native-read assertion and
adding proof that no mandate/execution rows are required. That repair will not
change the frozen run or retroactively turn its failures into passes.

The earlier pinned PostgreSQL unknown-response worker failure also remains in the
aggregate unchanged. Its root cause is still unproven. Complete failure counts and
classification await the terminal result; progress characters are not a substitute
for the final traceback/JUnit evidence.

Independent quality-evidence reconciliation is docs-only on another branch. All
Q01–Q16 and six human expert gates remain partial/unfulfilled. Hosted checks, live
provider calls, advertising writes, deployment and commercial release remain held.

The first bounded successor repair is independently reviewed and integrated from
`0ecd0d7`. All 66 SQLite/PostgreSQL account-diagnostic API cases passed with no
skips in 77.80s; whole Ruff, bare mypy (1,117 files) and diff checks passed. Production
code and every original API assertion are unchanged. The frozen W1 aggregate still
contains its original fixture and its recorded failures; no rerun or retrospective
pass claim is made. See `inlet-account-diagnostics-fixture-20261008.md`.

## Completed Explicit CI Gates

All six commands ran once on frozen `6a3b0f1`, with a clean checkout before each
and after completion, using only separate database
`inlet_w1_20261008_gates_09a55cf2_ci`. PostgreSQL: 3 passed (3.60s);
ReadOnly: 75 passed, 38 deselected (6.60s); Security: 99 passed, 28 deselected
(5.42s); Privacy: 14 passed, 58 deselected (2.09s); Focused: 43 passed,
29 deselected (42.05s); exact CI orchestration/diagnostics pair: 43 passed
(18.00s), including native PowerShell. All exit codes were zero, with no skips or
retries. Counts overlap and must not be added as unique acceptance coverage.
Evidence: `w1-aggregate/gates/results.json`, individual logs/XML/status files and
`checkout-final.json` under the evidence root's parent. This does not supersede
the still-running aggregate's observed failures.

At October 9 00:00 UTC the original aggregate processes remained alive after
roughly twelve minutes; the frozen checkout remained clean. Progress had reached
approximately 12%. No restart or source change occurred.

## Reviewed Next Acceptance Proposal

Docs-only `55bc389` is reviewed and integrated on this successor branch. The next
proposal is assembled Q16 privacy and separate later-day/corrected-sales acceptance,
using the original frozen common basis and actual workflow. Before implementation
or browser delegation, a bounded feasibility investigation must establish coherent
November 3/4 synthetic clocks across identity, paid/native freshness, goal binding
and database wall time. Existing guards, TTLs and frozen dates cannot be changed to
make the fixture pass. See `design/planning-next-quality-acceptance-v1.md`.
All quality cases and expert gates remain partial/unfulfilled.


## Successor Investigations

Reviewed docs-only Google investigation `8dee44e` records three existing limits:
raw missing fields are normalized to zero; selected-action totals cannot be equated
with legacy aggregate totals; current seven-day completions cannot prove full
August/September windows. Official provider documentation also says action-segmented
reports suppress zero-conversion rows. Missing rows therefore remain unavailable,
not explicit observed zero. See `design/planning-google-selected-event-proposal-v1.md`.
This review accepts the evidence and proposal for discussion, not its new collection,
selection, storage or consumer architecture. No implementation or tests accompanied
it; no Q01/Q02 completion claim follows.

Static test inventory additionally traced legacy mandate-bound diagnostic reads,
Meta budget acquisition and retained archive fixtures into guarded approval setup.
These are candidates for terminal-failure classification, not newly reproduced
failures. Mandate-binding negative tests must remain intact; archive cases whose
bodies execute historical optimizations require historical production/current-read
separation. Existing bounded historical fixtures are not failures merely because
they import old setup modules. No blanket fixture substitution is approved.


## Reviewed Dated Q16 Clock Probe

`41aa960` is independently reviewed and integrated only on this successor branch.
The explicit probe passed on SQLite/PostgreSQL (2 cases, 11.40s), with whole Ruff,
bare mypy (1,118 files) and diff checks passing. It uses actual login with narrowly
substituted issuance time and coherent synthetic verified-identity inputs; normal
session TTL, real authority/monotonic/database clocks and production code remain
unchanged. An expired October session is denied at the November stage; fresh
ordinary-TTL November logins permit actual default planning generation and saved-
version progress 0→25,000,000 micros after actual commerce import, preserving the
same plan digest/confirmed goal. The expired November 3 session is denied before
November 4 re-login. No provider execution attempts were created.

This is a dated UTC feasibility experiment, intentionally outside default pytest
collection, not the exact New York Q16 case or browser acceptance. It must not become
a date-dependent default regression. The reviewed fixture direction is documented
in `design/q16-fixture-feasibility-20261009.md`; exact source metadata, image,
reporting periods, refund, privacy and browser assertions remain to be implemented.
No production authentication clock seam is needed. Erased-ID refresh must never
restore deleted data; an intentional new fully validated submission is distinct and
is not silently prohibited by a new tombstone policy.


### Successor Integration Check Correction

Root's merged-tree check caught Ruff B009 in the final `getattr` assertion of
`41aa960`. The component's final mypy repair had not been followed by a successful
Ruff check, so its earlier all-checks statement did not describe that exact source.
Root changed only the module-restoration identity assertion to
`vars(customer_api)["time"] is time`. The explicit dated probe was rerun because
of this edit: 2 passed, no skips, in 9.99s. Whole Ruff and bare mypy (1,118 files)
now pass on the combined successor; diff check passes. This repeats the same two
backend cases and adds no independent Q16 acceptance. Both the initial lint failure
and final results are retained in
`/workspace/inlet-evidence/20261009/successor-integration/`.


## Reviewed Successor Packages At October 9 00:34 UTC

Native fixture repair `a0bc585` is independently CLOSED and integrated. Genuine
pinned historical mandate/source production now precedes unchanged current native
read/authority assertions. No current write guard is bypassed. Existing module:
78 passed, zero skips, 499.84s across SQLite/PostgreSQL; exact shared-producer
compatibility: 4 passed, zero skips, 82.01s. The single repaired SQLite pass overlaps
that module. Whole Ruff, bare mypy and diff checks passed. Original failure and
inherited lint failure remain recorded in `inlet-native-diagnostic-fixture-20261009.md`.

Exact dated Q16 fixture `d75855f` is independently CLOSED for its bounded claims
and integrated. Four explicit SQLite/PostgreSQL cases passed, zero skips, 15.902s.
Actual New York metadata, fixed September 15 baseline, October goal HTTP confirmation,
November DST closed-day prefixes and same-order signed refund prove 0→25→20 sales
with unchanged V1/digest/goal and no native reads during progress. A separate erasure
case proves old-ID/artifact/receipt denials and six empty lifecycle sections. Actual
owned image upload/download/SHA is proved; plan reference is text only, not vision
or typed asset binding. This is not full Q16, browser or streamed-archive acceptance.
See `inlet-q16-exact-dated-fixture-20261009.md` and the frozen shared fixture contract.

Combined successor code head `c597300` passes whole Ruff and bare mypy (1,121 files)
and diff checks. The two code packages modify disjoint test seams; their completed
focused tests were not needlessly repeated. Full W1 remains the original `6a3b0f1`
process, around 44% after 45 minutes, with failures visible and no terminal result.

After the shared fixture freeze, two independent successor lanes started from
`c597300`: explicit dated actual browser progress/correction/erasure, and real
workspace archive creation/snapshot/delivery privacy. They may add their own
controllers/tests but cannot silently change the shared fixture interface. Neither
may touch W1 source or its aggregate database. Manual-report/expert/full-quality
and live/commercial gates remain separately outstanding.


## Archive, Browser And Natural Chronology Successors

Reviewed archive `6df867c` passed two database cases (25.246s). Its actual request,
worker, database snapshot, media serialization and streaming route produce a complete
archive; semantic erasure after the unchanged builder returns causes the unchanged
final delivery guard to reject409, close the temporary file and mark interrupted
without a manifest digest. A fresh complete archive omits the erased graph. Actual
billing records and a populated foreign workspace remain untouched. `7259317`
adds one genuine decision event before archival and preserves the correct422 for
future-dated manual reporting (two cases, 25.709s). These are overlapping successor
runs; counts must not be added. No execution obligation was fabricated.

Reviewed browser `d43d28f` passes four actual HTTPS/Chromium cases across both
databases (25.943s), with Ruff, bare mypy, Node syntax and diff checks passing.
The UI shows0→25→20 with immutable document/goal and handles erased IDs. Root review
caught a fixed-delay race-proof gap in the earlier version; the corrected driver
awaits the actual held response body on a clone and a following task before checking
that stale bytes cannot repopulate the DOM. It returns the identical original
Response; the current controller rejects the stale epoch before parsing that body.
This proves the explicit-refresh race, not universal revocation of in-flight bytes.
Durable actual artifacts/responses are in `q16-browser/synchronized-artifacts/`.

The future-report422 is a correct real-clock validator result, not a product defect.
Reviewed additive chronology `9b43f9e` instead generates and reports in actual
October, then advances only the supported measurement/fixture clocks into November.
The shared helper adds optional `generation_stage="october"` and `initial_day`;
its default and scalar IDs stay unchanged. Eight compatibility cases passed once
(61.276s: old API4, old November archive2, new October2). Both genuine events remain
unchanged through0→25→20, serialize in the real archive, and disappear on erasure.
Root also inspected both unique archived reports: `customer_report_only`, no spending
authority, writes disabled. A first artifact-review count included pytest's current
symlink duplicate; resolved unique paths confirmed the two actual database cases.

Combined successor code head is `a368e22` before this documentation commit. The new
October browser lane starts only after that shared interface qualification; actual
UI reporting in that chronology remains pending. All Q01–Q16 and expert gates remain
partial; no full quality, live, deployment or commercial claim is made.

The SINGLE frozen aggregate is still original `6a3b0f1`, roughly65% after66 minutes.
Its checkout is clean and its separate database unchanged by successor work. No
terminal aggregate counts exist yet, and no aggregate was restarted.

## October 9: Actual UI Chronology And Continued Frozen Run

Reviewed `ef9f9af`, integrated `4982685`, extends the actual HTTPS/Chromium
Q16 journey to genuine October UI decisions and manual reports before November
measurement. The final invocation passed eight cases across SQLite/PostgreSQL
(202.012s, zero skips): four existing November cases plus four October cases.
It naturally waits for a representable nonfuture report minute; it does not backdate
generation or bypass the date validator. Both event payloads remain unchanged and
visibly unverified through sales0→25→20, then clear on semantic erasure. An initial
driver failure omitted the explicit history-read action and remains documented.
Root reviewed the exact changes; combined `4982685` whole Ruff, bare mypy1123,
Node syntax and diff checks passed. Raw results: `q16-browser-chronology/final.log`
and `final.xml` under `/workspace/inlet-evidence/20261009/`.

Reviewed documentation `4f5a367` reconciles E25–E29 and exact remaining Q16 gaps.
A dated matched-path401 must not be credited as proof of global authentication
clock advancement or real session expiry: the goal-progress reader uses injected
`as_of`, while ordinary authentication retains actual October time. The separate
same-owner held-response revocation and changed-goal browser cases are currently
under qualification, not passed evidence. All Q01–Q16 remain partial and all six
human expert gates remain unfulfilled.

The environment startup callback preserved the same container and original run.
At approximately92 minutes the SINGLE aggregate still has its original launcher
and pytest PIDs137720/137734 and clean frozen `6a3b0f1` checkout. It has reached the
historical-wrapper region after84% of top-level cases. It is continuing locally
past the hosted CI90-minute limit, an explicit CI-parity difference, with no hosted
run or spend. Failures are visible; no terminal counts, retry, or aggregate pass is
claimed. Successor fixes never rewrite this frozen result.
