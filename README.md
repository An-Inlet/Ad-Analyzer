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
