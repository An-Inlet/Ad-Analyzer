# Selected Raw Observation Package — 2026-10-11

Resumed existing `codex/inlet-w1-followup` at exactdb4574c after owner request.
No environment reset. All14checkpoint backups and3draft files matched SHA256s;
52baseline archive hashes and52JUnit hashes reverified. Frozen9d7aa2e remains clean
and df89d75 validation documents unchanged. Resume resources:1.9GiBworkspace,
5.8GiBscratch free, cgroup memory11,740,647,424bytes. No exhaustive tests restarted.

Implemented pure raw observation parsers, not activated imports:

- Exact UTF-8 JSON decimal decoding rejects duplicate keys/nonfinite tokens.
  Money uses bounded exact micros with context-independent precision; no truncation.
- Google raw selected-action parsing binds native advertiser/campaign/action, metric
  family, query profile, dates and caller-owned mapping. Count/value remain independent;
  absent selected rows remain absent. Empty pages carry capture/request commitments.
  Unsupported versions/profiles/manager-owned actions reject pending their own verified
  ownership/query support; this parser does not silently narrow overall product scope.
- TikTok raw generic campaign observations preserve base-field presence. Both selected
  metric cells always remain unsupported, even when generic conversion is explicit0.
  Timestamp forms are rejected rather than silently truncated to local dates.

Independent read-only review closed with no remaining P1/P2 in this pure-parser scope.
It identified encoding ambiguity and empty-page binding; both repaired. Review did
not execute tests or qualify provider query/catalog semantics.

## Actual Checks

- First combined cohort:198passed,0.80s.
- Final `python -m pytest tests/test_selected_raw_observations.py tests/test_selected_reporting_contracts.py tests/test_reporting_presence_contracts.py tests/test_reporting_presence_summary.py -ra`: **204passed,0skips,1.65s** (64new raw cases +140prior cases).
- `ruff check .`: passed after formatter addressed initial draft formatting findings.
- `mypy --cache-dir /tmp/inlet-selected-mypy app tests`: passed,1276source files.
- `git diff --check`: passed before commit.

Evidence: `/workspace/inlet-evidence/20261011/selected-raw-observations/`:
`recovery.json`, first/focusedJUnit andlogs, retained initial Ruff findings,
final Ruff/mypy logs. Tests include actual8,000,001-byte and10,001-row negatives,
not only reduced-cap simulation. No database/model/API migration was changed.

## Limits And Next Package

DTO/parsing success is not owned acquisition, durable publication or customer plan
consumption. No Google/TikTok HTTP runtime is wired to these parsers yet. Currency,
account timezone, action catalog ownership, source/session/selection freshness and
atomic final publication remain required. Google query availability/live zero
semantics are not verified; action-segmented missing rows do not become zero.
TikTok selected-event mapping remains unsupported pending exact native evidence.

Next: reviewed durable-selection/capture schema and service ports, currentness/CAS,
calibration privacy transition, export/erasure/restore, then actual import wiring and
plan consumer. Wider August/September range provenance must be real, not rewritten
completion dates. All Q01–Q16 remain partial; six human usefulness gates remain open.
No advertising writes, live provider calls, credentials, purchase, budget change,
website edit, push, hosted retry, merge or deployment occurred.
