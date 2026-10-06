# B20 Offline Two-Brand Acceptance Matrix

> Historical checkpoint / scoped evidence record. For current implementation, focused
> tests, exact-artifact aggregate validation and live qualification, start with the
> [current acceptance matrix](inlet-current-acceptance.md). Requirements and historical
> test/CI results below are preserved; old missing-feature claims are not current status.

This is engineering evidence for B20, not completion of its unrelated-business
pilot requirement. No real business, live advertising account, production purchase,
provider qualification or deployed browser journey is exercised. Base: `6eef6d8`.

The new `tests/test_two_brand_pilot.py` scenario uses **one database** for two
independent customer identities and workspaces. Each gets a unique Shopify domain
and shop identity; advertising account/connection IDs are distinct. Brand A starts
with Shopify, Google Ads and Klaviyo. Brand B starts with Shopify, Meta Ads and
HubSpot. Fixture names are synthetic, not real pilot participants.

## Scenario Contract

| Stage | New Composed Evidence | Explicit Boundary / Existing Evidence |
|---|---|---|
| Signup and owner session | Both identities exchange fixture-provider identity tokens through real assembled session APIs, then provision distinct owner workspaces | Identity provider is offline; browser authentication is covered separately by `test_customer_browser_api_journey.py` |
| Existing customer-data tools | Actual Klaviyo and HubSpot HTTP adapters perform OAuth/account proof through MockTransport and customer source APIs; cross-session callback fails before HTTP; each source listing is tenant-bound | No production grants, profile enrollment or CRM synchronization is claimed; real profile projection/lifecycle/quota cases remain in CRM runtime and pacing suites |
| Advertising ownership | Distinct Google and Meta native connections bind their own workspace/integration/account; foreign workspace reads fail | Native advertising authorization is explicitly installed as a fixture, not obtained through OAuth in this composed case; separate Google/Meta browser suites cover consent flows |
| Shopify baseline and goal | Real owned goal create/preview/confirm APIs consume separate Shopify ledgers and persist confirmation without spending authority | Shopify connection and baseline rows are explicit fixtures populated through real binding/ledger code; consent and ingestion qualification are separate suites |
| Exact campaign review | Google search and Meta image drafts are created, previewed and approved through real customer APIs, including real private image upload; foreign workspace and foreign draft IDs fail | This is offline-plan approval, not publication consent |
| Separate execution consent and creation | Brand A's same owner/goal/source draft flows into separate contract-test mandate consent and reviewed durable creation, with real Google compiler/HTTP/readback through MockTransport | This original fixture uses direct coordinator service calls. Customer execution and optimization facades now exist and are covered separately by `test_customer_execution_api.py` and `test_customer_optimization_api.py`. Qualification/exposure readers remain controlled contract-test evidence, not live qualification |
| Separate activation | Brand A requires the separate activation review/approval and executes real durable Google activation; projection is verified target state | `test_activation_review.py` covers missing/stale separate approval; `test_activation_coordinator.py` covers activation recovery. Brand B is not dispatched by this composed case; `test_social_coordinator_journeys.py` covers all declared social creation graphs and `test_social_activation_http.py` covers actual social activation HTTP |
| Owned outcome | Brand A's normalized latest receipt is owner-readable; Brand B is denied both by wrong workspace and wrong actor | This is a provider effect/state receipt, **not** mature measured action-outcome feedback. `test_owned_outcomes.py`, `test_outcome_commerce_projection.py`, `test_unified_outcome_data.py` and `test_outcome_evidence.py` cover separate measured-outcome evidence; no mature sales outcome is fabricated in this scenario |
| Closure and unrelated-brand continuity | Brand A closes through preview/confirm APIs, its owner still reads closure and original coordinator receipt, foreign closure read fails, reservations stay held, and Brand B still reads its confirmed goal and CRM connection | Local closing explicitly does not claim complete deletion, stopped ads or released exposure. No new provider calls occur during closure |

Global provider quotas intentionally retain their existing account/provider scope;
this fixture does not redefine quota isolation as one quota per tenant. Existing
CRM pacing and Meta quota suites remain authoritative for shared cooldowns and
cross-workspace limits.

## Existing Failure Evidence Reused

- `test_provider_coordinator.py`: lost response, immutable original attempts,
  reconciliation without replay, cancellation, revocation and late closure evidence.
- `test_activation_coordinator.py`: unknown activation, no replacement dispatch,
  native revocation and original reservation continuity.
- `test_social_coordinator_journeys.py`: declared Meta/TikTok media/campaign types,
  unknown response, current authority recheck and foreign media rejection.
- `test_customer_goals.py`: stale/partial/erased baseline and confirmation behavior.
- `test_crm_renewal.py` and CRM pacing/runtime suites: revoked grants, retry/backoff,
  source-generation fences, rotation uncertainty and shared-account cooldowns.
- `test_customer_quiescing.py`, `test_customer_lifecycle.py` and closure/export
  browser suites: local closure, retained historical authority and data disposition
  limitations.

These named suites are an evidence inventory, not a claim they were all rerun for
this documentation package. Exact newly run checks are recorded in the progress
ledger. Earlier receipt/activity PRs remain unchanged.

## Remaining Acceptance Gaps

B18 still needs a customer-owned reviewed coordinator dispatch/activation interface;
direct service invocation is not self-serve completion. This scenario is not a
single browser journey and does not bridge mature outcome measurement into provider
activation. Real unrelated pilots, intended-environment operations, configured
billing, live provider qualifications and closure disposition remain external and/or
engineering gates. The existing B15–B20 acceptance matrix remains authoritative;
this package does not mark B20 complete.

## Composed Archive And Closure Extension

`test_archive_closure_financial_social.py` adds two unrelated brands on each database.
It populates actual optimization/replacement accounting through coordinator services
and a strict Meta no-DSA configuration approval through source/review services.
Authenticated customer APIs then download the complete owned archive, deny foreign
access, close Brand A locally, deny its next execution, and advance Brand B through
the customer execution facade. Exact replacement/social documents, held/superseded
amounts, original receipts and cumulative accounting are checked across closure.

Initial identity, Shopify baseline and provider facts remain explicit test fixtures;
all advertising HTTP uses mock transports. Brand A is Meta and Brand B is Google.
The test does not claim all onboarding happened through customer APIs, physical
provider termination, final erasure, live cap qualification, or completion of B20.
