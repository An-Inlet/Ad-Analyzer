# Selected Plan Arithmetic Foundation — 2026-10-11

Private pure types now bind one full selected capture per account to its exact
source fence, aggregate, selection/request/capture commitments and complete sorted
campaign mapping. Window projections preserve account-local closed days and
independent count/value presence; omitted days never qualify as zero. Projection
validation recomputes every summary from the full graph rather than trusting a
hash or supplied summary.

Strict summary DTOs reject boolean/float/string coercion of integer day counts and
money, and reject binary floats/booleans for decimal counts. Exact decimal JSON
strings remain roundtrippable. The existing public summary helper now uses a
validated indexed context, reused once per capture inside a multi-window
projection. Whole-capture parsing, indexing and hashing do not repeat per window.
This is arithmetic/provenance evidence, not owned SQL proof, catalog authority or
an enabled planning policy. No V3 evidence is fabricated and v4 remains unavailable.

Evidence under `/workspace/inlet-evidence/20261011/`:

- `selected-plan-pure`: first 33-case pass; review identified coercible dataclass
  values and repeated whole-graph work despite those passing cases.
- `selected-plan-pure02`: strict repair run had one expected-error-message mismatch
  because invalid native IDs now fail earlier. Failure evidence retained.
- `selected-plan-pure03`: 48 tests passed, including unsafe copies, strict type
  negatives and one-index-per-capture instrumentation. Initial mypy exponent-type
  finding retained alongside the corrected run.
- `selected-plan-pure04`: 113 tests passed, zero skips/errors/failures, 0.657 seconds;
  includes overlapping prior summary/contract regressions. Whole Ruff and mypy
  passed (1316 source files after reviewed dependency integration). Diff check clean.

The evidence is local and pure. Original-session selected reads, current retained
witnesses, commerce/catalog collection, composer integration, actual browser-to-plan
flow and human usefulness qualification remain separate dependent work.
