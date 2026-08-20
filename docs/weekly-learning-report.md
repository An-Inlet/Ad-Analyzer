# Weekly learning report

## Purpose and output

Improvement step 9 turns local analysis activity and Step 8 operator-decision evidence into a
deterministic weekly product-improvement report. The report compares the latest fully completed
Monday-Sunday UTC week with the preceding week, then proposes bounded improvements to the Ad
Analyzer's diagnostics, explanations, or review experience. Suggestions are evidence for a future
human-reviewed implementation task; they are not advertising recommendations and are never
applied automatically.

The latest report is available through
`GET /api/v1/workspaces/{workspace_slug}/weekly-learning-report` and the authenticated workspace
dashboard. An optional `as_of=YYYY-MM-DD` query resolves the latest week completed before that UTC
date, which makes prior weeks reproducible without storing another copy of source evidence.

## Evidence compared

For each workspace, version 1 reports current and prior totals for:

- successful post-sync, nightly, and weekly local analysis runs;
- deterministic findings and high-severity findings;
- generated and deduplicated review proposals; and
- first approve/reject decisions and their observed acceptance rate.

The report also uses the Step 8 all-history learning profiles as they existed at the close of the
report week. Later decisions are excluded from historical reports. Actor identity and decision
reason columns are not selected by the weekly activity query, and neither appears in report
objects, API responses, or dashboard output.

## Version 1 suggestion policy

The report emits fixed, explainable suggestions when evidence crosses a bounded condition:

- restore analysis coverage when no successful run exists for the week;
- collect more operator decisions while profile evidence is absent or limited;
- review the precision, rationale, and supporting metrics of an established profile at or below
  40% observed acceptance;
- investigate a week-over-week acceptance decline of at least 20 percentage points when both
  weeks contain at least three decisions;
- add diagnostic context when findings per successful run rise by at least 25%; and
- add trend context when at least 75% of four or more proposal evaluations are safely
  deduplicated.

At most three low-acceptance profiles are listed, with deterministic ordering. If no condition is
met, the report recommends maintaining the current policy and monitoring the next completed week.
The exact counts and rates accompany every suggestion; no opaque model score is introduced.

## Safety and privacy boundary

Weekly learning reports:

- read only workspace-owned database rows and never call collectors, analytics or CRM providers,
  executors, advertising APIs, language models, or notification services;
- never select or expose search-term text, actor identities, free-text decision reasons, source
  payloads, credentials, patient data, or protected health information;
- do not alter thresholds, finding eligibility, severity, analytical confidence, recommendation
  ordering, cooldowns, approvals, configuration, or advertising state; and
- create no schema rows or hidden model state. Historical output is reconstructed from immutable
  audit timestamps and aggregate analysis records through a fixed policy version.

Any suggested analyzer change requires a separate scoped implementation, deterministic tests,
normal pull-request review, and green safety checks.
