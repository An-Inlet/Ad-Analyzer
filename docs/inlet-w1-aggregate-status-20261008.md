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
skips in77.80s; whole Ruff, bare mypy (1,117 files) and diff checks passed. Production
code and every original API assertion are unchanged. The frozen W1 aggregate still
contains its original fixture and its recorded failures; no rerun or retrospective
pass claim is made. See `inlet-account-diagnostics-fixture-20261008.md`.
