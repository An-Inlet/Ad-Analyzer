# Denticode Ads Optimizer

Denticode Ads Optimizer is a Python 3.12 FastAPI service intended to support controlled Google Ads and Meta Ads optimization workflows. The initial project configuration is intentionally read-only: it does not implement advertising API collectors, write access, or campaign mutations.

## Current capabilities

- FastAPI application with `GET /` and `GET /health` endpoints.
- Pydantic-based application settings.
- SQLAlchemy database session setup for PostgreSQL.
- Alembic migration configuration.
- pytest, Ruff, and mypy development tooling.
- Development Dockerfile.

## Safety model

This project is designed for cautious, auditable ad optimization. Until explicitly implemented and reviewed, the application must not:

- Connect to Google Ads, Meta Ads, OpenAI APIs, or other external services.
- Request or create credentials.
- Upload conversions.
- Change campaigns, budgets, bids, assets, audiences, or targeting.
- Run automated campaign mutations without human approval and dry-run review.

## Windows PowerShell setup

From a PowerShell terminal:

```powershell
git clone <repository-url>
cd Denticode-Ads-Optimizer
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

If PowerShell blocks virtual environment activation, run this command for the current shell session and try activation again:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process
.\.venv\Scripts\Activate.ps1
```

Create a local environment file only if you need to override defaults:

```powershell
Copy-Item .env.example .env
```

Do not put real advertising credentials in `.env` until credential handling has been explicitly requested and reviewed.

## Run the application locally

```powershell
uvicorn app.main:app --reload
```

Open <http://127.0.0.1:8000/health> and expect:

```json
{"status":"ok"}
```

## Run checks

```powershell
pytest
ruff check .
mypy
```

## Docker development image

Build and run the development container:

```powershell
docker build -t denticode-ads-optimizer:dev .
docker run --rm --env-file .env -p 8000:8000 denticode-ads-optimizer:dev
```

## Database and migrations

The default local database URL is:

```text
postgresql+psycopg://postgres:postgres@localhost:5432/denticode_ads_optimizer
```

Override it with the `DATABASE_URL` environment variable when running against a local PostgreSQL instance. Use Alembic for schema changes:

```powershell
alembic revision --autogenerate -m "describe change"
alembic upgrade head
```

## Local read-only API

Start the FastAPI application locally with:

```bash
uvicorn app.main:app --reload
```

Phase 5 exposes versioned read-only advertising data endpoints under `/api/v1`. These API routes read only from the local PostgreSQL database. They do not contact Google Ads, cannot trigger syncs, and cannot mutate Google Ads campaigns, bids, budgets, audiences, or conversions.

All `/api/v1` endpoints require an operator bearer token. `DENTICODE_API_TOKEN` must be a URL-safe opaque token containing only letters, digits, hyphens, and underscores (43–128 characters). Generate one locally with `python -c "import secrets; print(secrets.token_urlsafe(48))"`, then set it in your local environment or uncommitted `.env` file before starting the service. The container must receive the same variable (for example, through `--env-file .env`); protected routes are unavailable if it is not configured. Never commit the token.

Endpoint groups:

- Accounts: `GET /api/v1/accounts`, `GET /api/v1/accounts/{account_id}`
- Account campaigns: `GET /api/v1/accounts/{account_id}/campaigns`
- Campaigns and child data: `GET /api/v1/campaigns/{campaign_id}`, `GET /api/v1/campaigns/{campaign_id}/ad-groups`, `GET /api/v1/campaigns/{campaign_id}/metrics`
- Account metrics: `GET /api/v1/accounts/{account_id}/metrics/summary`
- Sync job visibility: `GET /api/v1/job-runs`, `GET /api/v1/job-runs/latest`, `GET /api/v1/sync-status`

Examples:

```bash
curl -H "Authorization: Bearer $DENTICODE_API_TOKEN" "http://127.0.0.1:8000/api/v1/accounts?platform=google_ads&limit=25&offset=0"
curl -H "Authorization: Bearer $DENTICODE_API_TOKEN" "http://127.0.0.1:8000/api/v1/campaigns/1/metrics?date_from=2026-07-01&date_to=2026-07-31"
curl -H "Authorization: Bearer $DENTICODE_API_TOKEN" "http://127.0.0.1:8000/api/v1/sync-status"
```

PowerShell:

```powershell
$headers = @{ Authorization = "Bearer $env:DENTICODE_API_TOKEN" }
Invoke-RestMethod "http://127.0.0.1:8000/api/v1/accounts?platform=google_ads&limit=25&offset=0" -Headers $headers
Invoke-RestMethod "http://127.0.0.1:8000/api/v1/accounts/1/metrics/summary?date_from=2026-07-01&date_to=2026-07-31" -Headers $headers
Invoke-RestMethod "http://127.0.0.1:8000/api/v1/job-runs/latest?platform=google_ads" -Headers $headers
```

## Local operator dashboard (Phase 6)

The server-rendered local dashboard is strictly read-only. It displays already-synchronized
local database data only; it never invokes collectors, starts a sync, contacts Google Ads, or
changes advertising accounts, campaigns, budgets, bids, audiences, or conversions.

Set a locally generated `DENTICODE_API_TOKEN` before startup (never commit the value), then run:

```powershell
$env:DENTICODE_API_TOKEN = "<your locally generated opaque token>"
uvicorn app.main:app --reload
```

For local loopback HTTP only, also set `DENTICODE_DASHBOARD_ALLOW_INSECURE_LOCAL_HTTP=true`.
This development-only opt-in is rejected for non-loopback hosts; deployed dashboard cookies always
use the `Secure` attribute. Dashboard sessions are process-local, bounded, and therefore require
a single worker (or future shared session storage) for reliable multi-worker navigation.

Open `http://127.0.0.1:8000/dashboard` through an operator tool that can send an
`Authorization: Bearer <token>` request on the first visit. The server validates that header
using the same boundary as `/api/v1`, then creates a short-lived opaque, HTTP-only dashboard
session. The bearer token is never put into dashboard URLs, HTML, JavaScript, storage, cookies,
or logs. Later dashboard requests use only that session.

Dashboard routes are `GET /dashboard`, `GET /dashboard/accounts/{account_id}`,
`GET /dashboard/campaigns/{campaign_id}`, and `GET /dashboard/job-runs`. All require operator
authentication. The public `GET /` and `GET /health` routes remain unchanged.

## Phase 7: separate Google Ads sync worker

The API/dashboard process and the sync scheduler are deliberately separate processes.  FastAPI
startup and lifespan hooks never schedule collection, so future API workers cannot multiply
Google Ads requests.  Both the API sync-health view and dashboard panel read only local JobRun
rows; neither can initiate a sync or call Google Ads.

Run the API and scheduler in separate PowerShell windows:

```powershell
# Window 1
python -m uvicorn app.main:app
# Window 2
python -m app.jobs.google_ads_scheduler
```

For a single production-oriented cycle use `python -m app.jobs.google_ads_sync_once`. Exit
codes are `0` for an actual successful sync, `2` when another worker already holds the
advisory lock and the cycle is skipped, and `1` for configuration or synchronization failure.
Cron jobs and supervisors can use that contract to distinguish success, overlap skips, and
failures. The worker
uses `DENTICODE_SYNC_INTERVAL_MINUTES` (5--1440, default 60),
`DENTICODE_SYNC_RUN_IMMEDIATELY` (default true), `DENTICODE_SYNC_MAX_ATTEMPTS` (1--5, default 3),
`DENTICODE_SYNC_RETRY_BASE_SECONDS` (1--300, default 5),
`DENTICODE_SYNC_RETRY_MAX_SECONDS` (1--900, default 60),
`DENTICODE_SYNC_STALE_AFTER_MINUTES` (1--10080, default 180), and
`DENTICODE_SYNC_LOCK_KEY` (a signed PostgreSQL bigint). Invalid settings stop the worker before
collection. Put only local values in an uncommitted `.env`; never commit `.env` or credentials.

Each cycle checks out one PostgreSQL connection, obtains a nonblocking session-level advisory
lock on that exact physical connection, and binds the synchronization SQLAlchemy Session to it
before any collector call. A competing worker logs a safe overlap skip and creates no JobRun, so
it cannot report an overlap as success. The lock remains held on the pinned connection across
all retries and is released on that same connection on success, failure, and shutdown; failed
unlocks invalidate the connection so a possibly locked connection cannot re-enter the pool. If
the lock-owning backend is invalidated, the cycle aborts fail-closed instead of reconnecting and
continuing without a verified advisory lock.
Retry is conservative: only recognized transient network/database/service
failures retry with capped exponential backoff and bounded jitter; authentication, configuration,
authorization, unknown commit outcomes, and unknown failures do not retry. The recurring
scheduler uses fixed-delay cadence: after each completed, failed, or skipped cycle, it waits the
full configured interval before the next attempt. If `DENTICODE_SYNC_RUN_IMMEDIATELY=false`, the
first cycle is delayed until the first interval elapses. Retry backoff is shutdown-aware in the
scheduler: Ctrl+C, SIGINT, and SIGTERM stop waiting, avoid another collector attempt, finalize
the authoritative JobRun with a bounded interruption summary, and release resources
deterministically. Startup/configuration failures are caught after runtime loading and logged as
sanitized event/type pairs without raw validation text or tracebacks.

`GET /api/v1/operations/sync-health` is bearer-token protected and exposes bounded, read-only
sync status. Stored JobRun failure text is treated as untrusted at this public boundary and
re-sanitized before JSON or dashboard rendering.  Healthy means the most recent successful sync is within the configured stale window;
Stale means it is older (or absent), Failed means the latest attempt failed, Running means the
latest JobRun is in progress, and Never Synced means no prior attempt exists. In production run
the scheduler as its own supervised process; do not put it in Uvicorn, FastAPI startup, or a web
request handler.
