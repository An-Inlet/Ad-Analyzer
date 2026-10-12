# Exact TikTok Research Handoff

Unresolved question: Does TikTok Business API v1.3 synchronous
`GET /open_api/v1.3/report/integrated/get/` support the website-purchase **count**
metric `complete_payment` for advertiser-scoped `report_type=BASIC`,
`data_level=AUCTION_CAMPAIGN`, and dimensions exactly
`["campaign_id", "stat_time_day"]`? What documented restrictions apply (objective,
placement, campaign type, status/deleted-object filters), and does its count denote
website Complete Payment for that scope rather than a generic optimization event,
app purchase or omnichannel total?

Need official evidence for that exact combination, count semantics, date/time basis
and advertiser timezone, plus page/page_size/total-page completion semantics.
Do not infer the combination from independent lists of metrics and dimensions.
Absence must remain missing/unsupported unless official evidence establishes zero.
No value metric, currency unit, pixel identity or effective attribution is requested
for this narrow count producer. Capture those as unknown/unverified when unproven.

Already inspected, without live-account calls:

- Official SDK ReportingApi.md:
  https://github.com/tiktok/tiktok-business-api-sdk/blob/main/python_sdk/docs/ReportingApi.md
  Readable in prior package; establishes synchronous endpoint and request parameter
  names, not this exact supported metric/report/data-level/dimension combination.
- Official metrics gateway document `1751443967255553`:
  https://business-api.tiktok.com/gateway/docs/index?doc_id=1751443967255553&identify_key=c0138ffadd90a955c1f0670a56fe348d1d40680b3c89461e09f78ed26785164b&language
- Official dimensions gateway document `1751443956638721`:
  https://business-api.tiktok.com/gateway/docs/index?doc_id=1751443956638721&identify_key=c0138ffadd90a955c1f0670a56fe348d1d40680b3c89461e09f78ed26785164b&language
- Official synchronous guide document `1738864778664961`:
  https://business-api.tiktok.com/gateway/docs/index?doc_id=1738864778664961&identify_key=c0138ffadd90a955c1f0670a56fe348d1d40680b3c89461e09f78ed26785164b&language
  These three gateway reads were inaccessible to this executor; bounded urllib
  attempts returned proxy tunnel403. Exact error records are retained in
  `/workspace/inlet-evidence/20261012/tiktok-count-research/`. No bodies downloaded.
- https://ads.tiktok.com/resources/help/article/conversion-discrepancies
  Appears in the parent's official-source handoff for impression-time reporting;
  not independently retrieved by this executor. That general statement cannot
  establish the exact metric combination or effective account attribution settings.

Parent handoff distinguishes `complete_payment` from `total_purchase`, app purchase,
custom app/page events, and ratio metrics; explicitly leaves metric availability
for every combination unknown. Its file is
`/workspace/inlet-evidence/20261012/social-semantics-research/parent-official-source-handoff.json`.
No new broad research or endpoint retries were performed in this package.
