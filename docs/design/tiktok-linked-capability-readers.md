# Owned Linked TikTok Capability Reads

`TikTokLinkedCapabilities` uses the frozen linked contracts and the existing
`OwnedTikTokContexts` private-session, paid-work, original-customer and source
credential checks. `identity(identity)` performs one `GET identity/info/`;
`advertiser()` performs a separate `GET advertiser/info/` with explicit JSON
`advertiser_ids` and `(ads_only_mode, can_use_custom_identity)` fields. The latter
uses the special response mode, never the ordinary account-profile decoder.

The parent verified the rendered official tables on October 7, 2026:
[Identity Info](https://business-api.tiktok.com/portal/docs/get-info-about-an-identity/v1.3)
and [Advertiser Details](https://business-api.tiktok.com/portal/docs/get-ad-account-details/v1.3).
Identity data is under `data.identity_info`; advertiser special rows are under
`data.list`. Identity/type/conditional BC and the singleton advertiser must match
exactly. Unknown status stays unknown; boolean absence, null and false remain
distinct. Raw names, image URLs and provider messages are not retained. TT identity
ads-only observations are not proof of the BC-only documented capability.

Transport admission remains explicit MockTransport plus contract_test manifest.
Each call has a ten-second monotonic bound and 256 KiB decoded-body cap, forbids
redirects, duplicate JSON keys and nonfinite numbers, and rechecks owned authority
before and after IO and after transport close. Result expiry cannot outlive the
original credential context or five minutes. Context changes discard the result.
No locks are held through HTTP. These observations do not grant publishing rights,
BC ownership, financial qualification, or permission for a live account call.

The configured linked publication consumer is assembled in its separate package;
this reader does not alter v1 reviews, old normalized results, source registries or
financial holds. Pull's post catalog is a separate endpoint and is not inferred
from these capability rows.

Validation: 28 actual original-session/vault/MockHTTP cases passed across SQLite and
PostgreSQL in 55.63 seconds, including revocation and source change during IO and
revocation on close. Five additional transport-boundary cases passed in 1.59 seconds
(oversized body, redirect, nonfinite JSON, invalid envelope and expiry during close).
Whole Ruff, mypy863 and diff checks passed; the five-test addition also received
scoped mypy. No live provider verification is claimed.
