# Provider Publication Contracts

This is implementation work toward B15/B16, not completion or live verification.
Fixture schemas/hashes and B07 simulation authority are unchanged. Provider review
and plan have separate `inlet.provider-publication-review.v1` and
`inlet.provider-publish-plan.v1` tags. No runtime provider factory is enabled.

`provider_contracts.py` owns shared typed ports: `ProviderPublicationReview`,
`ProviderPublishPlan`, `ProviderPublishStep`, `BoundProviderRequest`,
`ProviderReceipt`, `ProviderResponse`, `ValidationEvidence`, transient
`ProviderContext`, and `ProviderPublicationTransport`. Google is the only registered
configuration and operation union. Future providers must add explicit typed
variants through the central interface owner; arbitrary HTTP dictionaries are not
supported. The adapter lives under executors; compile/materialize are pure.

`compile_google` deterministically derives a bounded paused resource graph from a
separately reviewed source and explicit fields. `materialize_google` recompiles and
requires immutable original request/receipt pairs for all dependencies, exact
scope/plan/fence/digest and observation after dispatch. Customer supplied receipts
are not an accepted coordinator interface. Durable provider coordinator integration,
new review UI/approval persistence, qualified production mandate authority,
tracking/capability qualification, activation, and final settlement remain work.

The narrow first profile is Google Search with manual CPC, nonshared standard daily
budget, explicit conversion goal, exact keywords and responsive search ad. Average
daily budget is explicitly not a hard cap; the review reserves at least twice daily
budget for every included account-local day. This conservative calculation is not
live authority or a substitute for production provider qualification. Schedule must
explicitly cover whole local days. Additional schedule/bidding modes need new typed
review variants. Goal/country/language mappings require provider verification before
publication; their presence in the review is not verification.

Primary contracts checked 2026-10-06 and API pinned to v25:

- [Release notes](https://developers.google.com/google-ads/api/docs/release-notes)
- [REST mutation](https://developers.google.com/google-ads/api/rest/common/mutate)
- [Campaign](https://developers.google.com/google-ads/api/reference/rpc/v25/Campaign)
- [Campaign budget](https://developers.google.com/google-ads/api/reference/rpc/v25/CampaignBudget)
- [Conversion goal campaign configuration](https://developers.google.com/google-ads/api/reference/rpc/v25/ConversionGoalCampaignConfig)

No provider calls, real grants, customer data, mutations or advertising spend were
used to implement or test this package.

## Actual Google HTTP Adapter

`app/executors/google_publication.py` implements v25 REST validate-only, one-shot
mutation, exact-ID GAQL readback, and reconciliation against acknowledged original
attempts. It uses fixed Google origins and typed operation serializers, bounded
responses/timeouts, no redirects, sanitized failures, optional developer-token
headers, and no mutation retry. Construction performs no IO. The runtime factory
still returns unavailable; neither a valid document nor a transport is authority.

Readback checks all serialized semantic fields, including paused status, typed
parents, amounts, bidding, network, geography, schedule, text and URLs. Proto3
omitted default false/empty values are normalized only for explicitly requested
false/empty fields. A successful mutation acknowledgement is not a verified effect.
Conflicting fields or acknowledged IDs are conflicts. Empty/failed/incomplete
readback stays unknown. A timeout without an acknowledged resource ID stays unknown
and cannot be resent or inferred absent using a name search.

Mocked tests exercise the whole compiled graph through actual HTTP serialization,
validation, mutation acknowledgement and readback; before/after-effect timeouts,
foreign generation/workspace/login, expired context, invalid receipts, bounded
responses, redirects, rate limits, semantic drift, conflicting acknowledgements,
and preservation of fixture execution guards. These are offline contract tests,
not live API verification or qualified tracking evidence.

Remaining implementation includes provider account/currency/timezone and exact
conversion-goal/action/target qualification reads, durable provider approval and
coordinator integration, explicit production mandate authority, customer publication
review UI, separately reviewed activation, exposure settlement, and other providers.
The adapter does not establish production eligibility by itself.

## Persisted Google Configuration Qualification And Review

`google_qualification.qualify_google` now uses actual bounded Google search requests
through the injected HTTP client to check advertiser/currency/timezone, exact custom
conversion goal and enabled website purchase actions, geo country and targetable
language mappings. Only a digest of normalized evidence is retained; raw provider
payloads/tokens are not stored. This is configuration evidence, not full campaign
eligibility or spending authority. Qualification lasts at most five minutes.

`provider_service.prepare_google` builds the source/scope from current DB ownership,
releases locks for reads, then reacquires workspace/mandate/source locks and rechecks
owner, entitlement, source revision, advertiser and connection generation before
persisting. A reconnect during IO fails closed. Refresh appends a new qualification
and review rather than changing an approved proof. `approve` binds both exact review
and plan digests. `checked_review` rechecks current DB and fresh stored evidence.
`view` exposes the complete exact documents and explicit missing production features.

Migration0043 follows0040 and adds separate `provider_qualifications`,
`provider_reviews`, and `provider_review_approvals`, with scoped account/connection,
source-revision and qualification/review foreign keys. No provider review is inserted
into simulation mandate actions. `publication_authority` currently fails explicitly
because a production mandate/dispatch implementation is still missing code; it does
not interpret B07 simulation approval as permission. No live runtime is enabled.

The optional qualification proof is omitted from serialization when absent, preserving
existing unqualified Google review/plan hashes. Empty configuration blockers require
bound server evidence; the approval service verifies its persisted scope and expiry.
This does not clear unrelated production execution, activation or settlement work.

Additional primary field references:

- [Custom conversion goal](https://developers.google.com/google-ads/api/reference/rpc/v25/CustomConversionGoal)
- [Language constant](https://developers.google.com/google-ads/api/reference/rpc/v25/LanguageConstant)
- [Geo target constant](https://developers.google.com/google-ads/api/reference/rpc/v25/GeoTargetConstant)
