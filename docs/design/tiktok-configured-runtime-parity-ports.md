# TikTok Configured Runtime Parity: Proposed Ports

Design-only child of `422bbe4`. No runtime, parser, migration, source registration,
provider action or live qualification is implemented by this document.

## Existing Evidence And Exact Boundary

Existing `tiktok/http.py`, source ownership/vault lifecycle, customer consent UI,
`executors/tiktok_publication.py`, `tiktok_activation.py` and social configuration/
video-cover review already support bounded offline work. Reuse their actual HTTP
serializers, durable coordinator and original receipt/hold semantics.

`collectors/tiktok_native_inventory.py` already decodes regular campaign/adgroup
inventory. [Its evidence record](../inlet-tiktok-native-inventory.md) explicitly
states that the generic official SDK envelope does not independently qualify the
nested response; it reuses the existing regular adapter field contract. Its
`regular_inventory_read_complete` does not establish complete campaign families,
historical liabilities, pending changes or financial bounds. Do not describe this
as wholly absent code or upgrade it into an eligible optimization catalog.

Identity LIST/pixel LIST decoding remains genuinely absent: exact collection,
nullability, account ownership, pagination, status and configured-event response
contracts are missing as recorded in
[tiktok-catalog-response-evidence.md](tiktok-catalog-response-evidence.md).
No new research or invented `data.list` parser is proposed. Current
`SocialCatalog` requires `tiktok_native_catalog_parser_unverified` and
`discovery_evidence=tiktok_decoded_contract_only`; preserve both.

## Minimal Proposed Interfaces

New `production_runtime/tiktok_contracts.py`:

- `TikTokExecutionManifestV1`: schema/version, manifest ID/revision, environment,
  api_version=`v1.3`, evidence source/profile digest, configuration bundle digest,
  explicit live/activation flags, bounded required credential/context lifetimes.
  Contract-test cannot set live enabled; no numerical product policy defaults.
- `TikTokEvidenceDescriptor`: exact source/profile/environment/kind as other
  providers. Kind `contract_scenario` only in contract_test.
- `TikTokExecutionEvidence`: descriptor, existing configuration/exposure/activation
  readers, and **optional `decoded_contract_catalog: SocialCatalogReader`**.
  This last callback is permitted only for contract-test sources. It is explicitly
  an already-decoded fixture catalog, never a native HTTP parser or live source.
  No client JSON or customer-entered native identities populate it.
- `RegisteredTikTokEvidenceSource.build(sessions, authorize, actor_id, clock)`;
  registry returns None by default. Pure admission checks exact identity/environment
  before factory construction. Live assembly remains unavailable while the native
  parser blocker exists, even if a server source descriptor says qualified_live.
- `OwnedTikTokContexts.catalog(request, now)`, `.publication(bound_request)`,
  `.activation(original_request)`: typed TikTok scope only, actual source vault and
  original-session engine. Catalog context port is reserved for verified native
  discovery later; decoded fixture catalog does not pretend to consume HTTP.

New loader pins manifest and immutable configuration bundle transitively. Reuse
Meta canonical-byte/defensive-copy approach, bounded duplicate-key-rejecting reads,
exact TikTok profile/requirements association and explicit cover wording. Keep
existing profile/plan hashes unchanged. Settings are only manifest path/digest and
bundle path; no executable imports, provider proofs, credentials or fixture lists.
Real transport refuses contract_test before construction, with retries disabled and
no proxies/redirects. Offline tests inject only its low-level MockTransport factory.

## Owned Credentials And Lazy Composition

Reuse SourceConnection ownership/generation and source vault, not fabricated Meta
or Google rows. Validate current provider=tiktok_ads, integration/account, original
actor/session and paid entitlement under workspace-first locks. Release private
sessions before IO, then reauthorize after IO and before forward emission through
existing coordinator guards. Keep token values request-local and close resources
with ExitStack. Unknown grant expiry must remain unknown; do not invent a lifetime
or refresh endpoint. Before implementation, choose conservative unavailable for
unknown expiry unless an existing documented source validity contract explicitly
supports a shorter request context without asserting token lifetime.

Extend `provider_composition` by typed plan/catalog/original activation request,
not URL alone. Existing Google/Meta dispatch, manifests and bytes remain intact;
configured environments must agree. A TikTok operation cannot construct another
provider's source. Activation flag is checked again on exposure/context paths.
Media uses owned validated video plus exact cover and original-session checks around
private storage. Exact declaration/media/configuration confirmation remains required.
All live/native qualification blockers remain, with no permissive callback installed.

## Concrete Offline Acceptance Package After Review

Actual ordinary configured dependencies and HTTPS UI on SQLite/PostgreSQL:

1. Existing owned source and approved video/cover input; zero seeded execution
   reviews, attempts, receipts or holds. Real login/session and actual APIs.
2. Explicit server contract-test decoded catalog supplies opaque named choices;
   UI shows Contract Test and unavailable native qualification. Customer reviews
   exact video/cover declaration, confirms configuration, sets/consents mandate,
   then reviews and separately approves paused creation.
3. Actual TikTok upload/create/readback adapters through MockTransport; durable
   receipts and one conservative hold. Separate activation review/approval and
   actual status/readback requests, never automatic activation.
4. Unknown create/activation reconciles original request without replay. Retain
   hold; paused/absent observation never proves termination or zero remaining cost.
5. Revoke original session, reconnect source, remove media/change confirmation,
   expire credentials or change profile during IO: no new forward mutation.
6. Live+decoded scenario, real transport+contract_test, foreign provider/scope and
   partial/mismatched manifests deny before network/factory use. Assert cleanup.
7. Google/Meta configured journeys continue unchanged. No runtime-getter override;
   only trusted server registry/low-level HTTP test dependencies are injected.

This closes configured offline customer execution wiring, **not native discovery
parity or live TikTok readiness**. Identity/pixel response evidence and actual
qualification/economic source guarantees remain explicit blockers. Existing-campaign
optimization additionally needs genuinely qualified complete target-owner topology;
regular diagnostics and mutation adapters alone cannot provide that admission.
