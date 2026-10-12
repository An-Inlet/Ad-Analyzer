# Saved Reporting Comparability — 2026-10-12

Baseline: local `08573f22e837f78a8d0704763289f5fac99517ea` on
`codex/inlet-w1-followup`. Local implementation only, no push/new PR.

## Delivered Behavior

Saved plans show Reporting Comparability before Manual Actions, with separate account
currency/time zone, original source/capture lineage, requested reporting periods,
coverage/read time/expiry, and verbatim measurement explanations. Attribution windows,
report-time basis and event equivalence remain explicitly unknown when not retained.
Missing observations stay distinct from measured zero; acquisition ranges do not imply
complete day coverage. No combined metrics, ranking, causal claims or spending authority.

Full workspace/account/connection/platform/version joins refuse foreign, duplicate or
mismatched proof/evidence. Local disclosures reset on rerender and clear on interrupted
reads or session/workspace changes. Default V3, private V4–V6, existing design and
customer manual controls remain unchanged. No API/schema/persistence changes.

The [workflow and interface](design/reporting-comparability-review-v1.md) were defined
before implementation. Independent source review closed after matching-pin and strict
expiry-boundary checks were strengthened with malformed-data regressions.

## Checks Actually Run

One bounded attempt with separate SQLite then PostgreSQL gates:

- Whole `ruff check .`: original exit 0.
- Configured no-path `mypy --cache-dir /tmp/inlet-root-mypy`: original exit 0,
  1,507 source files.
- Focused pytest collection: original exit 0, exact 11 nodes.
- Five component/controller cases: new review rendering, legacy rendering, private
  V5/V6 compatibility, interrupted/repeated reads and late responses after workspace
  or session replacement. Usable, partial/missing, true zero, hostile and malformed
  data covered; no new requests from expanding/collapsing the view.
- Three SQLite plus three PostgreSQL cases: actual create/generate/current/export/replay
  with complete or deliberately missing selected days, and actual local TLS browser
  capture handoff → save/generate → review → historical export.

All 11 tests passed, exact unique XML identities, original exit 0, no errors/skips,
source continuity verified, no remaining process-group members. No qualification
failure this package and no full-suite repeat. Actual API/export artifacts validate
PlanVersion and digests. Exact replay makes no new acquisition. The raw partial fixture
omits September 12 before capture, retains ten September observations and complete
August data; social selected observations are honestly unavailable.

Evidence: `/workspace/inlet-evidence/20261012/reporting-comparability-attempt01/`.
Manifest SHA256 `8d744b160fa306a5162c13839d8a86abd561aa6a32dd4b40cf31c78a56a43f11`.
Completion freeze SHA256 `a37b32fd4a31a8c801c6823f47119813b2b79fb5b943652ec8a0a3ff3e40954d`
binds 100 evidence files and 1,716 application/test sources. `summary.json` lists exact
nodes/results. Post-commit binding remains separate from the immutable freeze.

An executor transport disconnect occurred after qualification/freeze, while attempting
to write this checkpoint. One recovery attempt timed out despite ready status. A later
actual command succeeded and verified all 14 results and no active test runner. This
was an infrastructure interruption, not a test failure; no completed checks restarted.

## Limits And Next Dependency

This is the focused Q09 customer visibility/recovery package, not full Q09. Original
event details are partly retained as verbatim rationale; prose is not parsed into typed
metadata. Genuine Meta leads/TikTok purchases with verified differing attribution need
source-qualified producers and a retained typed event/attribution contract next.

Provider IO is synthetic. Bounded Chromium TLS checks do not qualify BFCache restoration,
general capacity, live providers or production readiness. Historical R01–R03 causes
remain incompletely explained. Six human quality judgments and retention/artifact-sharing
owner decisions remain pending. No push, hosted CI, merge, deployment, credentials,
live provider/model calls, advertising changes or spending occurred.

Independent completion review CLOSED: all 100 evidence and 1,716 source hashes,
11 exact XML passes and all 14 original exits verified. Reviewer independently
recomputed every retained PlanVersion-domain digest across six API/TLS artifact files;
recorded document views match, advertising writes remain disabled and spending authority
is none. No blocker to local commit; qualification limits and human gates unchanged.
