# Bounded Selected Google Collection — 2026-10-11

Internal collector snapshots the owned mapping, collects only terminal pagination,
and rejects wrong request bindings, duplicate campaign/day rows, cursor cycles and
capacity/deadline failures. Missing rows remain missing. Partial graphs are discarded
in memory; the caller still must authorize and store under final SQL locks.

Independent review closed with no P1/P2 in this pure collection scope. Actual
MockHTTP metadata and two-page selected reads preserve explicit0 and10 values and
issue only `googleAds:search`. No provider capability, SQL finalization or public
customer flow is claimed by this package.

Final command: `pytest -q tests/test_google_selected_collection.py
tests/test_google_selected_http.py tests/test_selected_raw_observations.py ...`:
**102 passed, zero failures/skips, 1.116s** (18 new collector cases and84 prior cases;
overlaps earlier package counts). Whole `ruff check .` and mypy **1297 files** passed.
Diff check passed. Evidence `/workspace/inlet-evidence/20261011/selected-collection03/`.
Earlier01/02 logs retained, including corrected line-length and test callback typing
diagnostics. Capacity regressions lower constants to test enforcement without large
allocations; they do not claim a full32MiB stress qualification.

No remote/hosted/live/ad-write/merge/deploy operation. Next original-session resolver,
customer confirmation and actual capture finalization use the frozen interfaces.
