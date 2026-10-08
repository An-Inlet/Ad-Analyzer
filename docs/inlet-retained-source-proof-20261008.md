# Retained Local Source Proof Qualification

Branch `codex/inlet-retained-source-proof`, worktree `/workspace/inlet-retained-source-proof`, baseb557ab0; shared concrete interface frozenf68914f in `docs/design/planning-retained-source-proof.md` and coordinated with persistence before implementation.

New `retained_sources.py` implements the reviewed capture/recheck signatures and typed scalar witnesses in existing PlanDependencyRow rows. No SQL migration, model, public document or execution change. Generation captures only after actual bundle revalidation; the service owns the final authority/time checks and atomic insert. Each selected account gets a bounded whole-account local reporting state proof, including absence or mismatched-window state. It verifies actual current reporting provenance through read_current, recomputes the account manifest/count, and hashes exact completion fields plus bounded local/native campaign mapping. Commerce uses exact confirmed goal/store/privacy and freshly recomputed private goal-progress fields excluding only the moving as_of. Source binding and local state digests remain separate.

Retained reads accept READ_ROLES including viewer and make no identity/native-provider calls. They validate the COMPLETE ordinary-reference plus local-witness dependency row set, reject duplicate/extra/missing/foreign bindings, and recompute current local integrity. Typed RetainedSourcesChanged yields bounded not-current reasons; authentication errors propagate. Legacy versions missing new witnesses remain history, never inferred current. Native observations are not reread: their original expiry still bounds the document. At most MAX_ACCOUNTS+1 additional immutable scalar rows use existing ownership foreign keys, privacy revision, export allowlist and erasure lifecycle.

Qualification actually run:

- Initial persisted-version/proof cohort:36 passed53.85s.
- Expanded final cohort: **44 passed in60.78s**, both SQLite and isolated disposable PostgreSQL. Includes all-three-provider actual native MockHTTP plus actual reporting/Shopify/composer/persisted-version paths; unchanged viewer reads with provider callbacks forbidden; absent→available reporting; mismatch completion replacement and mismatch→matching window; same-pointer metric corruption; local/native mapping and generation changes; commerce revision/watermark/actual signed ledger amount/import state; privacy/session/expiry; legacy/missing/extra/duplicate ordinary and witness rows; bounded mapping overflow; existing scalar export coverage.
- Final explicit source query binding tightening (workspace/account/integration plus TikTok provider): **6 passed,38 deselected in9.71s**, unchanged viewer paths for all three providers on both databases.
- Whole Ruff passed; whole mypy passed **1045 files**; diff check passed.

Evidence `/workspace/inlet-evidence/20261008/retained-source-proof/`. No live provider calls or production latency claim. The helper verifies current local source integrity under caller locks, not live provider state; source capacity overflow fails closed. Independent review and service integration remain separate gates.
