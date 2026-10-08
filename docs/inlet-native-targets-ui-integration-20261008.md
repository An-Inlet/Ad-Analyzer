# Native Target Customer Display Integration

Reviewed UI `253ba4c` plus session-continuity repair `ddc56e8` are integrated at
`5c593f2` on `codex/inlet-planning-mvp`. Independent review closed the cross-request
same-owner session-rotation finding before integration.

Account Diagnostics now has an explicit Read Native Targets action and customer
navigation. A reusable text-only renderer shows observed names, provider advertiser/
entity/parent IDs, separate native-settings/metadata coverage, read times and expiry.
Unavailable names and partial scope are explicit. No guessed provider links, budget
authority, automatic reread or execution control is introduced. Selection changes,
operation/session changes, malformed/late responses and expiry clear native results.
The original authenticated operation is checked across the trailing session request
and immediately before rendering, not independently rebound between requests.

Assembled cohort: `test_native_targets_browser.py`,
`test_account_diagnostics_browser.py`, `test_planning_customer_boundary.py` and
`test_planning_document_contracts.py`: **67 passed in59.33seconds**, with SQLite and
approved disposable PostgreSQL, actual HTTPS/Chromium and MockHTTP provider readers.
Separate changed shell/navigation check `test_account_diagnostics_ui.py`: **1 passed**.
Whole Ruff, prescribed mypy (**1020 files**), three JavaScript syntax checks and diff
checks passed. Raw assembled log/JUnit:
`/workspace/inlet-evidence/20261008/native-targets-ui-integrated.{log,xml}`.

The old diagnostics browser seed now creates owned read sources without an execution
mandate, preserving its assertions under default planning policy. A native target list
is not a comprehensive advertising plan. Ports, persistence and the recommendation
composer continue separately. No live verification, hosted run, remote push, main
merge or deployment occurred.
