# Initial Planning Native Restore Evidence

This extends the disposable B19 restore drill at base `9833b9f` through migration
0075. It does not qualify a production backup, the initial planning policy, or
an executable advertising plan. No product code or migration changes are included.

The archive contains one owned initial observation, calibration, dependency and
preview in workspace 902, alongside the existing workspace 901 replacement
financial lineage and workspace 902 social approval. The observation references
the existing real terminal Meta publication fixture. The calibration and preview
are explicitly synthetic, strict-versioned **insufficient** documents; they do
not claim the goal/calibration/preview admission services ran. Their persisted
expired deadlines exercise cleanup without sleeps or invented retention defaults.
The observation remains unexpired. No native planning runtime is enabled.

The real PostgreSQL custom-format `pg_dump` / `pg_restore` roundtrip now checks,
before and after restore:

- Schema, data and privilege fingerprint equality, including all four populated
  0075 tables; all behavioral mutations roll back and must leave that fingerprint
  unchanged.
- Strict document/row bindings, unrelated workspace exclusion, and omission of
  `original_session_digest` and its value from the customer export projection.
- Actual observation reads for the original owner; foreign workspace, changed
  source generation, revoked original session and elapsed deadline are denied.
- Actual configuration-independent retention worker deletes expired derived data,
  preserves the retained observation and leaves the current performance report
  readable without another provider import or export-counter advancement.
- Semantic privacy erasure works in a closing workspace and removes the numeric
  graph, while the existing held financial reservation remains present.
- Restored immutability triggers, completion/workspace composite ownership and
  dependency deletion cascades remain enforced. Existing financial/social proof,
  unknown-attempt replay denial and sentinel-schema survival checks remain intact.

The independent serializer fixture tests also run on SQLite and PostgreSQL and
reject a forged workspace binding. SQLite tests are not described as native
backup/restore qualification. Authentication uses a local synthetic identity
provider; no real provider HTTP, cloud storage, credentials or customer data are
used. Media objects are still not restored by this database-only drill.

Validation uses a new disposable database `inlet_initial_restore_test_20261006`
and container `inlet-b01-postgres`; the active Full database is untouched:

```sh
AD_ANALYZER_TEST_POSTGRES_URL=postgresql+psycopg://postgres@127.0.0.1:55432/inlet_initial_restore_test_20261006 \
AD_ANALYZER_CI_DISPOSABLE_POSTGRES=true \
INLET_RESTORE_POSTGRES_CONTAINER=inlet-b01-postgres \
/workspace/inlet-venv/bin/pytest -o addopts='' -q tests/test_inlet_restore_drill.py
/workspace/inlet-venv/bin/ruff check .
/workspace/inlet-venv/bin/mypy
/workspace/inlet-venv/bin/mypy -p scripts.inlet_restore_initial_fixture -p scripts.inlet_restore_drill
git diff --check
```

Final results are recorded in the progress ledger. No Full, remote push, CI
dispatch, production restore or live qualification is part of this package.
