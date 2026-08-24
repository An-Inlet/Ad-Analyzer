# Phase 12.2 Managed Infrastructure Configuration

This guide documents configuration only; operators retain control of infrastructure deployment.

## Database

Local, Docker, test, and existing managed deployments may continue to set `DATABASE_URL`. Production TCP URLs require a PostgreSQL scheme, hostname, database, non-placeholder password, and `sslmode=require`, `verify-ca`, or `verify-full` (in the URL or `DATABASE_SSL_MODE`).

For Cloud Run, attach Cloud SQL instance `totemic-alchemy-502420-p4:us-west1:ad-analyzer-postgres` to every web service, worker job, scheduler job, and migration job. Set `CLOUD_SQL_CONNECTION_NAME`, `DATABASE_USER`, `DATABASE_PASSWORD`, and `DATABASE_NAME`; the application constructs a psycopg URL using `host=/cloudsql/<connection-name>`. Use `ad_analyzer_app` and `ad_analyzer` for the production user and database, and inject only the password from Secret Manager. Do not require PostgreSQL `sslmode` for this local Unix socket: Cloud Run's Cloud SQL integration secures the connection to Cloud SQL. Partial socket configuration fails startup validation.

Tune `DATABASE_POOL_SIZE`, `DATABASE_MAX_OVERFLOW`, `DATABASE_CONNECT_TIMEOUT_SECONDS`, and `DATABASE_POOL_RECYCLE_SECONDS` for the managed database.

## Secrets

Required production secrets are listed in `AD_ANALYZER_REQUIRED_SECRET_NAMES`. Use `AD_ANALYZER_API_TOKEN,DATABASE_PASSWORD` for Cloud SQL socket deployments; the default `DATABASE_URL` entry is also interpreted as `DATABASE_PASSWORD` when socket configuration is selected. Values must come from environment variables injected by an external secret manager or from file-mounted secrets that are mapped into environment variables by the runtime. Do not commit secrets. Placeholder values such as `replace-with-external-secret` are rejected in production validation. Rotate by creating a new secret version, updating the runtime reference, running startup validation, restarting one process group at a time, and revoking the old version after verification.

## Processes

Run separate web, worker, scheduler, and migration processes. Run migration validation and `alembic upgrade head` before starting web, worker, or scheduler for a release. Configure concurrency and timeouts with `AD_ANALYZER_WEB_CONCURRENCY`, `AD_ANALYZER_WORKER_CONCURRENCY`, `AD_ANALYZER_SCHEDULER_CONCURRENCY`, `AD_ANALYZER_*_TIMEOUT_SECONDS`, and `AD_ANALYZER_GRACEFUL_SHUTDOWN_SECONDS`. Web and scheduler may restart on failure; worker and migration jobs should be observable one-shot processes.

## Validation and rollback

Run `python scripts/validate_deployment_startup.py --process web|worker|scheduler|migration` before process start. Readiness checks do not call Google Ads or other advertising services. If configuration validation fails, roll back to the last known-good secret references and environment values, keep writes disabled, keep the kill switch enabled, rerun validation, and only then restart processes.

## Human decisions still required

Humans must still choose hosting, managed PostgreSQL, external secrets, monitoring destinations, backup retention, production credentials, production database connection, and final Phase 12.4 release approval. No live Google Ads writes or production deployment are approved by this guide.
