# Current Reported Acquisition And Retry Regression

Branch `codex/inlet-reported-acquisition`, approved proposal `936c2fe`, reviewed foundation `d667326`. Implements only the acquisition16+retry12 package. No production changes, capability exemptions, global seed changes, new recommendation policy or Full run.

## Fixture And Current Assertions

New `tests/reported_read_acquisition_fixture.py` accepts the current typed `PreparedReportedRead`, verifies the actual pending job/current source and original session/actor/account/campaign/attempt binding, and constructs current `MetaSyncService`. The reporting job is created by the reviewed current request service; no checkpoint, completion, capsule or comparison is prepopulated. The original effect still comes only from the separate pinned genuine producer and only bounded scalar IDs cross. Its measured original POST count remains1, and the inherited finally assertion requires every protected provider/financial row to remain unchanged.

The copied read fixture uses the same actual Vault/configuration, existing explicit mock90day grant and actual job next_due+1second clock advancement as before. Original60day session/request validity is asserted, not extended. Existing61second repeat advance, actual retry deadlines, actual second owner's20day session and database-aware effective_now remain unchanged. Native HTTP is strictly GET to the actual owned account's exact API-version campaigns/adsets/insights paths, with the existing12second transport timeout. All reports pass through real current parsing/staging/terminal publication. The control key set is closed; missing/zero/revision, before/after conversion values and terminal-insight hook retain existing meanings. Unsupported paths never receive permissive responses.

Only seven current functions switch to the new adapter and explicit `planning_boundary`. Original shared `acquisition_fixture` and `complete` have identical ASTs; other callers remain on their prior fixture pending separate packages. All original current status, timing, source/owner, fixed-frontier, missing-day, staged-data cleanup, previous publication and request-count assertions remain. Replacing Any with typed results exposed nullable timestamp assumptions: explicit non-null checks now precede the already-existing UTC comparisons after actual rolling completion/fixed start; no earlier denial or alternate predicate is credited.

The preserved zero/missing capsule assertion is the existing reported data-contract behavior, not a new selected-event presence qualification. New composition/archive/PlanningConsent/browser behavior is not claimed. In particular, current unknown readback receipt append needs its own exact financial delta seam; the invariant is not weakened here.

## Evidence

`/workspace/inlet-evidence/20261009/reported-acquisition/` retains raw logs/XML, original failed identities, extracted PIN/producer artifacts and isolated file-backed SQLite fixtures. All PostgreSQL cases use individual current UUID schemas in the existing disposable nonaggregate local test database. Counts below overlap; do not add them as distinct acceptance.

Commands run from this branch with `/workspace/inlet-venv/bin/`. BothDB invocations set `AD_ANALYZER_TEST_POSTGRES_URL=postgresql+psycopg://postgres@127.0.0.1:55432/inlet_oct07_next_integration_ci` and `AD_ANALYZER_CI_DISPOSABLE_POSTGRES=true`.

- Original exact SQLite baseline: `pytest -q 'tests/test_reported_feedback_acquisition.py::test_fixed_windows_preserve_rolling_coverage_and_repeat_spacing[sqlite]' 'tests/test_reported_feedback_retry.py::test_transient_fixed_page_resumes_only_after_deadline_same_run[sqlite-timeout]' --junitxml=…/baseline.xml` —2failed7.332s at the retired guard (`baseline.log/xml`).
- First repaired same pair —2passed14.726s (`first.log/xml`).
- `pytest --collect-only -q tests/test_reported_feedback_acquisition.py tests/test_reported_feedback_retry.py` —exact28 (16+12), `collection.log`.
- `pytest -q tests/test_reported_feedback_acquisition.py tests/test_reported_feedback_retry.py tests/test_reported_feedback_service.py tests/test_reported_feedback_customer_api.py tests/test_reported_feedback_contracts.py tests/test_advertising_capabilities.py --basetemp=…/qualified-tmp --junitxml=…/qualified.xml` —55passed, zero skips/failures/errors,331.282s. Includes the28 new repair identities plus overlapping reviewed foundation16 and11 current/pure boundary cases.
- Following the type-required non-null assertions and closed control-key check, affected `test_fixed_windows_preserve_rolling_coverage_and_repeat_spacing`, `test_transient_fixed_page_resumes_only_after_deadline_same_run`, `test_actual_zero_and_missing_day_remain_distinct`, and `test_expiry_during_terminal_http_retains_previous_publication` bothDB —10passed, zero skips/failures/errors,70.523s (`final.log/xml`, `final-tmp`).
- Whole `ruff check .`, bare `mypy` (1139source files), `git diff --check`: pass. Initial mypy's five nullable-field findings are retained in `mypy-first.log`; repaired by the explicit assertions above, not ignores or production changes.
- Exact original helper AST comparison: pass; `unchanged-helper-ast.json`. `matched-failure-nodes.json` maps all28 original failed IDs/ordinals/trace hashes to the successful current qualification.

No live/external provider requests, network credentials, execution under current capabilities, aggregate rerun, or production qualification.
