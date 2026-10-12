# Opt-In Google Reporting Runtime V1

Baseline 076695d. Concrete gap: the real application's Google reporting dependency
always returns None, so the existing customer range → event → capture workflow is
unavailable despite isolated qualification. Compose the existing services through
one explicit false-by-default `INLET_CUSTOMER_GOOGLE_REPORTING_ENABLED` switch and
the existing `google_customer_runtime_mode=google_read` and v24 configuration.
No new credential, grants, scopes, policy or persistent schema is introduced.

## Evidence-Based Scope Choice

TikTok website-purchase count remains unqualified. The official SDK documents
`GET /open_api/v1.3/report/integrated/get/` but not the exact complete_payment ×
BASIC × AUCTION_CAMPAIGN × campaign_id/stat_time_day report combination. The known
official metric/dimension/synchronous documentation gateway was inaccessible in
this executor (web-tool failure and direct request proxy 403). Earlier parent
research expressly leaves per-combination availability unknown. No guessed value
units, effective attribution, timezone or complete-pagination support is promoted.
Research records: `/workspace/inlet-evidence/20261012/tiktok-count-research/`.
Official SDK: https://github.com/tiktok/tiktok-business-api-sdk/blob/main/python_sdk/docs/ReportingApi.md

## Composition Boundary

Use existing GoogleHTTPRead/Vault/OwnedGoogleReportingContext and SQL sessions.
Factory construction must be IO-free. Local validation checks reporting switch,
existing mode, v24, client ID/secret/developer token and encryption key; absent or
invalid config yields fixed unavailable before real transport construction.
No new values are configured. State and explicit invalidation remain accessible
without reporting runtime. Existing fixture injection remains compatible.

The composed transport lazily permits only HTTPS POST to
`oauth2.googleapis.com/token` for the existing refresh_token grant, or
`googleads.googleapis.com/v24/customers/<10 digits>/googleAds:search` for reads.
Reject authorization-code exchange, foreign origins/ports/userinfo/fragments,
mutate paths and other verbs. Zero retries; no environment proxy/redirect support.
Own and close each inner HTTP transport across HTTP clients/pages; no global shared
open client. No advertising write-capable adapter is composed. Runtime disable/config
loss is rechecked before actual network construction and each request.

Provide optional availability callback on SelectedCustomerRuntime and
OwnedGoogleReportingContext. Production composition always supplies it. Existing
read guards must recheck it after authorization/expiry and immediately before final
range/confirmation/capture commit; context checks fence OAuth and every page.
Original customer, source/grant generation, account, aggregate, selection, mapping,
privacy, deadline and idempotency checks remain unchanged. A late disable rolls back
all pending durable effects. Replay is unavailable when reporting is disabled;
state/invalidation stay ungated. Injected legacy runtimes without callback preserve
existing behavior.

## Acceptance And Compatibility

Actual app.main.app dependency composition with fixture DB/identity/HTTP only;
no override of the new runtime dependency. Verify disabled/missing/wrong-version
configuration and original session failure cause no transport/rows. Verify provider
HTTP failure, final disable and exact replay. Full explicit aggregate → event option
→ confirmation → capture → Planning handoff/save/generate → history/export flow
uses fixture-private canonical v4 only; actual default v3 capability stays false.
Historical PlanVersion readers and Meta paths remain valid. Account timezone and
existing complete pagination proofs are preserved, not reinterpreted.

Run exact focused component then SQLite then PostgreSQL partitions with the proven
bounded runner, frozen source, original-exit/XML identity retention and resource
floors (512 MiB cgroup, 1 GiB workspace, 2 GiB scratch). Stop on first unexpected
failure, no unchanged retry, retain only independently source-applicable passes.
Independent contract, implementation and final evidence review required. No push,
hosted CI, merge, deploy, live provider/model call, real credential action or spend.
