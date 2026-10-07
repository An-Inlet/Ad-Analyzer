# TikTok Rendered Response Contract Evidence

The parent research task verified rendered public official response and request
tables on October 7, 2026, without login, advertiser API access or credentials.
This supersedes the earlier request for an owner-provided schema export. It resolves
the response-shape documentation blocker, not account eligibility, financial
qualification, implementation validation or permission for live operations.

Sources:
- [Get The Identity List](https://business-api.tiktok.com/portal/docs/get-the-identity-list/v1.3#anchor-0-3)
- [Get Pixels](https://business-api.tiktok.com/portal/docs/get-pixels/v1.3#anchor-0-3)
- Request tables use `#anchor-0-2` on those same pages.
- [2026 Custom Identity transition](https://ads.tiktok.com/business/en/blog/custom-identity-transition?redirected=1)

## Identity List

`GET identity/get/` requires advertiser_id. Specify identity_type for documented
pagination: CUSTOMIZED_USER, AUTH_CODE, TT_USER or BC_AUTH_TT. BC_AUTH_TT additionally
requires identity_authorized_bc_id. Optional filtering.keyword applies to
CUSTOMIZED_USER or omitted type. Page defaults to1; page_size defaults20, range1–100.
No info_type or LIST request field is documented.

The envelope has numeric code, message, request_id and data. Data contains
identity_list and page_info(page,total_page,total_number,page_size).
Documented identity fields: identity_id, identity_type, identity_authorized_bc_id,
ads_only_mode, username, is_gpppa, can_push_video, can_pull_video, can_use_live_ads,
can_manage_message, display_name, available_status and profile_image. Do not borrow
user_name or profile_image_url from a different endpoint.

available_status applies only to TT_USER/BC_AUTH_TT, with AVAILABLE,
NO_VALID_BIND_ACCOUNT, SCOPE_UNAVAILABLE, IS_PRIVATE_ACCOUNT, NOT_BUSINESS_ACCOUNT.
Permission booleans describe these types. is_gpppa=true excludes Spark Ads.
ads_only_mode is nonnull for BC_AUTH_TT and true prevents dark_post_status=OFF.
Missing/not-applicable fields must remain distinguishable from negative facts.

Custom Identity is being phased out in2026. Presence in this list, or a missing
status inapplicable to CUSTOMIZED_USER, does not establish advertiser launch
eligibility. Assess a supported linked-profile route separately; neither this
research nor implementation authorizes linking an account or expanding access.

## Pixel List

`GET pixel/list/` requires advertiser_id; optional code,pixel_id,name;
order_by EARLIEST_CREATE(default) or LATEST_CREATE; nested
filtering.available_for_catalog_only defaultsfalse. Page defaults1, minimum1;
page_size defaults10, range1–20.

The envelope data contains pixels and page_info(page,page_size,total_number,total_page).
Pixel fields: pixel_id,pixel_code,pixel_name,pixel_category(deprecated),pixel_script,
create_time,pixel_setup_mode(STANDARD/DEVELOPER),partner_name,
advanced_matching_fields(phone_number,email booleans),
automatic_advanced_matching_fields(phone_number,email,name,address,external_id booleans),
enable_first_party_cookies,enable_expanded_data_sharing,asset_ownership,events.
Avoid retaining scripts or unused personal-data configuration in discovery output.

asset_ownership has nullable asset_relation_status, boolean ownership_status,
nullable owner_bc_id and deprecated integer updated_at. Null/TRANSFERRED relation
means ownership_status=true; SHARED/UNBOUND meansfalse. owner_bc_id is nonnull for
TRANSFERRED, otherwise null. UNBOUND is former sharing and excluded from reporting.

Event fields: currency_value,currency,name,deprecated,event_type(standard only),
optimization_event(nullable for PAGE_VIEW),custom_event_type(custom only),event_code,
event_id,statistic_type(EVERY_TIME/ONCE),rules. Rules have operator,trigger,value,
variable. Parent's table transcription lists operators as
`OPERATORTYPE_CONTAINS/DOES_NOT_EQUAL/EQUALS` and triggers as
`TRIGGERTYPE_CLICK/PAGEVIEW`; preserve this transcription until full literal enum
spellings are checked in the rendered table before validating rules. Variables:
ELEMENT,PAGE_HOSTNAME,PAGE_PATH,PAGE_URL. Endpoint currency table lists INR,JPY,USD;
this does not restrict unrelated platform contracts.

Events can take2–4hours to refresh. Missing events do not establish missing tracking.
Use a returned optimization_event for adgroup creation; never derive it from
name/code/ID/type. PAGE_VIEW cannot be optimized. activity_status occurs in an
example as NO_RECENT_ACTIVITY but has no verified readiness enum in the field table.
Do not infer readiness from that example or require every applicability-dependent
field on every item.

## Implementation Order And Gates

First freeze a separate versioned discovery-only request/page/observation interface
and strict parser, with bounded pagination and regression fixtures. Preserve
unknown/absent states and original v1 social catalog bytes; the existing
tiktok_decoded_contract_only catalog and CUSTOMIZED_USER-only creation contract
cannot silently become verified native discovery or a linked-profile publisher.
Then review native collector/runtime composition and separately assess the exact
linked-profile creative/publication contract. No write eligibility, activity,
spending authority or financial evidence is created by parsing a discovery response.

Current V2 preview-to-review runtime/browser acceptance takes precedence over this
next package. No parser or provider integration is claimed complete by this record.
