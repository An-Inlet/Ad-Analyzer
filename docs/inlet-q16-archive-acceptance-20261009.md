# Dated Q16 Archive And Privacy Acceptance

Branch `codex/inlet-q16-archive`, base `c597300`, isolated worktree `/workspace/inlet-q16-archive`. This package consumes the frozen Q16 fixture without changing its interface. No production code, default collection, W1 source/database, native provider or external calls changed.

## Actual Workflow

`tests/q16_archive_acceptance.py` is explicitly invoked during the fixture's October 2026 validity window. It generates the exact owned New York/November Q16 plan using the shared fixture, then:

1. Creates an export request through the actual authenticated HTTP API. A foreign owner cannot download it. Actual download routing runs the existing builder in the FastAPI worker thread, takes its own database snapshot, serializes supported records and media, and streams the real tar archive. The test unpacks it, checks the complete-supported-data/media flags, actual plan and image bytes, and exclusion of the foreign workspace.
2. Creates a second real request. A bounded test hook calls the **unchanged actual builder**, waits for its complete result, then commits actual semantic privacy erasure before returning that result to the unchanged delivery path. Final authorization/privacy validation rejects with 409 JSON; the built temporary file closes, and the request is interrupted with no manifest digest. The hook does not forge builder output, replace a privacy predicate, or pretend an archive was completed. It models the after-snapshot/before-delivery race only, not every streaming interleaving.
3. Creates and downloads a fresh complete archive. All six planning graph sections are empty and no entry contains the erased plan ID. The archive does not resurrect the removed graph. The prior successfully downloaded local copy cannot be remotely revoked and is not claimed to be revoked.
4. Checks exact, primary-key-ordered scalar snapshots of actual paid subscription and received billing event rows remain unchanged. These are genuine billing financial records; **no protected execution obligation exists or is claimed** in this test. A separate owned foreign workspace and its populated configuration remain unchanged and absent from the owned archive.
5. Logs out through the actual session endpoint; another download is denied 401. Native-call count remains unchanged throughout archive/privacy operations.

SQLite uses a private file/WAL database with foreign keys so snapshot and control connections are independent, matching the existing archive test architecture. PostgreSQL uses only its fixture's randomly named isolated schema on the approved disposable database. No shared database reset is performed.

## Checks And Evidence

Final exact-source qualification: **2 passed, 0 skipped, 25.246 seconds**, SQLite and PostgreSQL. Whole Ruff and bare mypy (1,122 source files) passed; diff check passed. Raw artifacts reside in `/workspace/inlet-evidence/20261009/q16-archive/`.

```
AD_ANALYZER_TEST_POSTGRES_URL=postgresql+psycopg://postgres@127.0.0.1:55432/inlet_oct07_next_integration_ci \
AD_ANALYZER_CI_DISPOSABLE_POSTGRES=true \
/workspace/inlet-venv/bin/pytest -q tests/q16_archive_acceptance.py \
  --basetemp=/workspace/inlet-evidence/20261009/q16-archive/artifacts \
  --junitxml=/workspace/inlet-evidence/20261009/q16-archive/qualified.xml
/workspace/inlet-venv/bin/ruff check .
/workspace/inlet-venv/bin/mypy
git diff --check
```

Initial `first.log` records a test setup error: Ruff removed an imported alias needed only by pytest fixture injection. Explicit module fixture binding repaired this; no product defect or production change occurred. `second.log` passed both databases. Strengthened cleanup/interrupted-state/no-old-ID assertions also passed both databases (`final.log/xml`). Final `closed.log/xml` reruns the same two cases after deterministic primary-key ordering of financial snapshots. These overlapping runs are not added together.

This is bounded dated archive/privacy evidence, not full Q16, comprehensive planning quality, manual-application qualification, browser proof, production performance or live deployment acceptance. The separate browser/manual-report lane remains responsible for its own evidence.

The deterministic-order edit exposed a static Table annotation mismatch (`mypy-closed.log`), repaired with a runtime-neutral explicit `Table` cast. Final `qualified.log/xml` reruns both cases and retains synthetic `before-manifest.json`, `before-plan-versions.jsonl`, `after-manifest.json` and `after-plan-sections.json` under each database case in evidence-local `artifacts/`. These are outputs of the actual archive, not reconstructed serializer fixtures. Raw prior logs remain. Only sanitized manifests/plan payloads are evidence deliverables; local database files under the fixture temporary root are not publication artifacts.
