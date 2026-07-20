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
