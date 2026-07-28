# Phase 12.1 Provider-Neutral Deployment Architecture

This phase defines deployment packaging without choosing a cloud provider or connecting to any production service.

## Processes

- `web`: FastAPI application served by Uvicorn. It exposes `/health` for process health and `/ready` for startup configuration readiness.
- `worker`: one-shot read-only Google Ads sync process for controlled job execution.
- `scheduler`: long-running read-only scheduler that triggers sync jobs on an interval.
- `migration`: Alembic migration process that runs `alembic upgrade head` before a release is promoted.

All processes run the same container image and start with `scripts/validate_deployment_startup.py`.

## Configuration and secrets

Use environment variables or an external secret manager. Never commit populated `.env` files. Required production placeholders are documented in `.env.example`.

`DATABASE_URL` remains supported and must use a PostgreSQL-compatible scheme such as `postgresql+psycopg://...`. Compose includes a local PostgreSQL service for disposable environments only. On Cloud Run, all four process types instead use the same `CLOUD_SQL_CONNECTION_NAME`, `DATABASE_USER`, `DATABASE_PASSWORD`, and `DATABASE_NAME` settings and connect through `/cloudsql/<CLOUD_SQL_CONNECTION_NAME>`. Attach the instance to each service or job and source `DATABASE_PASSWORD` from Secret Manager.

Phase 12.1 preserves safety defaults:

- `DENTICODE_GOOGLE_ADS_WRITE_ENABLED=false`
- `DENTICODE_GOOGLE_ADS_EXECUTION_KILL_SWITCH=true`
- `DENTICODE_ALLOWED_EXECUTION_ACCOUNT_IDS=`
- `DENTICODE_ALLOWED_GOOGLE_ADS_MUTATIONS=`

## Ingress and TLS

`deploy/reverse-proxy.example.conf` shows a neutral Nginx TLS reverse proxy. Certificates and private keys must be provisioned outside the repository.

## Startup and readiness

- `/health` confirms the web process is alive.
- `/ready` validates startup configuration without contacting Google Ads or production databases.
- `scripts/validate_deployment_startup.py --process web|worker|scheduler|migration` fails fast when required safety guards or PostgreSQL URL settings are invalid.

## Graceful shutdown and restart

The Compose example uses `restart: unless-stopped` for persistent services and `stop_grace_period: 30s`. Operators should stop the scheduler before migrations, let in-flight jobs finish, run the migration process, then restart web and scheduler containers.

## Rollback and recovery

1. Keep the previously promoted image tag available.
2. Stop scheduler processes to avoid overlapping work.
3. Restore the previous image tag and environment variable set.
4. Restart `web` and verify `/health` and `/ready`.
5. Restart `scheduler` only after readiness succeeds.
6. For database issues, restore from a verified PostgreSQL backup or run an approved Alembic downgrade only in a controlled maintenance window.

No deployment step should enable live Google Ads writes or disable the kill switch in Phase 12.1.

## Phase 12.2 managed configuration extension

Managed TCP environments should supply `DATABASE_URL`, `DATABASE_SSL_MODE`, pool sizing, timeout, and secret-reference variables through external configuration. Cloud Run may supply the four Cloud SQL socket variables instead; `DATABASE_PASSWORD` is then the database secret and the local socket transport does not require PostgreSQL `sslmode`. The web, worker, scheduler, and migration processes remain separate and must each run startup validation. Migrations run before web, worker, and scheduler startup for a release; rollback means restoring the last known-good secret and environment references, rerunning validation, and restarting processes with writes disabled and the kill switch enabled.
