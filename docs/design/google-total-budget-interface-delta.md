# Google Total-Budget Publication Interface Delta

Approved additive interface against `c6d72b6`; backend implementation in progress. Scope is actual
reviewed PAUSED Search/manual-CPC publication/compiler/HTTP semantic readback only.
[Restricted profile rationale](google-restricted-mandate-profiles.md). No automatic existing
campaign enrollment, budget optimization, pause policy or financial qualification.

## Documents And Compatibility

- Keep existing `GoogleSearchPublicationFields` (`kind=google_search_v25`) unchanged
  semantically, including `daily_budget_micros`, its conservative reservation check,
  canonical serialized documents and hashes.
- Add `GoogleSearchTotalPublicationFields` with `kind=google_search_total_v25_v1`.
  Reuse tracking, geo/language, network, manual-CPC, activation and omission fields;
  replace the daily amount with positive `total_budget_micros` and the literal
  `budget_semantics=native_total_budget_not_portfolio_proof`. Mixed daily/total inputs fail.
  `reservation_micros` still exactly matches the approved creative definition's budget;
  total amount must not exceed it. This is an allocation check, not an exposure theorem.
- `ProviderPublicationReview.configuration` becomes a kind-discriminated union. Existing
  outer review schema remains v1; the new versioned configuration discriminator makes
  the extension explicit. Its digest and qualification binding include the variant.
- Preserve current reviewed local-midnight/day-end datetimes, with account timezone bound
  to provider qualification. Google documents 3–90 days without defining inclusive/DST
  boundary rounding. Initial Inlet support is 4–89 inclusive local days AND 72 through
  90*24 elapsed UTC hours; rejection is an Inlet qualification boundary, not a claim
  Google rejects those dates. No implicit extension or DAILY conversion.

## Operations And Compiler

- Add `GoogleCreateTotalBudget` with kind `google_create_total_budget_v1`,
  `total_amount_micros`, `period=CUSTOM_PERIOD`, `explicitly_shared=false`, and existing
  delivery method. No daily amount field.
- Extend `ProviderOperation` and `GoogleCreatePausedCampaign.configuration` unions.
  Existing campaign start/end datetime and PAUSED serialization remain exact.
- Extend `ProviderPublishPlan.compiler_id` with `google_search_total_v25_v1` and validate
  exact configuration/operation/compiler consistency. Existing DAILY compiler ID remains.
  All common tracking/criteria/adgroup/RSA steps and dependency/fence rules stay intact.
- `google_publication.serialize` emits documented `totalAmountMicros`, custom period and
  unshared flag. Semantic readback includes those fields and rejects a contradictory
  nonzero daily amount. It must not accept missing required total amount/period as defaults.
  The existing resource receipt normalization remains request/digest bound, never a
  financial completion assertion. Inspect generic creation and separate-activation
  consumers for the new operation; do not activate any runtime or relax their gates.

## Customer API And UI

- Preserve legacy `CreationIntent.google` daily request exactly (no newly serialized
  default discriminator). Add an unambiguous strict total request with required
  `budget_kind=campaign_total_v1`, `total_budget_micros`, and existing opaque catalog
  choice, maximum CPC and search-partner fields. Strict union rejects mixed budgets.
- `customer_intents.google_fields` builds the correct typed provider configuration using
  current account timezone, owned tracking catalog and exact reviewed draft schedule.
  The customer supplies neither provider resource paths nor new schedule overrides.
- Execution UI offers Average Daily / Campaign Total explicitly, displays the selected
  amount separately from retained reservation and reviewed dates, and resets exact
  approval on changes. Explain that creation is paused and total budget is not independent
  proof of the overall mandate. Native IDs remain hidden and all existing role/session
  guards remain. B14 creative schema does not change.

## Required Evidence Before Freeze

- Existing DAILY/social canonical JSON and digest invariance.
- API/UI strict amount-kind parsing, scoped catalog selection, exact review invalidation.
- Actual MockHTTP budget/campaign/child publication and semantic readback; field, currency,
  timezone, date boundary (including DST), sharing, unknown/partial failure and retry tests.
- No total-budget operation admitted through a mismatched DAILY plan/compiler or omitted
  dates; no activation/financial eligibility inferred from successful paused creation.
- All current financial gates/factories and existing optimization profile restrictions
  remain unchanged. No migration is planned.

Authoritative field semantics: [Google create budgets](https://developers.google.com/google-ads/api/docs/campaigns/budgets/create-budgets),
[Search/manual-CPC support](https://developers.google.com/google-ads/api/docs/campaigns/budgets/overview),
[total-budget dates and non-conversion](https://support.google.com/google-ads/answer/10486938).
