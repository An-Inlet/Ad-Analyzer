# TikTok Regular Inventory Diagnostics

`app/collectors/tiktok_native_inventory.py` implements the frozen
[diagnostic request/context port](design/native-diagnostic-assembly.md). It reads actual
fixed v1.3 advertiser/info, campaign/get and adgroup/get routes using an injected
bounded HTTP transport. Requests enumerate the advertiser's regular endpoint inventory
with STATUS_ALL, no selected campaign-ID filter, <=10 numbered pages and <=200 rows
per edge. Duplicate IDs, foreign advertiser/parent, changing totals, count mismatch,
malformed pages, oversized results, invalid amounts or stale context fail closed.
An empty zero-page response is accepted only with explicit zero total and no rows.

Each read freshly resolves exact account/generation/request-bound context before and
after IO. Limits are 5-second connect/12-second read-write-pool, 60-second elapsed checks,
21 calls, one MB per response/four MB total. No redirects or environment proxies.
No write route, token exchange, credential factory, persistence or retry is installed.
Error codes are fixed/sanitized; provider bodies, tokens and identifiers are not returned
in errors or logged by HTTP request logging.

Budgets preserve decimal observations (JSON parsed with Decimal) without binary-float
rounding or a fabricated currency conversion. Missing budget/schedule/optimization
fields stay null. Schedule strings remain native observations, not an enforced exposure
window. Results fix accounting and unit semantics to unqualified, and U/F/P, watermark,
account cap/reset epoch and original-request terminality to null.

`regular_inventory_read_complete` means the supported paginated reads finished.
`all_campaign_families_complete=false` and historical/pending-cap completeness false
remain explicit: separate Smart Plus/GMV Max APIs exist, and regular inventory does not
prove their absence or the complete historical liability set. Budget Manager, balances,
resets, original-request closure and native prevention are not guessed or qualified.

Primary endpoint/parameter evidence is the official TikTok SDK pinned at
`f809c396520df2d7b201a9ccc5378d822b728ed3`:
[CampaignCreationApi](https://github.com/tiktok/tiktok-business-api-sdk/blob/f809c396520df2d7b201a9ccc5378d822b728ed3/python_sdk/docs/CampaignCreationApi.md),
[AdgroupApi](https://github.com/tiktok/tiktok-business-api-sdk/blob/f809c396520df2d7b201a9ccc5378d822b728ed3/python_sdk/docs/AdgroupApi.md),
and existing [authentication/read runtime evidence](inlet-tiktok-http-runtime.md).
The SDK uses a generic response envelope; the diagnostic decoder reuses the existing
regular adapter field contract, with actual MockTransport parsing tests. This is not
a live response qualification claim. [Spending source gaps](design/production-spending-source-readiness.md)
remain explicit.

Validation:107 focused HTTP tests passed (TikTok and Meta native diagnostics plus social
optimization HTTP), no skips. Whole Ruff/mypy501/diff passed. No database/schema change,
Full, provider calls, live qualification or spending authority.
