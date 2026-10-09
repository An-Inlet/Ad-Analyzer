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
