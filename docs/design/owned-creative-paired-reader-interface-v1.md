# Owned Creative Paired Reader V1

Internal preparatory collector combining already reviewed ports. No service,
capability, repository, history or UI activation; default v3 remains unchanged.

Add `OwnedCreativePairedReader(sessions,*,principal,provider,policy,store,clock)` in
`creative_paired_reader.py`, exposing `collect(ticket)->CreativePairedEvidenceV1`.
Snapshot the original principal. Revalidate genuine canonical v5 policy/ticket,
explicit selected and typed creative input, and exact original actor/session before
provider, native or storage I/O. Require full canonical policy digest via the
shared validator; never construct a fake v4 ticket, strip fields or retag output.

Use OwnedSelectedPairedReader.collect and OwnedPlanningImageReader.collect_pinned
on the same original ticket, principal and provider. Retain the complete actual
returned reporting and private image evidence. Their existing bounded collection,
no-I/O-in-SQL and per-context original authority checks remain intact. Do not wrap
unexpected provider/clock/database failures in a broad source-unavailable catch.

After both collections, open one fresh original-session PlanningReadContexts
context. Under its existing workspace-first transaction, recheck_selected_paired_sources
and recheck_collected_creative on the original ticket and actual returned values.
Supply that context's SQL-only authorize callback and fresh aware UTC clock value.
Require the SQL-returned creative proof to equal the proof derived from the actual
private collection. Repeat final selected recheck after creative locks, and let
context exit revalidate original authority. This catches reporting changes during
image I/O and image changes during reporting/finalization. No identity/storage/native
I/O occurs inside this final transaction. Do not commit/persist anything.

Build/revalidate CreativePairedEvidenceV1 and assert_ticket before return; preserve
all image observation times and the exact selected/traffic proof. This is collection
evidence, not a guarantee of later currentness: future repository persistence must
repeat both rechecks atomically with saved-input/version/privacy/CAS checks.
A caller-supplied server ticket is not itself proof of an input revision's SQL head.

Tests use actual owned fixture ports with mocked native/storage bytes on both
SQLite/PostgreSQL: Google selected/traffic plus owned image and Meta/TikTok unsupported
selected reporting with owned images as available, explicit empty media, exact
original context retained. Mutate reporting during image I/O and image rows between
collection/final recheck; reject session/membership/goal/paid/privacy changes,
wrong/altered policies, wrong original session and mismatched creative inputs.
Assert before-I/O rejection where applicable, no reads under SQL, no new persisted
plan/version/receipt, and no capability registration. Unexpected provider/storage/
clock errors preserve the reviewed underlying boundaries. Run whole Ruff/configured
mypy; coordinate PostgreSQL. This is not actual customer v5 API generation or full
frozen Q03/Q04 acceptance, which still needs atomic service/history wiring.
