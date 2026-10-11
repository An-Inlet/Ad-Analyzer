# Owner Review Same-Call Reuse

Implements reviewed `ad7653a` only in `owner_review_generation._linked`. Every call
still fully validates its ticket and PlanVersion and derives exact linked catalogs.
That full PlanVersion validation already checks the owner proof. The final repeated
owner check is omitted only when complete ordered source JSON, full input JSON and
strict privacy match its already validated arguments; existing full catalog equality
remains mandatory. Any difference runs the original validator. No cache, prepared
artifact, new refusal, SQL boundary or public entry change.

Tests use real nested validators with alias spies. Two receipt-side calls independently
resolve and validate; later malformed candidate and changed source refuse. Resolver
stubs prove call/error boundaries, not SQL freshness qualification. Reordered sources
and changed unselected-source commitment must use original fallback without new refusal.
Unsafe copied models, missing/duplicate/extra sources and strict privacy remain checked.

Evidence: `/workspace/inlet-evidence/20261011/owner-linked-same-call/`.
Initial mypy01 exposed a test import of a non-reexported alias; changed to the defining
module. mypy03 exposed an invalid test sentinel reason; changed to the real `missing`
literal. Logs preserved. Ruff formatted a new long test expression. Final whole Ruff04
and no-path mypy04 passed1478 files before execution. No production behavior repair was
needed for these static findings.

The single authorized pure01 run passed24 cases, zero failures/errors/skips, in 8.112
seconds, exit0:16 new same-call cases plus8 existing phase cases. No repeated run or
source change followed. `selection.json` retains exact nodes/source hashes/resource
floors; final `manifest.json` binds source and evidence. Final diff check passed. This package does not establish ordinary V6 API latency qualification or
resolve previous observed authority expiry. Exact five-second guards, separate fresh
source passes, receipt SQL resolution and post-flush checks remain unchanged.
