# Current Campaign Review Retained Binding — 2026-10-09

Tests-only successor from root `f2099ac`, approved interface `c05df95`. Existing media-only repair remains unchanged. New isolated producer/helper files avoid the shared `seed_driver.py` and global `setup/seed`; no production or advertising capability edits.

The closed driver runs pinned `2155ff3e3ab00cd62057dd86cb49d45359d4f49f` services against current disposable schema tables. Google uses the actual original setup/approval sequence, total100/per-action80micros (90 rejects). Meta performs the original integration/source/policy edit and reapproval entirely inside the pinned process. Only scalar IDs cross. Fresh current sessions perform every review/edit/approval, binding recheck, exact media/rotation/generation, entitlement and race assertion.

Current `campaign_review.approve` approves an offline plan, not advertising publication. Current mandate-edit adverse testing remains actual current simulation code; no current legacy reapproval is invoked. Zero-effect assertions surround producer and current consumers; only the required genuine retained legacy mandate may exist. `provider_posts=0` is established by the closed producer's source (no HTTP adapter or provider client is constructed), not by a measured mock-server call counter. Current write guards remain false. Private producer source/schema/provenance checks and bounded strict scalar parsing precede current use.

Unsupported campaign kind remains a syntax-only test with explicit synthetic IDs, first validating a good RevisionInput then changing only the kind. Its two existing database-parametrized node identities remain for continuity, but it does not claim DB ownership proof. Media/API/copy-bound tests remain current and unchanged.

Evidence directory: `/workspace/inlet-evidence/20261009/campaign-review-regression/`. Baseline exact SQLite Google/Meta image cases:2 failed6.442s at the unchanged legacy approval guard (`baseline.log/xml`, same source in proposal checkout). First two repaired cases:2 passed16.178s (`first.log/xml`), overlapping final qualification. Selected consumer collection:22 nodes =21 formerly failing +existing SQLite-only row-lock skip (`collection.log`).

## Final Qualification

- Whole current campaign-review module: **41 passed,1 existing SQLite concurrency skip**,194.330s (`qualified.log/xml`). This covers21 originally failing nodes, the original skipped node, and20 unchanged compatibility nodes (media/API/copy/private-storage behavior). Exact original failure intersection is preserved in `matched-failure-nodes.json`.
- Review followup strengthens dynamic current-guard lookup, zero ProviderExecutionMandate and ProviderExposureReservation counts, Meta source ID length<=128 before integer conversion, and guaranteed post-consumer zero-effect checks. Final Google+Meta bothDB rerun: **4 passed,0 skips** (`final.log/xml`; overlapping cases, not four extra repairs). Retained producer logs and scalar outputs remain under evidence-local `qualified-tmp` and `final-tmp`.
- Initial static checks exposed local Connection/Session variable inference and pure payload inferred as object. Final variable names/type annotation repaired without behavior change. Final whole Ruff, bare mypy **1136 source files**, and diffcheck passed (`ruff-final.log`, `mypy-final.log`). Earlier diagnostic remains in `mypy.log`; intermediate final-named log was replaced by final successful verification.

Commands use `/workspace/inlet-venv/bin` tools. Baseline/first selected `tests/test_campaign_review.py::test_exact_review_edit_and_stale_approval[sqlite]` and `tests/test_campaign_review.py::test_image_review_binds_exact_media_and_meta_generation[sqlite]`. Collection explicitly selected the seven scoped functions (review/edit, binding, scope/limits, entitlement, image, concurrency, unsupported); exact22 node output is retained. Whole-module command:

```sh
AD_ANALYZER_TEST_POSTGRES_URL=postgresql+psycopg://postgres@127.0.0.1:55432/inlet_oct07_next_integration_ci AD_ANALYZER_CI_DISPOSABLE_POSTGRES=true pytest -q tests/test_campaign_review.py --basetemp=<evidence>/qualified-tmp --junitxml=<evidence>/qualified.xml
```

Final affected command uses the same environment, selects `tests/test_campaign_review.py::test_exact_review_edit_and_stale_approval tests/test_campaign_review.py::test_image_review_binds_exact_media_and_meta_generation`, and writes `final-tmp`/`final.xml`. Whole `ruff check .`, bare `mypy`, and `git diff --check` followed final source changes. PostgreSQL uses only caller-owned UUID fixture schemas; SQLite creates a dedicated current-schema file per producer. No aggregate source/database, Full, shared schema reset, live provider or advertising writes. No aggregate pass claim.
