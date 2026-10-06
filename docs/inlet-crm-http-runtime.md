# Customer Context HTTP Runtime Preparation

Branch `codex/inlet-crm-runtime` starts from PR75's
`01aa869b7df73bcdf1dca5fc25391a43f0af4efc` (`codex/inlet-tiktok-runtime`).
No migration, customer profile persistence, provider call, credential provisioning,
advertising action or deployment is part of this package.

## Implemented And Mock-Verified

| Provider | Implemented Runtime | Account Proof | Remaining Boundary |
| --- | --- | --- | --- |
| Klaviyo | OAuth authorization with per-attempt S256 PKCE; code exchange; current profiles/subscriptions; explicit refresh and revocation methods | One account from authenticated `/api/accounts`, checked before each profile page | Disabled by default; refresh/revoke lifecycle scheduling and live qualification remain |
| HubSpot | OAuth v3 exchange; POST token introspection; current contact lifecycle; explicit refresh method | Active access token, matching configured client, exact read scopes and provider Hub ID on every page | Disabled by default; lifecycle scheduling and live qualification remain |
| Omnisend | Fixed HTTP endpoint boundary and corrected contact projection preparation | Unverified current-brand response contract; no caller-provided account accepted | Factory and authorization/account methods fail closed; see exact blockers below |

Klaviyo requests only `accounts:read profiles:read`. HubSpot requests only
`oauth crm.objects.contacts.read`; overbroad grants are rejected. Profile projection
excludes email, phone, names, arbitrary properties and revenue. Consent and global/list
suppression remain separate. Unknown lifecycle/channel states remain unknown.

The source factory selects Klaviyo only with explicit `provider_read`, configured
client values, and the verified revision `2026-07-15`; otherwise it returns the
unavailable transport. HubSpot likewise requires explicit mode/client configuration.
No secrets or actual configuration were supplied. Constructors and factories perform
no network IO. These switches are implementation gates, not permission to enable live
access or deploy.

Every HTTP path/method is fixed. Requests use no environment proxies, reject redirects,
have 5-second connect and 20-second IO timeouts, and cap responses at 2 MB. Each call
has no implicit retries; authorization failures and rate limits return sanitized errors.
Account identity is re-proved before every page. Opaque cursors are bounded; untrusted
Klaviyo continuation links and immediately repeated cursors are rejected. The existing
context service additionally caps a complete transient read at 20 pages and detects
cursor cycles. HTTPX URL diagnostics are redacted for these CRM hosts because an opaque
cursor may itself encode an identifier.

## PKCE Concurrency And Consumption

The optional `PKCESourceTransport` capability adds explicit
`authorize_url_pkce(state, redirect_uri, code_challenge)` and
`exchange_pkce(code, redirect_uri, code_verifier)` methods without changing existing
SourceTransport signatures. Adapters store no mutable verifier or customer context.
The source service generates a fresh verifier per authorization, stores it inside the
existing encrypted authorization envelope bound to workspace/provider/state, and
requires the original session and a five-minute unexpired authorization. It clears
the encrypted verifier and commits the consumed/exchanging state before HTTP exchange.
An uncertain exchange requires restarting; it cannot replay the code/verifier.

SQLite and PostgreSQL tests interleave two customers using one adapter, then finish
in reverse order with fresh adapter instances. Each receives its own verifier;
swapped ciphertext, wrong session, expiry and replay fail. Consumed state and verifier
removal survive session closure. Verifiers and tokens are absent from logs and plain
stored authorization fields.

## Omnisend Blockers And Corrected Projection

Official OAuth documentation exists, so lack of OAuth support is **not** the blocker.
It documents `/oauth2/authorize` and form-encoded `/oauth2/token`, but its parameter
table says `scopes` while the request example says `scope`. The current-brand endpoint
reference documents `/api/brands/current` and `brands.read`, but the accessible page
has no response identity schema. The Markdown links were inaccessible to the web
reader, and executor requests to documentation were rejected by its network proxy.
No brand-ID field was guessed, and no live request was used to discover it.

Required next evidence: authoritative current-brand response schema and confirmed
OAuth scope parameter. After that, implement/qualify grant account proof and OAuth
exchange, then permit the disabled-default factory path. This is remaining code and
contract qualification, not merely missing credentials.

The official migration guide proved the existing profile fixture wrong: current
contact pages use `contacts[]`, not `data[]`, and `paging.hasMore` controls whether
`paging.cursors.after` is followed. Projection/tests now enforce that contract and
reject a missing required continuation. Omnisend revision `2026-03-15` is documented.

## Still Not B12 Acceptance

Provider HTTP transport is not verified Shopify-customer identity matching.
`customer_context.service.preview` deliberately still requires fixture mode and the
concrete fixture mapping. A live reader cannot use that mapping to claim verified
canonical identities. No real CRM context jobs/UI/export/erasure retention flow or
persistent enrichment was added. The existing source `token()` still fails closed on
expiry; explicit refresh methods are ready for later generation-safe lifecycle wiring.
Klaviyo revoke is implemented but not automatically invoked by disconnect. HubSpot
revocation and Omnisend lifecycle remain code gaps. No production or purchasable
product claim follows from these mocked tests.

## Checks

- `pytest tests/test_crm_http_runtime.py tests/test_customer_context.py
  tests/test_tiktok_sources.py tests/test_inlet_review_regressions.py`, with the
  explicit disposable `inlet_crm_runtime_ci` PostgreSQL configuration: **85 passed**.
  Includes real HTTP request construction with `httpx.MockTransport`, default gates,
  scopes/account/client proof, cross-provider readiness, timeouts/429/redirects,
  response limits, safe projection, continuation, PKCE replicas and PostgreSQL scope.
- `ruff check .`: passed.
- `mypy`: passed, 255 source files.
- `git diff --check`: passed.
- Full and hosted CI: **pending**, delegated to root after review.

## Official Contract References Checked 2026-10-06

- [Klaviyo OAuth and PKCE](https://developers.klaviyo.com/en/docs/set_up_oauth)
- [Klaviyo account proof](https://developers.klaviyo.com/en/reference/get_accounts)
- [Klaviyo profile revision and fields](https://developers.klaviyo.com/en/reference/get_profiles)
- [HubSpot OAuth v3 and POST introspection](https://developers.hubspot.com/docs/api-reference/legacy/authentication/manage-oauth-tokens)
- [Omnisend OAuth](https://api-docs.omnisend.com/reference/oauth)
- [Omnisend current brand](https://api-docs.omnisend.com/reference/get_brands-current)
- [Omnisend contacts](https://api-docs.omnisend.com/reference/get_contacts)
- [Omnisend current pagination and response migration](https://api-docs.omnisend.com/docs/migrate-from-v5-to-v2026-03-15)
