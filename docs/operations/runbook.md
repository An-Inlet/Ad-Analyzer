# Ad Analyzer operator runbook

The current production deployment serves the Denticode Ad Analyzer workspace inside the shared
Ad Analyzer platform. New platform resources and environment names use Ad Analyzer naming.

## Launch prerequisites
1. Provision PostgreSQL and configure `DATABASE_URL` through an external secret manager.
2. Configure read-only Google Ads credentials externally; never commit secrets.
3. Keep `AD_ANALYZER_GOOGLE_ADS_WRITE_ENABLED=false` and `AD_ANALYZER_GOOGLE_ADS_EXECUTION_KILL_SWITCH=true` until a human approves non-production execution testing.
4. Run migrations, validation scripts, and backup verification before production traffic.

## Backup and restore
- Take a PostgreSQL logical backup before each migration.
- Restore into disposable PostgreSQL and run `alembic upgrade head` before promoting backups as valid.

## Phase 11.4 execution operations dashboard
- Use `/dashboard/accounts/{account_id}/execution-operations` for the authenticated, operator-only, account-scoped execution operations view.
- The page shows recommendation status, dry-run preflight status, blocked versus successful dry runs, kill-switch state, write-enabled state, and allowlist configuration counts without exposing allowlisted account identifiers.
- Validation errors and planned payloads are redacted before rendering. Review database audit records only in approved investigation environments.
- The dashboard intentionally has no live execution button and no synchronization trigger. It must not import or invoke a live Google Ads client.
- For rollback review, follow each audit row's rollback instructions and compensating-action guidance. Phase 11.4 remains non-live, so rollback normally means discarding the modeled plan unless a future human-approved mutation policy says otherwise.
- Use server-side pagination links for long audit histories; do not export raw customer or campaign payloads from production.

## Incident response
- Activate the kill switch immediately for execution concerns.
- Stop workers before investigation.
- Preserve recommendation and execution audit tables.
- Do not retry live mutations until root cause and rollback instructions are reviewed by a human.

## Step 4 analysis cadence operations

- Review the latest aggregate run state on the workspace dashboard or through
  `GET /api/v1/workspaces/{workspace_slug}/analysis-runs`.
- Post-sync runs should reference one successful account sync. Nightly and weekly runs are
  workspace-wide and do not require that cycle's collector attempt to succeed.
- Treat `analysis_failed` as a separate local-analysis incident. Do not rerun Google Ads collection
  merely because the follow-on analysis failed.
- Validate `workspace_configurations.analysis.cadences` when a workspace has no due runs. Invalid
  values fail closed and logs expose only a fixed configuration failure.
- Keep the seeded Denticode measurement contract draft until its business rules and GA4 source are
  approved. A cadence run with a contract blocker is expected and is not a failed run.
- Never place raw source payloads, click IDs, CRM identifiers, credentials, or PHI in cadence
  configuration, run notes, logs, or incident records.

## Step 7 recommendation generation operations

- Compare each successful analysis run's created and deduplicated counts. A later run with zero
  created and nonzero deduplicated is expected while equivalent proposals remain active.
- Review generated proposals on the account dashboard. Search-term rows must use labels such as
  `Search term #42`; treat any raw query text in a proposal as a privacy incident.
- Generation is capped at 100 proposals per run, ordered by severity and then spend impact.
- A rejection suppresses the equivalent proposal for 14 days. This cooldown is deterministic and
  is not adaptive learning.
- Keep proposals pending until a workspace owner or administrator reviews them. Approval only
  unlocks the existing dry-run planner; it does not enable a live Google Ads mutation.

## Step 8 decision-learning operations

- Review workspace decision evidence on the workspace dashboard or through
  `GET /api/v1/workspaces/{workspace_slug}/decision-learning`.
- Treat fewer than five decisions for one signal/scope/review-action profile as limited evidence.
  The displayed raw rate and the add-one-smoothed rate remain available for audit.
- Confirm newly generated proposals contain `decision_learning.policy_version=v1` and
  `reason_text_used=false`. Actor identities and free-text reasons must never enter learning
  profiles or generated learning payloads.
- Learning can break only an equal-severity, equal-spend tie. Investigate any behavior that changes
  finding thresholds, severity, eligibility, approval requirements, or advertising state.
- Preserve recommendation and recommendation-audit rows. Profiles are derived from those local
  audit facts, so no separate opaque model state needs backup or manual editing.

## Step 9 weekly-learning-report operations

- Review the latest completed Monday-Sunday UTC comparison on the workspace dashboard or through
  `GET /api/v1/workspaces/{workspace_slug}/weekly-learning-report`.
- Use `?as_of=YYYY-MM-DD` to reproduce an earlier completed week. Decisions recorded after that
  week's close must not appear in the historical report.
- Treat suggestions as evidence for a separately scoped product change. The report must never edit
  analyzer rules, thresholds, configuration, recommendations, approvals, or advertising state.
- Investigate missing analysis coverage before interpreting week-over-week changes. A lack of
  successful local runs produces a fixed attention suggestion rather than an inferred diagnosis.
- Treat actor identity, free-text reason, raw search-term text, or cross-workspace content in a
  report as a privacy incident. Version 1 queries select only fixed decision action/timestamp and
  aggregate analysis evidence.
- Preserve analysis, recommendation, and audit history. Reports are reproducible read-only views;
  no separate report table, model training state, or backup procedure is required.

## Final readiness checklist
- CI green; migrations reversible; no secrets in repository; account isolation tests pass; dashboard/API authentication configured; live writes disabled by default.

## Phase 12.1 deployment operations

- Build one immutable container image from `Dockerfile` and run separate `web`, `worker`, `scheduler`, and `migration` processes.
- Source all secrets from the deployment platform secret store; never from committed files.
- Run `python scripts/validate_deployment_startup.py --process migration` before `alembic upgrade head`.
- Verify `GET /health` and `GET /ready` after every restart.
- Roll back by stopping `scheduler`, restoring the previous image tag and environment set, verifying `web`, and then restarting `scheduler`.
- Keep `AD_ANALYZER_GOOGLE_ADS_WRITE_ENABLED=false`, `AD_ANALYZER_GOOGLE_ADS_EXECUTION_KILL_SWITCH=true`, and production allowlists empty.

## Phase 12.2 managed configuration runbook

1. Confirm `APP_ENV=production` only in managed environments that have completed human release review.
2. Inject `DATABASE_URL` and `AD_ANALYZER_API_TOKEN` from external secret references or mounted secret files mapped to environment variables; never commit values.
3. Require PostgreSQL TLS (`require`, `verify-ca`, or `verify-full`) and bounded pool/timeout settings.
4. Run `python scripts/validate_deployment_startup.py --process migration`, then `alembic upgrade head`, then validate and start web, worker, and scheduler.
5. For rotation, create a new secret version, point runtime references to it, validate, restart safely, verify readiness, then revoke the old version.
6. For rollback, restore previous known-good configuration references, keep Google Ads writes disabled, keep the kill switch enabled, and rerun validation before restart.
