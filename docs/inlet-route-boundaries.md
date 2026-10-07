# Assembled Route Authentication Boundaries

Inventory baseline: PR130 `0cf6706ca9e12e8ccdba77f10c2247fd976e3593`.
This is application-route evidence, not deployment/IAM qualification. No new
runtime authorization or deployment permissions were introduced by this package.

The assembled application has 80 protected method/path combinations: 42 operator
API, 37 dashboard and one worker. Tests enumerate effective FastAPI include
contexts, including hidden routes. OpenAPI alone omits dashboard/worker handlers
and therefore cannot establish this inventory. The test also rejects any unclassified
API route or unexpected static/documentation mount.

## Protected Routes

| Method | Path | Required Boundary |
| --- | --- | --- |
| GET | `/api/v1/accounts` | operator |
| GET | `/api/v1/accounts/{account_id}` | operator |
| GET | `/api/v1/accounts/{account_id}/analytics/window` | operator |
| GET | `/api/v1/accounts/{account_id}/campaign-performance` | operator |
| GET | `/api/v1/accounts/{account_id}/campaigns` | operator |
| GET | `/api/v1/accounts/{account_id}/findings` | operator |
| GET | `/api/v1/accounts/{account_id}/metrics/summary` | operator |
| GET | `/api/v1/ad-groups/{ad_group_id}/keyword-performance` | operator |
| GET | `/api/v1/ad-groups/{ad_group_id}/search-term-performance` | operator |
| GET | `/api/v1/campaigns/{campaign_id}` | operator |
| GET | `/api/v1/campaigns/{campaign_id}/ad-group-performance` | operator |
| GET | `/api/v1/campaigns/{campaign_id}/ad-groups` | operator |
| GET | `/api/v1/campaigns/{campaign_id}/metrics` | operator |
| GET | `/api/v1/job-runs` | operator |
| GET | `/api/v1/job-runs/latest` | operator |
| GET | `/api/v1/operations/attention` | operator |
| GET | `/api/v1/operations/sync-health` | operator |
| GET | `/api/v1/recommendations` | operator |
| GET | `/api/v1/sync-status` | operator |
| GET | `/api/v1/workspaces` | operator |
| GET | `/api/v1/workspaces/{workspace_slug}` | operator |
| GET | `/api/v1/workspaces/{workspace_slug}/advertising-accounts` | operator |
| GET | `/api/v1/workspaces/{workspace_slug}/analysis-runs` | operator |
| GET | `/api/v1/workspaces/{workspace_slug}/configuration` | operator |
| GET | `/api/v1/workspaces/{workspace_slug}/decision-learning` | operator |
| GET | `/api/v1/workspaces/{workspace_slug}/integrations` | operator |
| GET | `/api/v1/workspaces/{workspace_slug}/intelligence` | operator |
| GET | `/api/v1/workspaces/{workspace_slug}/intelligence/records/{kind}` | operator |
| GET | `/api/v1/workspaces/{workspace_slug}/measurement-contract` | operator |
| GET | `/api/v1/workspaces/{workspace_slug}/memberships` | operator |
| GET | `/api/v1/workspaces/{workspace_slug}/meta` | operator |
| GET | `/api/v1/workspaces/{workspace_slug}/outcome-analysis` | operator |
| GET | `/api/v1/workspaces/{workspace_slug}/shopify` | operator |
| GET | `/api/v1/workspaces/{workspace_slug}/weekly-learning-report` | operator |
| GET | `/dashboard` | dashboard |
| GET | `/dashboard/accounts/{account_id}` | dashboard |
| GET | `/dashboard/accounts/{account_id}/execution-operations` | dashboard |
| GET | `/dashboard/ad-groups/{ad_group_id}` | dashboard |
| GET | `/dashboard/campaigns/{campaign_id}` | dashboard |
| GET | `/dashboard/job-runs` | dashboard |
| GET | `/dashboard/meta/callback` | dashboard |
| GET | `/dashboard/portfolio` | dashboard |
| GET | `/dashboard/shopify/callback` | dashboard |
| GET | `/dashboard/workspaces/{workspace_slug}` | dashboard |
| GET | `/dashboard/workspaces/{workspace_slug}/intelligence` | dashboard |
| GET | `/dashboard/workspaces/{workspace_slug}/intelligence/brief.csv` | dashboard |
| GET | `/dashboard/workspaces/{workspace_slug}/intelligence/edit/{kind}` | dashboard |
| GET | `/dashboard/workspaces/{workspace_slug}/meta` | dashboard |
| GET | `/dashboard/workspaces/{workspace_slug}/outcomes` | dashboard |
| GET | `/dashboard/workspaces/{workspace_slug}/shopify` | dashboard |
| GET | `/dashboard/workspaces/{workspace_slug}/shopify/privacy/{request_id}.json` | dashboard |
| GET | `/dashboard/workspaces/{workspace_slug}/shopify/sales.csv` | dashboard |
| POST | `/api/v1/accounts/{account_id}/recommendations/generate` | operator |
| POST | `/api/v1/recommendations/{recommendation_id}/approve` | operator |
| POST | `/api/v1/recommendations/{recommendation_id}/execute-dry-run` | operator |
| POST | `/api/v1/recommendations/{recommendation_id}/reject` | operator |
| POST | `/api/v1/workspaces/{workspace_slug}/intelligence/ask` | operator |
| POST | `/api/v1/workspaces/{workspace_slug}/intelligence/records/{kind}` | operator |
| POST | `/api/v1/workspaces/{workspace_slug}/intelligence/scenario` | operator |
| POST | `/dashboard/automation-controls/{control_name}` | dashboard |
| POST | `/dashboard/logout` | dashboard |
| POST | `/dashboard/recommendations/{recommendation_id}/approve` | dashboard |
| POST | `/dashboard/recommendations/{recommendation_id}/execute-dry-run` | dashboard |
| POST | `/dashboard/recommendations/{recommendation_id}/reject` | dashboard |
| POST | `/dashboard/workspaces/{workspace_slug}/automation-controls/{control_name}` | dashboard |
| POST | `/dashboard/workspaces/{workspace_slug}/intelligence/ask` | dashboard |
| POST | `/dashboard/workspaces/{workspace_slug}/intelligence/restore/{revision_id}` | dashboard |
| POST | `/dashboard/workspaces/{workspace_slug}/intelligence/save/{kind}` | dashboard |
| POST | `/dashboard/workspaces/{workspace_slug}/intelligence/scenario` | dashboard |
| POST | `/dashboard/workspaces/{workspace_slug}/meta/accounts/more` | dashboard |
| POST | `/dashboard/workspaces/{workspace_slug}/meta/connect` | dashboard |
| POST | `/dashboard/workspaces/{workspace_slug}/meta/disconnect` | dashboard |
| POST | `/dashboard/workspaces/{workspace_slug}/meta/select` | dashboard |
| POST | `/dashboard/workspaces/{workspace_slug}/meta/sync` | dashboard |
| POST | `/dashboard/workspaces/{workspace_slug}/shopify/connect` | dashboard |
| POST | `/dashboard/workspaces/{workspace_slug}/shopify/disconnect` | dashboard |
| POST | `/dashboard/workspaces/{workspace_slug}/shopify/privacy/{request_id}/delivered` | dashboard |
| POST | `/dashboard/workspaces/{workspace_slug}/shopify/sync` | dashboard |
| POST | `/internal/pubsub/crm-events` | worker |
| PUT | `/api/v1/workspaces/{workspace_slug}/intelligence/records/{kind}/{record_id}` | operator |

Operator routes require the configured bounded opaque bearer. Production dashboard
routes require verified IAP on every request, followed by their existing workspace
or platform authorization. Development dashboard sessions still require operator
bearer authentication; allowing local HTTP does not waive identity. Worker push
requires the configured Google audience/service-account identity independently of
Cloud Run IAM. Customer session cookies, CSRF tokens and Origin supply none of
these authorities.

## Explicit Public And Separately Signed Routes

Public HTML and configuration contain no customer records. GET callback routes
serve bridge documents; their POST continuations require customer authentication.
The readiness endpoint is deliberately public and this matrix makes no assertion
that database/schema readiness succeeds.

- `GET /`
- `GET /api/customer/v1/auth-config`
- `GET /api/customer/v1/google/callback`
- `GET /api/customer/v1/meta/callback`
- `GET /api/customer/v1/shopify/callback`
- `GET /api/customer/v1/sources/{provider}/callback`
- `GET /app`
- `GET /app/`
- `GET /app/campaign-review`
- `GET /app/settings`
- `GET /app/workspace-closure`
- `GET /app/workspace-closure/{workspace_id}/{request_id}`
- `GET /health`
- `GET /ready`

Public static/documentation routes or mounts:

- `/app/assets`
- `/dashboard/assets`
- `/docs`
- `/docs/oauth2-redirect`
- `/openapi.json`
- `/redoc`

Ingress authenticated by its own signature protocol, rather than customer cookies:

- `POST /api/billing/stripe/events`
- `POST /v1/crm/workspaces/{workspace_id}/connections/{connection_id}/events`

`POST /v1/crm/events` permanently rejects unscoped events. Customer login is the
other explicit exception to an existing customer session: `POST
/api/customer/v1/session` requires Origin and verified provider identity. Every
remaining customer API route must include the customer authentication dependency.
These classifications do not assert completeness of unrelated webhook protocols;
existing signature/ingress tests remain authoritative for those details.

## Negative Coverage

Each of the 80 protected routes is requested using a session created through the
actual customer login API. All routes must reject before the database dependency
can be entered. Both SQLite and PostgreSQL session stores run four configurations:
configured production, missing production auth configuration, configured local
HTTP development and missing development auth configuration. Local cases explicitly
present the authenticated customer's cookie over HTTP on a loopback peer, so Secure
cookie omission cannot explain rejection. Missing configuration yields 503;
configured boundaries without their own credentials yield 401. The customer session
remains valid afterward. No operator guard, IAP identity, push identity, or worker
processor is overridden to manufacture a rejection.

Existing verifier and malformed-credential tests are reused, rather than replacing
Google/IAP verification with new controls. This package does not prove Cloud Run,
IAP, Pub/Sub or provider setup in an intended deployment. Exact assembled Full/CI
and release qualification remain separate gates.
