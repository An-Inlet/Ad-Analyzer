# TikTok Configured Offline Runtime

This implements the request-local wiring following the
[reviewed contract freeze](inlet-tiktok-runtime-contracts.md). It is callable from
ordinary customer dependencies when an explicit server contract-test source and
mock transport are supplied. No source is registered by default. Live source
admission remains blocked; no native identity/pixel response decoder is added.

## Concrete Runtime

`OwnedTikTokContexts` uses the existing `SourceConnection` and `SourceVault`, with
workspace-first original-session authorization, paid-work checks, exact current
account/integration/external identity/generation and request-local credentials.
Missing, naive, expired or insufficiently long credential expiry is unavailable;
there is no guessed expiry or token refresh endpoint. Current authorization,
account and manifest pin are checked again before returning a bounded context.
Private media reads capture the owned DB binding and check it and original session
again after storage IO. No credential is returned in customer projections.

`provider_composition.configured_execution` selects Google, Meta or TikTok from
owned typed plan/catalog/activation requests. TikTok evidence/credentials/transport
are lazy and owned by the request ExitStack. All configured environments must
agree. A TikTok request cannot construct an unrelated provider's source. The three
optional nonsecret settings are `tiktok_execution_manifest_path`,
`tiktok_execution_manifest_digest` and `tiktok_execution_bundle_path` (environment
aliases are documented in `.env.example`). Malformed TikTok configuration yields a
sanitized unavailable response.

The scenario catalog callback returns an explicitly decoded `SocialCatalog`. Its
exact request, observation lifetime and mandatory
`tiktok_native_catalog_parser_unverified` / `tiktok_decoded_contract_only` markers
are validated. Owned credentials and original authority are checked on both sides
of that callback; it makes no native catalog HTTP-discovery claim. The existing
social declaration/cover-review APIs and durable creation/activation coordinator
remain the customer path, with separate exact approvals and retained holds.

## Acceptance Fixture And Limits

`tests.tiktok_runtime_fixture.configured_tiktok_customer(engine, configuration,
path, monkeypatch, replicas, video_bytes)` returns:

`(alice, base, policy_body, draft_id, draft_revision, server, requests, control)`.

`control['cover_id']` is the actual uploaded, validated cover ID. The fixture creates
owned source/vault and approved creative inputs, not execution reviews, attempts,
receipts or reservations. API tests assert those tables start empty and create the
execution state through ordinary authenticated customer routes. Only trusted
scenario evidence/decoded catalog and low-level HTTP transport seams are injected;
no runtime getter override is used. The genuine H264 MP4 and PNG are read/validated,
uploaded through actual adapters and independently read back through MockTransport.

The fixture's explicit numeric/economic facts are contract scenarios, not production
financial proof or proposed customer defaults. Unknown requests do not replay;
original holds survive uncertainty and configuration/media withdrawal. Native
catalog response evidence and qualified financial sources remain unavailable, and
unknown production credential expiry cannot be promoted by this runtime. TikTok
TLS customer acceptance is a separate dependent package after this backend freezes.

## Narrow Error Repair Found By Composition

Removing the exact cover file after paused creation produced an uncaught
`FileNotFoundError` in the existing selection boundary on both databases. Selection
now normalizes `OSError` alongside invalid media to a sanitized 409. It does not
replace the missing media, relax exact review, perform activation or release the
held reservation. The real API regression remains part of the fixture suite.

The fixture pins `assembly.execution_clock` to its explicit October 5 scenario
clock. A dependent browser harness visiting the pre-existing campaign-draft preview
route must use that same test clock for the route, as the configured Meta TLS
harness does; a real October 7 preview of the old fixture is correctly stale.

## Actual Browser Acceptance

`tests/test_configured_tiktok_execution_browser.py` serves the real social
configuration and execution page assets over local HTTPS with an ordinary API
session. Its drivers select the named decoded contract-test catalog option, decode
actual video/cover media, record exact pair confirmation, consent the spending
mandate, approve paused creation and separately approve activation. No execution
review, attempt, receipt or reservation is seeded and no runtime getter is replaced.
Injected provider transport remains MockTransport; browser success is not live
provider qualification or native catalog parser acceptance.

The browser suite also checks unknown original creation/activation requests through
explicit reconciliation without mutation replay, and denial after original-session
revocation, source-generation changes, missing media, withdrawn confirmation or
changed configuration pin. These cases retain the original reservation. Results
and exact checked package are recorded in the progress ledger.
