# Requested-Window Default Qualification

Base `a035d2f`; branch `codex/inlet-window-default`. The explicit V3 service and
actual customer browser predecessors were independently reviewed before this step.
Scope remains the frozen W1 milestone.

New customer planning services now use the exact canonical V3 policy/generator
pair. The old composer, policy allowlist, retained witness formulas, persisted
artifacts and zero-write boundary are unchanged. The V3 API/browser test helper
now asserts the real default and returns the actual service without replacing its
policy. Generic customer API and browser journeys therefore exercise that default.

Three V2-specific reporting/import tests explicitly select the genuine canonical
legacy pipeline; there is no global V2 override or policy alias. The existing
revocation-during-read test now checks both the default requested-window reader
and the explicit legacy reader on both databases, preserving its original rollback
assertions. Unknown/mixed policies remain rejected.

## Terminal Focused Checks

All commands used Python 3.12.14, the existing isolated SQLite/PostgreSQL fixtures,
and the explicit disposable PostgreSQL acknowledgement. Evidence is under
`/workspace/inlet-evidence/20261008/window-default/`.

- `python -m pytest -ra tests/test_window_service_api.py
  tests/test_window_evidence_contract.py`: **85 passed, 1 skipped, 232.18s**;
  `api.log/xml`. The skip is the PostgreSQL row-lock test's SQLite parameter.
- `python -m pytest -ra tests/test_planning_documents_browser.py
  tests/test_planning_periods.py`: **17 passed, zero skips, 189.44s**;
  `browser.log/xml`. This includes every existing authenticated planning browser
  journey plus exact requested-window generation/correction under the real default.
- `python -m pytest -ra tests/test_planning_document_repository.py
  tests/test_planning_documents_api.py tests/test_planning_service_error_boundaries.py
  tests/test_planning_qualified_reporting.py tests/test_meta_import_planning_presence.py
  tests/test_planning_retained_sources.py`: **115 passed, 3 skipped, 16 warnings,
  365.27s**; `compatibility.log/xml`. Skips are the original PostgreSQL-only races
  on SQLite. Warnings are deliberate invalid-model copies in rejection tests.
- Whole Ruff, bare mypy (**1,112 files**) and diff checks passed. One initial
  import-format finding was corrected before any of the above test runs.

The environment reported `starting` during this work and immediately returned
ready. The same container hostname `913600e4263d`, worktree and WIP survived.
All three pytest logs and JUnit files contain complete terminal outcomes with no
failures/errors. Old tool session handles were unavailable after reconnect, so no
wrapper exit-code claim is inferred from those handles. No pytest run was repeated.
Ruff/mypy were verified again after reconnect; `mypy.log` retains that result.

This is focused offline qualification. It is not the W1 aggregate, live advertising
verification, deployment, expert acceptance or a purchasable-product claim.
