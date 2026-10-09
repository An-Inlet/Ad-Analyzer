# Meta Owned Read Fixture Closure

Tests-only implementation of package A approved in `9e332a1`, based on root `64c5fbc`. Only the eight parametrized cases of `test_actual_owned_vault_and_original_session_after_http` change setup; pure/golden functions and production remain unchanged. Global acquisition/execution fixtures remain untouched.

New scalar `MetaBudgetReadIds` comes from actual login, two complete owned Meta history imports/captures and Shopify goal confirmation using `ready_history`. Actual goal assessment, revision, source sync marker and captured completion are asserted. No execution acquisition anchor is needed; reported jobs/capsules and all advertising authority/effect rows are absent. The explicit before/after zero-authority fixture is selected only on this function, alongside `planning_boundary`; no guard patch.

Original final reader assertions remain:45,000,000 micros, synthetic vault credential header, three GETs positive/one GET on adverse mutation, one transport close, original subject revocation/source generation/goal withdrawal after HTTP. Exact owned101/201 fixture identifiers are translated to the existing mock123/5 server and back; actual request scope/cohort is taken from current owned data.

Two intentional setup differences are documented. Current history already refreshed commerce, so the redundant actual refresh returns `up_to_date`, not the old acquisition fixture's due-time `complete`; clock/freshness windows are unchanged. The old prior optimization left campaign budget4500 minor units; a fresh server defaults zero, so this read-only fixture declares that same synthetic current4500 value directly. It does not execute a write to create it.

## Evidence

Raw logs/XML: `/workspace/inlet-evidence/20261009/meta-budget-read-regression/`.

- Exact SQLite baseline:1 failure at legacy mandate approval guard (`baseline`).
- First replacement positive:1 setup failure because actual refresh was already up to date (`first`).
- Initial combined Meta module/native contracts:26 tests,24 passed/2 positive failures from fresh mock campaign budget0 (`qualified`). This includes18 unchanged pure compatibility cases and6 adverse cases.
- After explicit current campaign4500:8/8 passed,12.885s (`final`).
- Added current provenance assertions; final8/8 passed, no skips (`final-frontier.xml` records terminal time). Same cases overlap, not extra repairs.
- Whole Ruff and bare mypy1129 source files passed (`ruff-final.log`, `mypy-final.log`); `git diff --check` passed.

Commands used `/workspace/inlet-venv/bin/pytest`, then whole `ruff check .` and bare `mypy`. Baseline selector was `tests/test_meta_budget_read.py::test_actual_owned_vault_and_original_session_after_http[sqlite-none]`. Combined run selected `tests/test_meta_budget_read.py tests/test_native_budget_contracts.py`; final runs selected the owned-read function. Both-DB runs used the existing disposable localhost `inlet_oct07_next_integration_ci` with isolated UUID fixture schemas and explicit disposable flag. No aggregate source/database, Full, browser, external provider or advertising writes.

## Separate Initial Planning Package Remains Held

Read-only investigation confirms the original precision mutation cannot simply transfer: `planning_consents.checked_planning_limits` requires `runtime.configuration == runtime.profile.initial`, as does `native_budget.catalog`. Changing only configuration gives an earlier mismatch rather than the original final preview precision guard. No initial-planning test was edited. A separately reviewed coherent precision-profile/preparation fixture is required; environment mismatch still has its explicit check in `initial_planning.native.catalog`. Do not count those ten cases as repaired.
