# Campaign and ad-group performance analysis

## Purpose and scope

Improvement step 5 makes synchronized performance actionable at campaign and ad-group scope. It
adds a fixed, read-only Google Ads ad-group metrics query, deterministic local aggregation, the
existing coverage-aware finding rules at both scopes, richer funnel and value metrics, and
authenticated API/dashboard views.

This step does not analyze keyword or search-term text, contact GA4 or CRM providers, create new
recommendations, learn from operator decisions, upload conversions, or mutate an advertising
account. Search-term collection remains operationally separate and search-term values are not
returned by these views.

## Advertising metric grain

Each daily metric has one explicit scope:

| Entity type | Required references | Canonical total behavior |
|---|---|---|
| Campaign | `campaign_id`; `entity_id == campaign_id` | Included in campaign and account totals |
| Ad group | `campaign_id`, `ad_group_id`; `entity_id == ad_group_id` | Included only in its ad-group row |

Database checks and compound foreign keys reject mismatched campaign, ad-group, and platform
references. Account and campaign totals use campaign rows only, so the same traffic is not counted
again when corresponding ad-group rows exist.

The collector issues only fixed internal GAQL: one campaign query and, when synchronized ad groups
exist, one ad-group query. Both are bounded by the approved date window and exclude removed
entities. No query string is accepted from an API or dashboard request.

## Read-only views

The authenticated API adds:

- `GET /api/v1/accounts/{account_id}/campaign-performance`
- `GET /api/v1/campaigns/{campaign_id}/ad-group-performance`

Both endpoints accept the existing bounded `date_from`, `date_to`, `limit`, and `offset` inputs.
Each row contains current and equal-length comparison windows, metric coverage, impressions,
clicks, spend, platform conversion diagnostics, platform CPA/ROAS diagnostics, and deterministic
finding codes with aggregate supporting metrics. External advertising IDs, raw analytics IDs,
CRM IDs, event payloads, keyword text, and search-term text are excluded.

The account and campaign dashboards show the same campaign/ad-group facts. Platform conversion
labels are deliberately qualified as diagnostic because the active workspace measurement contract,
not the advertising platform, defines authoritative leads, business outcomes, and observed value.

## Funnel and value metrics

The mature outcome report remains cohort-based and now includes nested ad-group rows when a paid
GA4 touchpoint carries a validated ad-group reference. Campaign and ad-group rows expose:

- traffic and platform diagnostics: coverage, CTR, platform conversion rate and value;
- funnel progression: click-to-paid-session, paid-session-to-lead,
  lead-to-optimization, optimization-to-business, lead-to-business, drop-off, and cancellation;
- efficiency: cost per lead, optimization outcome, and business outcome; and
- value: observed revenue and ROAS, revenue per click/session/lead/outcome, and median outcome lag.

Campaign totals remain authoritative even when ad-group attribution is incomplete. The report
therefore publishes separate `ad_group_analysis_ready` and `ad_group_blocking_reasons` fields plus
ad-group metric-day and journey-attribution coverage. Missing ad-group scope never silently becomes
zero and never downgrades an otherwise complete campaign attribution.

## Scheduled analysis

Post-sync, nightly, and weekly runs continue to store aggregate-only audit records. Their finding
totals now include the existing account findings plus campaign and ad-group findings calculated
from local synchronized rows. No finding payload, entity name, source identifier, or search term is
persisted in an analysis-run record.

## Activation boundary

Denticode's measurement contract and production GA4 identity path remain subject to the existing
human decisions. Until those are approved and configured, authoritative outcome reports fail
closed. Campaign/ad-group advertising diagnostics can still be read from already synchronized
local rows, but this step does not activate an importer or any external write path.
