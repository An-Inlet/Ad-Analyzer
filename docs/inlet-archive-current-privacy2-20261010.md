# Archive Financial/Social Current Privacy Two-Case Delivery

Local-only branch `codex/inlet-archive-current`, based on `1e3e127`.
Implements the approved closed source and exact privacy contracts in
[the source proposal](design/archive-closure-financial-social-current-v1.md) and
[the exact DTO/delta addendum](design/archive-closure-financial-social-exact-contract-v1.md).
No runtime advertising change, guard bypass, live provider, hosted run or push.

The exact original function body remains locally preserved (renamed only), and its
original SQLite/PostgreSQL node identities are in the new `archive_financial_social`
historical batch. Only that original two-case batch ran. Current tests consume only
the exact verified original prefix on fresh current DDL; child is reaped before
current identity/HTTP/privacy. Strict bounded DTOs carry scalar references, never a
historical runtime. Independent current readback validates owned policy/consent,
original/repeat approvals, request/response/receipt/capture, replacement, holds,
ledger dispatch/counters, source image and exact social confirmation.

Current two-brand checks retain actual complete owned archive, cross-brand denial,
exact allowed closure transitions, blocked closure and protected financial/social
records. Both active brands return exact planning409 without effects. After closure,
Alice returns canonical workspace404 before the planning gate; Bob remains planning409.
All requests compare full current graphs. No identity rewrites or clock extension.

## Actual Evidence

Durable directory: `/workspace/inlet-evidence/archive-current-contract-01/` contains
numbered failures and successes, source DB/media/DTO/lifetime logs, original historical
collection/log/XML/provenance and SHA256 manifest. The PostgreSQL fixture used a fresh
owned `inlet_test_*` schema in the approved disposable database, then dropped only that
schema during normal fixture teardown. No shared/default schema or database reset.

- `inlet-archive-source-01.xml`: failed exporter implementation (Meta server uses
  `posts`, Google uses `writes`); corrected without source changes.
- `inlet-archive-source-02.xml`: SQLite source cardinality/DTO/schema gate passed1.
- `inlet-archive-source-03.xml`: expanded typing initially assumed capture inside the
  normalized response. Corrected to `OptimizationResponse` plus the independent,
  owned typed `GoogleCompletionDocument`; preserved-source readback then passed.
- `inlet-archive-current-01.xml`: all archive/privacy transitions passed; proposed
  post-closureAlice409 failed actual404. Parent approved exact dependency-order
  refinement before continuing. `current-02` retained the exact-detail correction
  (`workspace not found`). No production change.
- `inlet-archive-current-03.xml`: current SQLite privacy case passed1.
- `inlet-archive-pg-01.xml`: latest current PostgreSQL case plus strict envelope/file
  guards passed16, zero skipped. This includes the final policy/consent/approval/step
  source checks; the same expanded validator separately passed against preserved
  pre-privacy SQLite evidence without rerunning historical source generation.
- `inlet-archive-historical-01.xml`: wrapper, exact AST/coverage mapping and changed
  partition test passed3. Nested `historical-01/historical.xml`: original2 passed,
  zero failures/skips. No prior historical batch rerun.
- Whole-repository Ruff passed. Required bare `mypy` passed1260 source files;
  `git diff --check` passed. Initial explicit `mypy app tests scripts` invocation
  rejected duplicate module discovery; bare repository-configured invocation used.

Local base14 batches/385 original identities becomes15/387. Root's later integrated
18/405 registry plus these two is19/407. BATCHES, literal partition contract,
HISTORICAL_PATHS, exact node list, coverage map and partition assertions all change
in this package; root must preserve its intervening additions when integrating.
No aggregate, live-environment qualification, deployment or commercial readiness claim.
