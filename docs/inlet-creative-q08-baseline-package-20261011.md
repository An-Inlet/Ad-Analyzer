# Q08 Actual Owned Empty-Query Baseline

Base `e5f7e8d`; branch `codex/inlet-creative-q08-baseline`. Approved baseline only,
not production preparation behavior. New isolated test module
`tests/test_creative_q08_baseline.py`; no shared fixture or application changes.

The helper uses the actual Meta Common Basis owner, connected vault/account and
owned PNG upload. Before any planning input is created it switches only the injected
read-only HTTP responder to empty campaign/adset/metadata lists, then publicly
revises, previews and confirms the goal with a zero budget. The actual catalog API,
V5 create/generate/current/export and exact generation replay execute normally.
No selected performance, saved plan, proof or fake campaign is seeded.

## Observed Result And Remaining Gap

Both databases return the expected bounded baseline: zero confirmed ceiling; no
paid allocation or reserve; no forecast/native edit; one original-account
investigation; explicit absent-event-not-zero instruction; no reported-metrics
reference or selected capture. The exact owned image/hash remains in the creative
proof, but creative proposals and briefs are empty with "no included campaign"
deferral. This reproduces the missing useful preparation brief. It does not close
Q08; production work still needs reviewed retained-witness validation.

Actual retained API catalog artifacts show both campaign and adset scopes:

- Native: `partial`, `sdk_known_effective_statuses`, observed count `0`, reason
  `effective_status_scope_limited`.
- Metadata: `partial`, `sdk_known_effective_statuses`, count `0`, reason
  `native_scope_limited`.

The fixture observes an empty **declared query**, not proof the provider account
has no other campaign families/statuses or has never served ads. It still has the
Common Basis Shopify history; advertising observations are absent, not zero
conversions. No unconnected-brand scope or source-authority bypass is introduced.

## Checks And Local Evidence

`/workspace/inlet-evidence/20261011/creative-q08-baseline/` retains logs/XML and
separate database catalog/document/export JSON with per-case SHA-256 manifests.
`evidence-manifest.json` hashes the retained evidence. No external sharing/upload.

- First SQLite baseline: 1 passed, 0 skipped, 8.026s, exit 0.
- Bounded SQLite/PostgreSQL cohort: 2 passed, 0 skipped, 19.039s, exit 0.
- Whole Ruff passed; configured no-path mypy passed over 1,424 source files.
- `git diff --check` passed before freeze.
- Preflight: 1,666 MiB workspace, 4,739 MiB scratch, 12,201 MiB available memory.

Native calls are GET-only fixture calls, unchanged after generation through replay,
current read and export. All six checked financial/execution count families remain
zero. PostgreSQL used disposable fixture schemas only, without database reset.
Pytest/PG slot released at terminal; no live, hosted, remote or deployment action.
