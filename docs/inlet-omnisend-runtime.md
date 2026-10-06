# Omnisend Read-Only Runtime

The prior current-brand schema and `scope`/`scopes` ambiguity are resolved by pinned
first-party Omnisend SDK source. See [contract evidence](inlet-omnisend-contract-evidence.md).
The adapter now implements the actual OAuth and read HTTP requests with injected
MockTransport tests. It is not live-qualified or enabled by default.

## Interface And Ownership

`OmnisendHTTPRead` retains the existing `SourceTransport` contract: authorization URL,
code exchange, current profile read, and explicit current-brand proof. `page()` proves
that the grant's top-level `brandID` matches the saved connection before each contacts
request. `refresh(refresh_token, expected_account)` re-proves the same brand with the
renewed access token. No caller-supplied field can become proof of brand ownership.
Generic Source authorization/session/state, encrypted grants, generation fencing,
workspace account selection, reconnect and disconnect remain in use. No DB migration.

The request scope is exactly `brands.read contacts.read` using singular `scope`.
An initial token response must explicitly affirm that scope. Renewal may omit scope,
meaning unchanged authorization under OAuth 2.0 (RFC 6749 sections 5.1 and 6); an
explicitly different or malformed scope is rejected. Missing initial scope fails closed.
Tokens must be Bearer. Returned expiry is honored; absent/null expiry remains unknown
(`None`), with no invented lifetime or claim of non-expiry. Expired saved grants still
fail closed at the Source boundary. The refresh method preserves a previous refresh
token only when the response omits a replacement; malformed supplied replacements fail.

There is no invented revocation or PKCE endpoint/capability. The verified official
SDK documents renewal despite the prose OAuth guide's non-expiry claim. Refresh is
an explicit adapter capability; automatic CRM refresh orchestration and provider
revocation remain separate lifecycle work. Local disconnect immediately blocks reads.

## Minimal Profile Projection And Bounds

Revision `2026-03-15` uses `contacts[]`, per-contact `id`, and `paging.hasMore` plus
`paging.cursors.after`. Requests use `limit=100`; responses over 250 profiles or 2MB
fail closed. Missing/malformed paging, missing required continuation and immediate
cursor repetition fail. Multi-page cycle bounds remain a caller responsibility;
the existing fixture context service already limits total pages and detects cycles.

Only source contact ID, channel-status context and observation time leave the adapter.
Email addresses, phone numbers and arbitrary profile properties are discarded. Missing
or null identifiers/channels/statuses mean unknown, never permission or unsubscribe.
Conflicting statuses across identifiers remain unknown. Malformed structural types
are rejected. No profile PII persistence, Shopify identity matching, canonical sales
mapping or marketing write is added. The existing enrichment preview stays fixture-only.

401/403 produce typed `CRMAuthenticationUnavailable`; 429 produces `CRMRateLimited`
with a bounded Retry-After hint; network, other HTTP and malformed-response errors remain
sanitized `CRMReadError`. HTTP requests have fixed endpoint allowlists, timeouts, no
redirect following, no implicit retries and redacted URL diagnostics. This adapter does
not itself run a background retry loop or convert a transport failure into published data.

## Activation Gate

Factory selection requires `AD_ANALYZER_OMNISEND_RUNTIME_MODE=provider_read`, configured
client ID/secret and exact `AD_ANALYZER_OMNISEND_API_REVISION=2026-03-15`. Default remains
`disabled`. No credentials or provider setup were created. Live consent, grant, scope,
brand binding, rate limits and refresh qualification require separately authorized
provider setup. Contact canonical identity/retention policy and runtime jobs remain
implementation work; they are not disguised as credentials-only blockers.
