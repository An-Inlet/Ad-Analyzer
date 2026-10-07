# Campaign Performance Restore Evidence

Base: `73ba61b` (migration `0074`). This package closes a restore-fixture
coverage gap; it does not repair a demonstrated production data-loss defect.
The existing restore fixture populated financial replacement/unknown-attempt and
social approval evidence, but no campaign-performance completion or current pointer.

The fixture now stages synthetic Meta campaign facts and invokes the actual terminal
`MetaSyncService._publish` implementation. This is an explicit staged-input boundary,
not a claim that OAuth, provider HTTP acquisition, or production credentials were
restored. There are no provider calls. The facts are 100 clicks, 10 conversions,
100,000,000 spend micros, and 250,000,000 conversion-value micros.

Before and after actual PostgreSQL custom-format `pg_dump` / `pg_restore`, the drill:

- Reads the owned current campaign through the application reader, which rechecks
  generation, coverage, privacy revision and recomputed fact-manifest integrity.
- Verifies the expected amounts, current reference, unqualified maturity and absence
  of spending authority, plus foreign-workspace reader and export exclusion.
- Rejects completion UPDATE (including no-op UPDATE), duplicate receipt insertion,
  foreign completion/account ownership, and foreign current workspace/account changes.
- Deletes the completion and observes cascading current-pointer removal within a
  rolled-back transaction, preserving the restored graph and all financial evidence.
- Retains the prior replacement hold, unknown replay, social approval and complete
  data/schema/privilege fingerprint checks without weakening them.

The native drill uses migrations, including the immutable trigger; ORM-created
SQLite/PostgreSQL fixtures are used only for populated-reader and tamper checks.
A changed stored metric must make current evidence unavailable. No trigger guarantee
is inferred from `Base.metadata.create_all`.

Validation uses the fresh disposable database `inlet_performance_restore_test_20261006`
and `INLET_RESTORE_POSTGRES_CONTAINER=inlet-b01-postgres`. Each native run creates and
removes its own generated schema; archive and restore failure cases verify that an
unrelated sentinel schema survives. No candidate or shared test database is reset.

Checks (final source):

- `pytest -o addopts='' -q tests/test_inlet_restore_drill.py`: 33 passed, 5 Alembic deprecation warnings in 70.82s; includes real native restore and both database fixtures.
- `ruff check .`: passed.
- `mypy`: passed, 623 source files.
- `mypy -p scripts.inlet_restore_fixture -p scripts.inlet_restore_drill`: passed, 2 files.
- `git diff --check`: passed.

No Full, live restore, media-object backup, hosted backup/key recovery, rollout, or
provider account qualification is claimed. Push/PR is held pending the parent's
GitHub pre-run failure diagnosis; an unknown failure is not asserted to be quota.
