# API-Created Selected Plan History And Erasure — 2026-10-11

Base: frozen consumer `963991ba37451951c280c3c071dd2c7592513a23`.
This package adds only a focused test module and this ledger; no production changes.

The fixture uses `configured/create/generation` from the frozen actual customer API
suite: real mocked raw-range HTTP acquisition and range publication API, selected
confirmation/capture APIs, saved-input HTTP, and selected v4 generation into SQL.
Only the existing private test policy enables v4; no default production activation.
No selected plan, proof or dependency rows are fabricated by this package.

## Verified Behaviors

- Both selected and raw-traffic pins belong to the customer's exact chosen capture.
- A scoped ordinary daily metric refresh makes the API report `source_changed`,
  while historical repository reads and export serialization retain the identical
  original document, including the selected and raw-traffic proof.
- Actual lifecycle archive construction includes that exact document and original
  selected capture/range receipt. Archive checks issue no provider HTTP calls.
- Semantic privacy invalidation removes owned plan/input/version/dependency/request,
  selection/capture/fact, range receipt and traffic-presence rows. The plan API then
  returns404, historical serialization rejects the old document, and the already
  prepared export authority returns409.
- Removing the exact chosen capture, exact range receipt, or traffic presence facts
  leaves the saved version row present but historical repository/API reads reject409
  and export serialization rejects the incomplete graph. No provider recovery is
  attempted and no synthetic replacement evidence is used.

## Evidence

Directory: `/workspace/inlet-evidence/20261011/selected-runtime-lifecycle/`.
Initial SQLite cohort: three negative cases passed; the positive test failed on an
incorrect test-only `DailyMetric.account_id` lookup. Ownership is through `Campaign`;
the repaired test uses an account-scoped campaign subquery. Failed log/XML retained.
The corrected positive SQLite case passed (`sqlite-repair.xml`). Whole Ruff and
configured mypy passed (1,361 source files); diff check passed.

Final PostgreSQL cohort: `pytest -q tests/test_selected_runtime_lifecycle.py -k postgres`
passed all **4 cases, zero skips**, 51.415 seconds (`postgres.xml`). SQLite coverage
comprises three negative passes in `sqlite.xml` and the corrected positive pass in
`sqlite-repair.xml` (12.391 seconds). Thus every new scenario passed on both databases.
The scope remained test-only; no application fallback or weakened assertion was needed.

No broad baseline,
live calls, hosted checks, remote pushes, merge or deployment were performed.
