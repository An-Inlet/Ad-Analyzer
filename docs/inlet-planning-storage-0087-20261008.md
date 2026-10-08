# Planning Storage 0087 — 2026-10-08

Branch `codex/inlet-plan-persistence-current`, worktree `/workspace/inlet-plan-persistence`,
base root `35e2a3b` (reviewed ports/UI). This is storage/lifecycle only; customer services,
authority/CAS races and API/composition integration are the next package.

Added six workspace-scoped tables with composite parent/source/result FKs and explicit
exclusive successful request result CHECK. Inputs, versions, dependencies, events and
receipts reject UPDATE in actual SQLite/PostgreSQL DDL; deletion remains permitted.
Input preview/goal/revision and event prior-chain family/action/version binding have
insert guards. Current-head CAS and prior-current-head enforcement belong to the service.
Migration0087 is frozen SQL, down0086; populated downgrade refuses loss of history.

Canonical document persistence/export reparses typed contracts, compares domain digests,
owned scalar IDs and timestamps. Planning-only row cap5MiB accommodates existing archive
four-byte conservative preflight and JSON escaping around max1MiB decoded contract;
other tables retain original bounds and entire archive caps are unchanged. Internal
request keys/digests remain excluded. Malformed/oversized planning rows fail export,
not falsely claim a complete result. Semantic privacy bump deletes the complete owned
six-table graph (events newest-first); counter-only correction preserves history.

Checks actually run:
- `AD_ANALYZER_TEST_POSTGRES_URL=postgresql+psycopg://postgres@127.0.0.1:55432/inlet_oct07_next_integration_ci AD_ANALYZER_CI_DISPOSABLE_POSTGRES=true /workspace/inlet-venv/bin/pytest tests/test_planning_document_storage.py`:
  **5 passed in9.39s**, both databases, one existing Alembic config deprecation warning.
  Actual0087 migration, all immutable row families, receipt CHECK/FK, populated downgrade,
  scoped semantic graph erasure, exact1MiB valid canonical export/overbound rejection,
  actual archive containing plan graph and privacy invalidation before delivery.
- Storage + model registry precursor: **7 passed in4.29s**.
- Existing export cohort (`-k 'fresh_stream_revocation or bounds_do_not or supported_schema or archive_snapshot'`):
  **23 passed,25 deselected in60.66s**. Original revocation/bounds/archive behavior retained.
- `/workspace/inlet-venv/bin/ruff check .`: passed.
- `/workspace/inlet-venv/bin/mypy`: final count in handoff.
- `git diff --check`: passed.

No live-provider/hosted calls, no Full claim. Raw DB fixtures prove storage invariants,
not a customer-generated plan or authorization. Next: reviewed one-shot five-second
local authority + create/revise/current-head service, trusted generation orchestration,
exact event chains and read/export access with both-DB races. Adapter recheck remains
mandatory before final commit; provider/source callbacks must run outside row locks.

Independent review repair: stored version `privacy_revision` now must equal every
canonical evidence reference privacy revision during load/export. Both a tampered scalar
and mixed canonical evidence with recomputed digest are rejected. Focused two-case repair
cohort passed; whole Ruff/mypy1027 passed before starting the separate authority/DTO WIP.

## Authority/DTO Interface Slice

Added planning-local immutable scalar identity fact and fixed5second monotonic final
acceptance helper; no global auth changes/provider IO under local lock helper. Pure
boundary tests: **5 passed in1.41s** (exact/overage/backward interval, provider-side
identity mutation, revocation, session expiry). Later rerun final timing in handoff.
Concrete request/response DTOs and public route/service shape are documented in
`docs/design/planning-customer-service-api.md`. These do not install routes or claim
working customer service. Root can implement dependent UI against this interface.
Whole Ruff/mypy **1031 files** passed; diffcheck passed. Service lock-wait/race/IO
integration tests remain the next implementation slice, not implied by pure helpers.
