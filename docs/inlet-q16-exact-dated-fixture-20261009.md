# Q16 Exact Dated Fixture — 2026-10-09

Branch `codex/inlet-q16-exact-fixture`, base `868a740`, worktree `/workspace/inlet-q16-exact-fixture`. Test-only successor; no production files, W1 source/database, default collection, native mutations or external calls changed.

Shared contract: [Q16 Exact Dated Fixture V1](design/q16-exact-dated-fixture-v1.md). Reusable helper `tests/q16_fixture.py`, explicit dated acceptance `tests/q16_exact_acceptance.py`, synthetic owned image `tests/fixtures/q16/synthetic-mug.png`. The inherited clock-probe assertion incorporates root's one-line Ruff-compatible `vars(customer_api)["time"]` correction.

## Qualified Outcome

Final explicit run: **4 passed, 0 skipped, 15.902 seconds**, SQLite and isolated PostgreSQL schemas, covering exact NY progress/correction and separate semantic-erasure/old-ID cases. Raw terminal log and JUnit: `/workspace/inlet-evidence/20261009/q16-exact/closed.log`, `closed.xml`.

```
AD_ANALYZER_TEST_POSTGRES_URL=postgresql+psycopg://postgres@127.0.0.1:55432/inlet_oct07_next_integration_ci \
AD_ANALYZER_CI_DISPOSABLE_POSTGRES=true \
/workspace/inlet-venv/bin/pytest -q tests/q16_exact_acceptance.py \
  --junitxml=/workspace/inlet-evidence/20261009/q16-exact/closed.xml
/workspace/inlet-venv/bin/ruff check .
/workspace/inlet-venv/bin/mypy
git diff --check
```

Whole Ruff passed (`ruff-final.log`), bare mypy passed 1,121 source files (`mypy-final.log`), diff check passed. No Full run, no default-suite acceptance claim and no overlapping counts added together.

## Iterations And Limitations

- First run stopped after actual Shopify first import and goal HTTP confirmation on a fixture enum attribute typo (`AdvertisingPlatform.google_ads`); changed to the actual enum constructor. Raw `first.log` retained.
- Initial two-DB progress sequence passed (`second.log`); expanded progress-only checks also passed (`qualified.log`, `final.log`). These are superseded overlapping runs, not additional final cases.
- First privacy extension reached all expected old-ID denials, then failed on the test's wrong lifecycle table name `planning_document_inputs`; corrected to actual `planning_input_revisions`. Raw `qualified-final.log/xml` retained. No production bug or guard change was needed.
- First bare mypy identified a fixture loop literal annotation; explicit `Literal` stage tuple fixed it. Original `mypy.log` retained; final full check passed.
- September agreement now explicitly September 15 at -04:00; final four-case run includes that correction. Current real October confirmation is not replayed at a fabricated future HTTP clock.
- Finite-date experiment deliberately remains outside pytest default filename patterns. It must not be promoted unchanged to permanent default collection after October 2026.
- Privacy evidence is actual semantic graph deletion plus bounded lifecycle section serialization and artifact/old-ID endpoints, not full archive construction/delivery. Actual browser, streamed archive/privacy races and full Q16 remain pending. Native Google reporting remains explicitly unavailable, not selected-event producer qualification. Image exists in owned media storage but is only referenced textually by current plan inputs, not consumed through a typed image/vision interface.

Next: independent fixture review before browser reuse; then browser progress/correction and archive delivery privacy with the same exact fixed inputs. No comprehensive quality or live qualification claim.
