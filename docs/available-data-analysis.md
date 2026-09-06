# Analysis with the connections each client has

Every workspace supports independent capabilities. Connecting all advertising, CRM,
analytics, and commerce providers is never an onboarding requirement.

| Available evidence | Available functionality | Additional evidence needed for |
| --- | --- | --- |
| No connections | Goals, approved budget, events, experiments, decision history, planning briefs | Observed performance |
| One advertising account | Imported spend, impressions, clicks, CTR, CPC, campaign comparisons and directional review suggestions | Verified customers, business acquisition cost, revenue attribution and profit |
| Shopify | Store sales, refunds, order cohorts and product demand | Advertising attribution and causal impact |
| Approved measurement and its required sources | Mature funnel and business-outcome reporting | Features whose own evidence or sample requirements are unmet |

The decision center reports readiness for each capability. Its platform section uses
28 completed days in each account's time zone, separately from mature business-outcome
cohorts. Accounts, currencies and providers are never silently blended. Canonical campaign
rows provide account totals; ad-group and keyword rows cannot double-count spend.
Missing observations and unavailable conversion tracking remain distinct from observed zero.

Fresh campaigns can provide directional suggestions even when another campaign or account
is stale. Period comparisons require complete comparable coverage and minimum samples.
Low-volume and stale imports remain visible with limitations. These are investigations
for review, not estimates of causal improvement or instructions executed on an ad account.
Goals and context improve recommendations without becoming prerequisites for traffic analysis.

The report API preserves `analysis_ready` for the existing business-outcome contract.
New consumers should use `available_analysis_ready`, `business_outcome_analysis_ready`,
and `available_evidence.capabilities` for the relevant operation. `health.blocking` is
explicitly scoped to business outcomes. Missing optional connections cannot block the
independent platform or sales capabilities. Approval fingerprints include the evidence
underlying platform recommendations, excluding the page-render timestamp.

Scheduled briefs do not require a strategy. Google, Meta and Shopify sync operations use
the existing worker and their own configuration and controls. A raised Google sync error
does not skip independent source maintenance and due local analysis. Disabled integrations
make no provider calls. Local analysis can continue while imports are paused.

## Meta connection setup

The dashboard provides an owner/admin connection flow for one Meta ad account per workspace.
The application requests read-only advertising access, stores credentials encrypted and
bound to the workspace, and lets the operator select an account available to the authorizing
Meta user. No advertising write capability is enabled.

Before clients can authorize Meta, the deployment operator must configure the organization's
Meta app and its permitted distribution/access, register the exact HTTPS redirect ending
`/dashboard/meta/callback`, and inject `META_CLIENT_ID`, `META_CLIENT_SECRET`,
`META_TOKEN_ENCRYPTION_KEY` (a Fernet key), and `META_REDIRECT_URI` into the existing web
service and sync worker. Set `AD_ANALYZER_META_ENABLED=true` when that configuration is ready.
Credentials belong in the existing secret manager, never in this repository or chat.
Absent configuration affects only Meta authorization; other workspace capabilities work.
Before enabling authorization, exclude `/dashboard/meta/callback` URLs and query strings
from Cloud Run, IAP and reverse-proxy request logs. Application access-log filtering is
included, but it cannot suppress infrastructure logs containing authorization codes.

An explicitly selected conversion event defines platform-reported conversions. Without it,
traffic and spend analysis still works and conversion figures are unavailable. Platform
conversion counts and values never become verified CRM customers or store revenue.

The importer reads campaign metadata, ad sets and daily campaign insights in bounded pages.
Incomplete insight windows are staged; only completed windows replace shared metrics.
Reconnect and throttling states are shown without exposing provider payloads or credentials.
The existing hourly worker resumes bounded imports; no new service or scheduler is provisioned.

## Verification

Offline regressions cover isolated portfolios, no-connection planning, single-provider
analysis, mixed currencies, partial/stale/zero data, conversion availability, recommendation
fingerprints, OAuth ownership and replay, read-only request boundaries, and independent jobs.
Live authorization requires an approved/configured Meta app and an account owner completing
consent; offline tests do not establish provider approval or production authorization.

Provider references: [Meta API versioning](https://developers.facebook.com/documentation/ads-commerce/marketing-api/overview/versioning),
[manual authorization flow](https://developers.facebook.com/documentation/facebook-login/guides/advanced/manual-flow),
[long-lived token exchange](https://developers.facebook.com/documentation/facebook-login/guides/access-tokens/get-long-lived),
and [advertising insights](https://developers.facebook.com/documentation/ads-commerce/marketing-api/reference/ad-account/insights).
The connector pins API v26.0; upgrading that contract requires a reviewed change.
