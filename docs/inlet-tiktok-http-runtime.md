# TikTok HTTP Runtime Preparation

Branch `codex/inlet-tiktok-runtime` starts at Google runtime head
`f92d0ab30707554b1b85c6798f2c70d4ab6a137a`, including PR73 current-error and retry
repairs. No live provider calls, credentials, grants, advertising writes, or deployment
occurred. This does not establish B11 acceptance in a live environment.

Implemented: real HTTP transport for TikTok v1.3 code exchange, advertiser metadata,
campaign/ad-group/ad inventory and integrated campaign/group/ad daily reporting.
The fixed endpoint allowlist includes no advertising mutations. Secret is sent only
in token-exchange JSON; reads use the Access-Token header. Query arrays and booleans
are JSON encoded. Requests disable redirects/environment proxies, bound connect/read
timeouts, cap decoded response bodies at 2 MB, and sanitize HTTP/provider/parse
errors. Existing cursor phases and six inventory/report streams are preserved.

Grant advertiser IDs are validated and metadata must exactly cover unique authorized
IDs. Runtime rejects foreign advertiser rows, malformed and unbounded pagination,
unsupported cursors, and excessive windows. Existing owner selection, encrypted
grants, generation checks, staged atomic publishing and account currency validation
remain unchanged. Factory settings only enable TikTok, never Klaviyo, HubSpot or
Omnisend. Optional customer-data providers still return unavailable defaults.

Runtime defaults to disabled. Explicit settings for a separately approved release:
`AD_ANALYZER_TIKTOK_RUNTIME_MODE=provider_read`, `AD_ANALYZER_TIKTOK_APP_ID`, and
`AD_ANALYZER_TIKTOK_APP_SECRET`. No values have been configured here. Optional
`expires_in` is validated and converted to an absolute expiry; absent lifetime stays
unknown. Existing service refuses expired grants and requires reconnect. Refresh
material returned by the provider is encrypted through the existing grant vault,
but automatic refresh is not implemented; no undocumented refresh endpoint is guessed.

Reporting semantics remain deliberately limited. Raw provider `conversion` is stored
as provider-attributed conversion data; it is not qualified as purchases. The shared
storage contract currently requires a numeric revenue field, so its existing zero
placeholder remains internal. Customer reports continue returning null conversions
and null conversion value with `conversion_semantics=not_yet_qualified`; they do not
claim measured zero revenue or canonical sales. Shopify remains canonical sales.

Remaining code/qualification gaps: provider revocation, documented token renewal,
late-conversion refresh, campaign-objective-specific conversion qualification and
revenue availability representation in storage, customer connection UI, and authorized
live advertiser/currency/timezone reconciliation. TikTok developer approval and
release enablement are additional gates, not substitutes for these implementation gaps.

Official references consulted October 6, 2026:
- https://github.com/tiktok/tiktok-business-api-sdk/blob/main/python_sdk/docs/AuthenticationApi.md
- https://github.com/tiktok/tiktok-business-api-sdk/blob/main/python_sdk/docs/ReportingApi.md
- https://business-api.tiktok.com/portal/docs?id=1738373164380162

The developer portal is JavaScript-rendered and did not expose readable text through
the browser tool; official SDK endpoint/parameter documentation supplied the readable
reference. Runtime provider lifetimes must be qualified against the actual app grant;
creator-token lifetime descriptions are not assumed to govern advertiser grants.

Validation: 89 focused HTTP/source/customer-context/review regressions passed with
explicit disposable PostgreSQL enabled (33 new HTTP cases). Ruff, mypy across 250
source files, and `git diff --check` passed. Only existing Alembic configuration
deprecation warnings appeared. Full validation and hosted CI remain outstanding.
