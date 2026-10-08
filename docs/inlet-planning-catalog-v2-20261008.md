# P02 Catalog V2 — 2026-10-08

Branch `codex/inlet-planning-catalog-v2`, worktree `/workspace/inlet-planning-catalog-v2`, basec7bb7f2. Concrete metadata/read-operation interface and legacy byte/hash fixtures frozen in8028b1e before collector implementation; root approved. No SQL migration.

Implemented additive `/planning/target-catalog-v2`: separate versioned metadata sidecar, owned provider-visible entity IDs/names for Google/Meta/TikTok and bounded Google adgroups with status/type. V1 remains available. Old Google/Meta/TikTok native observation models, defaults and digest domains are unchanged. Three synthetic serialized legacy fixtures round-trip with identical bytes and exact hashes.

V2 explicitly separates original native settings coverage from metadata coverage, with original and metadata read intervals, earliest actual expiry and non-atomic status. Meta known-effective-status and TikTok regular-family limitations remain partial. Missing names and names over the160-character display bound become null with explicit missing/over_bound provenance; no truncation. Names are plain data including literal HTML-like text; no UI HTML rendering was added. Google adgroups have no invented legacy campaign settings. Social budget ownership remains unresolved.

Each metadata HTTP request re-resolves current session/source/credentials before and after IO. No DB transaction spans HTTP. Final native operation and API checks preserve source generation, entitlement, read control and earliest expiry. Metadata binder validates actual owned advertiser/source/period against copied digests. Canonical entity IDs are stable lookup identifiers; snapshot selectors bind source generation and composite digest, never authority. Exact native settings/parent/owner links reject swaps, omissions and fabricated keys.

Limits:200 entities per kind,400 total,10 pages per kind, fixed endpoints/fields,20 metadata HTTP calls, bounded response bytes and60-second read deadline within the original native expiry. No new TTL; metadata cannot extend existing evidence. Pagination changes/cycles and capacity breaches fail; no truncated complete response.

Checks actually run:

- Golden/contract/binding plus V2 and retained V1 API cohort with SQLite and isolated disposable PostgreSQL schemas: **211 passed in191.69s**, no skips.
- During independent review, tightened final correspondence to reject replacement/omission of native targets. After this change: final pure golden/binding/pagination **22 passed in0.40s**; actual V2 positive paths across both databases **6 passed in9.40s** (120 intentionally deselected).
- Whole `ruff check .`: passed. Whole `mypy`: passed1003 source files. `git diff --check`: passed.

Adversaries cover metadata-phase original-session revocation, source rotation, expiry, foreign advertiser/resource, duplicates, capacity, missing parent; contract attacks swap settings keys, forge canonical/snapshot/owner keys, copy hashes to foreign scope, replace/drop native targets and forge coverage. Missing/overbound names have successful explicit-unavailable responses. Cycle/changed-page tests deny for all three providers. HTTP tests are real MockTransport calls through concrete provider readers with synthetic identity/vault fixtures only; no execution mandate or capability bypass.

Exploratory failures were fixture issues: OAuth form data was initially decoded as JSON by the new mock handler; the old Meta handler required budget fields on metadata-only reads. Corrected fixture request classification and explicit metadata response branch. Initial strict-schema review findings were fixed before this frozen implementation: exact settings/key/owner correspondence, actual advertiser/source binding and platform coverage matrix. No provider deadline/authority guard was weakened.

Raw evidence: `/workspace/inlet-evidence/20261008/planning-catalog-v2/`. Independent final review requested; root integration pending. No live provider, hosted environment, production latency, deployment or merge qualification. Remaining: planning consumers/UI and comprehensive plan evidence/scenarios/briefs; catalog is not completed comprehensive planning. Existing legacy settings coverage remains explicitly separate from metadata coverage.
