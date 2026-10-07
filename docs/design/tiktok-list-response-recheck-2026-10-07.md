# TikTok LIST Response Evidence Recheck

**Later October 7 evidence:** [rendered official tables](tiktok-rendered-response-contract-20261007.md)
resolved the document-access gap described below. This earlier failed/partial
research is retained, not evidence that an owner export is still required.

Research date: 2026-10-07 UTC. Documentation-only followup to
[the original evidence check](tiktok-catalog-response-evidence.md) and
[remaining implementation gap](tiktok-catalog-remaining-gap.md), based on repository
5509d37. No credentials, account API requests, code changes or live qualification.

## Result

The targeted public-source recheck adds **partial pixel-list evidence**, but does
not establish a complete native identity/pixel decoder. Keep native catalog
qualification blocked. This is a missing response-contract and implementation gap,
not merely deployment configuration. Existing decoded contract-test discovery and
publication/readback tests remain valid within their stated limits.

The official SDK repository's public default-branch page still identified commit
`f809c396520df2d7b201a9ccc5378d822b728ed3` during this check. All SDK links below
are pinned to that commit; this does not claim the deployed API cannot differ.

## Newly Read First-Party OpenAPI Evidence

[Official pixel_list.yml](https://github.com/tiktok/tiktok-business-api-sdk/blob/f809c396520df2d7b201a9ccc5378d822b728ed3/yml_files/pixel_list.yml)
identifies `/pixel/list/`, advertiser-scoped GET parameters, page minimum 1 and
page_size from 1 through 20. Its generated response-rule mapping names `pixels`
and `page_info`, sourced from internal RPC output. These are useful clues from an
authoritative artifact, **not a typed nested JSON response contract**: the HTTP
200 schema still declares nullable `data` as an object with empty `properties`.
It does not define pixel element fields/types, configured events, eligibility,
page-info fields, terminal-page rules, or empty/missing collection behavior.
Do not infer `data.list`, event eligibility, or numeric/string conversions.

The YAML also places Access-Token in a query declaration whereas generated client
usage supplies a header. This source inconsistency is not authority to change
existing authentication handling.

The pinned SDK archive contains 2,566 members. A bounded scan of its YAML/JSON
specifications found no standalone specification for the exact `/identity/get/`
endpoint. The visible identity YAML is
[gmv_max_identity_get.yml](https://github.com/tiktok/tiktok-business-api-sdk/blob/f809c396520df2d7b201a9ccc5378d822b728ed3/yml_files/gmv_max_identity_get.yml):
it contains an identity-list response mapping, but for `/gmv_max/identity/get/`,
with store and Business Center context and GMV Max eligibility. Those fields
cannot establish the ordinary identity-list contract.

## What Each SDK Actually Proves

- Python's previously checked `InlineResponse200` exposes generic `data: object`.
- [JavaScript InlineResponse200](https://github.com/tiktok/tiktok-business-api-sdk/blob/f809c396520df2d7b201a9ccc5378d822b728ed3/js_sdk/src/model/InlineResponse200.js)
  converts `data` to `Object`; it does not decode or validate LIST elements.
- Java's [IdentityApi](https://github.com/tiktok/tiktok-business-api-sdk/blob/f809c396520df2d7b201a9ccc5378d822b728ed3/java_sdk/docs/IdentityApi.md)
  and [MeasurementApi](https://github.com/tiktok/tiktok-business-api-sdk/blob/f809c396520df2d7b201a9ccc5378d822b728ed3/java_sdk/docs/MeasurementApi.md)
  return `Response`, not a typed identity/pixel collection. The actual
  [Response.java](https://github.com/tiktok/tiktok-business-api-sdk/blob/f809c396520df2d7b201a9ccc5378d822b728ed3/java_sdk/src/main/java/business_api/Response.java)
  retains `data` as `Object`. Its generated documentation and implementation also
  differ in outer-envelope detail; neither supplies the missing nested contract.

Request signatures and generic deserialization demonstrate endpoint invocation
support. They do not prove account ownership of every returned item, eligibility,
complete pagination, supported event configuration, or response-type strictness.

## Official Documentation Access Limits

[Get The Identity List](https://business-api.tiktok.com/portal/docs/get-the-identity-list/v1.3)
and [Get Pixels](https://business-api.tiktok.com/portal/docs/get-pixels/v1.3)
again yielded page titles but no readable response tables through the web reader.
The [official TikTok Postman identity request](https://www.postman.com/tiktok/tiktok-api-for-business/request/lsu77rw/identity-get)
shows the request, without a published response example. The readable
[identity INFO page](https://business-api.tiktok.com/portal/docs/get-info-about-an-identity/v1.3)
is a different endpoint; its identity_info/status fields do not prove ordinary
LIST shape or all identity-type eligibility.

A separate direct documentation-site fetch failed at the environment proxy's
CONNECT stage with 403; it was not a response from an authenticated TikTok API.
No retry/bypass, provider call or credential request followed. Public pinned SDK
sources remained readable. These limits do not prove that TikTok has no private
or browser-readable response documentation.

## Smallest Evidence Handoff That Unblocks Implementation

Prefer readable official v1.3 response tables and examples for **these exact two
LIST endpoints**, with source URL/version/retrieval date. Required facts:

1. Exact envelope, collection, element and pagination keys/types, including empty
   and terminal results. For pixels, confirm how the SDK `pixels`/`page_info`
   response mappings appear on the wire.
2. Identity ID/type and account/authorization binding; documented eligibility for
   the identity type Inlet offers. Unknown statuses remain unavailable.
3. Pixel ID/account binding and the exact response or separately documented
   endpoint that proves the selected configured conversion event is usable.
   Pixel existence or an event enum alone is insufficient.

If those documents omit wire examples, the minimum useful **separately authorized
nonproduction evidence pack** is one sanitized successful ordinary identity-list
response for the supported type, one pixel-list response containing its documented
configured-event representation (or the documented supplementary response), and
pagination/empty examples sufficient to establish completion. Add an ineligible or
permission-denied example only where necessary to distinguish eligibility/error
semantics. Do not require someone to generate advertising spend or writes.

Keep JSON keys, scalar types, nulls, nesting and pagination intact; consistently
replace advertiser/resource IDs and names with clearly synthetic values. Include
endpoint/version, request parameter names and safe pagination values, capture date,
and a short statement of nonproduction ownership/context. Omit tokens, auth headers,
request IDs, personal data and credentials. A sanitized capture proves an observed
shape, not universal permission or eligibility; missing semantics still fail closed.
No such capture was requested from a provider or obtained during this research.

After evidence is available, implement the bounded GET decoder, source/account
binding, complete pagination and explicit native discriminator; test it through
MockTransport and the ordinary configured customer path. Financial qualification,
liability/headroom evidence, calibrated policy and live authorization remain separate
requirements. No blockers or defaults are removed by this document.

## Retrieval Fingerprints

SHA-256 of exact public source bytes read at the pinned commit:

| Artifact | SHA-256 |
| --- | --- |
| yml_files/pixel_list.yml | `9c0a4ea8c558508d5e7fd8f125b2f17ceb65ea8bad95cc722dd43b4793b06ca2` |
| yml_files/gmv_max_identity_get.yml | `f2a46bfccc220f10d1ce8bc56d7abf134a6fb19cf7b9e5b641a843a63d129b18` |
| js_sdk/src/model/InlineResponse200.js | `d1e4f7b266f43d30ad523f0a20b735c445dbe4ac0082cbfba738ca883bfdce2e` |
| java_sdk/src/main/java/business_api/Response.java | `e2fc878c8baae4ad1e3e9581d7cbf61bd5b535901652f89fbd4059a2ed7dd11e` |
| java_sdk/docs/Response.md | `04d1e3c109bb593dbf50bb0f7808911004c95ef22b65ba64919ff1d74d49ca8b` |

Validation: source inspection and `git diff --check` only. No application tests,
Full, database operations or remote writes were needed for this documentation.
