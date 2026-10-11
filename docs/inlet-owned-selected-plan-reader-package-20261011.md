# Owned selected planning reader — 2026-10-11

Base8d40425 plus reviewed safe projection helper63ede67 (local9959f5e).
New `app/planning_documents/selected_plan_reader.py` supplies:

- `OwnedSelectedPlanContext(db, *, principal, account, expected_source, capture_id,
  catalog, authorize, clock)`, with `.pin`, `.snapshot()`, `.read(target, window)`
  and context-manager/close lifecycle.
- `load_selected_plan_graph(db, *, account, expected_source, capture_id)` returning
  SelectedPlanCaptureV1. This internal SQL-only port requires caller-owned original
  authority and active clean scope transaction. It does not authenticate or commit;
  witness callers must guard authority/source freshness before and after it.

The owned context uses the original PlanningReadContexts authorization callback;
external identity refresh occurs before its SQL transaction. It validates the
whole current selected capture, aggregate and complete sorted owned campaign map
once. Safe PreparedSelectedPlanProjection validates/indexes the graph once.
No per-window full-graph parser or summary-index reconstruction occurs.

Every output and successful context exit checks the exact root/connection
transaction, clean ORM state, resident values before refresh, original authority,
source/catalog/privacy and deadline, plus bounded exact SQL witnesses for the
capture/facts/selection/head/completion/current pointer, source/account/integration,
original user/session/membership, campaign map and aggregate-window metrics.
Witnesses remain private and are never serialized. Limits are50k facts/metrics,
10k campaigns,64MiB total witness representation. New/dirty/deleted objects,
flushes, savepoints and ended/replaced transactions fail closed. Hooks are removed
on failure/close; exceptional exits preserve the original exception. Explicit
foreign/stale/corrupt selectors abort rather than becoming a missing-data gap.

The shared graph loader validates current stored evidence and account/source scope,
then uses the same bounded sorted mapping as the owned reader. It has no catalog
requirement and grants no authority. No runtime/policy/witness registration,
customer route, network call or schema change is added by this package.

## Evidence and honest fixture boundary

Tests use actual selected customer API acquisition, original login/Vault/OAuth,
mocked Google selected HTTP and real retained SQL graph. The native catalog is
explicitly a synthetic typed server fixture bound to the owned account/source;
this does not claim a new native HTTP collection or integrated v4 generation.

Durable logs/XML: `/workspace/inlet-evidence/20261011/selected-plan-reader`.

- `sqlite01`:3 failed fixture catalog coverage assertions. `sqlite02`:13 failed
  because the corrective fixture referenced coverage on the raw native inventory
  rather than its catalog projection. Both failures retained; no production guard
  was weakened. `sqlite03`:3 actual positive cases passed6.000s;
  `sqlite04`:13 SQLite cases passed16.926s.
- `combined05`:37 passed/1 failed of38,84.353s. The failure supplied a datetime to
  BIGINT CustomerSession.revoked_at and occurred before the intended reader check.
- `final06`:12 passed27.033s after strict integer timestamp correction, including
  positive10/zero/omitted, revoked-session, before-constructor resident tamper and
  final authority expiry after witness work, on both databases.
- `final07`:8 passed27.552s after adding newly loaded source-resident protection,
  covering that attack and all three actual positive paths on both databases.
- Other successful cases cover raw metric/mapping/source/privacy/selection/capture
  changes, original role, dirty state, commit/rollback/savepoint, catalog expiry,
  successful-exit recheck, shared-loader foreign scope and exception cleanup.

These are successive focused cohorts, not an assertion that one final broad or
Full run occurred. All initial failures remain available. PostgreSQL used existing
per-test disposable schemas and was handed back after completion. No resets,
original evidence removal, hosted actions or live requests occurred.

Root-authorized one-line pure fixture repair changes setattr to object.__setattr__
for the same readonly-property AttributeError assertion, fixing inheritedB010.
Whole Ruff/mypy results are in `ruff08.log`/`mypy08.log`; pure follow-up is `pure08`.
Final static checks pass: whole Ruff, mypy1326 files and diff whitespace check.
`pure08` passed36 cases in0.775s, no skips. No additional database run was needed
for the inherited pure readonly-property test spelling change.
