# Selected Plan Current Witnesses

Reserved v4 now has standalone capture/recheck ports for exact saved selected
account proof plus the existing commerce witness. Qualified aggregate and selected
state are recomputed around commerce reads; changed privacy, source, selection,
mapping, graph or exact dependency set fails current use. Viewer-compatible local
guards are retained; callers still own original identity freshness and locks.
The old commerce witness calculation was extracted without changing its fields or
digest. Typed local witnesses now recognize local_reporting_v3; policy capability,
service dispatch and generation remain unchanged and v4 remains disabled.

`pytest -q tests/test_selected_plan_witnesses.py tests/test_planning_retained_sources.py`
with explicit disposable PostgreSQL opt-in passed 46 cases, zero skips. Two new
cases use real SQL goals, imports and commerce with an explicitly assembled
no-selection v4 document to test witness capture/recheck and historical separation;
they do not claim actual v4 composition. The other 44 exercise existing retained
witness behavior, including source, privacy, expiry, session and dependency changes.
Whole Ruff, configured mypy (1339 files) and diff check passed.
Evidence: `/workspace/inlet-evidence/20261011/selected-plan-witnesses/`.

Historical port ec1ab1f, pure bundle 62852ea and current proof ce6b01a have completed
independent source review with no P1/P2 findings. No reviewer test reruns claimed.
Next: selected collector, raw traffic presence, paired composer, current service
dispatch, and populated historical/archive/erasure qualification before activation.
