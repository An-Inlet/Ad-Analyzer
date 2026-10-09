# Retained Session Authorizer Regression Qualification

Base: `74ffc9d`. Five individually classified direct retained-engine functions in
`tests/test_execution_session_authorizer.py` receive the existing retained marker
and fixture. Their entire original AST, including shared helpers, remains unchanged
after stripping only the ten added decorators. Independent scope review by
`rule_review` classified all five as retained-engine behavior, with no current API
read assertions hidden by this classification.

The twenty original failing parameter identities cover revocation during creation
qualification and optimization preflight, expiry/revocation during final provider
contexts, and creation/activation session checks. Original no-emission assertions
remain intact. No production code or default planning consent policy changes.

Checks actually run on SQLite and the marked disposable local PostgreSQL database:
- This full module plus both current planning execution/provider transport boundary
  modules: **106 passed, zero skips/errors/failures, 33.710 seconds** (JUnit).
- Whole-repository Ruff: passed.
- Bare mypy: passed, 1161 source files.
- `git diff --check`: passed.

Evidence: `/workspace/inlet-evidence/20261009/retained-session20/` contains
`selection.json` (whole-module original AST proof), `qualified.log`,
`qualified.xml`, `ruff.log`, and `mypy.log`. The 86 boundary cases overlap prior
qualifications; exact original XML identity matching determines the twenty new
closures. This is offline retained behavior evidence, not current execution
permission or live provider verification. No aggregate was rerun.
