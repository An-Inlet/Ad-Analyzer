# Keyword and masked search-term analysis

## Purpose and scope

Improvement step 6 adds deterministic, read-only keyword and search-term waste/opportunity
analysis after campaign and ad-group analysis. It uses synchronized local metric rows only. The
service, API, and dashboard never trigger synchronization or contact an external provider. Step 7
may translate its fixed findings into local, human-review-only recommendations; it does not learn
from operator decisions or invoke an executor.

The normal fixed-query Google Ads synchronization path can populate keyword and search-term daily
metrics. It remains read-only and does not accept operator-supplied GAQL.

## Metric grain and isolation

Keyword and search-term daily metrics carry their full campaign and ad-group ancestry. Compound
foreign keys and a database check reject mismatched platform, campaign, ad-group, keyword, or
search-term references. Campaign/account totals continue to use campaign rows only, so lower-level
rows never double-count canonical totals. Google Ads keyword criterion IDs are resolved together
with their parent ad-group ID because the provider's keyword resource identity is compound.

The API exposes:

- `GET /api/v1/ad-groups/{ad_group_id}/keyword-performance`
- `GET /api/v1/ad-groups/{ad_group_id}/search-term-performance`

Both endpoints accept bounded comparison windows, `limit` from 1 through 100, and stable `offset`
pagination. Rows are sorted by current-window spend descending and then by stable local ID.

## Deterministic findings

Findings are calculated live and are never persisted as stale advice. The version 1 constants are:

| Gate | Value |
|---|---:|
| Minimum complete metric days | 3, or the full window when shorter |
| Minimum impressions | 500 |
| Minimum clicks | 30 |
| Minimum spend | 2,000,000 micros |
| Material comparison change | 50% |
| Major comparison change | 100% |

Eligible rows can report:

- material spend and clicks without diagnostic platform conversions;
- low click-through rate at sufficient impression volume;
- unusual spend change versus the equal-length previous window; and
- unusual impression change versus the equal-length previous window.

Changes of at least 50% are low severity and changes of at least 100% are medium severity. Stale
sync and insufficient-data findings keep their existing fail-closed behavior. Finding payloads
contain numeric metrics and fixed messages only.

## Privacy and action boundary

Search-term text is never selected by the analysis query or returned by its API/dashboard schema.
Each row uses a stable local label such as `Search term #42`, allowing an exact stored record to be
reviewed without exposing sensitive query text. Keyword text remains visible to authenticated
operators because it is advertiser-authored configuration, not a user's search query.

Platform conversions and value are explicitly diagnostic. They are not presented as
CRM-confirmed leads, qualified leads, sales, or revenue. A spend-without-platform-conversions
finding itself does not tell an operator to add a negative keyword. Step 7 may create a
`review_negative_keyword_candidate` proposal using only the masked local record label. That
proposal contains no advertising mutation, requires human approval, and cannot execute a live
write. Operator-decision learning and advertising mutations remain later roadmap units.
