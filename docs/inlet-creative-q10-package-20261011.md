# Q10 Actual V5 Constraint Join

Base `2059b78`; branch `codex/inlet-creative-q10-qualification`. Test-only package:
new `tests/test_creative_q10_common_basis.py` and its local helper contract. No shared
Q05/Q07/Common Basis fixture or production changes.

Actual owned Meta catalog HTTP fixtures expose campaigns A/B and their children.
An original customer uses the target-catalog API selectors to exclude A, fix B at
USD 200 of the USD 1,000 confirmed goal, and supply one owned image with one global
creative slot. New typed product restrictions include no discount claims and the
existing health/testimonial restriction. Exact V5 create/generate/current/export
and idempotent generation replay are exercised, with unchanged native call count
after generation and all six financial/execution count families remaining zero.

Assertions bind original workspace/account/advertiser and canonical entity keys,
including child parentage; immutable excluded-source evidence remains permissible.
All actionable targets exclude A and its child. B appears once per alternative;
allocations plus reserve equal the exact ceiling, native edits and forecasts remain
unqualified. Exact structured facts/hooks/offer/copy directions, original image
hash, production-required status and unassessed visual/rights statement are checked.
This is bounded structural copy coverage, not human expert assessment of every word.

The separate global freeform-constraint variant preserves that input and explicitly
verifies current creative deferral. It does **not** qualify useful creative proposals
under global constraints or complete all Q10 expert acceptance. Social selected-event
performance remains unsupported; there are no live provider calls or ad writes.

## Checks And Preserved Evidence

Durable directory: `/workspace/inlet-evidence/20261011/creative-q10/`.

- `sqlite-01`: stopped at the first case, fixture request key below the API's eight
  character minimum, 422 before generation (1 failed, 3.422s). Preserved log/XML.
  Corrected only the test key to `creative-q10-v5`; no application relaxation.
- `sqlite-02`: 2 passed, 0 skipped, 7.317s, exit 0.
- `both-03`: 4 passed, 0 skipped, 25.260s, exit 0; disposable random PostgreSQL
  schemas and SQLite, no database reset.
- Whole Ruff passed; configured no-path mypy passed over 1,419 source files.
- `git diff --check` passed before freeze.

Each final database/variant has separate generated document and export JSON plus
SHA-256 manifest, copied from temporary test artifacts into `both-03/`. Corrected
SQLite artifacts are retained separately. `evidence-manifest.json` hashes the logs,
XML and artifact files. Evidence stays local; no upload, push or hosted execution.
Preflight available: workspace 1,652 MiB, scratch 4,782 MiB, memory 12,248 MiB.
The pytest/PG slot was released immediately after terminal completion.
