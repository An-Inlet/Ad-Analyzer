# Social Customer Configuration Catalog

Implemented on an isolated child of customer catalog port `9c2d9f6`. This package
adds no routes, default runtime factory, credentials, live qualification or spend.
The Google catalog types and compiler hashes are unchanged.

`social_catalog.py` defines exact source/account/generation requests and separate
Meta/TikTok options. Their opaque identifiers bind all request and option fields;
refresh timestamps do not change selection, but source, generation or profile edits
do. Results are capped at 50 options, 64 KiB and five minutes. Portal consumers must
project only opaque identifiers, labels, meaningful profile summaries and blockers,
never serialize the internal catalog's provider references as customer proof.

`MetaCatalogHTTP` makes actual injectable read-only HTTP requests to v26 account
metadata, `/promote_pages` and `/adspixels`. It requires the exact active account,
uses fixed hosts, follows only returned cursor values on original account paths,
and never follows provider next URLs. It bounds requests (21), pages per edge (10),
rows per edge (100), total response bytes (4 MB), individual response bytes (1 MB)
and elapsed operation time (60 seconds, HTTP phases at most 12 seconds). There are
no retries or redirects. Credentials are excluded from repr/serialization; provider
failures produce fixed codes. A promotable Page or account-accessible pixel is not
proof of exclusive legal ownership, conversion eligibility or publish permission.

Server-registered Meta profiles explicitly bind currency precision, locale mapping,
ages, attribution, tracking tags and whether beneficiary/payor declarations are
required. The catalog does not claim these mappings/combinations are native-qualified.
The publication fields are the existing bounded Facebook feed image profile; no
additional formats, placements or autonomous settings are introduced.

`SocialPlanProducer.produce` selects a current opaque option, validates exact catalog
and artifact identity, reads real owned private media, builds existing typed fields,
compiles the canonical five-step paused/disabled graph, and calls the coordinator's
current DB source/owner/native-generation checks. It neither commits nor emits ads.
The facade must still authorize the original session after external IO, re-read the
catalog before selection, and present the entire exact execution review before
approval. The coordinator independently requires current configuration qualification,
separate production consent, complete exposure and spending reservations.

Meta requires a server `MetaDeclarationReader`: exact request digest, durable audit
record ID, confirmed actor/time, explicit no-special-category declaration and DSA
values. No category or beneficiary is inferred or defaulted from ecommerce content.
This package does not implement a production declaration persistence repository:
without the separately implemented audited customer-confirmation flow, production
Meta configuration remains unavailable. Tests explicitly inject a server contract
fixture, never claim a fixture ID is a persisted customer audit.

TikTok has a typed decoded catalog/profile port and canonical producer only. No
native response parser is installed: the official SDK exposes generic response
objects, and accessible portal/Postman material did not establish exact nested
identity/pixel response fields. Every decoded catalog must retain
`tiktok_native_catalog_parser_unverified`. A current owned image cover must be
explicitly selected; it is bound into the separate exact execution review, not
misrepresented as part of the earlier video-only B14 approval. Missing/foreign
covers fail closed. No video-to-cover heuristic runs.

## Verification

Focused MockTransport tests exercise real Meta URL/headers/query serialization,
pagination, unchanged original host, duplicates/cycles, wrong or disabled account,
response limits, redirects/timeouts and context/expiry guards. Database producer
tests use the actual source approval/native connection/private image/video fixtures
and cover canonical plans, generation changes, removed media/approval, expired
catalogs, invalid options, missing declarations and missing/unowned covers. These
are offline tests; no provider behavior has been live verified.

## Primary Contract Evidence

- [Meta official AdAccount SDK](https://github.com/facebook/facebook-python-business-sdk/blob/efd8423a2e595ea8d4c04eb824ce113f2f1d68cd/facebook_business/adobjects/adaccount.py): v26 account fields, promotable Page and AdsPixel edges.
- [Meta official Page SDK](https://github.com/facebook/facebook-python-business-sdk/blob/efd8423a2e595ea8d4c04eb824ce113f2f1d68cd/facebook_business/adobjects/page.py): selected id/name fields.
- [Meta official AdsPixel SDK](https://github.com/facebook/facebook-python-business-sdk/blob/efd8423a2e595ea8d4c04eb824ce113f2f1d68cd/facebook_business/adobjects/adspixel.py): selected id/name fields. Event statistics are not conversion eligibility proof.
- [TikTok official identity SDK](https://github.com/tiktok/tiktok-business-api-sdk/blob/f809c396520df2d7b201a9ccc5378d822b728ed3/python_sdk/business_api_client/api/identity_api.py): advertiser/type/page request contract; generic response.
- [TikTok official measurement SDK](https://github.com/tiktok/tiktok-business-api-sdk/blob/f809c396520df2d7b201a9ccc5378d822b728ed3/python_sdk/business_api_client/api/measurement_api.py): advertiser/pixel/page request contract; generic response.
- [TikTok official Postman identity request](https://www.postman.com/tiktok/tiktok-api-for-business/request/lsu77rw/identity-get): request-only evidence, no response sample.

## Package Validation Record

On this package tree, the focused command ran with
`AD_ANALYZER_CI_DISPOSABLE_POSTGRES=true` and the explicitly disposable local
PostgreSQL test service:

```
pytest -xra tests/test_social_customer_producer.py tests/test_meta_catalog_http.py \
  tests/test_social_customer_catalog.py tests/test_social_publication_contracts.py \
  tests/test_social_publication_http.py
```

Result: **75 passed, zero skips**, including SQLite and PostgreSQL producer cases.
Whole-tree `ruff check .`, configured `mypy` (440 files), and `git diff --check`
passed. No Full run, hosted CI result or live-provider verification is claimed.
Two initial producer test runs exposed a test-only encoded-video fixture invocation
typo; it was corrected before the successful complete focused run.
