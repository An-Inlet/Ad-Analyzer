# Historical Outcome, Export And Restore Regression

Current-policy tests in `test_owned_outcomes.py`, `test_export_owned_domains.py`
and `test_google_completion_restore.py` now create synthetic pre-MVP receipts inside
explicit setup-only override contexts. The shared write guard is restored and
asserted before commerce observations, outcome assessment, privacy erasure, archive
serialization, migration checks and restored-record reads. All three modules are
`planning_boundary`; no retained-engine fixture or production switch is used.

Existing uncertainty/no-causal-lift, exact original receipt, idempotency, ownership,
revocation, privacy locking, immutable lineage, strict serializer and held-exposure
assertions remain. The PostgreSQL drill uses its own random test schema in the
approved disposable database; it does not reset a database or touch live accounts.
It verifies exact 0066 migration roundtrip, refuses populated destructive downgrade,
then dumps/restores the populated current schema and compares fingerprints and
original owned commitments under the default planning policy.

Named three-module cohort: **15 passed, 1 expected SQLite row-lock skip,
10 existing Alembic configuration warnings, 113.83seconds**. PostgreSQL privacy
concurrency and both native completion restore variants passed. Whole Ruff,
prescribed mypy (**1019 files**) and diff checks passed. Raw evidence:
`/workspace/inlet-evidence/20261008/planning-retained-restore.{log,xml}`.

No production source, schema or migration changed. This narrows the historical
fixture backlog; it is not an aggregate Full pass or live restore/deployment proof.
