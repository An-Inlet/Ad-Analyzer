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
