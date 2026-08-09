# Post-sync, nightly, and weekly analysis cadences

## Purpose and scope

Improvement step 4 makes the existing deterministic analyzers run on a predictable schedule. It
does not add new analysis rules. Each run reads only synchronized local database rows, executes the
existing account-level finding rules and Step 3 aggregate outcome service, then stores a sanitized
`analysis_runs` audit summary.

This step does not contact Google Ads, GA4, BigQuery, Meta Ads, CRM providers, or notification
services. It does not create recommendations, learn from operator decisions, invoke executors,
upload conversions, or mutate campaigns. Those remain separate later roadmap units.

## Default policy

Cadences are resolved separately for each workspace from
`workspace_configurations.analysis.cadences`. When that object is absent, the fail-safe version 1
defaults are:

| Cadence | Default | Metric window | Outcome cohort window |
|---|---:|---:|---:|
| Post-sync | After every successful account sync | 7 completed days | 7 mature cohort days |
| Nightly | 02:00 UTC | 30 completed days | 30 mature cohort days |
| Weekly | Monday at 03:00 UTC | 90 completed days | 90 mature cohort days |

The long-running scheduler checks whether nightly and weekly periods are due after each sync-cycle
attempt. It runs a due period once even when that sync attempt failed, because scheduled local
analysis does not depend on a new collector success. It does not backfill every missed historical
period after downtime. The one-shot sync worker runs only the post-sync cadence.

An optional workspace override has this shape:

```json
{
  "cadences": {
    "version": "v1",
    "post_sync": {"enabled": true, "window_days": 7},
    "nightly": {"enabled": true, "hour_utc": 2, "window_days": 30},
    "weekly": {
      "enabled": true,
      "weekday_utc": 0,
      "hour_utc": 3,
      "window_days": 90
    }
  }
}
```

`weekday_utc` uses Monday `0` through Sunday `6`. Window lengths are limited to 1–366 days.
Unknown fields, unsupported policy versions, invalid times, and invalid window lengths fail closed
for that workspace. Other valid workspaces continue.

## Idempotency and failure behavior

Every run has a workspace-bound deterministic key:

- post-sync: the successful source job-run ID;
- nightly: the workspace and scheduled UTC date; and
- weekly: the workspace and scheduled UTC week occurrence.

Database uniqueness prevents a repeated scheduler tick from creating duplicate runs. Post-sync
runs also use compound foreign keys so a source job or advertising account cannot cross workspace
boundaries.

A successful data sync remains successful if its later analysis fails. The analysis run records a
separate `failed` status with the fixed code `analysis_failed`; it never stores exception messages,
raw source payloads, credentials, analytics identifiers, CRM identifiers, or protected health
information. The scheduler does not automatically re-run the same failed period under another key.

## Stored and displayed data

The run registry stores only:

- workspace/account scope and source job reference;
- cadence, scheduled time, policy version, metric window, and mature outcome window;
- counts of accounts, deterministic findings, high-severity findings, outcome campaigns, and
  attributed/unattributed journeys;
- aggregate outcome-readiness state and fixed blocking reason codes; and
- status timestamps and a fixed failure code.

Operators can read this history through
`GET /api/v1/workspaces/{workspace_slug}/analysis-runs` or the authenticated workspace dashboard.
Neither view exposes the internal run key, raw or digested click/user/session/lead identifiers,
search-term text, or source payloads.

The seeded Denticode measurement contract remains draft. Cadence runs therefore record the
contract blocker and do not treat outcome analysis as ready until the separately approved Step 2
and Step 3 activation decisions are complete.
