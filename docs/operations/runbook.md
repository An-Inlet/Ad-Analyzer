# Denticode Ads Analyzer operator runbook

## Launch prerequisites
1. Provision PostgreSQL and configure `DATABASE_URL` through an external secret manager.
2. Configure read-only Google Ads credentials externally; never commit secrets.
3. Keep `DENTICODE_GOOGLE_ADS_WRITE_ENABLED=false` and `DENTICODE_GOOGLE_ADS_EXECUTION_KILL_SWITCH=true` until a human approves non-production execution testing.
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

## Final readiness checklist
- CI green; migrations reversible; no secrets in repository; account isolation tests pass; dashboard/API authentication configured; live writes disabled by default.

## Phase 12.1 deployment operations

- Build one immutable container image from `Dockerfile` and run separate `web`, `worker`, `scheduler`, and `migration` processes.
- Source all secrets from the deployment platform secret store; never from committed files.
- Run `python scripts/validate_deployment_startup.py --process migration` before `alembic upgrade head`.
- Verify `GET /health` and `GET /ready` after every restart.
- Roll back by stopping `scheduler`, restoring the previous image tag and environment set, verifying `web`, and then restarting `scheduler`.
- Keep `DENTICODE_GOOGLE_ADS_WRITE_ENABLED=false`, `DENTICODE_GOOGLE_ADS_EXECUTION_KILL_SWITCH=true`, and production allowlists empty.

## Phase 12.2 managed configuration runbook

1. Confirm `APP_ENV=production` only in managed environments that have completed human release review.
2. Inject `DATABASE_URL` and `DENTICODE_API_TOKEN` from external secret references or mounted secret files mapped to environment variables; never commit values.
3. Require PostgreSQL TLS (`require`, `verify-ca`, or `verify-full`) and bounded pool/timeout settings.
4. Run `python scripts/validate_deployment_startup.py --process migration`, then `alembic upgrade head`, then validate and start web, worker, and scheduler.
5. For rotation, create a new secret version, point runtime references to it, validate, restart safely, verify readiness, then revoke the old version.
6. For rollback, restore previous known-good configuration references, keep Google Ads writes disabled, keep the kill switch enabled, and rerun validation before restart.
