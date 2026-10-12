# TikTok Count Source Update — 2026-10-12

The parent supplied targeted official-source findings during the creative package.
These were not independently retrieved by this executor; no live call was made.
They resolve the narrow report-combination documentation gap retained in the earlier
handoff, but do not qualify a producer or live availability.

For regular, non-iOS14-dedicated campaigns, documented v1.3 composition supports:
`GET /open_api/v1.3/report/integrated/get/`, advertiser scope,
`service_type=AUCTION`, `report_type=BASIC`, `data_level=AUCTION_CAMPAIGN`,
`dimensions=["campaign_id","stat_time_day"]`, `metrics=["complete_payment"]`,
`query_lifetime=false`. The metric is website purchase action count. Evidence is
composition of documented rules, not a single worked example of every field.

## Official Sources Supplied

- [Metrics](https://business-api.tiktok.com/gateway/docs/index?doc_id=1751443967255553&identify_key=c0138ffadd90a955c1f0670a56fe348d1d40680b3c89461e09f78ed26785164b&language) — document `1751443967255553`.
- [Dimensions](https://business-api.tiktok.com/gateway/docs/index?doc_id=1751443956638721&identify_key=c0138ffadd90a955c1f0670a56fe348d1d40680b3c89461e09f78ed26785164b&language) — document `1751443956638721`.
- [Synchronous Guide](https://business-api.tiktok.com/gateway/docs/index?doc_id=1738864778664961&identify_key=c0138ffadd90a955c1f0670a56fe348d1d40680b3c89461e09f78ed26785164b&language) — document `1738864778664961`.
- [Endpoint](https://business-api.tiktok.com/gateway/docs/index?doc_id=1740302848100353&identify_key=c0138ffadd90a955c1f0670a56fe348d1d40680b3c89461e09f78ed26785164b&language) — document `1740302848100353`.
- [Filters](https://business-api.tiktok.com/gateway/docs/index?doc_id=1751443975608321&identify_key=c0138ffadd90a955c1f0670a56fe348d1d40680b3c89461e09f78ed26785164b&language) — document `1751443975608321`.

## Required Producer Constraints

- Account timezone; maximum 30-day daily range; inclusive dates; returned local
  `stat_time_day` formatted `YYYY-MM-DD 00:00:00`.
- Pages start at 1; page size 1–1,000; retain `page_info` page/page_size/total_number/
  total_page and request IDs. Avoid deprecated CHUNK mode.
- Synchronous reports truncate at 20,000 advertisements. `X-Tt-Ads-Throttle`
  indicates truncation. Paging and `enable_total_metrics` do not remove this cap.
  A capped single campaign fails completeness; do not assume date splitting cures it.
- `campaign_ids` is supported at campaign level, maximum 100, using `IN` and a JSON
  array string in `filter_value`. `adgroup_ids`/`ad_ids` are not substitutes for
  campaign-level partitioning. Multiple filters are ANDed.
- Campaign status defaults to `STATUS_NOT_DELETE`; intended deleted-inclusive scope
  requires `STATUS_ALL`. Campaign system origins default to `TT_ADS_PLATFORM`,
  excluding Promote. Campaign-level reporting excludes Branded Mission. Synchronous
  BASIC excludes Shop Product/LIVE GMV Max. Regular metrics exclude iOS14 campaigns.
- Completeness requires identical scope across pages, successful responses, exact
  pagination coverage, unique campaign/day rows, matching `total_number`, and
  retained request IDs/truncation headers.
- Empty rows or dash values are missing/meaningless-query possibilities, never
  silently verified zero. Ordinary count dates are impression-attributed account-
  local dates, not purchase-occurrence dates. Attribution window remains unknown.
- Campaign/day event type does not prove pixel/custom-event identity. No value
  metric, currency unit or live availability is established by this narrow evidence.

Next step: define and review the bounded count producer contract before implementation.
The creative package still retains its existing unsupported TikTok reporting gaps.
No broad research or failed gateway retries were repeated here.
