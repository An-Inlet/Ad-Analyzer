# Current Retained Reporting Proof: Fourteen Regressions

Branch `codex/inlet-reported-proof14`, based on reviewed proposal `58a042c` and
current source `3fb6474`. This package changes only the setup of
`test_fixed_current_report_requires_retained_owned_terminal_proof`.

The reviewed scalar original fixture produces one authentic historical MockHTTP
effect in current tables. Fresh current sessions then create the request, execute
actual current GET acquisitions/checkpoints and capture observations. The unchanged
seven mutations exercise deleted capsule/job, exact expiry, superseded job, source
generation, revoked original session and another campaign. Current reader/auth
assertions remain identical. The outer strict financial/effect graph equality is
unchanged. No baseline, new planning/execution consent, guard override or TTL change.

The separate positive preview function's AST is unchanged and remains pending the
reviewed current planning-consent baseline work; this is not whole-module recovery.
The shared file-backed SQLite engine wrapper is required by the real subprocess
producer. PostgreSQL uses the existing disposable database with isolated UUID
schemas. No aggregate database/source or shared helper was edited.

## Actual Checks

Evidence directory: `/workspace/inlet-evidence/20261009/reported-proof14/`.

- `pytest --collect-only -q tests/test_reported_feedback_real_preview.py`: 16 nodes.
- Original SQLite capsule-deletion node: one failure, 3.747s, at retired mandate
  approval before current reading (`baseline.log/xml`).
- Initial adapted run: seven PostgreSQL passes and seven SQLite setup errors,
  102.468s (`qualified.log/xml`). SQLite accidentally imported the in-memory engine;
  corrected to the existing reviewed file-backed wrapper, no assertion changes.
- Final exact fourteen both-database nodes: all passed, no skips,
  121.685s (`final.log/xml`).
- `pytest -q tests/test_reported_feedback_contracts.py
  tests/test_reported_original_expectation.py`: seven passed, 1.985s (`compat.log/xml`).
- Whole `ruff check .`: passed (`ruff-final.log`).
- Bare `mypy`: passed, 1162 source files (`mypy-final.log`).
- `git diff --check`: passed.
- AST comparison proves all statements after the replaced setup, original decorators
  and the separate positive function unchanged (`assertion-preservation.json`).
- Exact fourteen original failed nodes are recorded in `matched-failure-nodes.json`;
  no overlapping compatibility count is added to original-node recovery.

Final command (preceded by explicit disposable PostgreSQL environment settings):

```text
/workspace/inlet-venv/bin/pytest -q tests/test_reported_feedback_real_preview.py
  -k retained_owned_terminal_proof
  --basetemp=/workspace/inlet-evidence/20261009/reported-proof14/final-artifacts
  --junitxml=/workspace/inlet-evidence/20261009/reported-proof14/final.xml
```

Raw baseline/setup-failure logs, terminal XML and producer IDs/logs are retained.
This qualification does not repair the current feedback planning-consent mismatch,
prove the remaining 28 preview/revision failures, or claim aggregate completion.
