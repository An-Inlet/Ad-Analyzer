# Selected Retained Source Dispatch — 2026-10-11

## Scope

Base `4cd8fb1`. The generic retained-source capture and recheck boundary now delegates
only the exact canonical v4 policy/generator pair to the selected witness validators.
Local imports preserve the existing dependency direction. Legacy v1–v3 source checks
remain in place, and unknown/mixed pairs cannot enter the selected path.

Authorization failures (401/402/403) retain their status. Selected capture integrity
conflicts (409) and expected invalid proof values use the established
`RetainedSourcesChanged` boundary. The existing recheck boundary continues to apply.

The new tests acquire actual offline raw-range and selected-event evidence, compose
and persist a v4 document with all dependencies, and exercise real customer decision
and manual-assertion persistence. Changing retained daily metrics blocks a subsequent
manual assertion without adding an event. These are customer reports, not provider
operations. Runtime/registry activation and public generation belong to the separate
consumer package; this package does not enable them.

## Verification

Evidence: `/workspace/inlet-evidence/20261011/selected-retained-dispatch/`.
Initial failed runs are retained: test fixture missing its `refs` binding, then missing
the required manual assertion statement. Both were corrected without application
relaxation. The repaired SQLite gate passed both new cases.

Final checks:

- `pytest -q tests/test_selected_retained_dispatch.py tests/test_selected_plan_witnesses.py tests/test_planning_retained_sources.py`: **50 passed, zero skips**, SQLite and PostgreSQL, 113.392 seconds (`final.xml`).
- After adding explicit ValueError coverage and binding the test exception callback's loop value, `pytest -q tests/test_selected_retained_dispatch.py -k error_boundaries`: **2 passed, zero skips**, both databases, 15.181 seconds (`boundaries-final.xml`).
- Whole-repository `ruff check .`: passed. Initial Ruff loop-binding failure was repaired before freeze; final static logs are retained.
- Configured `mypy --cache-dir /tmp/inlet-range-publication-mypy`: passed, 1,359 source files.
- `git diff --check`: passed.

No broad baseline, live provider calls, hosted checks, push, merge or deployment.
The next consumer lane must verify public input creation and v4 generation/save using
this dispatch; that independent integration is not claimed by these repository-level
manual-event checks.
