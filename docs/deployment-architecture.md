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

## Google Cloud IAP dashboard authentication

Production `/dashboard` requests require a signed Google Cloud IAP assertion. Configure
`DENTICODE_IAP_AUDIENCE` with the backend service audience (normally
`/projects/PROJECT_NUMBER/global/backendServices/BACKEND_SERVICE_ID`) and configure
`DENTICODE_DASHBOARD_ALLOWED_EMAILS` as a comma-separated, least-privilege list of operator
email addresses. Keep `DENTICODE_API_TOKEN` configured: every `/api/v1` route continues to use
its existing bearer-token authentication, independently of IAP. Do not use
`x-goog-authenticated-user-email` as an authorization input.

Deployment sequence:

1. Create the HTTPS backend and enable IAP, following the Google Cloud change-review process.
2. Grant the IAP-secured Web App User role only to intended operators.
3. Set `APP_ENV=production`, the exact IAP audience, and the allowed-email list in the managed
   runtime configuration; inject `DENTICODE_API_TOKEN` from the secret manager.
4. Confirm `DENTICODE_GOOGLE_ADS_WRITE_ENABLED=false` and
   `DENTICODE_GOOGLE_ADS_EXECUTION_KILL_SWITCH=true` before promotion.
5. Run migrations, start the web process, and verify `/health` and `/ready` through the approved
   ingress. Verify an allowed and a denied IAP identity before starting read-only workers.

The application verifies the IAP JWT signature, audience, expiration, and IAP issuer using the
official Google authentication library and authorizes only the verified JWT `email` claim.
Non-production dashboard access retains the local bearer-token flow; insecure HTTP additionally
requires the explicit loopback-only development setting. No deployment step enables advertising
mutations.

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
