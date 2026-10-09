# Current TikTok Read Fixture Regression Closure — 2026-10-09

## Scope And Implementation

This tests-only successor to approved interface `c9ca40a` restores the exact 50 owned-discovery and 22 customer-discovery nodes listed in `docs/design/regression-read-consumer-first-package-nodes.json`. Production code, `test_mandates.seed`, and global `configured_tiktok_customer` are unchanged. No advertising-write guard is overridden.

New `TikTokReadIds` and `prepare_tiktok_read_source` reuse the reviewed source-only catalog fixture: actual owned account/source, sealed synthetic grant, customer login, configuration files and manifest loader. The original owned contexts, session/source-generation fences, test clock, HTTP behavior, scope checks and all test assertions remain. Irrelevant video creation and approved execution setup are removed from these read consumers.

`configured_discovery_customer` preserves its six-value return and optional legacy video argument. Actual registered evidence descriptor resolution remains; its financial builder raises if invoked. All original tests continue to assert zero builder/effect calls. An explicitly selected before/after fixture additionally asserts zero legacy mandates, execution mandates/consents/reviews/attempts/responses/receipts/reservations, with the production write prohibition still enabled. It is not a global autouse fixture.

Other callers of both shared helpers retain positional compatibility. The existing discovery browser consumes the former execution page and is outside this 72-node package; it was neither edited nor counted as repaired. Linked-post/capability callers were type-checked, not execution-qualified here. Meta reads, initial native planning confirmation and campaign-review fixture proposals remain separate packages.

## Recorded Checks

Artifacts: `/workspace/inlet-evidence/20261009/tiktok-read-regression/`.

- Baseline exact SQLite `test_owned_get_traversal[sqlite-pixel]` and `test_configured_discovery_has_no_execution_or_native_identifier_output[sqlite-observed]`: **2 failed**, 2.522s, both at legacy `test_mandates.seed → mandates.approve → AdvertisingWritesDisabled`. Preserved `baseline.log/xml`; executed from the unchanged proposal checkout at the identical `c9ca40a` base.
- Collection before and after: exact frozen **72 node IDs** matched, not merely count. `collection-before.log`, `collection-after.log`.
- Repaired baseline cases: **2 passed**, 2.239s, `repaired.log/xml`; overlaps the subsequent full focused cohort.
- Both-database current discovery cohort: **72 passed, 0 skipped**, 59.450s, `qualified.log/xml`.
- Pure current compatibility: **71 passed, 0 skipped**, 0.454s, `compatibility.log/xml`.
- First whole Ruff passed; first bare mypy exposed three other callers still passing video to `prepare`. Restored the optional ignored argument; no production change. Original diagnostic retained in `mypy.log`.
- Final whole Ruff: passed (`ruff-final.log`). Final bare mypy: **1128 source files passed** (`mypy-final.log`). Final signature regression: the same two SQLite cases **2 passed**, 2.180s (`final-signature.log/xml`); overlap, not additional repaired nodes.
- `git diff --check`: passed.

## Commands

Using `/workspace/inlet-venv/bin` tools, working directory `/workspace/inlet-tiktok-read-regression` (baseline exception above):

```sh
pytest -o addopts='' --collect-only -q tests/test_tiktok_owned_discovery.py tests/test_customer_tiktok_discovery.py
pytest -q 'tests/test_tiktok_owned_discovery.py::test_owned_get_traversal[sqlite-pixel]' 'tests/test_customer_tiktok_discovery.py::test_configured_discovery_has_no_execution_or_native_identifier_output[sqlite-observed]' --junitxml=<evidence>/baseline.xml
AD_ANALYZER_TEST_POSTGRES_URL=postgresql+psycopg://postgres@127.0.0.1:55432/inlet_oct07_next_integration_ci AD_ANALYZER_CI_DISPOSABLE_POSTGRES=true pytest -q tests/test_tiktok_owned_discovery.py tests/test_customer_tiktok_discovery.py --junitxml=<evidence>/qualified.xml
pytest -q tests/test_tiktok_owned_discovery_contracts.py tests/test_tiktok_customer_discovery_contracts.py tests/test_tiktok_native_inventory.py tests/test_tiktok_runtime_contracts.py --junitxml=<evidence>/compatibility.xml
ruff check .
mypy
git diff --check
```

The repaired/final-signature commands use the same two baseline selectors and their respective XML output names. PostgreSQL uses isolated UUID fixture schemas, not the aggregate database. No Full, browser, live provider calls or advertising writes were run. These results close the bounded current read fixture package; they do not convert the original failed aggregate into a pass or qualify adjacent execution-era tests.
