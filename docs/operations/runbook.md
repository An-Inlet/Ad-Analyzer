# Denticode Ads Analyzer operator runbook

## Launch prerequisites
1. Provision PostgreSQL and configure `DATABASE_URL` through an external secret manager.
2. Configure read-only Google Ads credentials externally; never commit secrets.
3. Keep `DENTICODE_GOOGLE_ADS_WRITE_ENABLED=false` and `DENTICODE_GOOGLE_ADS_EXECUTION_KILL_SWITCH=true` until a human approves non-production execution testing.
4. Run migrations, validation scripts, and backup verification before production traffic.

## Backup and restore
- Take a PostgreSQL logical backup before each migration.
- Restore into disposable PostgreSQL and run `alembic upgrade head` before promoting backups as valid.

## Incident response
- Activate the kill switch immediately for execution concerns.
- Stop workers before investigation.
- Preserve recommendation and execution audit tables.
- Do not retry live mutations until root cause and rollback instructions are reviewed by a human.

## Final readiness checklist
- CI green; migrations reversible; no secrets in repository; account isolation tests pass; dashboard/API authentication configured; live writes disabled by default.

## Execution operations dashboard

The execution operations dashboard is available to authenticated dashboard operators at `/dashboard/accounts/{account_id}/executions`.

Use it to review safe, non-live execution state only:

- confirm the execution kill switch is visible and enabled by default;
- confirm Google Ads writes are visible and disabled by default;
- confirm live account allowlists are reported as empty/configured without exposing account identifiers;
- inspect account-scoped recommendation status, dry-run preflight status, latest dry-run audit status, redacted validation errors, and rollback or compensating-action guidance;
- page through recommendation execution rows without exposing planned action payloads or sensitive identifiers.

The dashboard must not be used to trigger synchronization, import Google Ads clients, perform live mutations, or expose raw API payloads. If a blocked execution attempt appears, keep the kill switch enabled, preserve the audit row, and review the validation errors before generating a new recommendation or dry-run plan.
