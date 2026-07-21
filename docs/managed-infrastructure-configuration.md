# Phase 12.2 Managed Infrastructure Configuration

This guide is provider-neutral. It does not select, purchase, activate, or deploy infrastructure.

## Database

Set `DATABASE_URL` to a PostgreSQL-compatible URL supplied by an external secret reference. Production validation rejects SQLite, malformed URLs, empty values, and placeholder passwords. Use `DATABASE_SSL_MODE=require`, `verify-ca`, or `verify-full`; a URL `sslmode` query parameter is also accepted. Tune `DATABASE_POOL_SIZE`, `DATABASE_MAX_OVERFLOW`, `DATABASE_CONNECT_TIMEOUT_SECONDS`, and `DATABASE_POOL_RECYCLE_SECONDS` for the selected managed database after human provider selection.

## Secrets

Required production secrets are listed in `DENTICODE_REQUIRED_SECRET_NAMES`. Values must come from environment variables injected by an external secret manager or from file-mounted secrets that are mapped into environment variables by the runtime. Do not commit secrets. Placeholder values such as `replace-with-external-secret` are rejected in production validation. Rotate by creating a new secret version, updating the runtime reference, running startup validation, restarting one process group at a time, and revoking the old version after verification.

## Processes

Run separate web, worker, scheduler, and migration processes. Run migration validation and `alembic upgrade head` before starting web, worker, or scheduler for a release. Configure concurrency and timeouts with `DENTICODE_WEB_CONCURRENCY`, `DENTICODE_WORKER_CONCURRENCY`, `DENTICODE_SCHEDULER_CONCURRENCY`, `DENTICODE_*_TIMEOUT_SECONDS`, and `DENTICODE_GRACEFUL_SHUTDOWN_SECONDS`. Web and scheduler may restart on failure; worker and migration jobs should be observable one-shot processes.

## Validation and rollback

Run `python scripts/validate_deployment_startup.py --process web|worker|scheduler|migration` before process start. Readiness checks do not call Google Ads or other advertising services. If configuration validation fails, roll back to the last known-good secret references and environment values, keep writes disabled, keep the kill switch enabled, rerun validation, and only then restart processes.

## Human decisions still required

Humans must still choose hosting, managed PostgreSQL, external secrets, monitoring destinations, backup retention, production credentials, production database connection, and final Phase 12.4 release approval. No live Google Ads writes or production deployment are approved by this guide.
