# Meta Import To Customer Plan Presence — 2026-10-08

Branch `codex/inlet-import-plan-presence`, integrated base `a21f034`.
Reviewed producer34dd4fb is integrated atd4f7c90; reviewed consumer03ad1e4 at
`a21f034`. This package adds combined acceptance tests, no production changes.

Actual MetaClient constructed read-only HTTP requests feed owned new-window rolling
imports across56closedUTCdays. Terminal SQL publication is read through presence
storage, followed by authenticated customer create/generate/current/version/export
APIs and the actual policyv2 composer. Existing owned goal/source/native-catalog
fixtures supply setup only; neither a ready evidence bundle nor a composer override
is used. Previously seeded legacy completion must be replaced by the real importer.

SQLite and PostgreSQL both cover:

-100reportedclicks/10selectedpurchases/USD100spend: exact persisted observations and
customer rationale; no spend-without-conversions finding.
-Complete explicit selectedzero on all56days: observed-zero conclusion and retained
click/spend context.
-One returned day omits selected actions: missing selected cell, never full-windowzero.
-One absent calendar day: sparse reporting, never full-windowzero.
-A second actual import replaces prior completezero with missing selectedcounts,
keeping numeric legacyzeros: saved plan becomes stale, its original version/document
and export remain unchanged, and generated version2 withdraws the zero conclusion.
-All flows leave provider execution runs/attempts empty. Import transport accepts
only expected Meta GET requests; native planning reads use offline MockHTTP.

This is local actual import-to-plan qualification for Meta. It is not live provider,
Google/TikTok selected-event, full frozenQ01/Q02/Q09, expert recommendation quality,
full-suite, deployment or purchasable-product qualification. Attribution is unknown;
no campaign changes, budget recommendations or spending authority are introduced.

## Checks Actually Run

Approved disposable PostgreSQL on127.0.0.1:55432/inlet_oct07_next_integration_ci,
`AD_ANALYZER_CI_DISPOSABLE_POSTGRES=true`, isolated UUID schemas. Executables in
`/workspace/inlet-venv/bin` and `/workspace/inlet-tools`.

```
pytest -q -o addopts='' tests/test_meta_import_planning_presence.py tests/test_campaign_performance.py -x --tb=short --junitxml=/workspace/inlet-evidence/20261008/meta-import-plan-presence.xml
ruff check .
mypy
git diff --check
```

**30passed,0skips,40.19s**:8new both-database flow cases plus22existing campaign
performance cases. First combined execution passed without runtime or fixture
repairs. WholeRuff passed; configured mypy passed**1085sourcefiles**; diffcheckpassed.
Logs and JUnit:
`/workspace/inlet-evidence/20261008/meta-import-plan-presence.log` and `.xml`.
A preliminary lint-only check found one overlong newly written test line; corrected
before the final wholeRuff/test run. No failed product execution is hidden by this.

No remote push, PR, merge to main, hosted diagnostic, live connection or deployment.
Root local integration review and quality-ledger reconciliation follow this package.
Next independent package proposal binds saved plan versions to current Shopify sales
progress, preserving separate customer reports and unknown attribution.
