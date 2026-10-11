# Google Owner Proof: Observed Metadata Status

The standalone owner contract was reviewed and integrated as `bb5fdfd` (author
`3112dbb`). Its final focused30 cases passed after the source-revision repair;
the earlier104 compatibility cases and retained fixture failures are separately
recorded in the types ledger. Root whole Ruff/mypy1,436 passed at that integration.

A root check against actual Q06 API artifacts found a runtime prerequisite that
the pure fixture did not establish: the existing metadata reader requested only
campaign resource/name and discarded campaign status. Those historical complete
catalogs have metadata status=None, while native status is ENABLED. The new strict
proof correctly refuses them. The first artifact-check assertion expected eligibility
and failed; the corrected record preserves status-unavailable for the two complete
artifacts and coverage-unavailable for the two partial artifacts. No old artifact
or receipt was modified, and no profile condition was relaxed.

The narrow repair adds campaign.status to the same bounded read-only Google query
and retains the returned field. Missing/null stays None; contradictory or unknown
status cannot qualify an owner, and malformed booleans fail metadata parsing.
Fresh metadata digests change naturally; historical reconstruction is unchanged.

## Checks Actually Run

- Before repair: the new observed-status test failed, preserved in before.log/XML.
- After repair: six HTTP-to-metadata-to-projection-to-owner variants plus relevant
  owner/metadata regressions passed:54 tests, 3.36s.
- Strengthened actual Q06 API cohort:4 SQLite/PostgreSQL tests passed,54.39s. Complete
  A/B snapshots now derive the exact two-member owner witness; partial membership
  still refuses. Existing replay/export, original session, arithmetic and zero
  financial/execution effects remain checked.
- Whole Ruff and configured no-path mypy passed over1,437 files; diff check passed.
- Root independently verified12 new artifact hashes, four strict document/export
  pairs, two actual complete-owner witnesses and two expected partial refusals.

Evidence: `/workspace/inlet-evidence/20261011/google-owner-metadata-status/`.
Old artifact findings: `google-budget-owner-integration/old-actual-artifact-check.json`.
Early scoped formatting errors were corrected before final static checks. All failed
and corrected attempts remain retained. No API/browser repeat beyond this bounded
changed-surface cohort was performed.

This qualifies observed owner facts only, not a daily spending cap, provider-valid
setting or native edit. Receipt-backed discovery is the next separate reviewed
slice. No provider/model call, advertising write, push, hosted retry, upload, merge
or deployment was performed; the original browser409 remains open.
