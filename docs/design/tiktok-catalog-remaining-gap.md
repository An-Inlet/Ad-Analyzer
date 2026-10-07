# TikTok Native Catalog: Remaining Work And Evidence

**Update:** the [rendered official tables](tiktok-rendered-response-contract-20261007.md)
now resolve the response-shape documentation blocker. Parser/collector integration
and separate linked-profile publication eligibility remain implementation work;
the historical owner-export request below is superseded.

Status: 2026-10-07, backend06e1a82 plus explicit-vault followup7a35202.
This clarification uses the [retained first-party evidence check](tiktok-catalog-response-evidence.md);
The [October7 official-source recheck](tiktok-list-response-recheck-2026-10-07.md)
adds partial pixel mapping/page-size evidence and narrows the minimal handoff. This
original clarification itself performed no new research, provider access or live
verification. TikTok remains
in launch scope. The gap is native discovery of publication configuration, not a
missing TikTok integration as a whole.

## What Already Exists

- [Native import wire](../../app/tiktok/wire.py) reads campaign/adgroup/ad inventory
  and reporting. [Regular inventory diagnostics](../inlet-tiktok-native-inventory.md)
  also read advertiser/campaign/adgroup endpoints with bounded pagination. These
  contracts do not establish identity/pixel LIST response shapes or eligibility.
- [Typed catalog and options](../../app/publication/social_catalog.py), canonical
  [plan producer](../../app/publication/social_customer_producer.py), owned vault
  contexts, video/cover review, creation and separate activation are implemented.
  [Configured runtime](../inlet-tiktok-configured-runtime.md) accepts a server-owned
  decoded catalog only in contract tests, retaining explicit unverified-parser markers.
  Actual HTTP adapter mocks exercise publication/readback; they do not qualify native
  catalog discovery.

## Missing Code Versus Missing Evidence

The missing code is a bounded, GET-only native identity/pixel catalog collector and
strict response decoder, plus its mapping into named owned options. The current
[context and admission ports](../../app/production_runtime/tiktok_contracts.py)
are present; no verified native decoder is hidden behind them. SocialCatalog currently
has only a decoded-contract TikTok discovery discriminator. Native evidence support
will require an explicit typed discriminator/validator and runtime integration change,
with compatibility tests; removing the existing blockers alone is not implementation.

Authoritative request evidence exists for v1.3 `identity/get/` and `pixel/list/`.
The official SDK returns generic `InlineResponse200.data: object`. The retained
documentation research could not obtain nested LIST response tables. Identity INFO
is a different endpoint; campaign/adgroup imports cannot fill this evidence gap.

The missing evidence is the exact collection/element keys and types, account binding,
identity type/status/eligibility, pixel configured-event representation and eligibility,
and pagination/empty/partial/error semantics. In particular, a create-operation event
enum does not establish that an owned pixel is eligible for that event.

## Concrete Owner-Actionable Requirement

Provide an export or readable copy of the official v1.3 **response parameter tables
and examples** for [Get The Identity List](https://business-api.tiktok.com/portal/docs/get-the-identity-list/v1.3)
and [Get Pixels](https://business-api.tiktok.com/portal/docs/get-pixels/v1.3), retaining
source URLs, API version and retrieval date. The [existing evidence checklist](tiktok-catalog-response-evidence.md#exact-evidence-required-before-a-native-parser)
lists the exact fields and cases needed. This may require access to TikTok's
developer documentation; no advertising-spend permission is needed to supply docs.

If official examples do not cover those cases, arrange separately authorized
**read-only nonproduction** access for a developer to capture sanitized responses
from the two endpoints: valid and multipage/terminal-empty results, inaccessible
resources, ineligible resources and errors, preserving schema/types. Document the
account ownership and endpoint/version for the capture; replace personal names/IDs
consistently and omit tokens and credentials. A capture demonstrates observed shape,
not universal eligibility semantics; retain unknowns where docs do not establish them.
Do not paste credentials into chat or authorize writes merely to obtain this evidence.

## Independent Offline Work And Subsequent Acceptance

Existing ownership/session/media/unknown-request/retained-hold regressions and
configured API/browser integration can continue without this evidence. A bounded
collector test harness can also be prepared, but guessed response fixtures cannot
complete native parser acceptance. Once evidence arrives, implement strict decoding,
request-bound advertiser/generation validation, bounded complete pagination and
sanitized error handling; test missing/duplicate/foreign/stale/truncated responses
through injected HTTP, then ordinary configured discovery and exact customer review.

Native parser completion still does not supply financial qualification, complete
liability/headroom, empirical profile inputs or live authorization. Those independent
gates remain; no source is registered by default, live TikTok admission is denied,
and real HTTP refuses contract-test evidence. Production admission requires explicit
reviewed code and verified evidence for every retained gate, not a settings flip.
