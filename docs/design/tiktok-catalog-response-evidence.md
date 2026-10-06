# TikTok Catalog Response Evidence Check

Checked 2026-10-06. Bounded official-documentation/official-SDK research only; no
provider API calls, credentials or customer data. Native catalog parser remains
unimplemented and `tiktok_native_catalog_parser_unverified` remains mandatory.

Related implementation: [Social customer configuration catalog](../inlet-social-customer-catalog.md),
[typed catalog ports](../../app/publication/social_catalog.py), and
[canonical plan producer](../../app/publication/social_customer_producer.py).

## Verified Evidence

Official SDK `tiktok/tiktok-business-api-sdk`, pinned
`f809c396520df2d7b201a9ccc5378d822b728ed3`:

- [identity_api.py](https://github.com/tiktok/tiktok-business-api-sdk/blob/f809c396520df2d7b201a9ccc5378d822b728ed3/python_sdk/business_api_client/api/identity_api.py): GET
  `/open_api/v1.3/identity/get/`; advertiser_id, identity_type and page/page_size;
  CUSTOMIZED_USER exists in the request enum. Return type InlineResponse200.
- [measurement_api.py](https://github.com/tiktok/tiktok-business-api-sdk/blob/f809c396520df2d7b201a9ccc5378d822b728ed3/python_sdk/business_api_client/api/measurement_api.py): GET
  `/open_api/v1.3/pixel/list/`; advertiser_id, optional filters and page/page_size;
  return type InlineResponse200.
- [inline_response200.py](https://github.com/tiktok/tiktok-business-api-sdk/blob/f809c396520df2d7b201a9ccc5378d822b728ed3/python_sdk/business_api_client/models/inline_response200.py): code integer,
  data object, message string, request_id string. No nested collection/resource
  schemas. This does not establish list keys, empty-list behavior, identity/pixel
  names, account links, event structures, pagination totals or eligibility flags.

Official documentation routes resolved their titles but yielded no readable body:

- https://business-api.tiktok.com/portal/docs/get-the-identity-list/v1.3
- https://business-api.tiktok.com/portal/docs/get-pixels/v1.3
- https://business-api.tiktok.com/portal/docs?id=1740858697598978

Identity document ID1740218420781057 was inaccessible to the web tool. Search queries
restricted to official TikTok documentation and the official SDK did not recover
these endpoints' nested response schemas. The official Postman identity request
verifies request shape only and has no available response sample:
https://www.postman.com/tiktok/tiktok-api-for-business/request/lsu77rw/identity-get

A useful but insufficient partial result is the indexed first-party identity INFO
endpoint, a different operation:
https://business-api.tiktok.com/portal/docs/get-info-about-an-identity/v1.3
It documents advertiser_id/identity_id/identity_type inputs and an identity_info
response object, identity_id/type strings, and the v1.3 profile_image_url rename.
It cannot establish the LIST endpoint's schema or completeness/pagination. Do not
silently replace discovery with customer-entered provider identities.

Another indexed first-party guide confirms pixel/list is used to retrieve configured
pixel optimization events, but does not specify its nested response representation:
https://business-api.tiktok.com/portal/docs/create-an-upgraded-smart-lead-generation-campaign-with-location-as-website/v1.3
That guide's Smart+ fields/formats are outside this package; no scope expansion.

## Exact Evidence Required Before A Native Parser

Obtain the v1.3 RESPONSE parameter tables and success examples for the identity LIST
and pixel LIST documents above, with source URL/version and retrieval date. Needed:

1. Exact data collection keys and element shapes; identity ID/type/display-name
   fields; pixel ID/name fields; string/number/nullability rules; whether each row
   echoes advertiser ID or account membership follows solely from the endpoint.
2. Exact page_info (or other) shape, page/size/total/page-count types and semantics,
   terminal empty-page behavior, allowed page size, and whether omissions imply
   truncation/unknown. Never assume `data.list` or absence means empty completion.
3. The pixel's configured event list shape and event identifiers, plus documented
   distinctions between configured/active/eligible/authorized. The SHOPPING create
   enum does not prove that a particular pixel can optimize for that event.
4. Identity eligibility/status fields and semantics for CUSTOMIZED_USER, if offered;
   absence of a field must not be promoted to permission. Broader TT_USER/BC_AUTH_TT
   identities are not part of the existing approved publication format.
5. Sanitized provider-published examples or an authorized nonproduction capture
   with exact schema preserved for: one valid page, multiple pages and final empty
   result, inaccessible/foreign resource, disabled/ineligible resource and normal
   error envelope. No access token, real customer name or unredacted identity data.

Once these are available, implement injected HTTP fixtures matching those exact
schemas and verify strict IDs, original advertiser/generation, pagination completeness,
limits, invalid/missing/duplicate fields, stale context, redirects and sanitized
errors. Native schema validation is still separate from configuration eligibility,
spend exposure, durable customer review and live runtime authorization.

## Declaration Interface Agreement

The coordinated declaration/cover design requires exact
option/profile/requirements/wording/media selection digests, persisted confirmation,
current confirmer ownership and original customer-session authorization. Optional
social configuration-review reference must serialize only when present to preserve
legacy hashes. Customer paths require it; compatibility must not bypass live guards.
Privacy erasure must cover downstream canonical plan/request copies and invalidate
forward authority. This record documents design agreement, not an implemented declaration repository.
No shared module or migration was edited in this research task.
