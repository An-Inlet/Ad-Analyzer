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
docker run --rm -p 8000:8000 denticode-ads-optimizer:dev
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
