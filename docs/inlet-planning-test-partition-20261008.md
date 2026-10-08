# Planning MVP Historical Test Partition

This is a bounded partition of existing regression coverage, not a whole-suite
qualification or a production execution switch. Production capabilities remain
unconditionally disabled. The existing non-autouse, function-scoped
`retained_execution_engine` fixture requires the explicit `retained_execution`
marker and cannot be combined with `planning_boundary` tests.

## Additional Reviewed Historical Engine Modules

These seven modules exercise preserved activation, optimization and repeat-engine
internals with MockHTTP. They now explicitly opt into the retained fixture; their
existing authorization, unknown-response, reservation, aggressiveness and
PostgreSQL competing-worker assertions remain intact:

- `test_google_activation.py`
- `test_activation_review.py`
- `test_activation_coordinator.py`
- `test_durable_optimization.py`
- `test_optimization_concurrency.py`
- `test_repeat_optimization.py`
- `test_repeat_history_capacity.py`

Importing a helper from a marked module does not opt the importing module into
historical execution. No collection-time automatic marking or blanket skip exists.

`test_provider_operations_attention.py` instead stays under `planning_boundary`.
Temporary setup-only overrides create authentic historical rows/MockHTTP receipts;
each override ends before attention/readback behavior is checked. The tests retain
held exposure, uncertainty and no-new-write assertions with default policy restored.

## Checks Run

Approved disposable PostgreSQL configuration, seven named historical modules plus
`test_advertising_capabilities.py` and `test_planning_execution_boundary.py`:
**141 passed, 2 expected SQLite row-lock skips, 224.07 seconds**. The same cohort
includes the PostgreSQL concurrency cases; those passed. Separate current-policy
operations attention cohort: **12 passed, 18.01 seconds**, SQLite and PostgreSQL.
Raw logs and JUnit are `/workspace/inlet-evidence/20261008/planning-retained-partition.*`
and `planning-retained-attention.*`. Whole Ruff, prescribed mypy (1001 files) and
diff checks passed. No production source code changed. Results are local offline
regression evidence, not live execution qualification.

## Remaining Classification Work

Independent read-only review identified these additional areas. This is a bounded
inventory, not an exhaustive prediction of every aggregate failure:

- Current history/export/restore modules need setup-only historical seeding, then
  restored default policy for the behavior under test: `test_customer_activity`,
  `test_export_execution_domains`, `test_export_optimization`,
  `test_export_owned_domains`, `test_google_completion_restore`,
  `test_owned_outcomes`. `test_provider_settlement` mixes historical behavior with
  a default-disabled runtime assertion; do not enable its whole module blindly.
- Execution UI/browser suites expect retired buttons. Adapt current-product tests
  to planning/history/no-write behavior; preserve any useful old UI test through an
  explicitly test-only archived harness, never by restoring production controls.
  Includes customer execution/social execution UI, configured Google/Meta/TikTok
  execution browsers, V2 execution browser and initial automatic browser.
- Customer execution/optimization/session-automation API suites mix authorization,
  history and old success paths. Keep current denial and access tests unpatched;
  isolate historical engine semantics deliberately.
- Initial preview/rule/restore fixtures that create only execution consent and an
  active mandate conflict with 0086 planning-only confirmation. Update current
  preview setup to create real planning confirmation. A retained-engine marker
  cannot replace that prerequisite, and the planning checker must not gain a
  legacy execution-consent fallback. Identified modules include initial preview
  review, initial rule start/prior lineage/acceptance, initial native restore,
  V2 execution browser and its helper fixture.

The final aggregate remains pending this classification and the coherent planning
integration. No redundant Full run is requested by this document.
