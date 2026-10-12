# Customer Planning Composition — 2026-10-12

Baseline `5ee2a00396e8bb1a1872e71b2aeb21b30578ea50`, branch
`codex/inlet-w1-followup`. Local code and fixture qualification only.

## Implemented

The real customer planning route now resolves `INLET_CUSTOMER_PLANNING_POLICY`.
Absent or explicit `v3` retains the established canonical v3 service default;
explicit `v4` constructs the canonical v4 selected-event requested-window policy.
Blank, unknown and unsupported versions fail Settings validation. A runtime value
that bypasses validation receives a fixed 503 before planner work, not fallback.
The example remains v3. No environment was activated outside test fixtures.

The selector is per-request composition, not mid-request revocation or customer
approval. It does not enable provider connections, token access, campaign mutations,
model calls, media stores or spend. Reporting flags remain false by default and
existing authority/data/revision/consent/receipt checks are unchanged.

Generation selection supports policy v3/v4. Policies v1/v2 remain historical;
v5/v6 are still private pending creative media-store composition and owner-review
qualification. That remaining creative work is not complete. Outer PlanVersion
v1/v2/v3 readers remain unchanged: policy version and document schema are separate
axes. Typed provenance with current request/effective settings still emits outer v3;
older provenance and original/interim readers retain their existing digest rules.

## Qualification

39 unique exact cases passed: 19 component, 10 SQLite and 10 PostgreSQL.
Full Ruff, configured no-path mypy (1,540 files), exact collection and diff passed.
All acceptance cases ran fresh in attempt03; no prior passes were carried forward.
Twelve browser artifact sets retain 36 PlanVersion payloads. Original exit codes,
exact XML identities, source hashes and clean process-group teardown were reconciled.
Evidence: `/workspace/inlet-evidence/20261012/planning-composition-attempt03/`.
Independent review and local commit binding are recorded alongside the final freeze.

New assembled cases parse the real environment setting and assert that the API's
planner constructor remains the real PlanningDocumentService. Synthetic fixtures
replace only SQL/identity/provider transport. Both missing/default and explicit v3
browser journeys generate, correct a source, generate a successor, and read the
unchanged historical export. Configured-v4 journeys cover Google positive/zero/
missing counts and Meta positive counts, capture selection, goal/account/input
save, generation and current/history/export. Google keeps complete pagination and
account-local dates; no unsupported TikTok combination is inferred.

Historical original/interim/v2 storage/export tests remain in the focused selection.
Current outer v3 is validated through retained browser artifacts. Capability tests
cover absent, v3, v4 and defensive invalid config on both databases; invalid config
cannot create a plan or make native reporting calls. Pure invalid-environment tests
reject v1/v2/v5/v6, blank, case/whitespace variants and unknown names.

Attempt01 stopped at configured mypy on four test module-export identity assertions.
Attempt02 stopped at Ruff B009 after the first test-only adjustment. Final assertions
inspect the module namespace directly, without suppressions or new production
exports. All original logs/exits/source snapshots and unrun cases are retained;
no failed run was retried unchanged or counted as acceptance.

Servers use local TLS with startup lifespan disabled. No startup/deployment, real
identity, provider availability, billing purchase or live customer behavior is
qualified. No push, PR, hosted CI, merge, deployment, credential operation,
advertising change or spend occurred. Owner retention/artifact-sharing decisions,
six human quality judgments, Q13 independent provider verification and historical
R01–R03 uncertainty remain open.

## Next Package

Creative planning v5/v6 needs explicit media-store composition and review-boundary
qualification, without bypassing owner decisions. TikTok count support remains
blocked on its exact supported report combination; see the targeted research
handoff. Default-disabled real provider access and all execution holds remain.
