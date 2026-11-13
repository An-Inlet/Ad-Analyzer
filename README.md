# Inlet

### Turn advertising data into a clearer growth strategy.

Inlet brings advertising performance, business goals, customer outcomes, and commerce data into one decision center. It helps growth teams understand where money is going, identify what deserves attention, and build an evidence-backed plan for what to do next.

**Connect the evidence. Diagnose performance. Explore the options. Review the plan. Learn from the results.**

Built by [An Inlet](https://aninlet.com), the platform is designed for founders, marketing teams, and operators managing one business or a portfolio of client workspaces.

[Explore the decision center](docs/business-decision-center.md) · [See integration coverage](docs/available-data-analysis.md) · [Developer setup](#developer-setup)

## What Inlet brings together

### A business plan behind every advertising decision

Set goals, approved budgets, acquisition-cost limits, margin assumptions, audiences, positioning, and offers. Connect those choices to launches, promotions, conferences, seasonal demand, and capacity constraints.

The decision center puts that context beside performance so recommendations can be evaluated against the business the advertising is meant to grow.

### A clearer view of performance and outcomes

Review spend, impressions, clicks, campaign comparisons, and available conversion metrics. With an approved measurement contract and the required sources, connect Google Ads cohorts, pseudonymous web-analytics events, and CRM outcomes to examine customer acquisition cost, observed revenue, and contribution after advertising.

Shopify sales add a separate commerce view: payments, refunds, orders, product demand, and supported campaign-tag comparisons. Inlet keeps platform-reported conversions, CRM outcomes, and store sales distinct so different sources do not quietly become the same number.

### Explainable recommendations

Find campaign, ad-group, keyword, and masked search-term issues using reproducible rules. Review a ranked action queue with supporting evidence, business context, next steps, confidence, budget implications, and review dates.

Record decisions and compare expected results with observed results later. Recommendation review history provides transparent prioritization context without silently rewriting diagnostic thresholds or treating approval as proof that an idea worked.

### Budget scenarios before budget commitments

Track completed-day spending against the approved plan, reserve funds for upcoming activities, and explore custom or 80% / 100% / 120% budget scenarios. Where the evidence supports it, preview bounded campaign-allocation changes.

Scenario outputs expose their assumptions. They are planning estimates, not guaranteed returns or automatic changes to live campaign budgets.

### A repeatable learning cycle

Plan two-arm experiments with defined success criteria, record aggregate results, and review sample and maturity checks. Keep a history of strategy revisions, business changes, and decisions.

Post-sync, nightly, and weekly analysis can refresh findings and save briefs. Weekly learning reports compare completed periods and suggest improvements for review. CSV action briefs make the next steps portable.

## Start with the connections you have

Inlet supports independent capabilities rather than requiring every source before anything becomes useful.

| Available evidence | What it unlocks |
| --- | --- |
| No connected sources | Goals, budgets, events, experiment plans, and decision history |
| An advertising account | Imported traffic and spend analysis, campaign comparisons, and directional review suggestions |
| Shopify sales | Order, payment, refund, and product-demand analysis |
| Approved measurement and required data sources | Mature funnel comparisons and business-outcome reporting |

Missing, stale, partial, and low-volume data remain visible. A missing connection is not treated as zero performance, and an unfinished import is not presented as complete.

## Current implementation and integration coverage

**The capabilities below are implemented in this repository.** Availability in a deployed workspace depends on configuration, provider authorization, data coverage, and release validation. This README does not imply that every integration is already connected or that a public self-service release is live.

| Area | Implemented scope | Important boundary |
| --- | --- | --- |
| Google Ads | Read-only collection, synchronization, campaign/ad-group analysis, keyword and masked search-term diagnostics | Requires authorized credentials and configured accounts; no live advertising mutations |
| Meta Ads | Workspace authorization, account selection, campaign/ad-set inventory, daily campaign insights, and import status | One Meta account per workspace in the current connection flow; operator app setup and provider approval are required |
| Web analytics + CRM | Pseudonymous event and CRM pipelines, measurement contracts, mature cohort and outcome reporting | Requires valid source mappings and sufficient evidence; not a universal one-click CRM connector |
| Shopify | Workspace store authorization, bounded sales imports, refunds, product demand, and privacy-event handling | Disabled by default; rolling 59-day order window and release checks apply; store sales are not Shop Campaigns advertising data |
| Decision center | Strategy, measurement health, funnel diagnosis, scenarios, events, creative test briefs, experiments, and decision history | Creative analysis uses campaign context, not isolated individual-ad or demographic performance |
| Reporting | Workspace dashboard, authorized portfolio views, operator API, CSV action briefs, scheduled briefs, and topic-based answers | Answers use deterministic evidence lookup, not unrestricted AI chat |
| Governance | Workspace memberships, review permissions, versioned planning records, audit history, and guarded dry runs | The current product remains planning and review focused; live ad writes are disabled |

See [available-data analysis and Meta setup](docs/available-data-analysis.md), [Shopify setup and measurement definitions](docs/shopify-sales.md), and the [decision-center operating guide](docs/business-decision-center.md).

## Built for accountable decisions

- **Evidence before confidence.** Coverage, freshness, comparable time windows, and sample requirements determine which conclusions are available.
- **Business outcomes stay distinct.** Platform conversions are not automatically customers. Observed revenue is not predicted lifetime value. Correlation is not proof of incremental impact.
- **Workspace boundaries.** Each business has its own configuration, memberships, integrations, accounts, findings, and operational history.
- **Privacy-conscious reporting.** Outcome reports exclude raw click, session, user, and CRM lead identifiers. Search-term diagnostics keep query text masked.
- **Human control.** Planning and review do not change live ads. Future execution requires separate implementation, explicit authorization, dry-run review, and auditability.
- **Operational visibility.** Separate collection workers, bounded imports, retry controls, sync-health reporting, and deduplicated analysis help operators understand what ran and what needs attention.

## Where Inlet is headed

The product direction is a comprehensive advertising-planning workspace that helps a team move from fragmented performance data to a prioritized, reviewable growth plan.

Future capabilities are **roadmap goals, not claims of availability or delivery dates**:

- Broader channel coverage, including TikTok Ads, with platform-specific measurement and permission controls.
- Deeper creative and audience analysis, richer planning outputs, and more ways to compare opportunities across connected accounts.
- Expanded import flexibility and historical coverage, subject to provider access, privacy requirements, and performance validation.
- More CRM and commerce connections, with clearer links between marketing activity and verified business results.
- A streamlined self-service SaaS experience for onboarding, account management, and recurring plan review.
- Optional, tightly controlled execution after the planning product, with explicit human approval and auditable safeguards.

The immediate focus remains useful diagnosis, comprehensive planning, and reliable review. Automatic campaign execution is outside the planning-only MVP.

## Architecture

```text
Inlet
└── Business / client workspace
    ├── Goals, strategy, budgets, events, and experiments
    ├── Memberships, permissions, and measurement contract
    ├── Advertising, web analytics, CRM, and commerce integrations
    ├── Performance evidence, findings, and recommended actions
    └── Decision history, scheduled briefs, and operational health
```

The implementation uses **Python 3.12, FastAPI, Pydantic, SQLAlchemy, PostgreSQL, and Alembic**, with a server-rendered dashboard and separate synchronization workers. The repository includes Docker and Google Cloud deployment configuration, plus pytest, Ruff, mypy, migration, privacy, and isolation checks.

The repository name `Ad-Analyzer`, package name `ad-analyzer`, and `AD_ANALYZER_` environment variables remain technical identifiers. The product presented here is **Inlet**; this documentation update does not rename infrastructure or alter deployments.

## Documentation

- [Decision center and calculation boundaries](docs/business-decision-center.md)
- [Analysis with partial connections and Meta setup](docs/available-data-analysis.md)
- [Shopify sales and privacy handling](docs/shopify-sales.md)
- [Workspace architecture](docs/workspace-architecture.md)
- [Measurement contracts](docs/measurement-contract.md) and [unified outcomes](docs/unified-outcome-data.md)
- [Granular analysis](docs/granular-analysis.md) and [masked search-term diagnostics](docs/query-performance-analysis.md)
- [Analysis cadences](docs/analysis-cadences.md), [recommendations](docs/automated-recommendations.md), and [decision learning](docs/decision-learning.md)
- [Weekly learning reports](docs/weekly-learning-report.md)
- [Deployment architecture](docs/deployment-architecture.md) and [operations runbook](docs/operations/runbook.md)

## Developer setup

<details>
<summary><strong>Installation, local development, API, dashboard, and worker operations</strong></summary>

The commands below retain the repository's existing technical names. Follow [AGENTS.md](AGENTS.md) and the release and security gates before connecting real services or changing a deployment.

### Windows PowerShell setup

From a PowerShell terminal:

```powershell
git clone https://github.com/An-Inlet/Ad-Analyzer.git
cd Ad-Analyzer
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

### Run the application locally

```powershell
uvicorn app.main:app --reload
```

Open <http://127.0.0.1:8000/health> and expect:

```json
{"status":"ok"}
```

### Run checks

```powershell
pytest
ruff check .
mypy
```

### Docker development image

Build and run the development container:

```powershell
docker build -t ad-analyzer:dev .
docker run --rm --env-file .env -p 8000:8000 ad-analyzer:dev
```

### Database and migrations

The default local database URL uses a platform-neutral local database name:

```text
postgresql+psycopg://postgres:postgres@localhost:5432/ad_analyzer
```

Override it with the `DATABASE_URL` environment variable when running against a local PostgreSQL instance. Use Alembic for schema changes:

```powershell
alembic revision --autogenerate -m "describe change"
alembic upgrade head
```

### Local operator API

Start the FastAPI application locally with:

```bash
uvicorn app.main:app --reload
```

Versioned operator endpoints are available under `/api/v1`. The reporting GET routes below read
synchronized PostgreSQL data. Separate, authorized decision-center commands save local planning
records and preview scenarios; they do not mutate advertising platforms. See the
[decision-center API](docs/business-decision-center.md#storage-access-and-apis) for those commands.

All `/api/v1` endpoints require an operator bearer token. `AD_ANALYZER_API_TOKEN` must be a URL-safe opaque token containing only letters, digits, hyphens, and underscores (43–128 characters). Generate one locally with `python -c "import secrets; print(secrets.token_urlsafe(48))"`, then set it in your local environment or uncommitted `.env` file before starting the service. The container must receive the same variable (for example, through `--env-file .env`); protected routes are unavailable if it is not configured. Never commit the token.

Endpoint groups:

- Workspaces: `GET /api/v1/workspaces`, `GET /api/v1/workspaces/{slug}`
- Workspace-owned resources: `GET /api/v1/workspaces/{slug}/configuration`,
  `GET /api/v1/workspaces/{slug}/measurement-contract`,
  `GET /api/v1/workspaces/{slug}/outcome-analysis`,
  `GET /api/v1/workspaces/{slug}/analysis-runs`,
  `GET /api/v1/workspaces/{slug}/decision-learning`,
  `GET /api/v1/workspaces/{slug}/weekly-learning-report`,
  `GET /api/v1/workspaces/{slug}/integrations`,
  `GET /api/v1/workspaces/{slug}/memberships`, and
  `GET /api/v1/workspaces/{slug}/advertising-accounts`
- Accounts: `GET /api/v1/accounts`, `GET /api/v1/accounts/{account_id}`
- Account campaigns: `GET /api/v1/accounts/{account_id}/campaigns`
- Campaign performance: `GET /api/v1/accounts/{account_id}/campaign-performance`
- Campaigns and child data: `GET /api/v1/campaigns/{campaign_id}`, `GET /api/v1/campaigns/{campaign_id}/ad-groups`, `GET /api/v1/campaigns/{campaign_id}/metrics`
- Ad-group performance: `GET /api/v1/campaigns/{campaign_id}/ad-group-performance`
- Account metrics: `GET /api/v1/accounts/{account_id}/metrics/summary`
- Sync job visibility: `GET /api/v1/job-runs`, `GET /api/v1/job-runs/latest`, `GET /api/v1/sync-status`

Replace `WORKSPACE_SLUG` below with a workspace returned by `GET /api/v1/workspaces`.

Examples:

```bash
curl -H "Authorization: Bearer $AD_ANALYZER_API_TOKEN" "http://127.0.0.1:8000/api/v1/accounts?platform=google_ads&limit=25&offset=0"
curl -H "Authorization: Bearer $AD_ANALYZER_API_TOKEN" "http://127.0.0.1:8000/api/v1/campaigns/1/metrics?date_from=2026-07-01&date_to=2026-07-31"
curl -H "Authorization: Bearer $AD_ANALYZER_API_TOKEN" "http://127.0.0.1:8000/api/v1/accounts/1/campaign-performance?date_from=2026-07-01&date_to=2026-07-31"
curl -H "Authorization: Bearer $AD_ANALYZER_API_TOKEN" "http://127.0.0.1:8000/api/v1/campaigns/1/ad-group-performance?date_from=2026-07-01&date_to=2026-07-31"
curl -H "Authorization: Bearer $AD_ANALYZER_API_TOKEN" "http://127.0.0.1:8000/api/v1/workspaces/WORKSPACE_SLUG/outcome-analysis?date_from=2026-04-01&date_to=2026-04-30"
curl -H "Authorization: Bearer $AD_ANALYZER_API_TOKEN" "http://127.0.0.1:8000/api/v1/workspaces/WORKSPACE_SLUG/analysis-runs?limit=25&offset=0"
curl -H "Authorization: Bearer $AD_ANALYZER_API_TOKEN" "http://127.0.0.1:8000/api/v1/sync-status"
```

PowerShell:

```powershell
$headers = @{ Authorization = "Bearer $env:AD_ANALYZER_API_TOKEN" }
Invoke-RestMethod "http://127.0.0.1:8000/api/v1/accounts?platform=google_ads&limit=25&offset=0" -Headers $headers
Invoke-RestMethod "http://127.0.0.1:8000/api/v1/accounts/1/metrics/summary?date_from=2026-07-01&date_to=2026-07-31" -Headers $headers
Invoke-RestMethod "http://127.0.0.1:8000/api/v1/job-runs/latest?platform=google_ads" -Headers $headers
```

### Local operator dashboard

The server-rendered dashboard's reporting views display already-synchronized database data.
Authorized planning and review flows can save local records, and separately configured integration
flows handle connections and permitted refreshes. Viewing performance does not trigger a Google Ads
sync, and no dashboard action enables live advertising mutations.

Set a locally generated `AD_ANALYZER_API_TOKEN` before startup (never commit the value), then run:

```powershell
$env:AD_ANALYZER_API_TOKEN = "<your locally generated opaque token>"
uvicorn app.main:app --reload
```

For local loopback HTTP only, also set `AD_ANALYZER_DASHBOARD_ALLOW_INSECURE_LOCAL_HTTP=true`.
This development-only opt-in is rejected for non-loopback hosts; deployed dashboard cookies always
use the `Secure` attribute. Dashboard sessions are process-local, bounded, and therefore require
a single worker (or future shared session storage) for reliable multi-worker navigation.

Open `http://127.0.0.1:8000/dashboard` through an operator tool that can send an
`Authorization: Bearer <token>` request on the first visit. The server validates that header
using the same boundary as `/api/v1`, then creates a short-lived opaque, HTTP-only dashboard
session. The bearer token is never put into dashboard URLs, HTML, JavaScript, storage, cookies,
or logs. Later dashboard requests use only that session.

Dashboard routes are `GET /dashboard`, `GET /dashboard/workspaces/{workspace_slug}`,
`GET /dashboard/workspaces/{workspace_slug}/outcomes`,
`GET /dashboard/accounts/{account_id}`, `GET /dashboard/campaigns/{campaign_id}`,
`GET /dashboard/ad-groups/{ad_group_id}`, and `GET /dashboard/job-runs`. Platform administrators
can see all workspaces. Other authenticated IAP identities see only workspaces with an active
membership; only workspace owners and administrators may approve, reject, or dry-run
recommendations.

The outcome view correlates mature Google Ads cohorts with pseudonymous GA4 paid sessions and
authoritative CRM outcomes. It returns no raw click, session, user, lead, or practice identifiers
and remains blocked while the workspace measurement contract is missing or draft. See
[unified outcome data](docs/unified-outcome-data.md).

Campaign and ad-group views use canonical entity rows, expose data coverage and diagnostic
platform metrics, and apply the existing deterministic finding rules without returning search-term
text or private identifiers. See [granular analysis](docs/granular-analysis.md).

Ad-group detail views add keyword and masked search-term performance, equal-length comparison
windows, and deterministic waste/traffic-shift findings. Search-term text is neither selected by
the analyzer nor returned by its API/dashboard responses. See
[keyword and masked search-term analysis](docs/query-performance-analysis.md).

Workspace pages also show aggregate cadence history. Post-sync, nightly, and weekly runs use local
synchronized data and create at most 100 deduplicated, human-review-only proposals. They never
trigger collectors, executors, or advertising mutations. See
[analysis cadences](docs/analysis-cadences.md) and
[automated recommendations](docs/automated-recommendations.md).

Workspace pages also expose decision-learning profiles derived from immutable approve/reject audit
actions. New proposals receive a transparent learning snapshot, which can break otherwise equal
severity-and-spend ties but cannot change finding thresholds, severity, spend priority, human
approval, or advertising state. See [decision learning](docs/decision-learning.md).

The weekly learning report compares the latest completed Monday-Sunday UTC week with the prior
week and emits deterministic, evidence-backed suggestions for improving analyzer diagnostics or
review context. It uses only local aggregate records, excludes identities, reasons, and search-term
text, and applies no changes. See [weekly learning reports](docs/weekly-learning-report.md).

### Separate synchronization worker

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
uses `AD_ANALYZER_SYNC_INTERVAL_MINUTES` (5--1440, default 60),
`AD_ANALYZER_SYNC_RUN_IMMEDIATELY` (default true), `AD_ANALYZER_SYNC_MAX_ATTEMPTS` (1--5, default 3),
`AD_ANALYZER_SYNC_RETRY_BASE_SECONDS` (1--300, default 5),
`AD_ANALYZER_SYNC_RETRY_MAX_SECONDS` (1--900, default 60),
`AD_ANALYZER_SYNC_STALE_AFTER_MINUTES` (1--10080, default 180), and
`AD_ANALYZER_SYNC_ADVISORY_LOCK_KEY` (a signed PostgreSQL bigint). Invalid settings stop the worker before
collection. Put only local values in an uncommitted `.env`; never commit `.env` or credentials.

After a successful sync, both workers run the idempotent post-sync analysis. The long-running
scheduler also checks due nightly and weekly workspace analyses after every cycle attempt. An
analysis failure is recorded separately and does not cause a successful collector run to repeat.

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
full configured interval before the next attempt. If `AD_ANALYZER_SYNC_RUN_IMMEDIATELY=false`, the
first cycle is delayed until the first interval elapses. Retry backoff is shutdown-aware in both the scheduler and one-shot worker: Ctrl+C, SIGINT,
and SIGTERM request shutdown, stop waiting, avoid another collector attempt, finalize the
authoritative JobRun with a bounded interruption summary when the transaction outcome is known,
and release resources deterministically. Startup/configuration failures are caught after runtime loading and logged as
sanitized event/type pairs without raw validation text or tracebacks.

`GET /api/v1/operations/sync-health` is bearer-token protected and exposes bounded, read-only
sync status. Stored JobRun failure text is treated as untrusted at this public boundary and
re-sanitized before JSON or dashboard rendering using exact fixed-message allowlists only;
legacy, extended, or externally inserted text is mapped to a generic public failure summary.  Healthy means the most recent successful sync is within the configured stale window;
Stale means it is older (or absent), Failed means the latest attempt failed, Running means the
latest JobRun is in progress, and Never Synced means no prior attempt exists. In production run
the scheduler as its own supervised process; do not put it in Uvicorn, FastAPI startup, or a web
request handler.

### Legacy workspace compatibility

The seeded Denticode Ad Analyzer workspace remains a client-specific migration detail, not the
identity or scope of Inlet. Existing workspace data and identifiers are unchanged. See the
[platform naming cutover](docs/platform-name-cutover.md) for migration history.

</details>
