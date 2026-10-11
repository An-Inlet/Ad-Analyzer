# Real Creative Authority Expiry Regression — 2026-10-11

The existing reader age regression used a legacy reader and an injected monotonic
clock. This new, separate test qualifies the real v5 API boundary after the scoped
selected/traffic read reuse, without changing any application source or clock.

`tests/test_creative_runtime_authority_delay.py` uses the parent's frozen actual
HTTP fixture from dc15f7b: Google range and selected capture, owned image upload,
explicit private v5 service, real private image read and genuine retained-source
capture. Only after that capture returns valid reporting and creative witnesses,
a wrapper performs exactly one six-second wait. The response must be precisely
409 `planning_authority_expired`; reaching the delayed capture and the actual
single image read are separately asserted. Input head stays1, version head0,
version/dependency/generation-receipt rows remain absent, and total request-receipt
count remains unchanged. There is no retry, synthetic time or larger deadline.

Execution waited for the parent's normal API and instrumented comparison runs to
finish. Their SQL reduction is not evidence of improved latency or a proven cause
for the earlier authority expiry. This regression proves the unchanged rejection
guard only.

Evidence: `/workspace/inlet-evidence/20261011/creative-authority-delay/`.
SQLite:1 passed,0 skipped,15.774s (`sqlite.xml`); PostgreSQL:1 passed,0 skipped,
20.758s (`postgres.xml`). Whole Ruff passed; configured no-path mypy passed1409
source files; `git diff --check` passed. No live providers,
advertising actions, remote writes or default policy changes.
