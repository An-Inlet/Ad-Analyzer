# Injected Google Aggregate Range Reader — 2026-10-11

Branch codex/inlet-google-range-read. Interfacef703426; based on eaf12e9 with exact
resolver repair cherry-picked as c159b73 (canonical repairbf0dc5d). Independent
range files only: app/google_connections/range_http.py and focused test module.

Actual injected v24 HTTP metadata/inventory/campaign-day queries for explicit closed
local ranges1..400days. Requires all five raw aggregate metrics; no legacy zero
defaults/rounding, no selected-action identity. Exact decimal conversions, integer
cost micros, exact conversion-value→micros. Missing fields reject; absent rows stay
absent. Result bound to entire request/owned original-session base digest, exact
native inventory joins, full pagination, units, dates and UTC deadlines. Total100pages
(including metadata),50000combinedrows,32MiB raw and canonical result,60s bounds.
No automatic descriptor registration, factory, SQL finalizer, route or grant getter.

Final checks:
- Focused pytest range/catalog/selected HTTP modules:92passed0skips.
- Whole repository Ruff: pass.
- Whole mypy:1299source files, pass (scratch cache).
- git diff --check: pass.

Durable /workspace/inlet-evidence/20261011/google-aggregate-range/ includes
final-focused.xml/.log, final-ruff.log, final-mypy.log and diff-check.log. Initial
35case range run also passed. Initial scopedmypy unused-ignore and later Ruff test
lambda-style finding logs retained; both repaired. No broad baseline or DB tests
for this pure HTTP package. No remote/provider/live/hosted/push calls.

Exact61day August1–September30 America/New_York query tested through actual paginated
MockTransport. Both metric families remain selected-reader work; this result reports
Google generic metrics.conversions only. Tests cover all five missing/null fields,
explicit zero versus empty rows, sparse records, foreign/mismatched/dangling/duplicate
identities, malformed dates/money/precision, rawduplicateJSON, repeated cursors,
100page/50000row/32MiB failures, blocked-authorizer and stream deadlines, copied DTOs,
private request commitment and no provider registration. Resource reserves maintained:
workspace1386MiB/scratch5847MiB available at final checks.

Remaining root integration: actual owned SQL aggregate finalization/current pointer,
selected capture range orchestration, customer planning consumer. DTOs/MockHTTP do
not establish live v24 compatibility or Q01/Q02 acceptance. Actual omitted required
provider cells cause unavailable instead of fabricated zero. Campaign inventory is
not ad-group evidence. No conversion maturity, source atomic snapshot or spending
permission is inferred. Resolver independent review remains a prerequisite for its
own integration; this range package does not change authorization internals.
