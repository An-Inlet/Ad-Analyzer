# Q13 Pure Field Comparison Checkpoint

Added an isolated comparator for exact plan/action proposals and normalized typed
field snapshots. It verifies snapshot bytes/digest, source/target identity, privacy,
extraction contract and observation interval; returns matching, conflicting or
unavailable results without attributing an implementation, change time or lift.
Customer reports and retractions remain separate immutable records. Existing event
DTOs, storage bytes, runtime routes and default planning behavior are unchanged.

The caller supplies admission inputs; this pure function does not authorize a read
or qualify provider semantics. Fixtures are synthetic. Current valid actions permit
only one proposed field, so partial/mixed comparisons remain a schema prerequisite,
not claimed positive coverage. No qualified native field producer or observation
writer exists. This is a prerequisite for Q13, not completed Q13 acceptance.
See the [shared interface and remaining joins](design/q13-field-comparison-boundary-20261012.md).

## Verification

Final evidence packet: `/workspace/inlet-evidence/20261012/q13-pure-comparison04`.
Manifest SHA-256:
`b558ea5d6f001d54c39792e95132d49bd3bb5db1632dae5d4a5432e440fce776`.
Whole Ruff, configured mypy (1,560 files), exact test collection and diff checks
passed. Runtime: 35 new comparator cases and 52 existing document contracts passed
(87 total), no skips. The two groups took 3.186399s and 2.179402s. Source integrity
verified; no interruption, escalation or surviving process-group members.

Coverage includes positive/conflicting/missing facts; exact ownership, generation,
privacy, source, digest and time refusals; URL/country ordering; unsafe model copies;
unsupported and account-level actions; report/retraction separation; reserved export
serialization and foreign-row refusal. Export checks exercise pure serialization,
not database/API workflows. No database, browser or live-provider test is claimed.

Earlier packets remain separate: attempt01 stopped on Ruff line length; attempt02
on test-fixture mypy inference; attempt03 passed static checks and 25 runtime cases,
then stopped on an invalid unsupported-budget fixture. Its remaining 61 cases were
unrun. The corrected fixture uses a valid unsupported-status action; production
code did not change after attempt03. These results are not added to the final count.

## Next Package And Release Limits

Implement the distinct read-only observation history renderer. Validate historical
chronology against event time, not wall-clock age. The browser can verify payload
structure/scope/derived status; it cannot recompute facts digests or prove action
binding without facts/the original document. Preserve all-or-nothing page rendering,
text-only values and report/retraction behavior. No fake producer or writer.

Branch `codex/inlet-w1-followup`; local checkpoint only. No push, PR, deployment,
provider call, payment or advertising action. V6 remains default-off but explicitly
selectable, unqualified, with INLET-REL-20261012-01 open. This package does not close
the reliability incident, external qualification or commercial/usefulness gates.
