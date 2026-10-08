# Planning Storage Integration — 2026-10-08

Reviewed storage `2ad7c52` merged at `745839d` into `codex/inlet-planning-mvp`.
Migration 0087 adds six scoped plan/history/dependency/event/request tables, immutable
history triggers, scoped result receipt constraints and refusal to downgrade populated
history. Semantic privacy erasure deletes the complete six-table graph; ordinary
corrections preserve it. Planning archives use a dedicated bounded serializer without
loosening global archive limits. Review repaired stored-versus-embedded privacy revision
validation, including mixed evidence with recomputed canonical digest.

Integrated actual SQLite/PostgreSQL and pure checks: 99 passed in 11.69s, one existing
Alembic `path_separator` deprecation warning. Cohort: planning document storage, model
registry, composer, contracts and ports. Ruff and prescribed mypy passed (1,029 source
files); diff check passed. Initial command named a nonexistent lifecycle registry test
and collected zero tests (exit 4); corrected command uses `test_model_registry.py`.
Both logs retained under `/workspace/inlet-evidence/20261008/planning-storage-integrated*`.

Storage fixtures and archives are verified offline; customer authority/service/routes,
successor CAS and full customer lifecycle journey are not yet qualified. No remote
push, live provider call, deployment or production migration.
