# Initial Preview Review Default Policy And Historical Blocker

Base: `93a93f7`. Only the default test in `tests/test_initial_preview_review_api.py`
and this ledger change. The current default test is explicitly `planning_boundary`.
Actual owned imported reporting, calibration, preview, session binding, immutable
preview bytes, and zero approval/attempt assertions remain intact. A CSRF-authorized
review request now asserts the exact planning-policy 409 for both ordinary and
forged extra-field bodies; the route dependency rejects before the old unavailable
runtime 503 or schema 422. Missing CSRF still returns 403.

## Historical Configured Case Remains Unqualified

The untouched default case first reproduced its expected503/actual409 failure.
Exploratory per-function retained-execution marking then allowed the second case
to reach its shared fixture, which failed at
`tests/initial_preview_review_fixture.py:182`: native-options has no planning
mandates because the fixture creates execution consent only.

Adding real planning confirmation is not sufficient to preserve this old bridge:

- `planning_consents.checked_planning_limits` requires a draft mandate and a real
  planning preparation/confirmation. `preview.amount` and `preview.read_preview`
  both invoke this guard for the stored preview mandate.
- `review_bridge.current_preview` invokes that current preview read. Later
  `prepare_preview_review` binds the same intent mandate and calls
  `execution_mandates.checked`, which requires active exact execution consent.
- Activating the mandate invalidates its planning read; using a separate execution
  mandate fails the preview's exact intent/digest binding. The old native fixture
  also uses ConfiguredOptimizationCatalog while current planning budget preparation
  requires a native-budget profile/NativeBudgetOptionV1.

No contradictory state, synthetic confirmation, guard bypass, missing-table
fallback, skip, or xfail was added. The exploratory retained marker was removed;
the historical configured case and shared fixture remain unchanged and failing.
This is an explicit retained pre-0086 execution compatibility blocker, not a reason
to weaken the planning product or restore execution capabilities.

Future proposal, not implemented: isolate a named archived pre-0086 test harness
with its corresponding frozen schema/read/authority implementation and original
actual consent path. Keep it separate from current planning tests and prove its
historical provenance before using it to credit legacy bridge regressions. Do not
combine current planning confirmation and execution consent into one authority or
claim the archived harness qualifies current customer behavior.

## Checks Actually Run

Approved disposable PostgreSQL configuration, isolated fixture schemas:

```text
pytest -q tests/test_initial_preview_review_api.py -k owned_status_default_off --junitxml=/tmp/initial-review-default.xml
pytest -q tests/test_advertising_capabilities.py tests/test_planning_execution_boundary.py --junitxml=/tmp/initial-review-boundary.xml
```

Default case: **2 passed, 0 skips, 7.181 seconds**, SQLite/PostgreSQL.
Boundary suites: **39 passed, 0 skips, 1.131 seconds**. JUnit elapsed times.
Whole `ruff check .`, prescribed `mypy` (**1078 source files**), and
`git diff --check` passed. **Not a whole-module pass.**

Initial inventory also ran unchanged `test_initial_preview_intent.py -k sqlite`:
all 6 selected cases passed, so that module was left alone. Raw logs/JUnit, including
the unsuccessful exploration, are under
`/workspace/inlet-evidence/20261008/initial-review-default/`.
No production or shared-fixture change, Full, live provider, remote, hosted, merge,
or deployment action occurred. The single aggregate remains unrun and this
historical blocker remains open.
