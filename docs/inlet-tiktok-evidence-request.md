# TikTok Evidence Needed To Finish Native Discovery

**Superseded October 7, 2026:** rendered public official tables resolved this
documentation request. No owner export or account access is needed. See the
[verified response-contract record](design/tiktok-rendered-response-contract-20261007.md).
The historical request below is retained as evidence of the former blocker.

We need readable official response documentation or sanitized examples from a
nonproduction account for these two TikTok Business API v1.3 GET endpoints:

- `GET https://business-api.tiktok.com/open_api/v1.3/identity/get/`
  — the ordinary identity LIST endpoint, not identity INFO or GMV Max.
- `GET https://business-api.tiktok.com/open_api/v1.3/pixel/list/`
  — pixel discovery and its documented conversion-event information.

**Preferred:** export the response-field tables and examples from
[Get The Identity List](https://business-api.tiktok.com/portal/docs/get-the-identity-list/v1.3)
and [Get Pixels](https://business-api.tiktok.com/portal/docs/get-pixels/v1.3).
Include the source link, API version and date. This requires no ad-account access
or advertising spend.

If documentation is insufficient, a developer with separately authorized read-only
access to a nonproduction account can provide this small example pack:

1. One successful ordinary identity-list response for the supported
   `CUSTOMIZED_USER` identity type. We need the identity ID/type, display label,
   account or authorization binding, and any fields that establish usable status.
2. One successful pixel-list response. We need the pixel ID/label/account binding
   and the documented configured conversion-event information that establishes
   which event can be selected. If that information comes from a different endpoint,
   include its official documentation and sanitized response instead of guessing.
3. The pagination and empty/last-page examples needed to tell a complete result from
   an incomplete one. Include a permission-denied or ineligible example only if the
   documentation does not explain how those cases are represented.

These are descriptions of the facts needed, **not guessed JSON field names**. Keep
the real JSON keys, nesting, scalar types, nulls and pagination unchanged. Replace
all advertiser/resource IDs and names consistently with clearly synthetic values.
Include endpoint/version, capture date, request parameter names and safe pagination
values, plus a statement that the examples came from an owned nonproduction account.
Remove tokens, authorization headers, credentials, request IDs and personal data.
Do not send live credentials, perform advertising writes or create spend for this task.

The official SDK gives partial clues (`pixels`, `page_info`, page size at most20),
but does not define the nested response or event eligibility. A sample establishes
an observed shape; unsupported eligibility still remains unavailable. This evidence
will let us implement and test strict native discovery. It does not authorize live
advertising or replace the separate financial qualification checks.

[Detailed official-source evidence and exact pins](design/tiktok-list-response-recheck-2026-10-07.md).
