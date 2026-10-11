# Google range receipt storage — 2026-10-11

This package implements the internal 0092 storage boundary defined in
`docs/design/google-range-publication-interface-v1.md`. It exposes no route,
provider acquisition, runtime registration, or new retention policy.

`RangeReceiptV1` is frozen in commit a72c3ed. `range_receipts.store_range_receipt`
flushes within the caller's transaction; `read_range_receipt` requires exact owned
scope and defaults to validating the whole current aggregate. Neither port
establishes original-session authority or commits. The publisher must bind the
original actor and session, acquire the actual requested range, and atomically
publish its successful dedicated job, completion, current aggregate and receipt.

The immutable erasable row binds the account/workspace/integration, completion
and dedicated successful Google job. Database insertion validates the canonical
receipt's completion fields, source generation/privacy, units, dates, exact query,
manifest, row count and completion time. Raw deletion takes the PostgreSQL
workspace NOWAIT fence, invalidates calibration outputs and advances the export
privacy counter. Semantic privacy erasure removes receipts. Historical export
contains metadata only and explicitly says historical_as_observed; it never
reconstructs old metrics or claims currentness. Populated downgrade refuses loss.

## Verification

Evidence is retained at `/workspace/inlet-evidence/20261011/range-receipts`.

- `contracts01`: six pure DTO cases passed.
- `storage02`: seven SQLite cases passed, one failed because the test incorrectly
  queried nonexistent `DailyMetric.account_id`. Corrected to join its Campaign;
  the original failure log/XML are retained.
- `storage03`: 22 passed, zero skips, 25.526 seconds (JUnit). Covers both SQLite
  and PostgreSQL: current versus historical reads, immutable updates, exact replay,
  foreign ownership, invalid job/completion insertion rollback, actual archive
  revocation after raw deletion, semantic erasure, and actual 0092 upgrade,
  populated-downgrade refusal, empty downgrade/upgrade and frozen SQL parity.
- Whole Ruff (`ruff04.log`), whole mypy (1307 source files, `mypy04.log`) and
  `git diff --check` pass. Earlier static failures are retained in `*03.log`.

The storage fixture uses actual OAuth/Vault and mocked Google aggregate HTTP
imports, then explicitly creates the scoped successful range-job metadata.
It does **not** prove atomic range acquisition or a 61-day customer API. Those
remain the separate publisher acceptance responsibility. PostgreSQL uses the
existing local disposable fixture with per-test random schemas; no original DB,
evidence or frozen qualification tree is reset. All provider traffic is mocked.

Bounded test recipe (with the established local disposable test environment):
`pytest -q tests/test_range_receipts.py tests/test_range_receipt_contracts.py
--durations=20 --basetemp=<unique durable directory>/tmp
--junitxml=<unique durable directory>/results.xml`.

Resource reserve was temporarily breached during concurrent workspace growth;
work paused. Only this lane's regenerable mypy cache moved to scratch. Tests
resumed after the parent restored reserves; no evidence was removed.

## Independent review follow-up

Review identified two strict-boundary gaps: an unsafe `model_copy` could be hashed
without validation, and historical receipt reads did not check the completion's
fixed aggregate semantics. The successor revalidates before hashing and requires
`selected_event IS NULL`, `provider_aggregate_unspecified` semantics and
`provider_defaults_unspecified` reporting basis in both the reader and insertion
trigger. Frozen 0092 literals have identical predicates. The adversarial tests
mutate metadata-created completion rows (the deployed 0074 immutability trigger
is an additional defense), prove historical read/export and new receipt insertion
deny, then prove rollback restores the original receipt.

`review05` passed 19 pure/SQLite cases in 8.113 seconds, zero skips; PostgreSQL
cases were deliberately deselected while the parent's integration cohort owned
the disposable PostgreSQL slot. Whole Ruff and mypy1307 passed (`*05.log`).

After the parent's PostgreSQL release, `review06` passed all 11 PostgreSQL cases
in 23.682 seconds, zero failures/skips. The final repaired package therefore has
30 passing cases across the split pure/SQLite and PostgreSQL checks. PostgreSQL
was released to the range publisher author after completion.
