# Owned Linked TikTok Video Posts

The parent supplied the rendered official
[Get Posts Under An Identity](https://business-api.tiktok.com/portal/docs/get-posts-under-an-identity/v1.3)
request/response table on 2026-10-07. A bounded text fetch of that exact URL returned
no page text; this implementation relies on the supplied rendered schema, not a
live advertiser call or a guessed SDK response.

## Frozen Pure Interface

`app.collectors.tiktok_linked_posts_contracts` adds immutable versioned types:
`LinkedPostsRequestV1`, `LinkedPostsPageRequestV1`, `LinkedVideoPostV1`,
`LinkedPostsPageV1`, and `LinkedPostsCatalogV1`. Existing LinkedOwnerV1 and the
TT_USER / BC_AUTH_TT discriminated LinkedIdentityV1 are reused unchanged. BC ID is
required only by the BC variant. AUTH_CODE, CUSTOMIZED_USER and CAROUSEL are outside
this supported reader. No keyword is sent: keyword belongs to AUTH_CODE.

`parse_linked_posts_page(request, payload)` accepts a losslessly decoded object;
HTTP JSON decoding must use Decimal for noninteger numbers. Video duration retains
its native numeric magnitude without unit conversion. The strict parser requires
`data.cursor` string, `has_more` boolean and `video_list` list. It retains item ID,
VIDEO type, caption, visibility status and scalar video metadata; optional values
preserve absent/null/present distinctly. It discards media/poster URLs, signatures,
auth_info and anchor_list contents. The latter two may be null or objects, never
misread as list/eligibility proof. No media URL is fetched; documented URL expiry
(one hour, or poster x-expires) does not authorize retention or imply freshness.

Rows contain no returned advertiser/identity/BC/author proof. Each post therefore
commits the exact request owner and linked identity with `identity_binding` set to
`request_context_only`. The owned collector separately proves current local
ownership before/after IO. The post digest commits owner/identity/item ID/copy/
status/metadata, not observation timestamps. There is no invented asset video_id;
future Pull creative uses item_id as tiktok_item_id and separately reviews inherited
copy/visibility/rights. Presence or status never establishes ad eligibility.

First-page cursor omission follows the supplied required-field list (advertiser_id,
identity_id, identity_type, and conditional BC ID); cursor was not required. No
zero/default is guessed. Continuations retain the original decimal string and
convert directly to an arbitrary-precision integer, rejecting noncanonical syntax
or precision loss. Cursors can decrease because one documented mode represents
last-item time. Repeated continuation/cyclic cursors, duplicate item IDs and empty
has_more=true pages fail closed. Empty terminal pages are valid.

The aggregate is returned only for a terminated traversal. It says
`complete_requested_view`, never full history or a stable snapshot. With
exclude_adsonly=true the documented view is the latest500 organic posts; otherwise
it is the identity VIDEO view. A500-row/25-page local bound with remaining has_more
means unavailable, not complete. Result publication_eligibility remains
not_assessed and spending_authority none. These are read facts, never financial or
publication qualification.

## Owned Reader Seam

The next implementation is `TikTokLinkedPosts(scope, contexts, transport, clock)`
with `.videos(identity, *, exclude_adsonly, count=20)`. It reuses actual
OwnedTikTokContexts, original principal/session, source-generation and Vault checks.
Only explicit MockTransport and contract_test contexts are accepted; construction
opens no sockets. GET goes only to the fixed v1.3 identity/video/get endpoint.
Technical bounds are25pages/500rows,2MB per page,8MB total and30seconds monotonic,
with observation expiry no later than the earliest credential expiry or five
minutes from read start. Sessions close before IO, checks repeat after pages and
transport close, and all exceptions return no partial catalogue. There are no
routes, UI, native-media downloads, stored records or live factory enablement here.
