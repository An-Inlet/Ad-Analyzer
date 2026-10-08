# Customer Comparison Period Form — 2026-10-08

Base81e42ae, branchcodex/inlet-comparison-period-form. Implements the frozen
planning-comparison-period-form-v1 interface without API/schema or default-policy
changes. Optional comparison controls create/edit/remove the existing field. Saved
server timestamp strings retain their exact offsets/fractional seconds when the
minute controls are unchanged. Exact UTC microsecond ordering rejects overlap;
invalid dates, missing bounds and future/empty periods reject locally. No provider
calendar rounding or causal inference is introduced.

Primary/goal/account changes keep the existing target invalidation; comparison-only
changes retain the same unexpired primary catalog selection. Saved target replacement
rules, operation recovery, session fencing and manual report timestamps are unchanged.
Cancel/new/workspace/session reset clears remembered period state. The form explains
UTC entry and source-local closed-day qualification; unsupported periods remain gaps.

## Actual Checks

Final focused compatibility cohort: **15 passed, zero skips,109.13seconds**. This is
one Node exact-period parser test and fourteen actual HTTPS browser cases across
SQLite/PostgreSQL, including existing document recovery, all-three-platform targets,
scenarios, sales progress and the new period journey. No API response/source bundle
stub is used. New journey creates a comparison, tests primary target invalidation
versus comparison preservation, preserves actual API-saved microseconds, generates
immutable successors, exports both periods, explicitly removes comparison and rejects
a real response after same-owner session replacement. Zero execution attempts remain.

Initial focused run had1pass/2fail because its assertion compared original request
spelling (`.000Z`) against canonical server response spelling (`Z`). Production
preserved the server strings correctly. The test now first reads the actual saved
inputs, independently verifies both microsecond fractions, and compares subsequent
requests to those exact server strings. Corrected new-only cohort3passed/12deselected
18.51seconds; final15-case cohort above includes it and supersedes its qualification.

Whole Ruff passed; bare mypy passed1098files on this isolated branch; Node syntax
checks for controller/parser/driver and git diff check passed. No source changed
after those static checks. Commands:

```text
pytest -q -o addopts='' tests/test_planning_periods.py tests/test_planning_documents_browser.py --junitxml=/workspace/inlet-evidence/20261008/comparison-period-form/browser-compat.xml
ruff check .
mypy
node --check app/portal/static/planning.mjs
node --check app/portal/static/plan-periods.mjs
node --check tests/javascript/planning_periods_browser.mjs
git diff --check
```

PATH used /workspace/inlet-venv/bin and /workspace/inlet-tools. Approved disposable
PostgreSQL fixture target remainedinlet_oct07_next_integration_ci with the exact
true disposable flag, no reset. Rawfocused/final/browser-compat logs and JUnit are
under/workspace/inlet-evidence/20261008/comparison-period-form/. The completed
browser cohort uses the existing defaultV2 service: it qualifies form/input/history
behavior, not requested-windowV3 composition. Actual raw-import→V3 customer API and
browser output plus reviewed default activation remain W1 requirements. No live,
aggregate, expert-quality or launch claim; no public webpage work.
