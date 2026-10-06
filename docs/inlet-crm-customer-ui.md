# CRM Customer Connection Journey — Implemented Offline Contract

Implemented on `codex/inlet-crm-customer-ui` from `915fbcc10151e56f7b28d2a1ae5f643c99503007`.
Predecessors remain unchanged. No migration, provisioning, credentials, live provider
requests or new gateway.

## Existing Architecture And Decision Boundary

Klaviyo, HubSpot and Omnisend already have independent disabled-default HTTP
factories and authenticated account identity checks. Customer OAuth binds an
existing SourceAuthorization to provider, workspace, session, nonce and phase;
selection creates scoped SourceConnection ownership and generation. Klaviyo uses
server-side per-attempt encrypted PKCE; HubSpot validates token introspection;
Omnisend reads authenticated current brand. Existing renewal/pacing is separate.

The private CRM ingestion gateway is NOT involved in these direct OAuth adapters.
B04 still needs an owner decision before deployment: restricted database lookup
identity (recommended existing proposal) versus a private ownership lookup service.
This package requires neither. It must not deploy either architecture or start
persistent enrichment. Verified Shopify identity mappings and retention/export/
erasure policy remain separate gates. Therefore no owner decision blocks this UI.

## API And UI Contract

1. Add membership-scoped no-store GET setup for each CRM provider, returning only
   enabled, can_manage, public client_id, exact same-origin redirect_uri, fixed
   authorization endpoint. Exact read scopes are fixed in the adapter and browser validator. Use existing independent factory
   readiness. Never disclose client secrets, verifier, tokens or another provider's
   settings. Unconfigured text: connection unavailable in this environment.
2. Add distinct Klaviyo/HubSpot/Omnisend owner/admin Connect controls. Validate every
   consent destination against fixed HTTPS hostname/path, configured client ID,
   exact callback, nonce, exact scopes and complete query allowlist. Klaviyo also
   requires response_type=code and S256 challenge; Omnisend response_type=code.
   HubSpot preserves its existing emitted query contract, without invented fields.
3. Dedicated shared CRM GET callback shell/module derives provider only from an
   exact known callback pathname. Accept one code and state; reject auth_code,
   duplicates or unknown provider. Strip query immediately. Provider errors are
   display-only and do not exchange. CSP/no-store/no-referrer/frame denial; nonce
   in memory only. No browser persistence of code, nonce, grant or PKCE verifier.
4. POST existing source callback with current cookies/CSRF. Display only returned
   authenticated account ID/name (currency/timezone are optional for CRM), then
   POST existing provider select API. Even a singleton account requires explicit
   customer confirmation. Return workspace only from server-verified response;
   no redirect query accepted. Back/bfcache/session changes require safe retry.
5. Scoped per-account local disconnect confirmation: remove local authorization,
   stop reads, invalidate local pending work; preserve existing historical financial
   reports/goals/audit, without implying a new retained contact dataset. No remote
   revocation, provider data deletion, sibling-grant revocation or sales changes.
6. Status copy distinguishes connected authorization from usable enrichment:
   optional customer context; Shopify remains the sales source; current provider
   connection does not prove live mapping, retained enrichment or targeting consent.
   Existing provider_error/reconnect_required labels and next_action remain visible.

## Shared Guard Extension

Preserve SourceTransport, PKCESourceTransport, renewal and page schemas. Reuse
PR139 GuardedSourceExchange for HubSpot/Omnisend. Add optional structural
GuardedPKCESourceExchange.exchange_pkce_guarded(code, redirect_uri, code_verifier,
checkpoint)->SourceGrant for Klaviyo. Source.finish chooses guarded PKCE before
legacy PKCE, then existing guarded exchange. Existing public exchange methods
retain signatures and delegate with a no-op checkpoint for operator compatibility.

Each adapter explicitly calls checkpoint after token HTTP and after authenticated
account/introspection HTTP. Do not attach mutable guard state to shared adapters.
Checkpoint refreshes canonical workspace-first actor/session/role and exact nonce/
phase/expiry, then releases locks before the next external call. Source.finish
retains its final persistence guard and failed-attempt semantics. No code replay
on uncertain failure; retry starts fresh and replaces only matching pending flow.
PKCE verifier remains encrypted server-side and cleared once exchange begins.

## Offline Acceptance

- Real HTTPS Chromium/API/database journeys for all three providers, SQLite and
  PostgreSQL, with fixed consent interception and actual adapters + MockTransport.
- Config-disabled and cross-provider setup isolation; owner/admin versus member;
  consent cancellation, retry/Back/bfcache, expired/consumed flow, alias/duplicate
  callback rejection, account tampering, quota and disconnect sibling preservation.
- Controlled role/session/retry races after each token/account HTTP call. Old
  exchange cannot store credentials after a newer attempt; CRM renewal unaffected.
- No callback code/verifier in response errors, console, storage, referrer/history;
  actual access logger suppresses callback queries. No external live requests.
- Existing TikTok/Google/Meta portal and CRM PKCE/renewal/pacing regression tests;
  static checks and draft PR. Root owns Full and integrated qualification.

Routine implementation choices above do not require another product decision.
Before enabling retained enrichment or the private gateway, prepare the separate
exact data-purpose/retention or IAM/SQL proposal for owner review; do not present
those as credential-only blockers or silently broaden this connection UI package.

## Validation Evidence

The combined source guards, CRM adapters, Omnisend, renewal, quota, source status,
portal and customer-browser batch passed **219 tests with 14 existing SQLite
concurrency skips**. PostgreSQL counterparts ran. The expanded three-provider
browser/sibling-isolation/status batch passed **10 tests**, including six actual
HTTPS Chromium/API/database journeys. Browser DNS maps the canonical HTTPS test
origin to an ephemeral loopback port; no privileged port or weakened OAuth URL
validation is needed. Consent navigation is intercepted and provider HTTP uses
MockTransport; this is not live provider qualification. Klaviyo tests verify the
actual challenge/verifier hash relationship and encrypted fresh-attempt context.

JavaScript exact-destination helpers: **14 passed**. Whole-tree Ruff and mypy
app/tests (**400 source files**) passed. The adjacent Meta journey exposed a
pre-existing test readiness race: visible disconnect controls were clicked while
workspace setup still kept them disabled. The test now waits for enabled controls
before its single click; the product's busy-state guard remains unchanged.

Private gateway architecture, persistent enrichment purpose/retention and verified
Shopify customer mappings remain separate release/design gates. No new permission
or owner decision is needed to review this offline connection implementation.
Full/hosted CI and assembled successor validation remain pending.

Final callback/access-log/API and adjacent TikTok/Google/Meta browser batch:
**51 passed, zero skipped** after the readiness repair. No Full was run here.
