# Reporting To Planning Capture Handoff — 2026-10-12

Implemented locally on `codex/inlet-w1-followup` after `c4224ce`. A customer can now
bring a completed Google reporting capture into a new plan without copying an
opaque ID. Planning removes the transient URL fragment, verifies owner workspace
access and selected-reporting capability, then requires the customer to choose the
account and explicitly apply the capture to a blank field. Other edits remain intact.
Saving and generation remain separate customer actions with existing server checks.

No new API/schema, provider integration, default V3 policy, advertising authority,
retention rule or public website change. Manual Capture ID entry remains supported.
Malformed/foreign hints, changed sessions/workspaces, saved-plan selection, cancel,
unsupported capability and nonblank capture choices cannot silently apply a hint.

The frozen interface, acceptance and current Q01–Q16 reconciliation are in
[Reporting Capture Handoff v1](design/reporting-planning-handoff-v1.md).
This closes a Q01/Q02 customer workflow join, not all planning quality acceptance.

## Checks Actually Run

Final qualification comprises **11 distinct passing tests**, original exits 0, exact
JUnit identities, no errors/skips and verified source hashes:

- Chromium component: new hint parser/lifecycle/application checks and existing
  manual selected-capture entry regression: 2.
- Actual planning controller with controlled Fetch: workspace and session replacement
  during pending Apply, cancellation, saved-plan selection and capability downgrade:
  5. Late responses cannot fill detached fields; no save/generation requests occur.
- Actual TLS browser → customer API → database: handoff journey and existing reporting
  regression on SQLite and PostgreSQL: 4. PostgreSQL started only after SQLite passed.

The handoff journey completes actual range/event/capture APIs, actual navigation,
explicit application, saved selected inputs, lost-save response recovery, generation
and V2 revision. Both databases retain V1 exports before/after V2, validate them as
`PlanVersion` JSON, verify their digests and exact Capture ID, and assert no advertising
or spending authority. The displayed evidence includes selected count 10 and 100
clicks without “spend without conversions” guidance.

Final `ruff check .` passed. Configured no-path
`mypy --cache-dir /tmp/inlet-root-mypy` passed across 1,505 files. Exact focused
collection succeeded. No whole pytest suite was repeated. Test subprocess durations
sum to 115.602744 seconds; this excludes static checks and interrupted/failed attempts.

Provider IO uses injected synthetic transports. TLS browsers run locally with external
network resolution disabled. The new navigation journey bounds renderers and disables
BackForwardCache to fit the execution environment; BFCache restoration, general browser
capacity and live providers are **not** qualified.

## Preserved Failures And Resource Limits

Qualification stopped at each unexpected result; changed fixes and unrun cases used
fresh output paths. Earlier passing component tests were carried only with verified
source continuity.

1. Attempt 01: runner reporting IndexError before any check subprocess launched.
2. Attempt 02: mypy rejected an optional test-fixture runtime access; explicitly bound
   a validated fixture runtime. Original failing source/log retained.
3. Attempt 03: pytest setup could not create basetemp because its parent was absent;
   corrected isolated temporary-directory preparation. Test body never ran.
4. Attempts 04/05: memory guard interrupted SQLite TLS, original exits -15, no XML.
   Headroom was 474,796,032 and 488,288,256 bytes respectively, below the unchanged
   512 MiB floor. Neither interruption is an assertion failure or passing test.
5. Inactive synthetic browser profiles were losslessly archived locally: 189 profiles,
   28,228 regular-file hashes verified before removing source profile directories.
   Logs/XML/exports/fixtures remained in place. This increased headroom from about
   934 MB to 1,264 MB; read-only cache advice alone had not helped. Archive location:
   `/tmp/inlet-inactive-browser-profiles-20261012.tar.gz`.
6. Attempt 06: actual TLS driver waited for Read Current Choice before choosing an
   account, while that button correctly remained disabled. Fixed only the driver’s
   busy indicator; production behavior unchanged.
7. Attempt 07: final SQLite/PostgreSQL cohort and static checks passed. The bounded
   runner preserves original leader exit status, reaps owned descendants, verifies
   process-group extinction and escalates remaining members after a bounded grace.

Historical R01–R03 remain incompletely explained; these results do not explain those
original incidents. No resource floor or assertion was weakened.

## Durable Evidence And Next Package

Evidence: `/workspace/inlet-evidence/20261012/capture-handoff-attempt01` through
`capture-handoff-attempt07`. Final manifest SHA-256:
`f96b5855e763352a3e6dd74b36000de8a3f5f54a2aa3b11fc6bb2ab21e8df2dd`.
Completion freeze covers 198 evidence files and 1,711 application/test files:
`3d99d25301f5b26a351c5c5c5ba349f648d2af0fb978f29c3d3459c98a15ebda`.
Commit binding is recorded separately after the local commit. Independent source
and evidence review closed: all frozen hashes and exact test identities verified,
including applicability of the seven carried component/controller cases.

Next recommended customer package: Q09’s explicit reporting comparability review,
showing missing event/attribution/window alignment without treating social leads as
purchases or summing incompatible conversions. Freeze a bounded interface before
implementation; social selected-observation producers remain a separate prerequisite
to qualified cross-platform comparison.

Six human planning quality judgments, retention and artifact-sharing owner decisions
remain pending. No push, hosted CI, merge, deployment, live provider call or spend.
