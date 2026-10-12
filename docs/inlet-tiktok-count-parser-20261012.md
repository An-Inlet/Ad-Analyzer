# TikTok Count Parser Checkpoint — 2026-10-12

Baseline `a2b8ca51`, branch `codex/inlet-w1-followup`. Pure parsing implementation;
no provider acquisition, storage, supported capture, runtime registration or activation.

## Implemented And Qualified

`app/tiktok/count_contracts.py` defines immutable query, campaign scope, row, page and
proposed retained-proof DTOs. `count_parser.py` parses bounded offline byte envelopes.
The finite query binds owned scope identifiers, account timezone, inclusive closed
1–30-day dates, exact `complete_payment`, regular auction/TT_ADS_PLATFORM description,
campaign/day grain, STATUS_ALL intent and a maximum 100-campaign partition. These
supplied descriptions are untrusted inputs, not proof of native campaign eligibility.
No HTTP query serializer is claimed; exact filtering wire syntax remains a prerequisite
to that later layer. Existing unverified profiles and CaptureSettings are unchanged.

Strict JSON rejects duplicate keys/nonfinite constants, including ignored envelope
fields. Returned dates require account-local midnight grammar and requested range;
foreign campaign, unsupported dimensions/metrics, malformed/null/negative/nonfinite/
overprecision counts, duplicate rows and inconsistent pagination refuse. Explicit
numeric zero remains present; dash/omitted metrics remain missing; absent campaign/days
are never synthesized. Money is unsupported and effective attribution unknown.

Page evidence retains request/query/body digests, request ID, acquisition time and
normalized throttle presence, not raw headers/bodies or error text. Every observed
throttle value is unqualified, including empty/zero, because no value vocabulary has
been justified. Case-insensitive duplicate throttle headers refuse. Header absence is
explicitly retained but never interpreted as positive uncapped evidence. Pagination
requires exact contiguous pages, stable totals/scope, unique provider rows and matching
raw row count; repeated request IDs are allowed. Acquisition timestamps must be within
60 seconds and nondecreasing. This is pure evidence validation, not an IO timeout or
authenticated acquisition implementation.

## Retained Proof Boundary And Precise Blocker

`TikTokCountProofV1` is a strict serializable proposal, not persisted. It admits only
`unknown` or `warning_present` uncapped state and unknown capability. It cannot admit
a caller-supplied positive Boolean or supported state; `require_complete_capture()`
always refuses. This preserves the difference between internally consistent returned
pages and a complete underlying report. Empty page_info shapes remain unavailable
until their exact source semantics are established, never verified zero.

The supplied official evidence establishes the synchronous 20,000-ad cap and a warning
header, but does not establish a positive, query-bound predicate proving that the cap
did not omit data. Header absence, few campaigns, few returned rows, complete pages,
or date splitting do not supply that predicate. Without it no supported durable capture
can be justified. A later positive proof must have documented semantics and qualified
acquisition provenance; it cannot be an arbitrary `uncapped=True` input.

Before persistence: review the exact additive proof/capture schema and reader floor;
commit proof to capture digest; qualify strict storage/export/history/erasure; preserve
all old payloads/digests. No existing capture or settings schema was widened here.
Unknown pure proof may be inspected in tests but is not inserted into customer data.

## Checks Actually Run

64 exact pure cases passed, no skips/errors. Full Ruff, configured no-path mypy
(1,546 source files), exact collection and `git diff --check` passed. No database,
browser, HTTP or live checks ran because this package introduces none of those paths.

- Attempt01: Ruff import-order failure, exit1; later checks and behavioral tests unrun.
- Attempt02: Ruff passed; mypy stopped on five type errors, exit1; later checks and
  behavioral tests unrun. Corrected literal annotation, required fixture descriptions,
  tuple type and unused ignore. Independent review identified nonfinite JSON constants
  in ignored fields; rejection callback and three regressions added before qualification.
- Attempt03: all four static checks passed. Exact collection discovered 64 node IDs.
- Attempt04: identical 1,856 source hashes verified against03, static result references
  retained explicitly; 64 frozen exact nodes passed in one bounded component invocation.

Evidence: `/workspace/inlet-evidence/20261012/tiktok-count-attempt01/` through
`attempt04/`, preparation scripts under `tiktok-count-preparation/`. Original exits,
logs, XML, source snapshots and unrun dispositions retained. One heavy slot, required
resource floors, bounded process group cleanup and source checks before/after used.
Final independent review/freeze/commit binding are stored beside attempt04 evidence.

No push/PR/hosted CI/merge/deployment, live provider/model operation, credentials,
customer advertising change or spend. Default v3 unchanged, v5 remains explicit,
v6 private; planning remains manual-action-only. Both pending owner decisions, six
human quality judgments, Q13 verification and R01–R03 uncertainty remain open.
Next step is targeted positive uncapped-completeness evidence, then reviewed durable
proof integration if justified; unrelated approved offline work can continue meanwhile.
