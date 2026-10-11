# Owner-Requested Pause — 2026-10-11

**Paused. Do not resume coding, reviews, tests, hosted runs or provider operations
until the owner explicitly resumes.** All six child workers were already completed
and have been told to remain idle. A process inspection found no active validation
or browser process; defunct browser entries remain environment-owned zombies.
No running test had to be interrupted for this pause.

## Exact State

Branch `codex/inlet-w1-followup`. Last implemented/reviewed code commit:
`68b96b7c824ea01cfb0854af85d6ce9e6a47e277` (shared selected-event contracts).
This pause document is a later documentation-only commit; its hash is recorded in
`/workspace/inlet-checkpoints/20261011-selected-event-pause/final-state.json`.

Completed package: immutable explicit customer selection, independent selected
count/value captures, whole aggregate/selection dependency binding, strict presence,
exact IDs and UTC instants. Independent reviewer closed all four reported P2 findings
and found no remaining P1/P2 in the pure-contract scope.140focused tests passed,
Ruff passed and mypy1272files passed. This is not a runtime/import/plan activation.
The exact changed files, commands, earlier warning/type-check repair and evidence
are recorded in [the package ledger](inlet-selected-contract-package-20261011.md).

**Three unfinished, untracked files remain intentionally in the worktree:**

- `app/campaign_performance/raw_cells.py`
- `app/google_connections/selected_presence.py`
- `app/tiktok/presence.py`

These raw parser drafts were written immediately before the pause request. They
have **not** been tested, linted, type-checked or independently reviewed. They have
not been committed as implemented code and are not wired into runtime defaults.
Do not infer their correctness from the contract package's140passing tests.

## Durable Preservation

`/workspace/inlet-checkpoints/20261011-selected-event-pause/` contains verified
byte-for-byte copies of all three drafts, the package test/check logs and JUnit,
three saved design proposals, and `committed-contract.patch` (df89d75→68b96b7).
`preservation-manifest.json` records14files,116,616bytes and individual SHA256s;
`process-check.json` records the process inspection. Additional checkpoint/review
notes and final state are retained alongside it. No unique data was deleted.

Existing exhaustive passing evidence remains at
`/workspace/inlet-evidence/20261010/w1-partitioned-9d7aa2e-c/qualification.json`:
7,011passed/83unchanged parent skips; separately404passed/3allowed historical skips.
Frozen source9d7aa2e and df89d75 validation documentation are unchanged. Original
failed/interrupted attempts remain preserved. No aggregate was restarted.

All new irreplaceable restart material is under `/workspace`, not `/tmp`.
`/tmp/inlet-selected-mypy` is a regenerable cache; losing it does not lose source or
evidence. Workspace copies are local preservation, not an off-machine backup:
no remote push was made. Resume requires the platform to retain or restore this
workspace/checkpoint and existing repository/evidence directories. Do not claim
cloud-environment persistence is guaranteed.

## Resume Instructions — Only After Explicit Owner Resume

1. Read this file and final-state/manifest; check branch/head/status, then verify
   draft hashes before changing them. Preserve the independently qualified9d source.
2. Review the raw parser drafts before testing. Known unreviewed concerns include
   decimal money bounds using ambient Decimal context, missing strict invariants
   on directly constructed TikTok observation DTOs, and provider-profile/query
   compatibility. These are review notes, not measured failures. Do not silently
   turn parsing fixtures into provider capability evidence.
3. Add focused raw-byte tests for exact decimal tokens, duplicate JSON keys,
   zero/missing/null/unsupported, account/event/date/mapping/pagination mismatches,
   precision/overflow and sanitized errors. Review independently before activation.
4. Implement durable owned selection/capture publication, scoped export/erasure,
   fresh source/session/selection checks and atomic checkpoint/outbox integration.
   Existing V3 equality remains unchanged; selected10 and aggregate12 stay distinct.
5. Resolve actual immutable range provenance before August/September acceptance.
   Current Google seven-day/TikTok roughly30-day completions cannot be relabelled.
   Then wire actual planning consumption/API and qualify bounded integration groups.
6. Follow [the Q01–Q16 work and human-review matrix](inlet-quality-next-packages-20261011.md).
   All cases remain partial; six human gates remain open. Prepare concrete packets
   rather than requesting approval for routine authorized engineering.

Google action-segmented zero-row suppression is documented; empty response is not
zero. Exact configured query/ownership semantics and TikTok selected-event mapping
are still unqualified. No owner approval can replace that technical evidence.
No advertising writes, live provider/model calls, credentials, purchases, budget
increases, remote push, hosted retry, merge, deployment or website work are authorized.
