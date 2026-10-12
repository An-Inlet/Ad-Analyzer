# Meta Website Purchase Counts — Bounded Producer V1

Baseline b463383. The previous hold was broader than needed: effective attribution
and monetary units are not prerequisites to retaining exact provider-reported counts
with explicit unknowns. This package covers one standard event at one report grain.

## Evidence And Inference

The supplied official AdsActionStats research identifies
`offsite_conversion.fb_pixel_purchase`. Meta's primary documentation endpoints still
returned429/fetch errors here; no bypass was attempted. Independent permitted reads
of the official SDK26.0.2 establish the current v26 wire contract:

- [API configuration](https://raw.githubusercontent.com/facebook/facebook-python-business-sdk/26.0.2/facebook_business/apiconfig.py): v26.0.
- [AdAccount.get_insights](https://raw.githubusercontent.com/facebook/facebook-python-business-sdk/26.0.2/facebook_business/adobjects/adaccount.py): GET Insights, fields, campaign level, action breakdown, date range and increment.
- [AdsInsights](https://raw.githubusercontent.com/facebook/facebook-python-business-sdk/26.0.2/facebook_business/adobjects/adsinsights.py): account/campaign identity, currency, dates and actions list.
- [AdsActionStats](https://raw.githubusercontent.com/facebook/facebook-python-business-sdk/26.0.2/facebook_business/adobjects/adsactionstats.py): exact action_type and value strings.

Combined with the previously verified [action reference](https://developers.facebook.com/docs/marketing-api/reference/ads-action-stats)
and [Insights reference](https://developers.facebook.com/documentation/ads-commerce/marketing-api/reference/ad-account/insights),
this is sufficient engineering evidence for a fixture-qualified standard, unbroken-down
campaign/day count reader. This is an inference from the documented building blocks,
not universal account availability or a live API qualification. SDK enums do not
override the verified changelog concerning ignored flags and retired windows.

## Fixed Interface

New profile `meta.website-purchase-count.campaign-day.v1`; retain the existing three
unverified social profiles unchanged. Exact selected event above, family `actions`,
APIv26.0, advertiser-owned reporting scope (not pixel ownership). Distinct producer
and query digest bind the full fixed query descriptor. Requested attribution options
are all absent. Effective windows/report time and counting mode remain unknown.
Value unit remains unknown; selected money is always unsupported, never inferred.
The finite support state means documented count parsing, not verified live coverage.

GET `/v26.0/act_<advertiser>/insights`, fields
`account_id,campaign_id,date_start,date_stop,account_currency,actions`, `level=campaign`,
`time_increment=1`, bounded closed `time_range`, `action_breakdowns=[action_type]`,
limit100 and explicit after cursor. No general breakdowns, filtering, summary,
unique_actions, action_values, attribution windows or ignored report-time flags.
No claim of deleted-object/status-complete coverage; omitted campaign/days remain
missing. The fixed query descriptor retains that omission policy.

Parser validates exact account/currency, owned campaign mapping, dates and grain.
Only the exact action item may supply count. Missing actions/item/value remains
missing; explicit numeric0 is present; null, malformed/nonfinite/negative/excess-
precision values and duplicate action types/rows fail closed. Generic/grouped/app
purchase keys never substitute. Window or extra breakdown fields on the selected
item cannot masquerade as the unbroken-down value. Raw duplicate JSON keys fail.
Complete cursor pagination is required; next URLs are never followed or retained.

Bounded HTTP reader receives a request-bound ephemeral context and revalidates
original authority before/after IO. Account metadata must match native advertiser,
currency and timezone. A owned acquisition function derives campaigns from SQL,
checks original customer/session/workspace/connection generation/selection/aggregate,
rechecks after all IO, then atomically stores through existing selected storage.
No DB transaction is held across provider IO. The injecting caller owns and closes
the underlying HTTP transport after the operation, on success or failure; per-page
clients borrow it and still close every response stream. The write context starts
a physical SQLite outer transaction before nested storage, and authorizes/checks
the deadline before committing on either backend. No default network factory or public
picker/route activation is added in this first producer package. Tests inject HTTP
and synthetic grants only; no live calls or real credential handling.

New captures retain request2/capture2/provenance2/plan3 boundaries. Old profiles,
payloads and digests remain unchanged; old readers reject the new profile. Reader
floor advances to this profile-capable version without data rewriting/migration.
UI keeps requested/effective separation, displays unavailable money and unknown
counting mode, and refuses capability/profile contradictions. Cross-account/platform
comparison remains unqualified.

## Qualification And Remaining Gaps

Focused pure parser, injected HTTP/collection, SQL ownership/revocation/atomicity,
pagination/error/malformed/missing/zero, storage/export and UI cases. Whole Ruff,
configured mypy and reviewed frozen evidence; one heavy slot, SQLite before PG,
stop first unexpected failure, preserve original artifacts and resource floors.

Optional for this producer: known attribution windows/report time/counting mode,
monetary value and deleted-object completeness. They remain explicitly unknown or
unavailable. True deferred prerequisites: custom-event/pixel identity, explicit-window
and other-breakdown combinations, and money scaling before those features are added.
TikTok's exact website count report combination and money units remain separate gaps;
no need to block this narrower Meta count reader on them. All owner, remote, live,
release, credential and spending holds remain; planning is manual-action-only.
