# Ad Analyzer Agent Instructions

## Security requirements

- Treat this repository as the multi-workspace Ad Analyzer platform. Safety, auditability, client isolation, and operator review take precedence over automation speed.
- Do not connect to Google Ads, Meta Ads, OpenAI APIs, or any external service unless a human explicitly requests that task in the current conversation.
- Do not request, create, print, commit, or store credentials, API tokens, OAuth refresh tokens, client secrets, private keys, service-account files, or production database URLs.
- Never commit `.env` files or credential material. Use `.env.example` only for non-secret variable names and safe placeholder values.
- Advertising integrations must default to read-only behavior. Any future write access, bid changes, budget changes, campaign mutations, audience changes, or conversion uploads must require explicit human approval, clear dry-run output, and auditable logs.
- Avoid logging sensitive campaign identifiers, customer data, patient data, conversion payloads, access tokens, or raw API responses that may contain confidential data.
- Dental and healthcare advertising can involve regulated and sensitive data. Do not add features that infer, expose, or target protected health information.

## Engineering requirements

- Target Python 3.12.
- Keep the FastAPI application small and modular. Add API routes under `app/api/` as the service grows.
- Use Pydantic for settings and request/response schemas.
- Use SQLAlchemy and Alembic for database access and migrations. Do not make ad-hoc schema changes outside migrations.
- Use PostgreSQL-compatible database types and SQLAlchemy models.
- Add tests for new behavior and keep tests deterministic; tests must not require network access or real third-party credentials.
- Run pytest, Ruff, and mypy before committing code changes.
- Prefer dry-run planning and explicit policy checks for optimizer logic.
- Keep collectors and executors separated. Collectors may read data; executors are the only future location for controlled mutations.
- Do not implement advertising API collectors, write access, or campaign mutations unless explicitly requested.
