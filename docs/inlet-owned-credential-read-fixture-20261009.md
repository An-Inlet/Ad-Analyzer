# Current Owned Credential Fixture Closure

Base d665feb; local fixture design in `design/owned-credential-read-fixture-v1.md`.
Only one 32-case current-reader function changes setup. Source-only account/source
rows, actual sealed synthetic grants and ordinary owner login replace execution
approval. Google OAuth client and refresh values remain synthetic; Meta lifetime
remains NOW+2h. All statements after setup, adverse mutations, parameters and
existing predicates are unchanged. Before/after zero-authority fixture explicitly
covers only this function; no capability is overridden. All other module tests
remain unchanged, apart from moving the existing SecretStr import to module scope.

Evidence `/workspace/inlet-evidence/20261009/owned-credential-read-fixture/`:
- Unchanged SQLite Google/Meta positive baseline: 2 failures, 5.416s, both actual
  legacy approval guard. `baseline.log/xml` retained.
- Full module on SQLite and isolated disposable PostgreSQL: 41 passed, zero
  failures/errors/skips, 26.158s. `qualified.log/xml` retained. This includes32
  originally failing current context cases plus9 previously passing pure cases.
- Whole Ruff, bare mypy1128 and diff checks passed. First focused Ruff applied
  import ordering only; final whole checks passed before commit.

Commands use `/workspace/inlet-venv/bin/pytest -q` with the two original
`test_owned_credentials_context_and_cleanup[sqlite-None-google_ads]` and
`[sqlite-None-meta_ads]` selectors for baseline; full
`tests/test_optimization_runtime_substrate.py` for qualification, with
AD_ANALYZER_TEST_POSTGRES_URL pointing to the existing isolated test database and
AD_ANALYZER_CI_DISPOSABLE_POSTGRES=true. No aggregate database or live provider.

Independent review precedes integration. This is fixture repair, not a newly
verified live connection or a passing Full-suite claim.
