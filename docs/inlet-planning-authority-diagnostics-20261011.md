# Bounded planning authority diagnostics

Implementation follows reviewed450e27c on isolated rootce25c17 branch. Fixed JSON
records contain only allowlisted route, phase, cause, status and schema literals.
No principal/fact identifiers, paths, requests, SQL, payloads, exceptions or extra
clock samples. Original invalid-age short circuit skips session/wallclock as
before. Lock means any lock admission, including nested final-source locks.

Dedicated planning APIRoute scopes ContextVar around the original handler once;
FastAPI propagates context into sync endpoints/dependencies and resets on every
exit. Fixed other_conflict logs recover route/status only, not underlying reason;
future nonauthority409 may require separately reviewed allowlisted classification.
No retrospective R01/R02/R03 cause or reliability claim. Existing sink may drop
records; no new sink configuration or persistence guarantee is introduced.

Logging/serialization/filter/handler failures are suppressed only inside telemetry,
without fallback logging; original refusals remain. Two existing final spies accept
and forward diagnostic_phase. Changed actual V6 deliberate-delay test requires the
new exact post_flush/fact_age_outside_window event with unchanged full rollback.
Its earlier two passing cases remain distinct from any new-source qualification.

Initial Ruff01 requested suppress(Exception) and a combined conditional; both style
findings and fixes retained in evidence. Ruff02/configured no-path mypy02 passed
before final narrow test refinements. No pytest bodies have run; source/selection
review and parent authorization remain required. Evidence directory:
`/workspace/inlet-evidence/20261011/planning-authority-diagnostics/`.

Final source/test preflight CLOSED; Ruff03/configured mypy03 clean (1491 files).
Collect01 selected exactly32 nodes:28new pure/ASGI,2changedV6delay,2existing
sales-progress final_timeout;6other sales variants deselected. No bodies executed.

## Diagnostics01 stopped qualification (not all32 passed)

The preceding held statements describe preparation. Parent authorized manifest
`8b726b3008a13aef0dffc8147eb71df5ed8f97603a3f10034a9e9769547b2688`
and runner `d002dff04ff8b03426fd40860ed7b1cebb7332606ff533f6e7e1008590ff69d3`.
One serial -x process exited1 after29passes/1failure/2unrun, no skips. The28 new
pure/ASGI cases and changed SQLite V6delay passed. Changed PostgreSQL V6delay
failed before its flush marker/six-second delay; both sales final_timeout nodes
were unrun. No retry, guard alteration or later test body followed.

Original process40.182590s, XMLsuite37.801s. SQLite V6delay testcase15.322s;
PostgreSQL failed testcase20.463s. These are whole case/process durations, not
fact ages or phase attribution. The actual new safe event was:

```json
{"cause":"fact_age_outside_window","event":"planning_authority_expired","phase":"pre_cas","route":"generate","schema_version":1,"session_predicate":"not_evaluated","status":409}
```

This identifies a new real generate/pre-CAS fact-age predicate refusal. The exact
age, whether outside by high/negative/nonfinite value, and session remaining time
were not recorded. The session expiry predicate was short-circuited; it was not
proved healthy or expired. The test's deliberately delayed post-flush seam was
not reached, so it correctly failed rather than accepting an earlier refusal.
This does not retroactively classify R01/R02/R03 or qualify the full32 cohort.
The earlier original-source two-DB post-flush passes remain separate evidence.

All1786 tested source hashes matched. All8 exact WIP source files, original
log/XML/result, bounded event summary and the passed SQLite assertion-backed
artifact are durable. Failure summary SHA:
`7c99454191b0c16be1373f4a2b226d355041b9ab41f8622f96e7f2b882cc7045`.
Whole Ruff03/configured mypy03 passed before this run; no tested code changed
subsequently, so no repeats. Only this final ledger records the failed outcome.
The diagnostic-only local freeze is not a fully qualified integration candidate.
