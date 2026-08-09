# Unified Google Ads, GA4, and CRM outcome data

## Purpose and current scope

Improvement step 3 adds the local, read-only data foundation for connecting advertising activity
to website sessions and CRM-confirmed business outcomes. It can answer questions such as how many
mature paid sessions became qualified leads or sales and how much observed revenue was associated
with a campaign.

This step does not configure a GA4 property, query BigQuery, contact Google Ads or GA4, upload
conversions through Google Data Manager, change recommendations, or mutate an advertising account.
`Ga4EventCreate` and `WebAnalyticsRepository` are the strict adapter boundary that a separately
approved, read-only importer can use later.

## Data path

| Source | Stored input | Authority in this step |
|---|---|---|
| Google Ads | Existing mature campaign-level daily impressions, clicks, and spend | Traffic and cost totals |
| GA4 | Allowlisted events, paid-touch campaign references, bounded traffic dimensions, and workspace-bound identifier digests | Session and touchpoint evidence |
| CRM | Existing allowlisted lifecycle/value events plus an optional opaque `analytics_pseudonymous_id` | Qualified lead, sale, cancellation, and observed-revenue truth |

The service collapses GA4 events into sessions, chooses the latest eligible paid touch for each CRM
lead journey, applies the active measurement contract's paid-click lookback, and attributes the
journey's later authoritative outcomes to that campaign. A matching pseudonymous subject digest is
preferred; a matching `gclid`, `gbraid`, or `wbraid` digest is the fallback. Identifiers are scoped
to a workspace, so equal raw values in different workspaces cannot correlate.

## Privacy boundary

Raw GA4 user IDs, session IDs, shared subject IDs, and paid-click IDs are converted to deterministic
SHA-256 digests before persistence. The digest includes the workspace ID and an identifier
namespace. The database never receives those raw values through this adapter. Landing pages are
path-only and reject query strings, fragments, and `@`; unknown fields are rejected. Account and
campaign references must belong to the event's workspace.

The API and dashboard expose aggregates only. They never return raw or digested click, user,
session, CRM lead, opportunity, or practice identifiers. Do not send names, email addresses,
telephone numbers, treatment or diagnosis data, free text, patient data, or PHI as any identifier
or analytics field.

## Contract and cohort gates

Outcome analysis fails closed when the workspace measurement contract is missing, incomplete, or
draft. When active, the service:

1. excludes cohorts after `today - outcome_maturity_days`;
2. considers only CRM mappings marked authoritative;
3. uses the configured optimization and business-value stages;
4. accepts only paid touches within `click_lookback_days` before the lead;
5. applies mapping value behavior and the contract currency; and
6. uses observed revenue only unless a later approved contract explicitly changes that rule.

The source-coverage response separately reports Google Ads metric rows, GA4 paid touchpoints, CRM
events, mapped CRM events, and attributable journeys. Missing inputs are blockers, not implicit
zeros. Immature or out-of-lookback journeys remain unattributed.

## Reported aggregates

`GET /api/v1/workspaces/{workspace_slug}/outcome-analysis` and
`GET /dashboard/workspaces/{workspace_slug}/outcomes` report workspace totals and campaign rows for
the selected paid-touch cohort dates. Defaults end at the contract maturity cutoff and cover 30
days.
The response includes:

- impressions, clicks, spend, paid sessions, attributed leads, optimization outcomes, business
  outcomes, cancellations, and observed revenue;
- lead-to-optimization and optimization-to-business rates;
- revenue per click, cost per optimization outcome, funnel drop-off, and median lead-to-business
  lag; and
- coverage counts, blockers, maturity cutoff, contract version, and the requested cohort range.

Ad-platform conversion counts remain diagnostic and are not used as qualified-lead or revenue
truth. Revenue adjustments replace the journey's current observed value; a cancellation removes
the net sale and zeros its current observed value. Currency mismatches are reported as coverage
blockers rather than converted or silently summed.

## Activation requirements and later work

The seeded Denticode measurement contract remains draft. Before production outcome reporting is
enabled, humans must approve that contract and DR-021, including the exact read-only GA4 BigQuery
export, opaque subject-ID producer and lifecycle, permitted dimensions, retention, access owner,
and monitoring. Credentials and dataset identifiers belong in approved external configuration,
not Git.

Sample-size confidence, seasonality adjustment, device/location/landing-page slices, asset,
keyword, and search-term grain, modeled customer value, payback analysis, scheduled imports, and
Google Data Manager feedback are later increments. Google Data Manager uploads require a separate
write-path design and explicit approval; this step deliberately contains no upload capability.
